from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.enums import BatchStatus, TaskStatus
from app.models.tasks import BatchJob, GenerationTask
from app.services.executor import process_generation_task

DEFAULT_LEASE_SECONDS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 3.0

logger = logging.getLogger(__name__)


async def fetch_and_lock_next_generation_task(
    session: AsyncSession,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    lease_owner: str = "scheduler",
    batch_id: int | None = None,
) -> GenerationTask | None:
    now = datetime.utcnow()

    statement = (
        select(GenerationTask)
        .join(BatchJob, GenerationTask.batch_id == BatchJob.id)
        .where(BatchJob.status == BatchStatus.RUNNING)
        .where(GenerationTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRYING]))
        .where(or_(GenerationTask.next_run_at.is_(None), GenerationTask.next_run_at <= now))
        .order_by(BatchJob.created_at.desc(), GenerationTask.id.asc())
        .limit(1)
    )
    if settings.db_supports_skip_locked:
        statement = statement.with_for_update(skip_locked=True)
    else:
        statement = statement.with_for_update()
    if batch_id is not None:
        statement = statement.where(GenerationTask.batch_id == batch_id)

    result = await session.execute(statement)
    task = result.scalar_one_or_none()

    if task is None:
        await session.rollback()
        return None

    task.status = TaskStatus.PROCESSING
    task.attempt_count += 1
    task.processing_started_at = now
    task.lease_owner = lease_owner
    task.lease_until = now + timedelta(seconds=lease_seconds)
    task.next_run_at = None

    await session.commit()
    await session.refresh(task)
    return task


async def claim_generation_task_by_id(
    session: AsyncSession,
    task_id: int,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    lease_owner: str = "celery",
) -> GenerationTask | None:
    now = datetime.utcnow()
    statement = (
        select(GenerationTask)
        .join(BatchJob, GenerationTask.batch_id == BatchJob.id)
        .where(GenerationTask.id == task_id)
        .where(BatchJob.status == BatchStatus.RUNNING)
        .where(GenerationTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRYING]))
        .where(or_(GenerationTask.next_run_at.is_(None), GenerationTask.next_run_at <= now))
        .limit(1)
    )
    if settings.db_supports_skip_locked:
        statement = statement.with_for_update(skip_locked=True)
    else:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    task = result.scalar_one_or_none()

    if task is None:
        await session.rollback()
        return None

    task.status = TaskStatus.PROCESSING
    task.attempt_count += 1
    task.processing_started_at = now
    task.lease_owner = lease_owner
    task.lease_until = now + timedelta(seconds=lease_seconds)
    task.next_run_at = None

    await session.commit()
    await session.refresh(task)
    return task


TaskProcessor = Callable[[AsyncSession, GenerationTask], Awaitable[None]]

_active_execution_tasks: set[asyncio.Task[None]] = set()


def _handle_execution_task_done(background_task: asyncio.Task[None]) -> None:
    _active_execution_tasks.discard(background_task)
    with contextlib.suppress(asyncio.CancelledError):
        exc = background_task.exception()
        if exc is not None:
            logger.exception("生成执行任务发生崩溃", exc_info=exc)


async def noop_task_processor(session: AsyncSession, task: GenerationTask) -> None:
    logger.info("尚未配置任务处理器，任务将退回重试队列", extra={"task_id": task.id})
    task.status = TaskStatus.RETRYING
    task.next_run_at = datetime.utcnow()
    task.lease_owner = None
    task.lease_until = None
    task.last_error_code = "processor_not_implemented"
    task.last_error_message = "调度循环已抢到任务，但当前尚未接入实际生成处理器"
    await session.commit()


async def dispatch_generation_task(session: AsyncSession, task: GenerationTask) -> None:
    del session

    background_task = asyncio.create_task(
        process_generation_task(task.id, AsyncSessionLocal),
        name=f"generation_task_{task.id}",
    )
    _active_execution_tasks.add(background_task)
    background_task.add_done_callback(_handle_execution_task_done)


async def run_scheduler_loop(
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    worker_name: str = "scheduler",
    processor: TaskProcessor | None = None,
) -> None:
    task_processor = processor or dispatch_generation_task

    while True:
        try:
            if len(_active_execution_tasks) >= settings.scheduler_max_inflight_tasks:
                await asyncio.sleep(poll_interval_seconds)
                continue

            async with AsyncSessionLocal() as session:
                task = await fetch_and_lock_next_generation_task(
                    session,
                    lease_seconds=lease_seconds,
                    lease_owner=worker_name,
                )
                if task is None:
                    await asyncio.sleep(poll_interval_seconds)
                    continue

                await task_processor(session, task)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("调度循环单次迭代失败")
            await asyncio.sleep(poll_interval_seconds)


async def run_recovery_loop(*, poll_interval_seconds: float = 15.0) -> None:
    from app.services.recovery import is_retryable_lock_error, recover_expired_task_ids, recover_expired_tasks

    while True:
        try:
            async with AsyncSessionLocal() as session:
                if settings.async_execution_mode == "celery":
                    recovered_ids = await recover_expired_task_ids(session)
                    if recovered_ids:
                        from app.services.async_tasks import enqueue_generation_task

                        for recovered_task_id in recovered_ids:
                            enqueue_generation_task(recovered_task_id)
                        logger.warning("已回收租约过期任务并重新入队", extra={"count": len(recovered_ids)})
                else:
                    recovered = await recover_expired_tasks(session)
                    if recovered:
                        logger.warning("已回收租约过期任务", extra={"count": recovered})
            await asyncio.sleep(poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if is_retryable_lock_error(exc):
                logger.warning("恢复循环遇到可重试的数据库锁冲突，将在下个周期继续", exc_info=exc)
                await asyncio.sleep(poll_interval_seconds)
                continue
            logger.exception("恢复循环单次迭代失败")
            await asyncio.sleep(poll_interval_seconds)
