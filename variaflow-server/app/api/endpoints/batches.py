from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.models.enums import BatchStatus, ExportStatus
from app.models.tasks import BatchJob
from app.schemas.batches import BatchResponse
from app.services.async_tasks import enqueue_generation_task
from app.services.upload import process_upload

router = APIRouter()
logger = logging.getLogger(__name__)


def _estimate_remaining_seconds(batch: BatchJob) -> int | None:
    terminal_count = batch.success_generation_count + batch.failed_generation_count
    remaining = max(batch.total_generation_count - terminal_count, 0)
    if remaining == 0:
        return 0
    return remaining * 10


def _processing_generation_count(batch: BatchJob) -> int:
    return max(batch.total_generation_count - batch.success_generation_count - batch.failed_generation_count, 0)


def _terminal_generation_count(batch: BatchJob) -> int:
    return batch.success_generation_count + batch.failed_generation_count


def _progress_percent(batch: BatchJob) -> float:
    if batch.total_generation_count <= 0:
        return 0.0
    return round((_terminal_generation_count(batch) / batch.total_generation_count) * 100, 2)


def _download_ready(batch: BatchJob) -> bool:
    return (
        batch.success_generation_count > 0
        and batch.status in {BatchStatus.COMPLETED, BatchStatus.PARTIAL_SUCCESS, BatchStatus.FAILED}
    )


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
        processing_generation_count=_processing_generation_count(batch),
        terminal_generation_count=_terminal_generation_count(batch),
        progress_percent=_progress_percent(batch),
        download_ready=_download_ready(batch),
        export_status=batch.export_status.value,
        estimated_remaining_seconds=_estimate_remaining_seconds(batch),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _cleanup_export_path(path: str) -> None:
    file_path = Path(path)
    try:
        if file_path.is_dir():
            shutil.rmtree(file_path, ignore_errors=True)
        else:
            file_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to cleanup export temp path", extra={"path": path})


async def _build_batch_export_archive(batch: BatchJob) -> Path:
    output_root = Path(batch.output_root_path or "")
    if not output_root.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前批次暂无可下载输出。")

    output_files = sorted(file_path for file_path in output_root.rglob("*") if file_path.is_file())
    if not output_files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前批次暂无可下载输出。")

    await asyncio.to_thread(settings.export_temp_root.mkdir, parents=True, exist_ok=True)
    export_temp_dir = Path(tempfile.mkdtemp(prefix=f"{batch.batch_code}_", dir=str(settings.export_temp_root)))
    archive_path = export_temp_dir / f"{batch.batch_code}_outputs.zip"

    def _write_archive() -> None:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for output_file in output_files:
                archive.write(output_file, arcname=output_file.relative_to(output_root).as_posix())

    await asyncio.to_thread(_write_archive)
    return archive_path


@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_zip(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> BatchResponse:
    if file.content_type not in {"application/zip", "application/x-zip-compressed", "multipart/x-zip"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件类型不受支持，请上传 ZIP 压缩包。",
        )

    try:
        upload_result = await process_upload(file, session)
        if settings.async_execution_mode == "celery":
            for task_id in upload_result.generation_task_ids:
                enqueue_generation_task(task_id)
        return _to_batch_response(upload_result.batch)
    except HTTPException:
        logger.exception(
            "ZIP解析或任务创建失败",
            extra={
                "upload_filename": file.filename,
                "upload_content_type": file.content_type,
            },
        )
        raise
    except Exception as exc:
        logger.exception(
            "ZIP解析或任务创建失败",
            extra={
                "upload_filename": file.filename,
                "upload_content_type": file.content_type,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ZIP解析或任务创建失败: {exc}",
        ) from exc


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: int, session: AsyncSession = Depends(get_db)) -> BatchResponse:
    result = await session.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = result.scalar_one_or_none()

    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应批次。")

    return _to_batch_response(batch)


@router.get("/{batch_id}/download")
async def download_batch_outputs(
    batch_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    result = await session.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = result.scalar_one_or_none()

    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应批次。")

    if not _download_ready(batch):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前批次尚未生成可下载图片，请稍后重试。",
        )

    batch.export_status = ExportStatus.PROCESSING
    batch.exported_at = datetime.utcnow()
    await session.commit()

    try:
        archive_path = await _build_batch_export_archive(batch)
    except Exception:
        batch.export_status = ExportStatus.FAILED
        await session.commit()
        raise

    batch.export_zip_path = str(archive_path)
    batch.export_status = ExportStatus.SUCCESS
    await session.commit()

    background_tasks.add_task(_cleanup_export_path, str(archive_path))
    background_tasks.add_task(_cleanup_export_path, str(archive_path.parent))

    return FileResponse(
        path=str(archive_path),
        media_type="application/zip",
        filename=f"{batch.batch_code}_outputs.zip",
    )
