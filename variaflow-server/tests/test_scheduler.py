from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BatchStatus, ExportStatus, SourceTaskStatus, TaskStatus, UploadMode, VariantAxis
from app.models.tasks import BatchJob, GenerationTask, SourceTask
from app.services.scheduler import fetch_and_lock_next_generation_task


@pytest.mark.asyncio
async def test_fetch_and_lock_next_generation_task_prefers_newest_running_batch(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(delete(GenerationTask))
    await db_session.execute(delete(SourceTask))
    await db_session.execute(delete(BatchJob))
    await db_session.commit()

    older_batch = BatchJob(
        batch_code="batch_old",
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="old.zip",
        input_archive_path="old.zip",
        input_root_path="old",
        unzip_root_path="old_unpack",
        normalized_root_path="old_norm",
        output_root_path="old_out",
        failed_root_path="old_failed",
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=1,
        total_source_count=1,
        total_generation_count=1,
        created_at=datetime.utcnow() - timedelta(minutes=5),
        updated_at=datetime.utcnow() - timedelta(minutes=5),
    )
    newer_batch = BatchJob(
        batch_code="batch_new",
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="new.zip",
        input_archive_path="new.zip",
        input_root_path="new",
        unzip_root_path="new_unpack",
        normalized_root_path="new_norm",
        output_root_path="new_out",
        failed_root_path="new_failed",
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=1,
        total_source_count=1,
        total_generation_count=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    older_source = SourceTask(
        batch=older_batch,
        source_index=1,
        status=SourceTaskStatus.PENDING,
        source_name="old.png",
        source_ext="png",
        source_relative_path="old.png",
        source_path="old.png",
        normalized_path="old.png",
        source_hash="old_hash",
        source_size_bytes=123,
        target_variant_count=1,
    )
    newer_source = SourceTask(
        batch=newer_batch,
        source_index=1,
        status=SourceTaskStatus.PENDING,
        source_name="new.png",
        source_ext="png",
        source_relative_path="new.png",
        source_path="new.png",
        normalized_path="new.png",
        source_hash="new_hash",
        source_size_bytes=123,
        target_variant_count=1,
    )

    older_task = GenerationTask(
        batch=older_batch,
        source_task=older_source,
        variant_index=1,
        variant_axis=VariantAxis.MIXED,
        status=TaskStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )
    newer_task = GenerationTask(
        batch=newer_batch,
        source_task=newer_source,
        variant_index=1,
        variant_axis=VariantAxis.MIXED,
        status=TaskStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )

    db_session.add_all([older_batch, newer_batch, older_source, newer_source, older_task, newer_task])
    await db_session.commit()

    locked = await fetch_and_lock_next_generation_task(
        db_session,
        lease_owner="pytest-scheduler-priority",
        lease_seconds=120,
    )

    assert locked is not None
    assert locked.batch_id == newer_batch.id
