from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.enums import SourceTaskStatus
from app.models.tasks import SourceTask
from app.schemas.tasks import GenerationTaskSlotResponse, TaskListResponse, TaskResponse

router = APIRouter()


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
            from fastapi import HTTPException, status as http_status

            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
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

    task_items = [
        TaskResponse(
            id=item.id,
            batch_id=item.batch_id,
            source_index=item.source_index,
            status=item.status.value,
            source_name=item.source_name,
            source_path=item.source_path,
            normalized_path=item.normalized_path,
            source_hash=item.source_hash,
            target_variant_count=item.target_variant_count,
            success_count=item.success_count,
            failed_count=item.failed_count,
            created_at=item.created_at,
            updated_at=item.updated_at,
            generation_tasks=[
                GenerationTaskSlotResponse(
                    id=slot.id,
                    variant_index=slot.variant_index,
                    variant_axis=slot.variant_axis.value,
                    status=slot.status.value,
                    provider_final=slot.provider_final,
                    provider_route_final=slot.provider_route_final.value if slot.provider_route_final else None,
                    attempt_count=slot.attempt_count,
                    max_attempts=slot.max_attempts,
                    output_path=slot.output_path,
                    output_file_name=slot.output_file_name,
                    qc_status=slot.qc_status.value,
                    last_error_code=slot.last_error_code,
                    last_error_message=slot.last_error_message,
                    completed_at=slot.completed_at,
                    created_at=slot.created_at,
                    updated_at=slot.updated_at,
                )
                for slot in item.generation_tasks
            ],
        )
        for item in items
    ]

    return TaskListResponse(
        items=task_items,
        total=total,
        page=page,
        page_size=page_size,
    )
