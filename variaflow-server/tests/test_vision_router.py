from __future__ import annotations

from app.services.vision_router import (
    INTENT_POSE_VARIATION,
    INTENT_SCENE_EDIT,
    _extract_json_object,
    _extract_response_text,
    _normalize_intent,
)


def test_extract_json_object_from_markdown_wrapped_response() -> None:
    raw_text = """```json
{"intent":"POSE_VARIATION","reason":"主体为卡通IP形象"}
```"""
    parsed = _extract_json_object(raw_text)
    assert parsed["intent"] == "POSE_VARIATION"
    assert parsed["reason"] == "主体为卡通IP形象"


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
                        {"type": "text", "text": '{"intent":"SCENE_EDIT","reason":"标准商品"}'}
                    ]
                }
            }
        ]
    }
    assert _extract_response_text(payload) == '{"intent":"SCENE_EDIT","reason":"标准商品"}'
