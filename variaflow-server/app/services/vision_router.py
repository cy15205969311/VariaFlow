from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INTENT_SCENE_EDIT = "SCENE_EDIT"
INTENT_POSE_VARIATION = "POSE_VARIATION"
SUPPORTED_INTENTS = {INTENT_SCENE_EDIT, INTENT_POSE_VARIATION}

VISION_SYSTEM_PROMPT = (
    "You are an ecommerce visual routing system. "
    "Analyze the primary subject in the image and classify it into exactly one intent. "
    "Return only valid JSON with the keys intent, reason, and subject_features. "
    "Use SCENE_EDIT for inanimate products or standard merchandise whose physical shape must stay unchanged. "
    "Use POSE_VARIATION for cartoon IP, mascots, animals, dolls, characters, or people whose pose, expression, styling, or outfit may vary. "
    "For POSE_VARIATION, subject_features must be a detailed English description of stable identity traits only, "
    "including species, rendering style, face structure, fur or material texture, color palette, body proportions, and signature accessories. "
    "Do not mention the current pose, gesture, camera angle, background, or temporary clothing unless it is a permanent identity trait. "
    "For SCENE_EDIT, subject_features must be an empty string. "
    'Example: {"intent":"POSE_VARIATION","reason":"cartoon mascot character with editable pose and outfit","subject_features":"3D chibi cartoon monkey, large brown eyes, fluffy light brown fur, big round ears, oversized head-to-body ratio"}'
)

JSON_OBJECT_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)


@dataclass(slots=True)
class VisionRouteDecision:
    intent: str
    reason: str
    raw_text: str
    subject_features: str = ""
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


def _normalize_subject_features(value: Any, intent: str) -> str:
    if intent != INTENT_POSE_VARIATION:
        return ""
    return re.sub(r"\s+", " ", str(value or "")).strip()


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
                        "text": (
                            "Classify this image as SCENE_EDIT or POSE_VARIATION. "
                            "Return only JSON with intent, reason, and subject_features."
                        ),
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
            subject_features="",
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
            subject_features="",
            used_fallback=True,
        )

    try:
        raw_text = _extract_response_text(response_json)
        parsed = _extract_json_object(raw_text)
        intent = _normalize_intent(parsed.get("intent"))
        reason = str(parsed.get("reason") or "").strip() or "classified_by_model"
        subject_features = _normalize_subject_features(parsed.get("subject_features"), intent)
        return VisionRouteDecision(
            intent=intent,
            reason=reason,
            raw_text=raw_text,
            subject_features=subject_features,
            used_fallback=False,
        )
    except Exception as exc:
        logger.warning("Vision router parse failed, fallback to %s: %s", _default_intent(), exc)
        return VisionRouteDecision(
            intent=_default_intent(),
            reason=f"vision_router_parse_error:{exc}",
            raw_text="",
            subject_features="",
            used_fallback=True,
        )
