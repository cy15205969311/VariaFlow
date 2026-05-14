from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import TaskStatus
from app.models.tasks import GenerationTask

logger = logging.getLogger(__name__)

RETRYABLE_LOCK_ERROR_CODES = {
    1205,  # Lock wait timeout exceeded
    1213,  # Deadlock found when trying to get lock
}


def is_retryable_lock_error(exc: Exception) -> bool:
    if not isinstance(exc, OperationalError):
        return False

    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    if not args:
        return False

    try:
        error_code = int(args[0])
    except (TypeError, ValueError):
        return False

    return error_code in RETRYABLE_LOCK_ERROR_CODES


async def recover_expired_tasks(session: AsyncSession) -> int:
    """
    回收因工作协程崩溃而遗留在 processing 状态的任务。

    这些任务的租约已经过期，因此调度器可以安全地重新抢占它们。
    """

    now = datetime.utcnow()
    statement = (
        select(GenerationTask)
        .where(GenerationTask.status == TaskStatus.PROCESSING)
        .where(GenerationTask.lease_until.is_not(None))
        .where(GenerationTask.lease_until < now)
    )
    if settings.db_supports_skip_locked:
        statement = statement.with_for_update(skip_locked=True)
    else:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    expired_tasks = result.scalars().all()

    if not expired_tasks:
        await session.rollback()
        return 0

    for task in expired_tasks:
        logger.warning(
            "正在回收租约过期的生成任务",
            extra={
                "task_id": task.id,
                "source_task_id": task.source_task_id,
                "previous_lease_until": task.lease_until.isoformat() if task.lease_until else None,
            },
        )
        task.status = TaskStatus.RETRYING
        task.next_run_at = now
        task.lease_owner = None
        task.lease_until = None
        task.last_error_code = task.last_error_code or "lease_expired"
        task.last_error_message = task.last_error_message or "任务租约已过期，已由看门狗恢复到重试队列"

    await session.commit()
    return len(expired_tasks)


async def recover_expired_task_ids(session: AsyncSession) -> list[int]:
    now = datetime.utcnow()
    statement = (
        select(GenerationTask)
        .where(GenerationTask.status == TaskStatus.PROCESSING)
        .where(GenerationTask.lease_until.is_not(None))
        .where(GenerationTask.lease_until < now)
    )
    if settings.db_supports_skip_locked:
        statement = statement.with_for_update(skip_locked=True)
    else:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    expired_tasks = result.scalars().all()

    if not expired_tasks:
        await session.rollback()
        return []

    recovered_ids: list[int] = []
    for task in expired_tasks:
        logger.warning(
            "正在回收租约过期的生成任务",
            extra={
                "task_id": task.id,
                "source_task_id": task.source_task_id,
                "previous_lease_until": task.lease_until.isoformat() if task.lease_until else None,
            },
        )
        task.status = TaskStatus.RETRYING
        task.next_run_at = now
        task.lease_owner = None
        task.lease_until = None
        task.last_error_code = task.last_error_code or "lease_expired"
        task.last_error_message = task.last_error_message or "任务租约已过期，已由恢复循环重新入队"
        recovered_ids.append(task.id)

    await session.commit()
    return recovered_ids
