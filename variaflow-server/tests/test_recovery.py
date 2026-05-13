from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.services.recovery import is_retryable_lock_error
from app.services.recovery import recover_expired_task_ids


def _build_operational_error(code: int, message: str) -> OperationalError:
    original = SimpleNamespace(args=(code, message))
    return OperationalError("mock statement", {}, original)


def test_is_retryable_lock_error_detects_deadlock() -> None:
    exc = _build_operational_error(1213, "Deadlock found when trying to get lock")
    assert is_retryable_lock_error(exc) is True


def test_is_retryable_lock_error_detects_lock_wait_timeout() -> None:
    exc = _build_operational_error(1205, "Lock wait timeout exceeded")
    assert is_retryable_lock_error(exc) is True


def test_is_retryable_lock_error_ignores_other_operational_errors() -> None:
    exc = _build_operational_error(1049, "Unknown database")
    assert is_retryable_lock_error(exc) is False


def test_is_retryable_lock_error_ignores_non_sqlalchemy_errors() -> None:
    assert is_retryable_lock_error(RuntimeError("boom")) is False


@pytest.mark.asyncio
async def test_recover_expired_task_ids_returns_requeue_candidates(db_session) -> None:
    from datetime import datetime, timedelta

    from app.models.enums import BatchStatus, ExportStatus, SourceTaskStatus, TaskStatus, UploadMode, VariantAxis
    from app.models.tasks import BatchJob, GenerationTask, SourceTask

    batch = BatchJob(
        batch_code="batch_recovery",
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="recovery.zip",
        input_archive_path="archive.zip",
        input_root_path="archive",
        unzip_root_path="unpacked",
        normalized_root_path="normalized",
        output_root_path="outputs",
        failed_root_path="failed",
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=1,
        total_source_count=1,
        total_generation_count=1,
    )
    source_task = SourceTask(
        batch=batch,
        source_index=1,
        status=SourceTaskStatus.PENDING,
        source_name="source.png",
        source_ext="png",
        source_relative_path="source.png",
        source_path="source.png",
        normalized_path="source.png",
        source_hash="hash",
        source_size_bytes=1,
        target_variant_count=1,
    )
    generation_task = GenerationTask(
        batch=batch,
        source_task=source_task,
        variant_index=1,
        variant_axis=VariantAxis.MIXED,
        status=TaskStatus.PROCESSING,
        attempt_count=1,
        max_attempts=3,
        lease_until=datetime.utcnow() - timedelta(seconds=10),
    )
    db_session.add_all([batch, source_task, generation_task])
    await db_session.commit()

    recovered_ids = await recover_expired_task_ids(db_session)

    assert recovered_ids == [generation_task.id]
