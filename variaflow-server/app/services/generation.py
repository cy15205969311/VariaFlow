from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AttemptOutcome, ProviderRoute, QCStatus, TaskStatus
from app.models.tasks import GenerationAttempt, GenerationTask

logger = logging.getLogger(__name__)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_basic_output(file_path: Path, *, min_file_size_bytes: int) -> int:
    """
    MVP 阶段的基础规则校验。

    后续迭代可在这里补充图片解码、尺寸等更细的校验逻辑。
    """

    size = file_path.stat().st_size
    if size < min_file_size_bytes:
        raise ValueError(f"生成文件过小：{size} 字节")
    return size


async def finalize_generation_task(
    session: AsyncSession,
    *,
    task: GenerationTask,
    attempt: GenerationAttempt,
    image_bytes: bytes,
    final_output_path: Path,
    tmp_dir: Path,
    provider_route: ProviderRoute,
    min_file_size_bytes: int = 51_200,
    temp_path: Path | None = None,
) -> GenerationTask:
    """
    以“文件系统优先”的语义收尾一次成功生成任务。

    崩溃恢复说明：
    - 如果进程在数据库提交之前退出，任务行会保持 processing 状态并保留租约。
    - 当 lease_until 过期后，恢复循环可以在检查最终文件是否存在且槽位匹配后，
      将任务重新放回 retrying。
    - 这样可以避免“数据库已成功，但文件只写了一半”的脏数据问题。
    """

    await asyncio.to_thread(tmp_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(final_output_path.parent.mkdir, parents=True, exist_ok=True)

    resolved_temp_path = temp_path or (tmp_dir / f"{task.id}_attempt_{attempt.attempt_no}.part")
    if temp_path is None:
        await asyncio.to_thread(resolved_temp_path.write_bytes, image_bytes)

    output_size_bytes = await asyncio.to_thread(
        _validate_basic_output,
        resolved_temp_path,
        min_file_size_bytes=min_file_size_bytes,
    )
    output_hash = _sha256_bytes(image_bytes)

    # 在同一文件系统内，os.replace 具备原子性。
    # 这里是“不完整临时文件”切换为“最终可见产物”的关键交接点。
    await asyncio.to_thread(os.replace, resolved_temp_path, final_output_path)
    logger.info(
        "Generation output saved task_id=%s path=%s bytes=%s provider_route=%s",
        task.id,
        final_output_path,
        output_size_bytes,
        provider_route.value,
    )

    task.status = TaskStatus.FALLBACK_SUCCESS if provider_route == ProviderRoute.FALLBACK else TaskStatus.SUCCESS
    task.provider_route_final = provider_route
    task.output_path = str(final_output_path)
    task.output_file_name = final_output_path.name
    task.output_ext = final_output_path.suffix.lstrip(".")
    task.output_hash = output_hash
    task.output_size_bytes = output_size_bytes
    task.qc_status = QCStatus.PASSED
    task.completed_at = datetime.utcnow()
    task.lease_owner = None
    task.lease_until = None
    task.last_error_code = None
    task.last_error_message = None
    task.manual_retry_requested = False

    attempt.finished_at = datetime.utcnow()
    attempt.outcome = AttemptOutcome.SUCCESS
    attempt.temporary_file_path = str(resolved_temp_path)

    # 只有在持久化文件已经稳定落盘后，才把成功状态写入 MySQL。
    await session.commit()
    await session.refresh(task)
    return task
