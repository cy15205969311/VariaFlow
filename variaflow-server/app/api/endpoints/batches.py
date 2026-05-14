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
from app.models.enums import BatchStatus, ExportStatus, TaskStatus
from app.models.tasks import BatchJob, GenerationTask
from app.schemas.batches import BatchResponse
from app.services.async_tasks import enqueue_generation_task
from app.services.upload import process_upload

router = APIRouter()
logger = logging.getLogger(__name__)

NO_DOWNLOADABLE_OUTPUTS_DETAIL = "当前批次暂无可下载输出。"
UNSUPPORTED_ZIP_DETAIL = "文件类型不受支持，请上传 ZIP 压缩包。"
BATCH_FETCH_FAILED_DETAIL = "批次已创建，但回读批次信息失败。"
DOWNLOAD_NOT_READY_DETAIL = "当前批次尚未生成可下载图片，请稍后重试。"
BATCH_NOT_FOUND_DETAIL = "未找到对应批次。"


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


def _build_archive_member_name(output_file: Path, output_root: Path | None, generation_task: GenerationTask) -> str:
    if output_root is not None:
        try:
            return output_file.relative_to(output_root).as_posix()
        except ValueError:
            pass

    if generation_task.output_file_name:
        return generation_task.output_file_name

    if output_file.parent.name:
        return f"{output_file.parent.name}/{output_file.name}"

    return output_file.name


async def _build_batch_export_archive(batch: BatchJob, session: AsyncSession) -> Path:
    output_root = Path(batch.output_root_path).resolve(strict=False) if batch.output_root_path else None
    result = await session.execute(
        select(GenerationTask)
        .where(
            GenerationTask.batch_id == batch.id,
            GenerationTask.status.in_((TaskStatus.SUCCESS, TaskStatus.FALLBACK_SUCCESS)),
            GenerationTask.output_path.is_not(None),
        )
        .order_by(GenerationTask.source_task_id, GenerationTask.variant_index, GenerationTask.id)
    )
    generation_tasks = result.scalars().all()

    output_files: list[tuple[Path, str]] = []
    for generation_task in generation_tasks:
        output_path = Path(generation_task.output_path or "")
        if not output_path.is_file():
            logger.warning(
                "Skip missing generation output during export",
                extra={
                    "batch_id": batch.id,
                    "generation_task_id": generation_task.id,
                    "output_path": generation_task.output_path,
                },
            )
            continue
        output_files.append((output_path, _build_archive_member_name(output_path, output_root, generation_task)))

    if not output_files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_DOWNLOADABLE_OUTPUTS_DETAIL)

    await asyncio.to_thread(settings.export_temp_root.mkdir, parents=True, exist_ok=True)
    export_temp_dir = Path(tempfile.mkdtemp(prefix=f"{batch.batch_code}_", dir=str(settings.export_temp_root)))
    archive_path = export_temp_dir / f"{batch.batch_code}_outputs.zip"

    def _write_archive() -> None:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for output_file, archive_name in output_files:
                archive.write(output_file, arcname=archive_name)

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
            detail=UNSUPPORTED_ZIP_DETAIL,
        )

    try:
        upload_result = await process_upload(file, session)
        if settings.async_execution_mode == "celery":
            for task_id in upload_result.generation_task_ids:
                enqueue_generation_task(task_id)

        batch = (
            await session.execute(select(BatchJob).where(BatchJob.id == upload_result.batch_id))
        ).scalar_one_or_none()
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=BATCH_FETCH_FAILED_DETAIL,
            )
        return _to_batch_response(batch)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=BATCH_NOT_FOUND_DETAIL)

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=BATCH_NOT_FOUND_DETAIL)

    if not _download_ready(batch):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DOWNLOAD_NOT_READY_DETAIL,
        )

    batch.export_status = ExportStatus.PROCESSING
    batch.exported_at = datetime.utcnow()
    await session.commit()

    try:
        archive_path = await _build_batch_export_archive(batch, session)
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
