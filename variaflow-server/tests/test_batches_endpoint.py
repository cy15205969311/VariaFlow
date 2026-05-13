from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints.batches import upload_batch_zip


@pytest.mark.asyncio
async def test_upload_batch_zip_logs_and_reraises_http_exception(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    async def _fake_process_upload(file, session) -> None:
        del file, session
        raise HTTPException(status_code=400, detail="bad zip")

    monkeypatch.setattr("app.api.endpoints.batches.process_upload", _fake_process_upload)

    caplog.set_level(logging.ERROR)

    upload_file = SimpleNamespace(filename="broken.zip", content_type="application/zip")

    with pytest.raises(HTTPException) as exc_info:
        await upload_batch_zip(file=upload_file, session=None)

    assert exc_info.value.status_code == 400
    assert "ZIP解析或任务创建失败" in caplog.text
