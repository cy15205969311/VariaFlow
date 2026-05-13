from __future__ import annotations

import asyncio
import logging

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.executor import process_generation_task
from app.services.scheduler import claim_generation_task_by_id

logger = logging.getLogger(__name__)


def enqueue_generation_task(task_id: int, *, countdown: int = 0) -> None:
    generate_task_async.apply_async(args=[task_id], countdown=max(int(countdown), 0))


def _calculate_requeue_countdown(task_row) -> int:
    if task_row.next_run_at is None:
        return 0

    base_time = task_row.updated_at or task_row.created_at or task_row.next_run_at
    return max(int((task_row.next_run_at - base_time).total_seconds()), 0)


@celery_app.task(
    bind=True,
    name="app.services.async_tasks.generate_task_async",
    autoretry_for=(ConnectionError, TimeoutError, SoftTimeLimitExceeded),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def generate_task_async(self, task_id: int) -> dict[str, object]:
    async def _runner() -> dict[str, object]:
        async with AsyncSessionLocal() as session:
            claimed_task = await claim_generation_task_by_id(
                session,
                task_id,
                lease_seconds=settings.worker_lease_seconds,
                lease_owner=f"celery:{self.request.hostname or 'worker'}",
            )

        if claimed_task is None:
            logger.info("Skip celery dispatch because task is not claimable", extra={"task_id": task_id})
            return {"task_id": task_id, "dispatched": False, "reason": "not_claimable"}

        await process_generation_task(task_id, AsyncSessionLocal)

        async with AsyncSessionLocal() as session:
            from app.models.enums import TaskStatus
            from app.models.tasks import GenerationTask
            from sqlalchemy import select

            task_row = (
                await session.execute(select(GenerationTask).where(GenerationTask.id == task_id))
            ).scalar_one_or_none()

            if task_row and task_row.status == TaskStatus.RETRYING:
                next_eta_seconds = _calculate_requeue_countdown(task_row)
                enqueue_generation_task(task_id, countdown=next_eta_seconds)
                return {
                    "task_id": task_id,
                    "dispatched": True,
                    "status": task_row.status.value,
                    "requeued": True,
                    "countdown": next_eta_seconds,
                }

        return {"task_id": task_id, "dispatched": True, "requeued": False}

    return asyncio.run(_runner())
