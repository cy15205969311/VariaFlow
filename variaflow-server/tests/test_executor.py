from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.gateways import ai_provider
from app.models.enums import ProviderRoute, TaskStatus
from app.models.tasks import GenerationAttempt, GenerationTask
from app.services.executor import process_generation_task
from app.services.scheduler import fetch_and_lock_next_generation_task


def _build_http_status_error(status_code: int, url: str, message: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url, json={"mock": True})
    response = httpx.Response(status_code=status_code, request=request, json={"error": message})
    return httpx.HTTPStatusError(message, request=request, response=response)


@pytest.mark.asyncio
async def test_happy_path(monkeypatch: pytest.MonkeyPatch, mock_batch_data: dict[str, object]) -> None:
    session_factory = mock_batch_data["session_factory"]

    async def _always_success(payload_json: dict, provider_route: ProviderRoute = ProviderRoute.PRIMARY) -> tuple[bytes, dict]:
        del payload_json
        adapter = ai_provider.MockAIAdapter(provider_route)
        result = await adapter.generate(client=None, payload_json={})
        return result.image_bytes, result.meta

    monkeypatch.setattr(ai_provider, "call_ai_provider", _always_success)

    async with session_factory() as session:
        locked = await fetch_and_lock_next_generation_task(
            session,
            lease_owner="pytest-happy-path",
            batch_id=int(mock_batch_data["batch_id"]),
        )
    assert locked is not None
    task_id = locked.id
    await process_generation_task(task_id, session_factory)

    async with session_factory() as session:
        generation_task = (
            await session.execute(select(GenerationTask).where(GenerationTask.id == task_id))
        ).scalar_one()
        attempt = (
            await session.execute(
                select(GenerationAttempt)
                .where(GenerationAttempt.generation_task_id == task_id)
                .order_by(GenerationAttempt.attempt_no.desc())
            )
        ).scalars().first()

    assert generation_task.status == TaskStatus.SUCCESS
    assert generation_task.output_path
    assert Path(generation_task.output_path).exists()
    assert attempt is not None
    assert attempt.latency_ms is not None
    assert attempt.provider_route == ProviderRoute.PRIMARY
    assert not list(Path(mock_batch_data["tmp_root"]).glob("*.part"))


@pytest.mark.asyncio
async def test_fallback_path(monkeypatch: pytest.MonkeyPatch, mock_batch_data: dict[str, object]) -> None:
    session_factory = mock_batch_data["session_factory"]

    async def _primary_timeout_then_fallback_success(
        payload_json: dict,
        provider_route: ProviderRoute = ProviderRoute.PRIMARY,
    ) -> tuple[bytes, dict]:
        del payload_json
        if provider_route == ProviderRoute.PRIMARY:
            adapter = ai_provider.MockAIAdapter(ProviderRoute.FALLBACK)
            result = await adapter.generate(client=None, payload_json={})
            result.meta["switch_reason"] = "primary_timeout"
            result.meta["provider_route"] = ProviderRoute.FALLBACK.value
            return result.image_bytes, result.meta
        adapter = ai_provider.MockAIAdapter(ProviderRoute.FALLBACK)
        result = await adapter.generate(client=None, payload_json={})
        return result.image_bytes, result.meta

    monkeypatch.setattr(ai_provider, "call_ai_provider", _primary_timeout_then_fallback_success)

    async with session_factory() as session:
        locked = await fetch_and_lock_next_generation_task(
            session,
            lease_owner="pytest-fallback-path",
            batch_id=int(mock_batch_data["batch_id"]),
        )
    assert locked is not None
    task_id = locked.id
    await process_generation_task(task_id, session_factory)

    async with session_factory() as session:
        generation_task = (
            await session.execute(select(GenerationTask).where(GenerationTask.id == task_id))
        ).scalar_one()
        attempt = (
            await session.execute(
                select(GenerationAttempt)
                .where(GenerationAttempt.generation_task_id == task_id)
                .order_by(GenerationAttempt.attempt_no.desc())
            )
        ).scalars().first()

    assert generation_task.status == TaskStatus.FALLBACK_SUCCESS
    assert generation_task.output_path
    assert Path(generation_task.output_path).exists()
    assert attempt is not None
    assert attempt.provider_route == ProviderRoute.FALLBACK
    assert attempt.switch_reason == "primary_timeout"


@pytest.mark.asyncio
async def test_dead_letter_path(monkeypatch: pytest.MonkeyPatch, mock_batch_data: dict[str, object]) -> None:
    session_factory = mock_batch_data["session_factory"]

    async def _always_fail(payload_json: dict, provider_route: ProviderRoute = ProviderRoute.PRIMARY) -> tuple[bytes, dict]:
        del payload_json, provider_route
        raise _build_http_status_error(502, "mock://dead-letter", "all providers failed")

    monkeypatch.setattr(ai_provider, "call_ai_provider", _always_fail)

    task_id = int(mock_batch_data["generation_task_ids"][0])

    for _ in range(3):
        async with session_factory() as session:
            locked = await fetch_and_lock_next_generation_task(
                session,
                lease_owner="pytest-dead-letter",
                batch_id=int(mock_batch_data["batch_id"]),
            )
        assert locked is not None
        await process_generation_task(task_id, session_factory)
        async with session_factory() as session:
            task = (
                await session.execute(select(GenerationTask).where(GenerationTask.id == task_id))
            ).scalar_one()
            if task.status == TaskStatus.FAILED:
                break
            task.next_run_at = None
            await session.commit()

    async with session_factory() as session:
        generation_task = (
            await session.execute(select(GenerationTask).where(GenerationTask.id == task_id))
        ).scalar_one()
        attempts = (
            await session.execute(
                select(GenerationAttempt)
                .where(GenerationAttempt.generation_task_id == task_id)
                .order_by(GenerationAttempt.attempt_no.asc())
            )
        ).scalars().all()

    assert generation_task.status == TaskStatus.FAILED
    assert generation_task.attempt_count >= generation_task.max_attempts
    assert attempts
    assert attempts[-1].error_code is not None
