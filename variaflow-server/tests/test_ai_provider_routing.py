from __future__ import annotations

from app.core.config import settings
from app.gateways.adapters.openai_adapter import OpenAIImageAdapter
from app.gateways.adapters.openai_variation_adapter import OpenAIVariationAdapter
from app.gateways.ai_provider import _build_adapter
from app.models.enums import ProviderRoute


def test_build_adapter_routes_pose_variation_to_openai_generation_adapter() -> None:
    assert settings.use_mock_ai is False
    assert settings.image_provider == "openai"
    adapter = _build_adapter(ProviderRoute.PRIMARY, {"intent": "POSE_VARIATION"})
    assert isinstance(adapter, OpenAIVariationAdapter)


def test_build_adapter_routes_scene_edit_to_edit_adapter() -> None:
    assert settings.use_mock_ai is False
    assert settings.image_provider == "openai"
    adapter = _build_adapter(ProviderRoute.PRIMARY, {"intent": "SCENE_EDIT"})
    assert isinstance(adapter, OpenAIImageAdapter)


def test_build_adapter_respects_explicit_provider_hint() -> None:
    adapter = _build_adapter(ProviderRoute.PRIMARY, {"intent": "POSE_VARIATION", "provider_hint": "openai_image_generation"})
    assert isinstance(adapter, OpenAIVariationAdapter)


def test_pose_variation_payload_can_route_to_openai_generation_provider_hint() -> None:
    adapter = _build_adapter(
        ProviderRoute.PRIMARY,
        {"intent": "POSE_VARIATION", "provider_hint": "openai_image_generation"},
    )
    assert isinstance(adapter, OpenAIVariationAdapter)
