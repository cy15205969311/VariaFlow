from __future__ import annotations

from types import SimpleNamespace

from app.core.config import _normalize_openai_image_edit_url
from app.core.config import _normalize_openai_image_generation_url
from app.services.prompt_builder import build_provider_payload


def test_normalize_openai_image_edit_url_accepts_base_host() -> None:
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com") == "https://api2.apiaqi.com/v1/images/edits"
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com/v1") == "https://api2.apiaqi.com/v1/images/edits"
    assert _normalize_openai_image_edit_url("https://api2.apiaqi.com/v1/images/edits") == "https://api2.apiaqi.com/v1/images/edits"


def test_normalize_openai_image_generation_url_accepts_edit_url() -> None:
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com") == "https://api2.apiaqi.com/v1/images/generations"
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com/v1") == "https://api2.apiaqi.com/v1/images/generations"
    assert _normalize_openai_image_generation_url("https://api2.apiaqi.com/v1/images/edits") == "https://api2.apiaqi.com/v1/images/generations"


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
    )

    assert payload["intent"] == "POSE_VARIATION"
    assert snapshot["intent"] == "POSE_VARIATION"
    assert "You may change pose" in payload["prompt"]
