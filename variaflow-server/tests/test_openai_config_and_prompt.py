from __future__ import annotations

import importlib
from types import SimpleNamespace

import app.core.config as config_module
from app.core.config import _normalize_openai_image_edit_url
from app.core.config import _normalize_openai_image_generation_url
from app.core.prompt_lexicon import CAMERA_TERMS, LIGHTING_TERMS, QUALITY_TERMS, RENDER_TERMS
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
        subject_features="3D chibi cartoon monkey, large brown eyes, fluffy light brown fur",
        style_features="polished 3D blind-box render, glossy toy material",
        background_features="soft warm indoor studio gradient background",
    )

    assert payload["intent"] == "POSE_VARIATION"
    assert snapshot["intent"] == "POSE_VARIATION"
    assert snapshot["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert snapshot["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert snapshot["background_features"] == "soft warm indoor studio gradient background"
    assert payload["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert payload["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert payload["background_features"] == "soft warm indoor studio gradient background"
    assert payload["provider_hint"] == "openai_image_generation"
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

def test_default_aliyun_imageedit_strength_is_high_enough_for_pose_variation() -> None:
    assert config_module.settings.aliyun_imageedit_strength == 0.85
