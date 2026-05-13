from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.endpoints.batches import download_batch_outputs, get_batch, upload_batch_zip
from app.models.enums import BatchStatus, ExportStatus, UploadMode
from app.models.tasks import BatchJob
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
        return UploadBatchResult(batch=batch, generation_task_ids=[101, 102, 103])

    fake_settings = SimpleNamespace(async_execution_mode="celery")
    monkeypatch.setattr("app.api.endpoints.batches.process_upload", _fake_process_upload)
    monkeypatch.setattr("app.api.endpoints.batches.settings", fake_settings)
    monkeypatch.setattr("app.api.endpoints.batches.enqueue_generation_task", lambda task_id: queued_ids.append(task_id))

    upload_file = SimpleNamespace(filename="demo.zip", content_type="application/zip")

    response = await upload_batch_zip(file=upload_file, session=None)

    assert response.id == 12
    assert response.progress_percent == 0.0
    assert response.download_ready is False
    assert response.processing_generation_count == 6
    assert queued_ids == [101, 102, 103]


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
async def test_download_batch_outputs_returns_file_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "outputs"
    output_file = output_root / "S0001" / "variant_1.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"png")

    batch = BatchJob(
        id=99,
        batch_code="batch_export",
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
        output_root_path=str(output_root),
        export_status=ExportStatus.NOT_REQUESTED,
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

        async def commit(self):
            return None

    fake_settings = SimpleNamespace(export_temp_root=tmp_path / "_exports")
    monkeypatch.setattr("app.api.endpoints.batches.settings", fake_settings)

    response = await download_batch_outputs(
        99,
        background_tasks=BackgroundTasks(),
        session=_FakeSession(),
    )

    assert response.media_type == "application/zip"
    assert response.filename == "batch_export_outputs.zip"
    assert Path(response.path).exists()
