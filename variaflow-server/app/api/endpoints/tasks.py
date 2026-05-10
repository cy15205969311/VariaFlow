from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.core.config import settings
from app.models.enums import BatchStatus, QCStatus, SourceTaskStatus, TaskStatus
from app.models.tasks import GenerationTask, SourceTask
from app.schemas.tasks import GenerationTaskSlotResponse, TaskListResponse, TaskResponse
from app.services.executor import _recompute_source_and_batch_state

router = APIRouter()


def _extract_task_intent(slot: GenerationTask) -> tuple[str | None, str | None]:
    snapshot = slot.prompt_snapshot_json or {}
    intent = snapshot.get("intent")
    reason = snapshot.get("intent_reason")
    vision_router = snapshot.get("vision_router") or {}
    if not reason:
        reason = vision_router.get("reason")
    if not intent:
        intent = vision_router.get("intent")
    if isinstance(intent, str):
        intent = intent.strip().upper() or None
    return intent, reason


def _extract_subject_features(slot: GenerationTask) -> str | None:
    snapshot = slot.prompt_snapshot_json or {}
    subject_features = snapshot.get("subject_features")
    vision_router = snapshot.get("vision_router") or {}
    if not subject_features:
        subject_features = vision_router.get("subject_features")
    if isinstance(subject_features, str):
        return subject_features.strip() or None
    return None


def _intent_label(intent: str | None) -> str | None:
    if intent == "SCENE_EDIT":
        return "场景重绘"
    if intent == "POSE_VARIATION":
        return "动作变体"
    return None


def _build_generation_task_slot_response(slot: GenerationTask) -> GenerationTaskSlotResponse:
    intent, reason = _extract_task_intent(slot)
    subject_features = _extract_subject_features(slot)
    return GenerationTaskSlotResponse(
        id=slot.id,
        variant_index=slot.variant_index,
        variant_axis=slot.variant_axis.value,
        intent=intent,
        intent_label=_intent_label(intent),
        intent_reason=reason,
        subject_features=subject_features,
        status=slot.status.value,
        provider_final=slot.provider_final,
        provider_route_final=slot.provider_route_final.value if slot.provider_route_final else None,
        attempt_count=slot.attempt_count,
        max_attempts=slot.max_attempts,
        output_path=_to_public_asset_url(slot.output_path),
        output_file_name=slot.output_file_name,
        qc_status=slot.qc_status.value,
        last_error_code=slot.last_error_code,
        last_error_message=slot.last_error_message,
        completed_at=slot.completed_at,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
    )


def _to_public_asset_url(path: str | None) -> str | None:
    if not path:
        return None

    normalized = path.replace("\\", "/")
    if normalized.startswith(("http://", "https://", "data:image/", "/static/")):
        return normalized

    try:
        relative_path = Path(path).resolve().relative_to(settings.data_root)
        return f"/static/{relative_path.as_posix()}"
    except Exception:
        return None


def _build_task_response(item: SourceTask) -> TaskResponse:
    return TaskResponse(
        id=item.id,
        batch_id=item.batch_id,
        source_index=item.source_index,
        status=item.status.value,
        source_name=item.source_name,
        source_path=_to_public_asset_url(item.source_path) or item.source_path,
        normalized_path=_to_public_asset_url(item.normalized_path),
        source_hash=item.source_hash,
        target_variant_count=item.target_variant_count,
        success_count=item.success_count,
        failed_count=item.failed_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
        generation_tasks=[
            _build_generation_task_slot_response(slot)
            for slot in item.generation_tasks
        ],
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    batch_id: int = Query(..., ge=1),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    filters = [SourceTask.batch_id == batch_id]

    if status:
        allowed_statuses = {item.value for item in SourceTaskStatus}
        if status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的原图任务状态筛选值：{status}",
            )
        filters.append(SourceTask.status == status)

    total_stmt = select(func.count()).select_from(SourceTask).where(*filters)
    total = (await session.execute(total_stmt)).scalar_one()

    stmt = (
        select(SourceTask)
        .where(*filters)
        .options(selectinload(SourceTask.generation_tasks))
        .order_by(SourceTask.source_index.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await session.execute(stmt)).scalars().unique().all()

    return TaskListResponse(
        items=[_build_task_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{generation_task_id}/retry")
async def retry_generation_task(
    generation_task_id: int,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str | int]:
    stmt = (
        select(GenerationTask)
        .where(GenerationTask.id == generation_task_id)
        .options(
            selectinload(GenerationTask.source_task),
            selectinload(GenerationTask.batch),
        )
    )
    task = (await session.execute(stmt)).scalar_one_or_none()

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到需要重试的生成任务。",
        )

    now = datetime.utcnow()
    if task.status == TaskStatus.PROCESSING and task.lease_until and task.lease_until > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前任务仍在处理中，请稍后再试。",
        )

    if task.batch.status == BatchStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前批次已取消，无法执行手动重试。",
        )

    if task.attempt_count >= task.max_attempts:
        task.max_attempts = task.attempt_count + 1

    task.status = TaskStatus.RETRYING
    task.next_run_at = now
    task.processing_started_at = None
    task.completed_at = None
    task.lease_owner = None
    task.lease_until = None
    task.qc_status = QCStatus.PENDING
    task.qc_fail_codes_json = None
    task.last_error_code = None
    task.last_error_message = None
    task.last_provider_http_status = None
    task.last_switch_reason = None
    task.manual_retry_requested = True

    task.source_task.last_error_code = None
    task.source_task.last_error_message = None
    task.batch.last_error_code = None
    task.batch.last_error_message = None
    task.batch.status = BatchStatus.RUNNING
    task.batch.scheduler_finished_at = None
    if task.batch.scheduler_started_at is None:
        task.batch.scheduler_started_at = now

    await session.flush()
    await _recompute_source_and_batch_state(session, task_id=task.id)

    return {
        "task_id": generation_task_id,
        "status": TaskStatus.RETRYING.value,
        "message": "重试请求已提交，调度器将尽快重新消费该任务。",
    }
