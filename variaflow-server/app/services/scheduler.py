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
    """
    以原子方式抓取并锁定一条可执行的生成任务。

    这里使用 SELECT ... FOR UPDATE SKIP LOCKED，
    允许多个工作协程并发竞争而不会拿到同一行任务。
    """

    now = datetime.utcnow()

    statement = (
        select(GenerationTask)
        .join(BatchJob, GenerationTask.batch_id == BatchJob.id)
        .where(BatchJob.status == BatchStatus.RUNNING)
        .where(GenerationTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRYING]))
        .where(or_(GenerationTask.next_run_at.is_(None), GenerationTask.next_run_at <= now))
        .order_by(GenerationTask.id.asc())
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

    # 立即提交租约状态，确保其他工作协程可以立刻看到这条任务已被占用。
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
    """
    兼容保留的临时安全处理器。

    当前默认流程已经改为 `dispatch_generation_task -> process_generation_task`，
    这里只保留一个可显式注入的降级处理器，方便调试或故障演练。
    """

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
    """
    由 FastAPI lifespan 托管的长生命周期调度循环。

    循环内部会捕获单次迭代错误并继续运行，
    避免一次数据库异常或处理失败直接拖垮整个服务。
    """

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
    """
    长生命周期看门狗循环，用于回收租约过期的处理中任务。
    """

    from app.services.recovery import is_retryable_lock_error, recover_expired_tasks

    while True:
        try:
            async with AsyncSessionLocal() as session:
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
