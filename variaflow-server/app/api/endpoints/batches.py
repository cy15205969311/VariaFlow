from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.tasks import BatchJob
from app.schemas.batches import BatchResponse
from app.services.upload import process_upload

router = APIRouter()


def _estimate_remaining_seconds(batch: BatchJob) -> int | None:
    completed = batch.success_generation_count + batch.failed_generation_count
    remaining = max(batch.total_generation_count - completed, 0)
    if remaining == 0:
        return 0
    return remaining * 10


def _to_batch_response(batch: BatchJob) -> BatchResponse:
    return BatchResponse(
        id=batch.id,
        batch_code=batch.batch_code,
        status=batch.status.value,
        upload_mode=batch.upload_mode.value,
        original_upload_name=batch.original_upload_name,
        target_variant_count=batch.target_variant_count,
        total_source_count=batch.total_source_count,
        total_generation_count=batch.total_generation_count,
        completed_source_count=batch.completed_source_count,
        partial_source_count=batch.partial_source_count,
        failed_source_count=batch.failed_source_count,
        success_generation_count=batch.success_generation_count,
        failed_generation_count=batch.failed_generation_count,
        estimated_remaining_seconds=_estimate_remaining_seconds(batch),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_batch_zip(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> BatchResponse:
    if file.content_type not in {"application/zip", "application/x-zip-compressed", "multipart/x-zip"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件类型不受支持，请上传 ZIP 压缩包。",
        )

    batch = await process_upload(file, session)
    return _to_batch_response(batch)


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: int, session: AsyncSession = Depends(get_db)) -> BatchResponse:
    result = await session.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = result.scalar_one_or_none()

    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应批次。")

    return _to_batch_response(batch)
