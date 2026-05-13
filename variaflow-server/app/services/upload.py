from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import BatchStatus, ExportStatus, SourceTaskStatus, TaskStatus, UploadMode, VariantAxis
from app.models.tasks import BatchJob, GenerationTask, SourceTask

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NormalizedImage:
    source_index: int
    source_name: str
    source_ext: str
    source_relative_path: str
    source_path: str
    normalized_path: str
    source_hash: str
    source_size_bytes: int


@dataclass(slots=True)
class UploadBatchResult:
    batch: BatchJob
    generation_task_ids: list[int]


def _compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _normalize_zip_member_name(member_name: str) -> str:
    return member_name.replace("\\", "/")


def _is_safe_zip_member(member_name: str) -> bool:
    pure_path = PurePosixPath(_normalize_zip_member_name(member_name))
    if pure_path.is_absolute():
        return False
    if any(part.endswith(":") for part in pure_path.parts):
        return False
    return all(part not in {"..", ""} for part in pure_path.parts)


def _extract_zip_safely(zip_path: Path, destination: Path) -> list[Path]:
    extracted_files: list[Path] = []

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            normalized_member_name = _normalize_zip_member_name(info.filename)
            if not _is_safe_zip_member(normalized_member_name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"检测到不安全的 ZIP 条目：{info.filename}",
                )

            member_path = PurePosixPath(normalized_member_name)
            suffix = member_path.suffix.lower()
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            target_path = destination / Path(*member_path.parts)
            resolved_destination = destination.resolve()
            resolved_target = target_path.resolve(strict=False)
            if resolved_destination not in resolved_target.parents and resolved_target != resolved_destination:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"检测到非法解压目标：{info.filename}",
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source_handle, target_path.open("wb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle)
            extracted_files.append(target_path)

    return extracted_files


async def _save_upload_to_disk(upload_file: UploadFile, destination: Path) -> None:
    await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)

    try:
        with destination.open("wb") as output_handle:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                await asyncio.to_thread(output_handle.write, chunk)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=f"上传文件落盘失败：{exc}",
        ) from exc
    finally:
        await upload_file.close()


async def _normalize_images(
    *,
    extracted_files: list[Path],
    normalized_root: Path,
    unpacked_root: Path,
) -> list[NormalizedImage]:
    if not extracted_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的 ZIP 压缩包中未发现受支持的图片文件。",
        )

    await asyncio.to_thread(normalized_root.mkdir, parents=True, exist_ok=True)

    unique_images: list[NormalizedImage] = []
    seen_hashes: set[str] = set()

    for extracted_file in sorted(extracted_files):
        source_hash = await asyncio.to_thread(_compute_sha256, extracted_file)
        if source_hash in seen_hashes:
            continue
        seen_hashes.add(source_hash)

        source_index = len(unique_images) + 1
        suffix = extracted_file.suffix.lower()
        normalized_name = f"S{source_index:04d}_src_{source_hash[:8]}{suffix}"
        normalized_path = normalized_root / normalized_name

        await asyncio.to_thread(shutil.move, str(extracted_file), str(normalized_path))
        source_size_bytes = await asyncio.to_thread(lambda: normalized_path.stat().st_size)

        try:
            relative_path = str(extracted_file.relative_to(unpacked_root))
        except ValueError:
            relative_path = extracted_file.name

        unique_images.append(
            NormalizedImage(
                source_index=source_index,
                source_name=normalized_name,
                source_ext=suffix.lstrip("."),
                source_relative_path=relative_path.replace("\\", "/"),
                source_path=str(normalized_path),
                normalized_path=str(normalized_path),
                source_hash=source_hash,
                source_size_bytes=source_size_bytes,
            )
        )

    if not unique_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZIP 压缩包内所有文件均为重复文件或不受支持的格式。",
        )

    return unique_images


async def process_upload(file: UploadFile, session: AsyncSession) -> UploadBatchResult:
    batch_code = f"batch_{uuid.uuid4().hex[:12]}"
    batch_root = settings.data_root / batch_code
    archive_root = batch_root / "input_archive"
    unpacked_root = batch_root / "input_unpacked"
    normalized_root = batch_root / "normalized"
    output_root = batch_root / "outputs"
    failed_root = batch_root / "failed"

    archive_name = Path(file.filename or "upload.zip").name or "upload.zip"
    archive_path = archive_root / archive_name

    if not archive_name.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前仅支持上传 .zip 压缩包。",
        )

    try:
        await _save_upload_to_disk(file, archive_path)
        extracted_files = await asyncio.to_thread(_extract_zip_safely, archive_path, unpacked_root)
        normalized_images = await _normalize_images(
            extracted_files=extracted_files,
            normalized_root=normalized_root,
            unpacked_root=unpacked_root,
        )
    except zipfile.BadZipFile as exc:
        logger.exception("ZIP解析失败：非法压缩包", extra={"archive_name": archive_name, "batch_code": batch_code})
        await asyncio.to_thread(shutil.rmtree, batch_root, True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不是合法的 ZIP 压缩包。",
        ) from exc
    except HTTPException:
        logger.exception("ZIP解析或图片归一化失败", extra={"archive_name": archive_name, "batch_code": batch_code})
        await asyncio.to_thread(shutil.rmtree, batch_root, True)
        raise
    except OSError as exc:
        logger.exception("ZIP上传文件系统操作失败", extra={"archive_name": archive_name, "batch_code": batch_code})
        await asyncio.to_thread(shutil.rmtree, batch_root, True)
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=f"文件系统操作失败：{exc}",
        ) from exc
    except Exception as exc:
        logger.exception("ZIP解析或任务创建失败", extra={"archive_name": archive_name, "batch_code": batch_code})
        await asyncio.to_thread(shutil.rmtree, batch_root, True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ZIP解析或任务创建失败: {exc}",
        ) from exc

    target_variant_count = (
        settings.default_target_variant_count
        if settings.default_target_variant_count in {1, 2, 3}
        else 1
    )
    total_source_count = len(normalized_images)
    total_generation_count = total_source_count * target_variant_count

    batch = BatchJob(
        batch_code=batch_code,
        status=BatchStatus.INGESTING,
        upload_mode=UploadMode.ZIP,
        original_upload_name=archive_name,
        input_archive_path=str(archive_path),
        input_root_path=str(archive_root),
        unzip_root_path=str(unpacked_root),
        normalized_root_path=str(normalized_root),
        output_root_path=str(output_root),
        failed_root_path=str(failed_root),
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=target_variant_count,
        total_source_count=total_source_count,
        total_generation_count=total_generation_count,
    )

    generation_task_refs: list[GenerationTask] = []

    for normalized_image in normalized_images:
        source_task = SourceTask(
            source_index=normalized_image.source_index,
            status=SourceTaskStatus.PENDING,
            source_name=normalized_image.source_name,
            source_ext=normalized_image.source_ext,
            source_relative_path=normalized_image.source_relative_path,
            source_path=normalized_image.source_path,
            normalized_path=normalized_image.normalized_path,
            source_hash=normalized_image.source_hash,
            source_size_bytes=normalized_image.source_size_bytes,
            target_variant_count=target_variant_count,
            success_count=0,
            failed_count=0,
        )

        source_task.generation_tasks = [
            GenerationTask(
                batch=batch,
                variant_index=variant_index,
                variant_axis=VariantAxis.MIXED,
                status=TaskStatus.PENDING,
                attempt_count=0,
                max_attempts=3,
            )
            for variant_index in range(1, target_variant_count + 1)
        ]
        generation_task_refs.extend(source_task.generation_tasks)
        batch.source_tasks.append(source_task)

    try:
        async with session.begin():
            session.add(batch)
            await session.flush()
            batch.status = BatchStatus.RUNNING
            batch.scheduler_started_at = datetime.utcnow()
        await session.refresh(batch)
    except Exception as exc:
        logger.exception(
            "批次写库失败",
            extra={
                "archive_name": archive_name,
                "batch_code": batch_code,
                "total_source_count": total_source_count,
                "total_generation_count": total_generation_count,
            },
        )
        await asyncio.to_thread(shutil.rmtree, batch_root, True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库初始化批次失败：{exc}",
        ) from exc

    generation_task_ids = [task.id for task in generation_task_refs if task.id is not None]
    return UploadBatchResult(batch=batch, generation_task_ids=generation_task_ids)
