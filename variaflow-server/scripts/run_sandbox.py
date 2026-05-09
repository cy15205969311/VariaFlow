from __future__ import annotations

import asyncio
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.enums import BatchStatus, ExportStatus, ProviderRoute, SourceTaskStatus, TaskStatus, UploadMode, VariantAxis
from app.models.tasks import BatchJob, GenerationAttempt, GenerationTask, QualityCheckResult, SourceTask
from app.services.executor import process_generation_task
from app.services.scheduler import fetch_and_lock_next_generation_task


def _build_sandbox_paths(batch_code: str) -> dict[str, Path]:
    batch_root = settings.data_root / "sandbox" / batch_code
    return {
        "batch_root": batch_root,
        "archive_root": batch_root / "input_archive",
        "unpacked_root": batch_root / "input_unpacked",
        "normalized_root": batch_root / "normalized",
        "output_root": batch_root / "outputs",
        "failed_root": batch_root / "failed",
        "tmp_root": batch_root / "tmp",
    }


async def _prepare_directories(paths: dict[str, Path]) -> None:
    for path in paths.values():
        if path.suffix:
            continue
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)


async def _cleanup_batch_code(batch_code: str) -> None:
    async with AsyncSessionLocal() as session:
        batch_ids = (
            await session.execute(select(BatchJob.id).where(BatchJob.batch_code == batch_code))
        ).scalars().all()
        if batch_ids:
            await session.execute(delete(BatchJob).where(BatchJob.id.in_(batch_ids)))
            await session.commit()

    batch_root = settings.data_root / "sandbox" / batch_code
    if batch_root.exists():
        await asyncio.to_thread(shutil.rmtree, batch_root, True)


async def _seed_sandbox_data(batch_code: str) -> tuple[int, dict[str, Path]]:
    paths = _build_sandbox_paths(batch_code)
    await _prepare_directories(paths)

    normalized_file = paths["normalized_root"] / "S0001_src_mock.png"
    await asyncio.to_thread(
        normalized_file.write_bytes,
        b"mock-source-file",
    )

    batch = BatchJob(
        batch_code=batch_code,
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="sandbox.zip",
        input_archive_path=str(paths["archive_root"] / "sandbox.zip"),
        input_root_path=str(paths["archive_root"]),
        unzip_root_path=str(paths["unpacked_root"]),
        normalized_root_path=str(paths["normalized_root"]),
        output_root_path=str(paths["output_root"]),
        failed_root_path=str(paths["failed_root"]),
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=2,
        total_source_count=1,
        total_generation_count=2,
        scheduler_started_at=datetime.utcnow(),
    )

    source_task = SourceTask(
        batch=batch,
        source_index=1,
        status=SourceTaskStatus.PENDING,
        source_name=normalized_file.name,
        source_ext="png",
        source_relative_path=normalized_file.name,
        source_path=str(normalized_file),
        normalized_path=str(normalized_file),
        source_hash=uuid.uuid4().hex * 2,
        source_size_bytes=normalized_file.stat().st_size,
        target_variant_count=2,
        success_count=0,
        failed_count=0,
        identity_profile_json={"identity_lock": "Preserve the exact mock subject identity from the reference image."},
    )

    generation_tasks = [
        GenerationTask(
            batch=batch,
            source_task=source_task,
            variant_index=variant_index,
            variant_axis=VariantAxis.MIXED,
            status=TaskStatus.PENDING,
            attempt_count=0,
            max_attempts=3,
        )
        for variant_index in range(1, 3)
    ]

    async with AsyncSessionLocal() as session:
        session.add(batch)
        session.add(source_task)
        session.add_all(generation_tasks)
        await session.commit()
        return batch.id, paths


async def _drive_batch_until_terminal(batch_id: int, max_rounds: int = 12) -> list[int]:
    """
    模拟调度器持续消费任务，直到该批次下没有可运行任务或达到最大轮数。
    """

    processed_task_ids: list[int] = []

    for _ in range(max_rounds):
        locked_task_id: int | None = None
        async with AsyncSessionLocal() as session:
            task = await fetch_and_lock_next_generation_task(
                session,
                lease_owner="sandbox-runner",
                batch_id=batch_id,
            )
            if task is not None and task.batch_id == batch_id:
                locked_task_id = task.id

        if locked_task_id is None:
            break

        processed_task_ids.append(locked_task_id)
        await process_generation_task(locked_task_id, AsyncSessionLocal)

        async with AsyncSessionLocal() as session:
            pending_retry_tasks = (
                await session.execute(
                    select(GenerationTask).where(
                        GenerationTask.batch_id == batch_id,
                        GenerationTask.status == TaskStatus.RETRYING,
                    )
                )
            ).scalars().all()
            for task in pending_retry_tasks:
                task.next_run_at = datetime.utcnow()
            if pending_retry_tasks:
                await session.commit()

        async with AsyncSessionLocal() as session:
            remaining = (
                await session.execute(
                    select(GenerationTask.id).where(
                        GenerationTask.batch_id == batch_id,
                        GenerationTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRYING]),
                    )
                )
            ).scalars().all()
        if not remaining:
            break

    return processed_task_ids


async def _assert_sandbox_result(batch_id: int, paths: dict[str, Path]) -> None:
    async with AsyncSessionLocal() as session:
        batch = (
            await session.execute(
                select(BatchJob).where(BatchJob.id == batch_id)
            )
        ).scalar_one()
        generation_tasks = (
            await session.execute(
                select(GenerationTask)
                .where(GenerationTask.batch_id == batch_id)
                .order_by(GenerationTask.variant_index.asc())
            )
        ).scalars().all()
        attempts = (
            await session.execute(
                select(GenerationAttempt)
                .join(GenerationTask, GenerationAttempt.generation_task_id == GenerationTask.id)
                .where(GenerationTask.batch_id == batch_id)
                .order_by(GenerationAttempt.attempt_no.asc())
            )
        ).scalars().all()
        qc_rows = (
            await session.execute(
                select(QualityCheckResult)
                .join(GenerationTask, QualityCheckResult.generation_task_id == GenerationTask.id)
                .where(GenerationTask.batch_id == batch_id)
            )
        ).scalars().all()

    assert batch.status in {
        BatchStatus.COMPLETED,
        BatchStatus.PARTIAL_SUCCESS,
        BatchStatus.FAILED,
        BatchStatus.RUNNING,
    }, f"批次状态异常：{batch.status.value}"
    assert generation_tasks, "未生成 generation_task 记录"
    assert attempts, "未生成 generation_attempt 审计记录"
    assert attempts[-1].latency_ms is not None, "最后一次尝试未记录耗时"
    assert attempts[-1].provider_code, "最后一次尝试未记录 provider_code"

    success_tasks = [task for task in generation_tasks if task.status in {TaskStatus.SUCCESS, TaskStatus.FALLBACK_SUCCESS}]
    failed_tasks = [task for task in generation_tasks if task.status == TaskStatus.FAILED]
    retrying_tasks = [task for task in generation_tasks if task.status == TaskStatus.RETRYING]

    for task in success_tasks:
        assert task.output_path, f"成功任务未写入 output_path：{task.id}"
        final_path = Path(task.output_path)
        assert final_path.exists(), f"正式输出文件不存在：{final_path}"
        assert task.provider_route_final in {ProviderRoute.PRIMARY, ProviderRoute.FALLBACK}

    assert not retrying_tasks, "沙盒运行结束后仍存在 retrying 任务，说明重试链路未跑完"
    if success_tasks:
        assert qc_rows, "存在成功任务时应有质检结果"

    part_files = list(paths["tmp_root"].glob("*.part")) if paths["tmp_root"].exists() else []
    assert not part_files, f"临时 .part 文件未清理：{[str(item) for item in part_files]}"

    print("沙盒运行完成。")
    print(f"批次状态：{batch.status.value}")
    print(f"成功任务数：{len(success_tasks)}")
    print(f"失败任务数：{len(failed_tasks)}")
    print(f"尝试次数：{len(attempts)}")
    print(f"最后一次 provider：{attempts[-1].provider_code}")
    print(f"最后一次耗时：{attempts[-1].latency_ms} ms")
    if success_tasks:
        print("正式文件：")
        for task in success_tasks:
            print(f"  - {task.output_path}")


async def main() -> None:
    batch_code = f"sandbox_{uuid.uuid4().hex[:10]}"
    print(f"开始沙盒运行：{batch_code}")
    print(f"Mock AI 开关：{settings.use_mock_ai}")
    print(f"Mock 故障率：{settings.mock_failure_rate}")

    await _cleanup_batch_code(batch_code)
    batch_id, paths = await _seed_sandbox_data(batch_code)

    try:
        processed_task_ids = await _drive_batch_until_terminal(batch_id)
        print(f"本轮处理过的任务 ID：{processed_task_ids}")
        await _assert_sandbox_result(batch_id, paths)
    finally:
        # 默认保留文件与数据库记录，方便本地观察。
        # 如果需要无痕调试，可把下面两行取消注释。
        # await _cleanup_batch_code(batch_code)
        # print("已清理沙盒数据。")
        pass


if __name__ == "__main__":
    asyncio.run(main())
