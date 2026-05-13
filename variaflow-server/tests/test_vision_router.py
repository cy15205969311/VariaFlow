from __future__ import annotations

from app.services.vision_router import (
    INTENT_POSE_VARIATION,
    INTENT_SCENE_EDIT,
    SUPPORTED_SKU_CATEGORIES,
    SUPPORTED_SCENE_RECIPE_KEYS,
    VISION_SYSTEM_PROMPT,
    _extract_json_object,
    _extract_response_text,
    _normalize_feature_text,
    _normalize_intent,
    _normalize_dynamic_prompt_field,
    _normalize_scene_recipe_key,
    _normalize_suggested_scene,
    _normalize_subject_type,
    _normalize_sku_category,
    _normalize_subject_features,
    _normalize_camera_perspective,
)


def test_extract_json_object_from_markdown_wrapped_response() -> None:
    raw_text = """```json
{"intent":"POSE_VARIATION","reason":"cartoon_ip","subject_type":"product_only","sku_category":"3d_toy","suggested_scene":"","suggested_scene_recipe":"soft_girly_lifestyle","dynamic_spatial_prompt":"","dynamic_lighting_prompt":"","primary_sku_description":"3D monkey mascot figure","secondary_props":"yellow jacket, candy prop","dynamic_props":[],"camera_perspective":"","subject_features":"3D chibi monkey, big brown eyes","style_features":"3D blind-box render","background_features":"soft warm studio background"}
```"""
    parsed = _extract_json_object(raw_text)
    assert parsed["intent"] == "POSE_VARIATION"
    assert parsed["reason"] == "cartoon_ip"
    assert parsed["subject_type"] == "product_only"
    assert parsed["sku_category"] == "3d_toy"
    assert parsed["suggested_scene_recipe"] == "soft_girly_lifestyle"
    assert parsed["primary_sku_description"] == "3D monkey mascot figure"
    assert parsed["secondary_props"] == "yellow jacket, candy prop"
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
                            "text": '{"intent":"SCENE_EDIT","reason":"standard_product","subject_type":"product_only","sku_category":"bottle_standing","suggested_scene":"natural_skincare_luxury","suggested_scene_recipe":"natural_skincare_luxury","dynamic_spatial_prompt":"Standing upright on a solid stone surface with crisp contact shadow directly beneath the base.","dynamic_lighting_prompt":"Use bright reflective skincare lighting with clean highlights and controlled glass reflections.","primary_sku_description":"glass skincare bottle","secondary_props":"folded towel, glass dropper","dynamic_props":["glass accent","folded spa textile"],"camera_perspective":"eye-level","subject_features":"","style_features":"","background_features":""}',
                        }
                    ]
                }
            }
        ]
    }
    assert _extract_response_text(payload) == '{"intent":"SCENE_EDIT","reason":"standard_product","subject_type":"product_only","sku_category":"bottle_standing","suggested_scene":"natural_skincare_luxury","suggested_scene_recipe":"natural_skincare_luxury","dynamic_spatial_prompt":"Standing upright on a solid stone surface with crisp contact shadow directly beneath the base.","dynamic_lighting_prompt":"Use bright reflective skincare lighting with clean highlights and controlled glass reflections.","primary_sku_description":"glass skincare bottle","secondary_props":"folded towel, glass dropper","dynamic_props":["glass accent","folded spa textile"],"camera_perspective":"eye-level","subject_features":"","style_features":"","background_features":""}'


def test_normalize_subject_features_only_keeps_pose_variation_values() -> None:
    assert _normalize_subject_features(" fluffy monkey  with big eyes ", INTENT_POSE_VARIATION) == "fluffy monkey with big eyes"
    assert _normalize_subject_features("steel bottle", INTENT_SCENE_EDIT) == ""


def test_normalize_feature_text_only_keeps_pose_variation_values() -> None:
    assert _normalize_feature_text(" glossy 3d toy render ", INTENT_POSE_VARIATION) == "glossy 3d toy render"
    assert _normalize_feature_text("white seamless background", INTENT_SCENE_EDIT) == ""


def test_normalize_dynamic_prompt_field_only_keeps_scene_edit_values() -> None:
    assert _normalize_dynamic_prompt_field(" standing upright on a firm surface ", INTENT_SCENE_EDIT) == "standing upright on a firm surface"
    assert _normalize_dynamic_prompt_field("soft side light", INTENT_POSE_VARIATION) == ""


def test_normalize_camera_perspective_only_keeps_scene_edit_values() -> None:
    assert _normalize_camera_perspective(" 45-degree angle ", INTENT_SCENE_EDIT) == "45-degree angle"
    assert _normalize_camera_perspective("top-down", INTENT_POSE_VARIATION) == ""


def test_normalize_subject_type_falls_back_from_sku() -> None:
    assert _normalize_subject_type("human_model") == "human_model"
    assert _normalize_subject_type("product_only") == "product_only"
    assert _normalize_subject_type("", "real_human_model") == "human_model"
    assert _normalize_subject_type("", "other_flat") == "product_only"


def test_normalize_suggested_scene_only_keeps_scene_edit_values() -> None:
    assert _normalize_suggested_scene("  old_money_vintage  ", INTENT_SCENE_EDIT) == "old_money_vintage"
    assert _normalize_suggested_scene("warm indoor studio", INTENT_POSE_VARIATION) == ""


def test_normalize_scene_recipe_key_restricts_to_known_recipes() -> None:
    assert _normalize_scene_recipe_key(" gourmet_morning_bakery ") == "gourmet_morning_bakery"
    assert _normalize_scene_recipe_key("unknown_recipe") == ""


def test_normalize_sku_category_falls_back_to_other_flat() -> None:
    assert _normalize_sku_category("3d_toy") == "3d_toy"
    assert _normalize_sku_category("apparel_leaning") == "apparel_leaning"
    assert _normalize_sku_category("beauty_palette_open") == "beauty_palette_open"
    assert _normalize_sku_category("real_human_model") == "real_human_model"
    assert _normalize_sku_category("unknown") == "other_flat"


def test_vision_system_prompt_excludes_temporary_clothing_and_props() -> None:
    assert "Do not include clothing, accessories, props, held items, gesture, pose, camera angle, or temporary styling in subject_features" in VISION_SYSTEM_PROMPT
    assert "temporary clothing, props, or temporary accessories" in VISION_SYSTEM_PROMPT
    assert "subject_type must be exactly one of: human_model, product_only." in VISION_SYSTEM_PROMPT
    assert "dynamic_spatial_prompt" in VISION_SYSTEM_PROMPT
    assert "dynamic_lighting_prompt" in VISION_SYSTEM_PROMPT
    assert "suggested_scene" in VISION_SYSTEM_PROMPT
    assert "suggested_scene_recipe must be exactly one of these recipe keys" in VISION_SYSTEM_PROMPT
    assert "primary_sku_description" in VISION_SYSTEM_PROMPT
    assert "secondary_props" in VISION_SYSTEM_PROMPT
    assert "dynamic_props" in VISION_SYSTEM_PROMPT
    assert "camera_perspective" in VISION_SYSTEM_PROMPT
    assert "When analyzing a real_human_model image" in VISION_SYSTEM_PROMPT
    assert "CRITICAL RULE: If there is ANY human body part" in VISION_SYSTEM_PROMPT
    assert "Use apparel_leaning when the product is best merchandised leaning against a wall" in VISION_SYSTEM_PROMPT
    assert "prefer apparel_leaning over apparel_flat" in VISION_SYSTEM_PROMPT
    assert "For apparel_flat, prefer top-down. For apparel_hanging, prefer eye-level." in VISION_SYSTEM_PROMPT
    for category in SUPPORTED_SKU_CATEGORIES:
        assert category in VISION_SYSTEM_PROMPT
    for recipe_key in SUPPORTED_SCENE_RECIPE_KEYS:
        assert recipe_key in VISION_SYSTEM_PROMPT
