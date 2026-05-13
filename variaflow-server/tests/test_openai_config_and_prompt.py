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
        suggested_scene_recipe="natural_skincare_luxury",
        dynamic_spatial_anchor="Standing upright on a solid stone surface with crisp contact shadow directly beneath the base.",
        dynamic_lighting_needs="Use bright reflective skincare lighting with clean highlights and controlled glass reflections.",
        primary_sku_description="glass skincare bottle",
        secondary_props="folded towel, glass dropper",
        dynamic_props=["glass accent", "folded spa textile"],
    )

    assert payload["provider_hint"] == "openai_image_edit"
    assert payload["sku_category"] == "bottle_standing"
    assert payload["suggested_scene"] == "natural_skincare_luxury"
    assert payload["suggested_scene_recipe"] == "natural_skincare_luxury"
    assert payload["dynamic_spatial_anchor"] == "Standing upright on a solid stone surface with crisp contact shadow directly beneath the base."
    assert payload["dynamic_lighting_needs"] == "Use bright reflective skincare lighting with clean highlights and controlled glass reflections."
    assert payload["primary_sku_description"] == "glass skincare bottle"
    assert payload["secondary_props"] == "folded towel, glass dropper"
    assert payload["dynamic_props"] == ["glass accent", "folded spa textile"]
    assert snapshot["sku_category"] == "bottle_standing"
    assert snapshot["suggested_scene"] == "natural_skincare_luxury"
    assert snapshot["suggested_scene_recipe"] == "natural_skincare_luxury"
    assert snapshot["dynamic_spatial_anchor"] == "Standing upright on a solid stone surface with crisp contact shadow directly beneath the base."
    assert snapshot["dynamic_lighting_needs"] == "Use bright reflective skincare lighting with clean highlights and controlled glass reflections."
    assert snapshot["primary_sku_description"] == "glass skincare bottle"
    assert snapshot["secondary_props"] == "folded towel, glass dropper"
    assert snapshot["dynamic_props"] == ["glass accent", "folded spa textile"]
    assert "SPATIAL GROUNDING:" in payload["prompt"]
    assert "LIGHTING & MATERIAL:" in payload["prompt"]
    assert "ENVIRONMENT & VIBE:" in payload["prompt"]
    assert "CRITICAL IDENTITY LOCK:" in payload["prompt"]
    assert "Aesthetically integrate the following complementary props into the scene: glass accent, folded spa textile." in payload["prompt"]
    assert "Standing upright on a solid stone surface with crisp contact shadow directly beneath the base." in payload["prompt"]
    assert "Use bright reflective skincare lighting with clean highlights and controlled glass reflections." in payload["prompt"]
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
        suggested_scene_recipe="soft_girly_lifestyle",
        dynamic_spatial_anchor="",
        dynamic_lighting_needs="",
        primary_sku_description="open pastel eyeshadow palette",
        secondary_props="makeup brush, mirror",
    )

    assert payload["sku_category"] == "beauty_palette_open"
    assert snapshot["sku_category"] == "beauty_palette_open"
    assert "Placed naturally in a believable real-world position with clear surface contact and realistic grounding." in payload["prompt"]
    assert "Use realistic commercial product lighting that preserves material texture, natural shadow structure, and clean subject separation." in payload["prompt"]
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
    assert payload["dynamic_props"]


def test_scene_recipes_do_not_hardcode_old_props() -> None:
    banned_terms = {"sunglasses", "watch", "coffee", "leaves", "book", "books"}
    for recipe_text in SCENE_RECIPES.values():
        lowered = recipe_text.lower()
        for term in banned_terms:
            assert term not in lowered


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
        suggested_scene_recipe="soft_girly_lifestyle",
        primary_sku_description="blind-box monkey mascot figure",
        secondary_props="yellow jacket, gingerbread prop",
        subject_features="3D chibi cartoon monkey, large brown eyes, fluffy light brown fur",
        style_features="polished 3D blind-box render, glossy toy material",
        background_features="soft warm indoor studio gradient background",
    )

    assert payload["intent"] == "POSE_VARIATION"
    assert snapshot["intent"] == "POSE_VARIATION"
    assert snapshot["sku_category"] == "3d_toy"
    assert snapshot["suggested_scene_recipe"] == "soft_girly_lifestyle"
    assert snapshot["primary_sku_description"] == "blind-box monkey mascot figure"
    assert snapshot["secondary_props"] == "yellow jacket, gingerbread prop"
    assert snapshot["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert snapshot["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert snapshot["background_features"] == "soft warm indoor studio gradient background"
    assert payload["subject_features"] == "3D chibi cartoon monkey, large brown eyes, fluffy light brown fur"
    assert payload["style_features"] == "polished 3D blind-box render, glossy toy material"
    assert payload["background_features"] == "soft warm indoor studio gradient background"
    assert payload["provider_hint"] == "openai_image_generation"
    assert payload["sku_category"] == "3d_toy"
    assert payload["suggested_scene"] == ""
    assert payload["suggested_scene_recipe"] == "soft_girly_lifestyle"
    assert snapshot["suggested_scene"] == ""
    assert payload["suggested_scene_prompt"] == ""
    assert "CRITICAL IDENTITY LOCK: You MUST preserve the exact design, texture, and color of the primary subject: [blind-box monkey mascot figure]." in payload["prompt"]
    assert "The secondary accessories like [yellow jacket, gingerbread prop] are OPTIONAL and can be removed or altered naturally." in payload["prompt"]
    assert f"SCENE EMOTION RECIPE: [{SCENE_RECIPES['soft_girly_lifestyle']}]." in payload["prompt"]
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
        suggested_scene_recipe="french_street_vibe",
        primary_sku_description="structured cream trench coat",
        secondary_props="oversized sunglasses, leather shoulder bag",
        subject_features="young female fashion model, oval face, shoulder-length dark hair, slim body proportions",
        style_features="premium editorial fashion photography, natural human skin tones, elegant softbox lighting",
        background_features="chic outdoor Parisian cafe atmosphere with soft city blur",
    )

    assert payload["provider_hint"] == "openai_image_edit"
    assert snapshot["sku_category"] == "real_human_model"
    assert snapshot["primary_sku_description"] == "structured cream trench coat"
    assert snapshot["secondary_props"] == "oversized sunglasses, leather shoulder bag"
    assert "Use the provided real human model image as the direct visual reference." in payload["prompt"]
    assert "Do not replace the person with a different model or mannequin." in payload["prompt"]
    assert f"SCENE EMOTION RECIPE: [{SCENE_RECIPES['french_street_vibe']}]." in payload["prompt"]


def test_build_provider_payload_for_food_scene_forces_warm_recipe() -> None:
    batch = SimpleNamespace(batch_code="batch-004")
    source_task = SimpleNamespace(
        source_name="S0004_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0004_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=4,
        source_hash="food123",
    )
    generation_task = SimpleNamespace(
        id=104,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="food_packaged_standing",
        suggested_scene="clean_fit_minimal",
        suggested_scene_recipe="clean_fit_minimal",
        dynamic_spatial_anchor="Standing upright on a bakery counter with believable grounded package weight and crisp contact shadow.",
        dynamic_lighting_needs="Use warm appetizing morning backlight with soft highlights that make the packaging and food feel fresh.",
        primary_sku_description="fresh bakery gift box",
        secondary_props="linen napkin, wooden tray",
    )

    assert payload["suggested_scene"] == "gourmet_morning_bakery"
    assert payload["suggested_scene_recipe"] == "gourmet_morning_bakery"
    assert snapshot["suggested_scene"] == "gourmet_morning_bakery"
    assert snapshot["suggested_scene_recipe"] == "gourmet_morning_bakery"
    assert payload["suggested_scene_prompt"].startswith(SCENE_RECIPES["gourmet_morning_bakery"])
    assert SCENE_RECIPES["gourmet_morning_bakery"] in payload["prompt"]
    assert "Use warm appetizing morning backlight with soft highlights that make the packaging and food feel fresh." in payload["prompt"]
    assert payload["dynamic_props"]


def test_build_provider_payload_scene_edit_uses_dynamic_fallback_when_prompt_is_too_short() -> None:
    batch = SimpleNamespace(batch_code="batch-005")
    source_task = SimpleNamespace(
        source_name="S0005_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0005_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=5,
        source_hash="fallback-dyn-001",
    )
    generation_task = SimpleNamespace(
        id=105,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="shoes_resting",
        suggested_scene="clean_fit_minimal",
        suggested_scene_recipe="clean_fit_minimal",
        dynamic_spatial_anchor="upright",
        dynamic_lighting_needs="soft light",
        primary_sku_description="black ankle boots",
        secondary_props="none",
    )

    assert snapshot["dynamic_spatial_anchor"] == "upright"
    assert snapshot["dynamic_lighting_needs"] == "soft light"
    assert "Placed firmly on the ground at realistic 1:1 scale with strong contact shadows and no oversized environment distortion." in payload["prompt"]
    assert "Use clean commercial side lighting that preserves material texture, scale realism, and strong grounded shadow shape." in payload["prompt"]


def test_build_provider_payload_injects_shoe_perspective_lock_and_camera_perspective() -> None:
    batch = SimpleNamespace(batch_code="batch-006")
    source_task = SimpleNamespace(
        source_name="S0006_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0006_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=6,
        source_hash="shoe-perspective-001",
    )
    generation_task = SimpleNamespace(
        id=106,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="shoes_resting",
        suggested_scene="clean_fit_minimal",
        suggested_scene_recipe="clean_fit_minimal",
        dynamic_spatial_anchor="Keep the shoes resting naturally on the floor with firm sole contact and realistic weight distribution.",
        dynamic_lighting_needs="Use premium directional side lighting with crisp texture separation and realistic grounded shadows.",
        primary_sku_description="matte black ankle boots",
        secondary_props="none",
        camera_perspective="45-degree angle",
    )

    assert payload["camera_perspective"] == "45-degree angle"
    assert snapshot["camera_perspective"] == "45-degree angle"
    assert "Shot from a consistent 45-degree angle perspective." in payload["prompt"]
    assert "CRITICAL: Match the camera angle and perspective of the original shoe exactly." in payload["prompt"]
    assert "The background must be generated from the same 45-degree angle perspective as the original product." in payload["prompt"]
    assert "Ensure the ground plane matches the reference shoe orientation. No geometric warping. Realistic pressure shadows at the contact points." in payload["prompt"]


def test_build_provider_payload_injects_human_model_strict_lock_without_extra_props() -> None:
    batch = SimpleNamespace(batch_code="batch-007")
    source_task = SimpleNamespace(
        source_name="S0007_src_mock.jpg",
        source_ext="jpg",
        source_path="E:/tmp/S0007_src_mock.jpg",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=7,
        source_hash="human-lock-001",
    )
    generation_task = SimpleNamespace(
        id=107,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="real_human_model",
        subject_type="human_model",
        suggested_scene="french_street_vibe",
        suggested_scene_recipe="french_street_vibe",
        dynamic_spatial_anchor="Keep the real model naturally grounded in the frame with intact body continuity and realistic stance.",
        dynamic_lighting_needs="Use premium editorial daylight with realistic skin tone rendering and clean garment detail.",
        primary_sku_description="structured cream trench coat",
        secondary_props="oversized sunglasses, leather shoulder bag",
        dynamic_props=["linen editorial card", "stone tabletop detail"],
        camera_perspective="eye-level",
    )

    assert payload["camera_perspective"] == "eye-level"
    assert snapshot["camera_perspective"] == "eye-level"
    assert "Shot from a consistent eye-level perspective." in payload["prompt"]
    assert "ABSOLUTELY DO NOT add any new accessories, jewelry, bags, or props to the human model." in payload["prompt"]
    assert "NEGATIVE PROMPT LOCK: ABSOLUTELY DO NOT add any new accessories, jewelry, bags, or props to the human model." in payload["prompt"]
    assert "Strictly NO new accessories, NO extra jewelry, NO bags, NO watches, NO hats. Preserve every pixel of the person and clothing." in payload["prompt"]
    assert "Match the original reference camera perspective: eye-level." in payload["prompt"]
    assert "Aesthetically integrate the following complementary props into the scene:" not in payload["prompt"]


def test_build_provider_payload_injects_leaning_prefix_and_domain_props() -> None:
    batch = SimpleNamespace(batch_code="batch-008")
    source_task = SimpleNamespace(
        source_name="S0008_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0008_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=8,
        source_hash="leaning-001",
    )
    generation_task = SimpleNamespace(
        id=108,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="apparel_leaning",
        suggested_scene="old_money_vintage",
        suggested_scene_recipe="old_money_vintage",
        dynamic_spatial_anchor="Leaning naturally against a wall corner with soft fabric weight and realistic grounded shadows.",
        dynamic_lighting_needs="Use warm directional daylight with subtle wall shadow falloff and refined knit texture detail.",
        primary_sku_description="heavy vintage green knit sweater",
        secondary_props="none",
        dynamic_props=[],
        camera_perspective="30-to-45-degree angle",
    )

    assert payload["camera_perspective"] == "30-to-45-degree angle"
    assert snapshot["camera_perspective"] == "30-to-45-degree angle"
    assert "Shot from a consistent 30-to-45-degree angle perspective." in payload["prompt"]
    assert "A composition featuring a clean 90-degree intersection of a vertical minimalist wall and a horizontal solid floor. The apparel is leaning naturally against the wall." in payload["prompt"]
    assert "Must generate a clear 90-degree intersection between a vertical wall and a horizontal floor." in payload["prompt"]
    assert "Aesthetically integrate the following complementary props into the scene:" in payload["prompt"]


def test_build_provider_payload_filters_watch_for_non_business_sku() -> None:
    batch = SimpleNamespace(batch_code="batch-009")
    source_task = SimpleNamespace(
        source_name="S0009_src_mock.png",
        source_ext="png",
        source_path="E:/tmp/S0009_src_mock.png",
        identity_profile_json={"identity_lock": "Keep the same subject identity."},
        batch=batch,
        id=9,
        source_hash="props-filter-001",
    )
    generation_task = SimpleNamespace(
        id=109,
        variant_index=1,
        variant_axis=SimpleNamespace(value="scene"),
    )

    payload, snapshot = build_provider_payload(
        source_task,
        generation_task,
        intent="SCENE_EDIT",
        sku_category="bag_standing",
        suggested_scene="french_street_vibe",
        suggested_scene_recipe="french_street_vibe",
        dynamic_spatial_anchor="Keep the straw bag standing upright with natural handle drape and realistic base support.",
        dynamic_lighting_needs="Use soft Parisian daylight with clean highlight control across the woven texture.",
        primary_sku_description="straw bag",
        secondary_props="none",
        dynamic_props=["watch", "straw hat", "sunscreen"],
        camera_perspective="15-degree top-down",
    )

    assert payload["dynamic_props"] == ["straw hat", "sunscreen"]
    assert snapshot["dynamic_props"] == ["straw hat", "sunscreen"]
    assert "watch" not in payload["prompt"].lower()


def test_default_aliyun_imageedit_strength_is_high_enough_for_pose_variation() -> None:
    assert config_module.settings.aliyun_imageedit_strength == 0.85
