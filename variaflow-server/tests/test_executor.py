from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import select

from app.gateways import ai_provider
from app.models.enums import ProviderRoute, TaskStatus
from app.models.tasks import GenerationAttempt, GenerationTask
from app.services.executor import process_generation_task
from app.services.executor import _resolve_provider_hint_for_route
from app.services.scheduler import fetch_and_lock_next_generation_task


def _build_http_status_error(status_code: int, url: str, message: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url, json={"mock": True})
    response = httpx.Response(status_code=status_code, request=request, json={"error": message})
    return httpx.HTTPStatusError(message, request=request, response=response)


def _build_deterministic_test_image_bytes() -> bytes:
    from io import BytesIO

    image = Image.new("RGB", (1536, 1536), color=(28, 78, 138))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=0)
    return buffer.getvalue()


def test_resolve_provider_hint_for_real_human_pose_variation_uses_openai_edit() -> None:
    assert _resolve_provider_hint_for_route("POSE_VARIATION", "real_human_model") == "openai_image_edit"
    assert _resolve_provider_hint_for_route("POSE_VARIATION", "toy_standing") == "openai_image_generation"


@pytest.mark.asyncio
async def test_happy_path(monkeypatch: pytest.MonkeyPatch, mock_batch_data: dict[str, object]) -> None:
    session_factory = mock_batch_data["session_factory"]

    async def _always_success(
        payload_json: dict,
        provider_route: ProviderRoute = ProviderRoute.PRIMARY,
        source_image_bytes: bytes | None = None,
    ) -> tuple[bytes, dict]:
        del payload_json, source_image_bytes
        return _build_deterministic_test_image_bytes(), {
            "provider_code": "pytest_mock_openai_image_edit",
            "provider_route": provider_route.value,
            "request_url": f"mock://{provider_route.value}",
            "http_status": 200,
            "content_type": "image/png",
            "mock": True,
        }

    monkeypatch.setattr(ai_provider, "call_ai_provider", _always_success)
    monkeypatch.setattr("app.services.executor.call_ai_provider", _always_success)

    async def _fake_analyze_image_intent(*, image_bytes: bytes, source_image_name: str):
        del image_bytes, source_image_name
        from app.services.vision_router import VisionRouteDecision

        return VisionRouteDecision(
            intent="SCENE_EDIT",
            reason="pytest_happy_path",
            raw_text='{"intent":"SCENE_EDIT"}',
            subject_type="product_only",
            sku_category="apparel_flat",
            suggested_scene="clean_fit_minimal",
            suggested_scene_recipe="clean_fit_minimal",
            dynamic_spatial_anchor="Placed naturally on a clean surface with realistic fabric volume and grounded folds.",
            dynamic_lighting_needs="Use soft commercial daylight with clean shadows and visible textile texture.",
            primary_sku_description="white hoodie",
            secondary_props="",
            dynamic_props=[],
            camera_perspective="top-down",
        )

    def _fake_prepare_scene_edit_source_image(
        image_path,
        temp_root,
        *,
        sku_category,
        subject_type,
        suggested_scene,
        target_size,
    ):
        assert sku_category == "apparel_flat"
        assert subject_type == "product_only"
        assert suggested_scene == "clean_fit_minimal"
        assert target_size == "1024x1024"
        source_path = Path(image_path)
        generated_path = Path(temp_root) / "happy_path_source.png"
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        generated_path.write_bytes(source_path.read_bytes())
        from app.utils.image_processor import PreparedSceneEditImage

        return PreparedSceneEditImage(
            path=generated_path,
            background_removed=False,
            canvas_padded=True,
            anchor="center",
            canvas_size=(1024, 1024),
            subject_bbox=(128, 160, 896, 864),
            scale_ratio=0.65,
        )

    monkeypatch.setattr("app.services.executor.analyze_image_intent", _fake_analyze_image_intent)
    monkeypatch.setattr("app.services.executor.prepare_scene_edit_source_image", _fake_prepare_scene_edit_source_image)

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
        source_image_bytes: bytes | None = None,
    ) -> tuple[bytes, dict]:
        del payload_json, source_image_bytes
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

    async def _always_fail(
        payload_json: dict,
        provider_route: ProviderRoute = ProviderRoute.PRIMARY,
        source_image_bytes: bytes | None = None,
    ) -> tuple[bytes, dict]:
        del payload_json, provider_route, source_image_bytes
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


@pytest.mark.asyncio
async def test_scene_edit_uses_transparent_preprocessing_for_openai_edit(
    monkeypatch: pytest.MonkeyPatch,
    mock_batch_data: dict[str, object],
) -> None:
    session_factory = mock_batch_data["session_factory"]
    captured_payloads: list[dict] = []
    generated_path_holder: dict[str, Path] = {}

    async def _always_success(
        payload_json: dict,
        provider_route: ProviderRoute = ProviderRoute.PRIMARY,
        source_image_bytes: bytes | None = None,
    ) -> tuple[bytes, dict]:
        assert provider_route == ProviderRoute.PRIMARY
        assert source_image_bytes is not None
        captured_payloads.append(dict(payload_json))
        adapter = ai_provider.MockAIAdapter(provider_route)
        result = await adapter.generate(client=None, payload_json={})
        return result.image_bytes, result.meta

    async def _fake_analyze_image_intent(*, image_bytes: bytes, source_image_name: str):
        del image_bytes, source_image_name
        from app.services.vision_router import VisionRouteDecision

        return VisionRouteDecision(
            intent="SCENE_EDIT",
            reason="standard_product",
            raw_text='{"intent":"SCENE_EDIT"}',
            subject_type="product_only",
            sku_category="apparel_flat",
            suggested_scene="cozy_winter_morning",
            suggested_scene_recipe="cozy_winter_morning",
            dynamic_spatial_anchor="Laid naturally on a soft textile surface with realistic hoodie volume and grounded folds.",
            dynamic_lighting_needs="Use cozy warm editorial lighting with soft window highlights and gentle fabric shadow transitions.",
            primary_sku_description="white oversized hoodie",
            secondary_props="beige scarf, coffee mug",
            dynamic_props=["soft knit textile accent", "warm ceramic accent"],
            camera_perspective="top-down",
        )

    def _fake_prepare_scene_edit_source_image(
        image_path,
        temp_root,
        *,
        sku_category,
        subject_type,
        suggested_scene,
        target_size,
    ):
        assert sku_category == "apparel_flat"
        assert subject_type == "product_only"
        assert suggested_scene == "cozy_winter_morning"
        assert target_size == "1024x1024"
        source_path = Path(image_path)
        generated_path = Path(temp_root) / "converted.png"
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        generated_path.write_bytes(source_path.read_bytes())
        generated_path_holder["path"] = generated_path
        from app.utils.image_processor import PreparedSceneEditImage

        return PreparedSceneEditImage(
            path=generated_path,
            background_removed=True,
            canvas_padded=True,
            anchor="bottom_center",
            canvas_size=(1024, 1024),
            subject_bbox=(210, 430, 814, 940),
            scale_ratio=0.62,
        )

    monkeypatch.setattr(ai_provider, "call_ai_provider", _always_success)
    monkeypatch.setattr("app.services.executor.call_ai_provider", _always_success)
    monkeypatch.setattr("app.services.executor.analyze_image_intent", _fake_analyze_image_intent)
    monkeypatch.setattr("app.services.executor.prepare_scene_edit_source_image", _fake_prepare_scene_edit_source_image)

    async with session_factory() as session:
        locked = await fetch_and_lock_next_generation_task(
            session,
            lease_owner="pytest-scene-edit-preprocess",
            batch_id=int(mock_batch_data["batch_id"]),
        )
    assert locked is not None

    await process_generation_task(locked.id, session_factory)

    assert captured_payloads
    assert captured_payloads[0]["provider_hint"] == "openai_image_edit"
    assert captured_payloads[0]["source_image_name"] == "converted.png"
    assert captured_payloads[0]["subject_type"] == "product_only"
    assert captured_payloads[0]["suggested_scene_recipe"] == "cozy_winter_morning"
    assert captured_payloads[0]["dynamic_spatial_anchor"] == "Laid naturally on a soft textile surface with realistic hoodie volume and grounded folds."
    assert captured_payloads[0]["dynamic_lighting_needs"] == "Use cozy warm editorial lighting with soft window highlights and gentle fabric shadow transitions."
    assert captured_payloads[0]["primary_sku_description"] == "white oversized hoodie"
    assert captured_payloads[0]["secondary_props"] == "beige scarf, coffee mug"
    assert captured_payloads[0]["dynamic_props"] == ["soft knit textile accent", "warm ceramic accent"]
    assert captured_payloads[0]["camera_perspective"] == "top-down"
    assert captured_payloads[0]["source_image_preprocessed"] is True
    assert captured_payloads[0]["source_image_background_removed"] is True
    assert captured_payloads[0]["source_image_canvas_padded"] is True
    assert captured_payloads[0]["source_image_anchor"] == "bottom_center"
    assert captured_payloads[0]["source_image_canvas_size"] == [1024, 1024]
    assert captured_payloads[0]["source_image_subject_bbox"] == [210, 430, 814, 940]
    assert captured_payloads[0]["source_image_scale_ratio"] == 0.62
    assert "path" in generated_path_holder
    assert not generated_path_holder["path"].exists()


@pytest.mark.asyncio
async def test_scene_edit_real_human_model_passes_background_mask_to_openai_edit(
    monkeypatch: pytest.MonkeyPatch,
    mock_batch_data: dict[str, object],
) -> None:
    session_factory = mock_batch_data["session_factory"]
    captured_payloads: list[dict] = []
    generated_paths: dict[str, Path] = {}

    async def _always_success(
        payload_json: dict,
        provider_route: ProviderRoute = ProviderRoute.PRIMARY,
        source_image_bytes: bytes | None = None,
    ) -> tuple[bytes, dict]:
        assert provider_route == ProviderRoute.PRIMARY
        assert source_image_bytes is not None
        captured_payloads.append(dict(payload_json))
        adapter = ai_provider.MockAIAdapter(provider_route)
        result = await adapter.generate(client=None, payload_json={})
        return result.image_bytes, result.meta

    async def _fake_analyze_image_intent(*, image_bytes: bytes, source_image_name: str):
        del image_bytes, source_image_name
        from app.services.vision_router import VisionRouteDecision

        return VisionRouteDecision(
            intent="SCENE_EDIT",
            reason="real_human_model_scene_swap",
            raw_text='{"intent":"SCENE_EDIT"}',
            subject_type="human_model",
            sku_category="real_human_model",
            suggested_scene="french_street_vibe",
            suggested_scene_recipe="french_street_vibe",
            dynamic_spatial_anchor="Keep the real model naturally grounded in the frame with intact body continuity and realistic stance.",
            dynamic_lighting_needs="Use premium editorial daylight with realistic skin tone rendering and clean garment detail.",
            primary_sku_description="structured cream trench coat",
            secondary_props="oversized sunglasses, leather shoulder bag",
            dynamic_props=["linen editorial card"],
            camera_perspective="eye-level",
        )

    def _fake_prepare_scene_edit_source_image(
        image_path,
        temp_root,
        *,
        sku_category,
        subject_type,
        suggested_scene,
        target_size,
    ):
        assert sku_category == "real_human_model"
        assert subject_type == "human_model"
        assert suggested_scene == "french_street_vibe"
        source_path = Path(image_path)
        generated_source_path = Path(temp_root) / "human_source.png"
        generated_mask_path = Path(temp_root) / "human_mask.png"
        generated_source_path.parent.mkdir(parents=True, exist_ok=True)
        generated_source_path.write_bytes(source_path.read_bytes())
        generated_mask_path.write_bytes(source_path.read_bytes())
        generated_paths["source"] = generated_source_path
        generated_paths["mask"] = generated_mask_path
        from app.utils.image_processor import PreparedSceneEditImage

        return PreparedSceneEditImage(
            path=generated_source_path,
            background_removed=False,
            canvas_padded=False,
            anchor="background_mask_lock_subject",
            canvas_size=(1024, 1024),
            subject_bbox=(0, 0, 1024, 1024),
            scale_ratio=1.0,
            mask_path=generated_mask_path,
            mask_generated=True,
        )

    monkeypatch.setattr(ai_provider, "call_ai_provider", _always_success)
    monkeypatch.setattr("app.services.executor.call_ai_provider", _always_success)
    monkeypatch.setattr("app.services.executor.analyze_image_intent", _fake_analyze_image_intent)
    monkeypatch.setattr("app.services.executor.prepare_scene_edit_source_image", _fake_prepare_scene_edit_source_image)

    async with session_factory() as session:
        locked = await fetch_and_lock_next_generation_task(
            session,
            lease_owner="pytest-scene-edit-human-mask",
            batch_id=int(mock_batch_data["batch_id"]),
        )
    assert locked is not None

    await process_generation_task(locked.id, session_factory)

    assert captured_payloads
    assert captured_payloads[0]["provider_hint"] == "openai_image_edit"
    assert captured_payloads[0]["source_image_mask_generated"] is True
    assert captured_payloads[0]["source_image_canvas_padded"] is False
    assert captured_payloads[0]["source_image_mask_name"] == "human_mask.png"
    assert captured_payloads[0]["dynamic_props"] == ["linen editorial card"]
    assert captured_payloads[0]["camera_perspective"] == "eye-level"
    assert isinstance(captured_payloads[0]["mask_image_bytes"], bytes)
    assert captured_payloads[0]["mask_image_name"] == "human_mask.png"
    assert "source" in generated_paths
    assert "mask" in generated_paths
    assert not generated_paths["source"].exists()
    assert not generated_paths["mask"].exists()
