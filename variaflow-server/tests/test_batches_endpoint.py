from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.endpoints.batches import download_batch_outputs, get_batch, upload_batch_zip
from app.models.enums import BatchStatus, ExportStatus, TaskStatus, UploadMode
from app.models.tasks import BatchJob, GenerationTask
from app.services.upload import UploadBatchResult


@pytest.mark.asyncio
async def test_upload_batch_zip_returns_accepted_and_enqueues_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = BatchJob(
        id=12,
        batch_code="batch_async",
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="demo.zip",
        target_variant_count=3,
        total_source_count=2,
        total_generation_count=6,
        completed_source_count=0,
        partial_source_count=0,
        failed_source_count=0,
        success_generation_count=0,
        failed_generation_count=0,
        export_status=ExportStatus.NOT_REQUESTED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    queued_ids: list[int] = []

    async def _fake_process_upload(file, session) -> UploadBatchResult:
        del file, session
        return UploadBatchResult(batch_id=12, generation_task_ids=[101, 102, 103])

    class _FakeScalarResult:
        def scalar_one_or_none(self):
            return batch

    class _FakeSession:
        async def execute(self, statement):
            del statement
            return _FakeScalarResult()

    fake_settings = SimpleNamespace(async_execution_mode="celery")
    monkeypatch.setattr("app.api.endpoints.batches.process_upload", _fake_process_upload)
    monkeypatch.setattr("app.api.endpoints.batches.settings", fake_settings)
    monkeypatch.setattr("app.api.endpoints.batches.enqueue_generation_task", lambda task_id: queued_ids.append(task_id))

    upload_file = SimpleNamespace(filename="demo.zip", content_type="application/zip")

    response = await upload_batch_zip(file=upload_file, session=_FakeSession())

    assert response.id == 12
    assert response.progress_percent == 0.0
    assert response.download_ready is False
    assert response.processing_generation_count == 6
    assert queued_ids == [101, 102, 103]


@pytest.mark.asyncio
async def test_upload_batch_zip_reads_batch_by_id_instead_of_reusing_detached_orm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = BatchJob(
        id=21,
        batch_code="batch_scalar_only",
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="scalar.zip",
        target_variant_count=1,
        total_source_count=1,
        total_generation_count=1,
        completed_source_count=0,
        partial_source_count=0,
        failed_source_count=0,
        success_generation_count=0,
        failed_generation_count=0,
        export_status=ExportStatus.NOT_REQUESTED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async def _fake_process_upload(file, session) -> UploadBatchResult:
        del file, session
        return UploadBatchResult(batch_id=21, generation_task_ids=[])

    class _FakeScalarResult:
        def scalar_one_or_none(self):
            return batch

    class _FakeSession:
        async def execute(self, statement):
            del statement
            return _FakeScalarResult()

    monkeypatch.setattr("app.api.endpoints.batches.process_upload", _fake_process_upload)
    monkeypatch.setattr("app.api.endpoints.batches.settings", SimpleNamespace(async_execution_mode="inline"))

    upload_file = SimpleNamespace(filename="scalar.zip", content_type="application/zip")
    response = await upload_batch_zip(file=upload_file, session=_FakeSession())

    assert response.id == 21


@pytest.mark.asyncio
async def test_upload_batch_zip_logs_and_reraises_http_exception(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    async def _fake_process_upload(file, session) -> None:
        del file, session
        raise HTTPException(status_code=400, detail="bad zip")

    monkeypatch.setattr("app.api.endpoints.batches.process_upload", _fake_process_upload)

    upload_file = SimpleNamespace(filename="broken.zip", content_type="application/zip")

    with pytest.raises(HTTPException) as exc_info:
        await upload_batch_zip(file=upload_file, session=None)

    assert exc_info.value.status_code == 400
    assert "ZIP解析或任务创建失败" in caplog.text


@pytest.mark.asyncio
async def test_get_batch_includes_progress_and_download_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = BatchJob(
        id=88,
        batch_code="batch_ready",
        status=BatchStatus.PARTIAL_SUCCESS,
        upload_mode=UploadMode.ZIP,
        original_upload_name="ready.zip",
        target_variant_count=3,
        total_source_count=2,
        total_generation_count=6,
        completed_source_count=1,
        partial_source_count=0,
        failed_source_count=1,
        success_generation_count=4,
        failed_generation_count=2,
        export_status=ExportStatus.SUCCESS,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    class _FakeResult:
        def scalar_one_or_none(self):
            return batch

    class _FakeSession:
        async def execute(self, statement):
            del statement
            return _FakeResult()

    response = await get_batch(88, session=_FakeSession())

    assert response.progress_percent == 100.0
    assert response.terminal_generation_count == 6
    assert response.processing_generation_count == 0
    assert response.download_ready is True


@pytest.mark.asyncio
async def test_download_batch_outputs_returns_file_response_and_only_includes_success_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "outputs"
    success_file = output_root / "S0001" / "variant_1.png"
    success_file.parent.mkdir(parents=True, exist_ok=True)
    success_file.write_bytes(b"png-success")

    fallback_file = output_root / "S0002" / "variant_2.png"
    fallback_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_file.write_bytes(b"png-fallback")

    failed_file = output_root / "S0003" / "variant_3.png"
    failed_file.parent.mkdir(parents=True, exist_ok=True)
    failed_file.write_bytes(b"png-failed")

    batch = BatchJob(
        id=99,
        batch_code="batch_export",
        status=BatchStatus.COMPLETED,
        upload_mode=UploadMode.ZIP,
        original_upload_name="export.zip",
        target_variant_count=3,
        total_source_count=3,
        total_generation_count=3,
        completed_source_count=3,
        partial_source_count=0,
        failed_source_count=0,
        success_generation_count=2,
        failed_generation_count=1,
        output_root_path=str(output_root),
        export_status=ExportStatus.NOT_REQUESTED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    generation_tasks = [
        GenerationTask(
            id=1,
            batch_id=99,
            source_task_id=11,
            variant_index=1,
            status=TaskStatus.SUCCESS,
            output_path=str(success_file),
            output_file_name="variant_1.png",
        ),
        GenerationTask(
            id=2,
            batch_id=99,
            source_task_id=12,
            variant_index=2,
            status=TaskStatus.FALLBACK_SUCCESS,
            output_path=str(fallback_file),
            output_file_name="variant_2.png",
        ),
        GenerationTask(
            id=3,
            batch_id=99,
            source_task_id=13,
            variant_index=3,
            status=TaskStatus.FAILED,
            output_path=str(failed_file),
            output_file_name="variant_3.png",
        ),
    ]

    class _FakeBatchResult:
        def scalar_one_or_none(self):
            return batch

    class _FakeTaskResult:
        def scalars(self):
            successful_tasks = [
                task for task in generation_tasks if task.status in {TaskStatus.SUCCESS, TaskStatus.FALLBACK_SUCCESS}
            ]
            return SimpleNamespace(all=lambda: successful_tasks)

    class _FakeSession:
        def __init__(self) -> None:
            self.commits = 0
            self.execute_calls = 0

        async def execute(self, statement):
            del statement
            self.execute_calls += 1
            if self.execute_calls == 1:
                return _FakeBatchResult()
            return _FakeTaskResult()

        async def commit(self):
            self.commits += 1
            return None

    fake_settings = SimpleNamespace(export_temp_root=tmp_path / "_exports")
    monkeypatch.setattr("app.api.endpoints.batches.settings", fake_settings)

    session = _FakeSession()
    response = await download_batch_outputs(
        99,
        background_tasks=BackgroundTasks(),
        session=session,
    )

    assert response.media_type == "application/zip"
    assert response.filename == "batch_export_outputs.zip"
    assert Path(response.path).exists()
    assert session.commits == 2

    with zipfile.ZipFile(response.path) as archive:
        assert sorted(archive.namelist()) == ["S0001/variant_1.png", "S0002/variant_2.png"]
        assert archive.read("S0001/variant_1.png") == b"png-success"
        assert archive.read("S0002/variant_2.png") == b"png-fallback"


@pytest.mark.asyncio
async def test_download_batch_outputs_returns_404_when_no_existing_success_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    batch = BatchJob(
        id=109,
        batch_code="batch_missing_export",
        status=BatchStatus.COMPLETED,
        upload_mode=UploadMode.ZIP,
        original_upload_name="export.zip",
        target_variant_count=1,
        total_source_count=1,
        total_generation_count=1,
        completed_source_count=1,
        partial_source_count=0,
        failed_source_count=0,
        success_generation_count=1,
        failed_generation_count=0,
        output_root_path=str(tmp_path / "outputs"),
        export_status=ExportStatus.NOT_REQUESTED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    generation_tasks = [
        GenerationTask(
            id=4,
            batch_id=109,
            source_task_id=14,
            variant_index=1,
            status=TaskStatus.SUCCESS,
            output_path=str(tmp_path / "outputs" / "S0004" / "variant_1.png"),
            output_file_name="variant_1.png",
        )
    ]

    class _FakeBatchResult:
        def scalar_one_or_none(self):
            return batch

    class _FakeTaskResult:
        def scalars(self):
            return SimpleNamespace(all=lambda: generation_tasks)

    class _FakeSession:
        def __init__(self) -> None:
            self.commits = 0
            self.execute_calls = 0

        async def execute(self, statement):
            del statement
            self.execute_calls += 1
            if self.execute_calls == 1:
                return _FakeBatchResult()
            return _FakeTaskResult()

        async def commit(self):
            self.commits += 1
            return None

    monkeypatch.setattr("app.api.endpoints.batches.settings", SimpleNamespace(export_temp_root=tmp_path / "_exports"))

    session = _FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        await download_batch_outputs(
            109,
            background_tasks=BackgroundTasks(),
            session=session,
        )

    assert exc_info.value.status_code == 404
    assert batch.export_status == ExportStatus.FAILED
    assert session.commits == 2
