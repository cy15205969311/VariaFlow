from __future__ import annotations

from app.services.vision_router import (
    INTENT_POSE_VARIATION,
    INTENT_SCENE_EDIT,
    SUPPORTED_SKU_CATEGORIES,
    VISION_SYSTEM_PROMPT,
    _extract_json_object,
    _extract_response_text,
    _normalize_feature_text,
    _normalize_intent,
    _normalize_suggested_scene,
    _normalize_sku_category,
    _normalize_subject_features,
)


def test_extract_json_object_from_markdown_wrapped_response() -> None:
    raw_text = """```json
{"intent":"POSE_VARIATION","reason":"cartoon_ip","sku_category":"3d_toy","suggested_scene":"","subject_features":"3D chibi monkey, big brown eyes","style_features":"3D blind-box render","background_features":"soft warm studio background"}
```"""
    parsed = _extract_json_object(raw_text)
    assert parsed["intent"] == "POSE_VARIATION"
    assert parsed["reason"] == "cartoon_ip"
    assert parsed["sku_category"] == "3d_toy"
    assert parsed["subject_features"] == "3D chibi monkey, big brown eyes"
    assert parsed["style_features"] == "3D blind-box render"
    assert parsed["background_features"] == "soft warm studio background"


def test_normalize_intent_falls_back_to_scene_edit() -> None:
    assert _normalize_intent("SCENE_EDIT") == INTENT_SCENE_EDIT
    assert _normalize_intent("pose_variation") == INTENT_POSE_VARIATION
    assert _normalize_intent("UNKNOWN") == INTENT_SCENE_EDIT


def test_extract_response_text_supports_content_array() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"intent":"SCENE_EDIT","reason":"standard_product","sku_category":"bottle_standing","suggested_scene":"premium stone pedestal in a bright skincare studio","subject_features":"","style_features":"","background_features":""}',
                        }
                    ]
                }
            }
        ]
    }
    assert _extract_response_text(payload) == '{"intent":"SCENE_EDIT","reason":"standard_product","sku_category":"bottle_standing","suggested_scene":"premium stone pedestal in a bright skincare studio","subject_features":"","style_features":"","background_features":""}'


def test_normalize_subject_features_only_keeps_pose_variation_values() -> None:
    assert _normalize_subject_features(" fluffy monkey  with big eyes ", INTENT_POSE_VARIATION) == "fluffy monkey with big eyes"
    assert _normalize_subject_features("steel bottle", INTENT_SCENE_EDIT) == ""


def test_normalize_feature_text_only_keeps_pose_variation_values() -> None:
    assert _normalize_feature_text(" glossy 3d toy render ", INTENT_POSE_VARIATION) == "glossy 3d toy render"
    assert _normalize_feature_text("white seamless background", INTENT_SCENE_EDIT) == ""


def test_normalize_suggested_scene_only_keeps_scene_edit_values() -> None:
    assert _normalize_suggested_scene("  old_money_vintage  ", INTENT_SCENE_EDIT) == "old_money_vintage"
    assert _normalize_suggested_scene("warm indoor studio", INTENT_POSE_VARIATION) == ""


def test_normalize_sku_category_falls_back_to_other_flat() -> None:
    assert _normalize_sku_category("3d_toy") == "3d_toy"
    assert _normalize_sku_category("beauty_palette_open") == "beauty_palette_open"
    assert _normalize_sku_category("real_human_model") == "real_human_model"
    assert _normalize_sku_category("unknown") == "other_flat"


def test_vision_system_prompt_excludes_temporary_clothing_and_props() -> None:
    assert "Do not include clothing, accessories, props, held items, gesture, pose, camera angle, or temporary styling in subject_features" in VISION_SYSTEM_PROMPT
    assert "temporary clothing, props, or temporary accessories" in VISION_SYSTEM_PROMPT
    assert "suggested_scene" in VISION_SYSTEM_PROMPT
    assert "For SCENE_EDIT, suggested_scene must be exactly one of these recipe keys" in VISION_SYSTEM_PROMPT
    assert "old_money_vintage" in VISION_SYSTEM_PROMPT
    for category in SUPPORTED_SKU_CATEGORIES:
        assert category in VISION_SYSTEM_PROMPT
