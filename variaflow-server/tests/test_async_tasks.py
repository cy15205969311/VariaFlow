from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import async_tasks


def _make_bound_task(hostname: str = "pytest-worker"):
    return async_tasks.generate_task_async.__wrapped__.__get__(
        SimpleNamespace(request=SimpleNamespace(hostname=hostname)),
        object,
    )


def test_generate_task_async_disposes_engine_when_task_not_claimable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispose_calls: list[str] = []
    worker_dispose_calls: list[str] = []

    async def _fake_claim_generation_task_by_id(*args, **kwargs):
        del args, kwargs
        return None

    async def _fake_dispose() -> None:
        dispose_calls.append("disposed")

    async def _fake_worker_dispose() -> None:
        worker_dispose_calls.append("disposed")

    def _fake_create_null_pool_session_factory():
        return SimpleNamespace(dispose=_fake_worker_dispose), async_tasks.AsyncSessionLocal

    monkeypatch.setattr(async_tasks, "claim_generation_task_by_id", _fake_claim_generation_task_by_id)
    monkeypatch.setattr(async_tasks, "engine", SimpleNamespace(dispose=_fake_dispose))
    monkeypatch.setattr(async_tasks, "create_null_pool_session_factory", _fake_create_null_pool_session_factory)

    bound_task = _make_bound_task()
    result = bound_task(123)

    assert result == {"task_id": 123, "dispatched": False, "reason": "not_claimable"}
    assert dispose_calls == ["disposed"]
    assert worker_dispose_calls == ["disposed"]


def test_generate_task_async_disposes_engine_when_processing_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispose_calls: list[str] = []
    worker_dispose_calls: list[str] = []

    async def _fake_claim_generation_task_by_id(*args, **kwargs):
        del args, kwargs
        return object()

    async def _fake_process_generation_task(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    async def _fake_dispose() -> None:
        dispose_calls.append("disposed")

    async def _fake_worker_dispose() -> None:
        worker_dispose_calls.append("disposed")

    def _fake_create_null_pool_session_factory():
        return SimpleNamespace(dispose=_fake_worker_dispose), async_tasks.AsyncSessionLocal

    monkeypatch.setattr(async_tasks, "claim_generation_task_by_id", _fake_claim_generation_task_by_id)
    monkeypatch.setattr(async_tasks, "process_generation_task", _fake_process_generation_task)
    monkeypatch.setattr(async_tasks, "engine", SimpleNamespace(dispose=_fake_dispose))
    monkeypatch.setattr(async_tasks, "create_null_pool_session_factory", _fake_create_null_pool_session_factory)

    bound_task = _make_bound_task()

    with pytest.raises(RuntimeError, match="boom"):
        bound_task(456)

    assert dispose_calls == ["disposed"]
    assert worker_dispose_calls == ["disposed"]
