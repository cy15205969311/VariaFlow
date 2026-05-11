from __future__ import annotations

import importlib
from types import SimpleNamespace

import app.core.config as config_module
from app.core.config import _normalize_openai_image_edit_url
from app.core.config import _normalize_openai_image_generation_url
from app.core.prompt_lexicon import (
    CAMERA_TERMS,
    ENVIRONMENT_TEMPLATES,
    LIGHTING_TERMS,
    NEGATIVE_SPACE_COMPOSITION_RULE,
    QUALITY_TERMS,
    RENDER_TERMS,
    SCENE_RECIPES,
    SPATIAL_GROUNDING_PROMPTS,
)
from app.services.prompt_builder import build_provider_payload


def test_normalize_openai_image_edit_url_accepts_base_host() -> None:
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com") == "https://api2.apiaqi.com/v1/images/edits"
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com/v1") == "https://api2.apiaqi.com/v1/images/edits"
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com/v1/images/edits") == "https://api2.apiaqi.com/v1/images/edits"


def test_normalize_openai_image_generation_url_accepts_edit_url() -> None:
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com") == "https://api2.apiaqi.com/v1/images/generations"
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com/v1") == "https://api2.apiaqi.com/v1/images/generations"
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com/v1/images/edits") == "https://api2.apiaqi.com/v1/images/generations"


def test_settings_selects_mimo_vision_stack(monkeypatch) -> None:
    monkeypatch.setenv("VARIAFLOW_VISION_PROVIDER", "mimo")
    monkeypatch.setenv("VARIAFLOW_MIMO_VISION_API_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    monkeypatch.setenv("VARIAFLOW_MIMO_VISION_MODEL", "mimo-v2-omni")
    monkeypatch.setenv("VARIAFLOW_MIMO_VISION_API_KEY", "mimo-key")
    reloaded = importlib.reload(config_module)
    assert reloaded.settings.vision_provider == "mimo"
    assert reloaded.settings.vision_api_url == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert reloaded.settings.vision_model == "mimo-v2-omni"
    assert reloaded.settings.vision_api_key == "mimo-key"
    monkeypatch.undo()
    importlib.reload(config_module)


def test_settings_selects_deepseek_vision_stack(monkeypatch) -> None:
    monkeypatch.setenv("VARIAFLOW_VISION_PROVIDER", "deepseek")
    monkeypatch.setenv("VARIAFLOW_DEEPSEEK_VISION_API_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("VARIAFLOW_DEEPSEEK_VISION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("VARIAFLOW_DEEPSEEK_VISION_API_KEY", "deepseek-key")
    reloaded = importlib.reload(config_module)
    assert reloaded.settings.vision_provider == "deepseek"
    assert reloaded.settings.vision_api_url == "https://api.deepseek.com/v1/chat/completions"
    assert reloaded.settings.vision_model == "deepseek-v4-pro"
    assert reloaded.settings.vision_api_key == "deepseek-key"
    monkeypatch.undo()
    importlib.reload(config_module)


def test_build_provider_payload_preserves_source_extension() -> None:
    batch = SimpleNamespace(batch_code="batch-001")
    source_task = SimpleNamespace(
        source_name="S0001_src_mock.webp",
        source_ext="webp",
        source_path="E:/tmp/S0001_src_mock.webp",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=1,
        source_hash="abc123",
    )
    generation_task = SimpleNamespace(
        id=101,
        variant_index=1,
        variant_axis=SimpleNamespace(value="mixed"),
    )

    payload, _ = build_provider_payload(source_task, generation_task)

    assert payload["source_image_name"] == "S0001_src_mock.webp"


def test_build_provider_payload_injects_grounding_prompt_for_scene_edit() -> None:
    batch = SimpleNamespace(batch_code="batch-001a")
    source_task = SimpleNamespace(
        source_name="S0001_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0001_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=11,
        source_hash="grounding001",
    )
    generation_task = SimpleNamespace(
        id=111,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        intent_reason="standard_product",
        sku_category="bottle_standing",
        suggested_scene="natural_skincare_luxury",
    )

    assert payload["provider_hint"] == "openai_image_edit"
    assert payload["sku_category"] == "bottle_standing"
    assert payload["suggested_scene"] == "natural_skincare_luxury"
    assert snapshot["sku_category"] == "bottle_standing"
    assert snapshot["suggested_scene"] == "natural_skincare_luxury"
    assert "CRITICAL GROUNDING:" in payload["prompt"]
    assert "VIRAL SCENE RECIPE:" in payload["prompt"]
    assert "ENVIRONMENT & BACKGROUND:" in payload["prompt"]
    assert SPATIAL_GROUNDING_PROMPTS["bottle_standing"] in payload["prompt"]
    assert SCENE_RECIPES["natural_skincare_luxury"] in payload["prompt"]
    assert payload["suggested_scene_prompt"].startswith(SCENE_RECIPES["natural_skincare_luxury"])
    assert NEGATIVE_SPACE_COMPOSITION_RULE in payload["prompt"]


def test_build_provider_payload_supports_expanded_sku_grounding_dictionary() -> None:
    batch = SimpleNamespace(batch_code="batch-001c")
    source_task = SimpleNamespace(
        source_name="S0001_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0001_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=13,
        source_hash="expanded001",
    )
    generation_task = SimpleNamespace(
        id=113,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="beauty_palette_open",
        suggested_scene="soft_girly_lifestyle",
    )

    assert payload["sku_category"] == "beauty_palette_open"
    assert snapshot["sku_category"] == "beauty_palette_open"
    assert SPATIAL_GROUNDING_PROMPTS["beauty_palette_open"] in payload["prompt"]
    assert payload["provider_hint"] == "openai_image_edit"


def test_build_provider_payload_uses_scene_fallback_template_when_suggested_scene_missing() -> None:
    batch = SimpleNamespace(batch_code="batch-001b")
    source_task = SimpleNamespace(
        source_name="S0001_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0001_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=12,
        source_hash="fallback001",
    )
    generation_task = SimpleNamespace(
        id=112,
        variant_index=2,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="apparel_hanging",
        suggested_scene="",
    )

    assert payload["provider_hint"] == "openai_image_edit"
    assert payload["sku_category"] == "apparel_hanging"
    assert payload["suggested_scene"] in SCENE_RECIPES
    assert snapshot["suggested_scene"] in SCENE_RECIPES
    assert payload["suggested_scene_prompt"].startswith(SCENE_RECIPES[payload["suggested_scene"]])
    assert any(template in payload["suggested_scene_prompt"] for template in ENVIRONMENT_TEMPLATES["apparel_hanging"])


def test_build_provider_payload_switches_prompt_for_pose_variation() -> None:
    batch = SimpleNamespace(batch_code="batch-002")
    source_task = SimpleNamespace(
        source_name="S0002_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0002_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=2,
        source_hash="def456",
    )
    generation_task = SimpleNamespace(
        id=102,
        variant_index=1,
        variant_axis=SimpleNamespace(value="mixed"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="POSE_VARIATION",
        intent_reason="cartoon_character",
        sku_category="3d_toy",
        subject_features="3D chibi cartoon monkey, large brown eyes, fluffy light brown fur",
        style_features="polished 3D blind-box render, glossy toy material",
        background_features="soft warm indoor studio gradient background",
    )

    assert payload["intent"] == "POSE_VARIATION"
    assert snapshot["intent"] == "POSE_VARIATION"
    assert snapshot["sku_category"] == "3d_toy"
    assert snapshot["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert snapshot["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert snapshot["background_features"] == "soft warm indoor studio gradient background"
    assert payload["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert payload["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert payload["background_features"] == "soft warm indoor studio gradient background"
    assert payload["provider_hint"] == "openai_image_generation"
    assert payload["sku_category"] == "3d_toy"
    assert payload["suggested_scene"] == ""
    assert snapshot["suggested_scene"] == ""
    assert payload["suggested_scene_prompt"] == ""
    assert "Create a masterpiece, ultra-high definition image of the exact same IP character in a new pose." in payload["prompt"]
    assert "Must strictly adhere to this exact artistic style and lighting" in payload["prompt"]
    assert "The environment and background must be" in payload["prompt"]
    assert "The main character must exactly match this physical description and identity" in payload["prompt"]
    assert "ACTION & OUTFIT MODIFICATION:" in payload["prompt"]
    assert "Ensure the result feels like the exact same IP in a new pose." in payload["prompt"]
    assert "COMMERCIAL PHOTOGRAPHY REQUIREMENTS:" in payload["prompt"]
    assert "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur" in payload["prompt"]
    assert "polished 3D blind-box render, glossy toy material" in payload["prompt"]
    assert "soft warm indoor studio gradient background" in payload["prompt"]
    for term in [QUALITY_TERMS[0], LIGHTING_TERMS[0], CAMERA_TERMS[0], RENDER_TERMS[0]]:
        assert term in payload["prompt"]


def test_build_provider_payload_routes_real_human_pose_variation_to_openai_edit() -> None:
    batch = SimpleNamespace(batch_code="batch-003")
    source_task = SimpleNamespace(
        source_name="S0003_src_mock.jpg",
        source_ext="jpg",
        source_path="E:/tmp/S0003_src_mock.jpg",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=3,
        source_hash="ghi789",
    )
    generation_task = SimpleNamespace(
        id=103,
        variant_index=1,
        variant_axis=SimpleNamespace(value="mixed"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="POSE_VARIATION",
        intent_reason="real_model",
        sku_category="real_human_model",
        subject_features="young female fashion model, oval face, shoulder-length dark hair, slim body proportions",
        style_features="premium editorial fashion photography, natural human skin tones, elegant softbox lighting",
        background_features="chic outdoor Parisian cafe atmosphere with soft city blur",
    )

    assert payload["provider_hint"] == "openai_image_edit"
    assert snapshot["sku_category"] == "real_human_model"
    assert "Use the provided real human model image as the direct visual reference." in payload["prompt"]
    assert "Do not replace the person with a different model or mannequin." in payload["prompt"]


def test_default_aliyun_imageedit_strength_is_high_enough_for_pose_variation() -> None:
    assert config_module.settings.aliyun_imageedit_strength == 0.85
