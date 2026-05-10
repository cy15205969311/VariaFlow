from __future__ import annotations

from app.services.vision_router import (
    INTENT_POSE_VARIATION,
    INTENT_SCENE_EDIT,
    _extract_json_object,
    _extract_response_text,
    _normalize_feature_text,
    _normalize_intent,
    _normalize_subject_features,
)


def test_extract_json_object_from_markdown_wrapped_response() -> None:
    raw_text = """```json
{"intent":"POSE_VARIATION","reason":"cartoon_ip","subject_features":"3D chibi monkey, big brown eyes","style_features":"3D blind-box render","background_features":"soft warm studio background"}
```"""
    parsed = _extract_json_object(raw_text)
    assert parsed["intent"] == "POSE_VARIATION"
    assert parsed["reason"] == "cartoon_ip"
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
                            "text": '{"intent":"SCENE_EDIT","reason":"standard_product","subject_features":"","style_features":"","background_features":""}',
                        }
                    ]
                }
            }
        ]
    }
    assert _extract_response_text(payload) == '{"intent":"SCENE_EDIT","reason":"standard_product","subject_features":"","style_features":"","background_features":""}'


def test_normalize_subject_features_only_keeps_pose_variation_values() -> None:
    assert _normalize_subject_features(" fluffy monkey  with big eyes ", INTENT_POSE_VARIATION) == "fluffy monkey with big eyes"
    assert _normalize_subject_features("steel bottle", INTENT_SCENE_EDIT) == ""


def test_normalize_feature_text_only_keeps_pose_variation_values() -> None:
    assert _normalize_feature_text(" glossy 3d toy render ", INTENT_POSE_VARIATION) == "glossy 3d toy render"
    assert _normalize_feature_text("white seamless background", INTENT_SCENE_EDIT) == ""
