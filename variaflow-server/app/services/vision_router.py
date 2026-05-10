from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import base64
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INTENT_SCENE_EDIT = "SCENE_EDIT"
INTENT_POSE_VARIATION = "POSE_VARIATION"
SUPPORTED_INTENTS = {INTENT_SCENE_EDIT, INTENT_POSE_VARIATION}

VISION_SYSTEM_PROMPT = (
    "你是一个专业的电商视觉特征分析系统。"
    "请分析用户提供的图片主体，并严格按照以下规则进行二分类。"
    "规则1 [SCENE_EDIT]：如果图片主体是独立的无生命商品，或者必须保持物理形态绝对不变的标品，请判定为 SCENE_EDIT。"
    "规则2 [POSE_VARIATION]：如果图片主体是卡通IP、人物模特，或者明显期望改变姿势、表情、服装的生命体，请判定为 POSE_VARIATION。"
    "你必须只输出合法 JSON，不要输出 markdown，不要输出解释。"
    '输出格式示例：{"intent":"SCENE_EDIT","reason":"主体为标准商品，需要保持外形稳定"}'
)

JSON_OBJECT_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)


@dataclass(slots=True)
class VisionRouteDecision:
    intent: str
    reason: str
    raw_text: str
    provider: str = "vision_router"
    model: str = settings.vision_model
    used_fallback: bool = False


def _default_intent() -> str:
    value = settings.vision_default_intent.strip().upper()
    return value if value in SUPPORTED_INTENTS else INTENT_SCENE_EDIT


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 10:
        return value
    return f"{value[:6]}...{value[-4:]}"


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    for match in JSON_OBJECT_PATTERN.finditer(raw_text):
        candidate = match.group(0).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("vision router response does not contain a valid JSON object")


def _normalize_intent(value: Any) -> str:
    intent = str(value or "").strip().upper()
    if intent in SUPPORTED_INTENTS:
        return intent
    return _default_intent()


def _image_to_data_url(image_bytes: bytes, source_image_name: str) -> str:
    suffix = Path(source_image_name).suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _build_payload(image_data_url: str) -> dict[str, Any]:
    return {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请判断该图片应该走 SCENE_EDIT 还是 POSE_VARIATION，并仅返回 JSON。",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                        },
                    },
                ],
            },
        ],
        "temperature": 0,
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("vision router response missing choices")

    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    fragments.append(text_value)
            elif isinstance(item, str):
                fragments.append(item)
        combined = "\n".join(fragment for fragment in fragments if fragment.strip())
        if combined.strip():
            return combined
    raise ValueError("vision router response missing message content")


async def analyze_image_intent(
    *,
    image_bytes: bytes,
    source_image_name: str,
) -> VisionRouteDecision:
    if not settings.vision_router_enabled:
        return VisionRouteDecision(
            intent=_default_intent(),
            reason="vision_router_disabled",
            raw_text="",
            used_fallback=True,
        )

    image_data_url = _image_to_data_url(image_bytes, source_image_name)
    payload = _build_payload(image_data_url)
    debug_payload = {
        "model": payload["model"],
        "message_types": ["system", "user_text", "user_image_url"],
        "image_data_url_length": len(image_data_url),
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"

    try:
        timeout = httpx.Timeout(settings.vision_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            if settings.provider_debug_log:
                logger.info(
                    "Vision router request debug url=%s model=%s auth=%s payload=%s",
                    settings.vision_api_url,
                    settings.vision_model,
                    _mask_secret(settings.vision_api_key),
                    json.dumps(debug_payload, ensure_ascii=False),
                )
            response = await client.post(
                settings.vision_api_url,
                headers=headers,
                json=payload,
            )
            if settings.provider_debug_log and response.is_error:
                logger.warning(
                    "Vision router error status=%s body=%s",
                    response.status_code,
                    response.text[:2000],
                )
            response.raise_for_status()
            response_json = response.json()
    except Exception as exc:
        logger.warning("Vision router failed, fallback to %s: %s", _default_intent(), exc)
        return VisionRouteDecision(
            intent=_default_intent(),
            reason=f"vision_router_error:{exc}",
            raw_text="",
            used_fallback=True,
        )

    try:
        raw_text = _extract_response_text(response_json)
        parsed = _extract_json_object(raw_text)
        intent = _normalize_intent(parsed.get("intent"))
        reason = str(parsed.get("reason") or "").strip() or "classified_by_model"
        return VisionRouteDecision(
            intent=intent,
            reason=reason,
            raw_text=raw_text,
            used_fallback=False,
        )
    except Exception as exc:
        logger.warning("Vision router parse failed, fallback to %s: %s", _default_intent(), exc)
        return VisionRouteDecision(
            intent=_default_intent(),
            reason=f"vision_router_parse_error:{exc}",
            raw_text="",
            used_fallback=True,
        )
