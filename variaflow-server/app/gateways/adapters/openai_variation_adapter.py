from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.gateways.shared import ProviderResult, extract_image_bytes
from app.models.enums import ProviderRoute

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAIVariationAdapter:
    provider_code: str = "openai_image_generation"
    provider_route: ProviderRoute = ProviderRoute.PRIMARY
    request_url: str = settings.openai_image_generation_url
    api_key: str = settings.openai_image_api_key
    model_name: str = settings.openai_image_model

    def _mask_secret(self, value: str | None) -> str:
        if not value:
            return "<empty>"
        if len(value) <= 10:
            return value
        return f"{value[:6]}...{value[-4:]}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_prompt(self, payload_json: dict[str, Any]) -> str:
        prompt_text = str(payload_json.get("prompt", "") or "").strip()
        source_hint = str(payload_json.get("source_image_name") or "reference image").strip()
        return (
            "Use the uploaded reference image as the sole identity and style reference. "
            f"Preserve the same core character/product identity represented by {source_hint}. "
            f"{prompt_text}"
        ).strip()

    def _build_json_payload(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": str(payload_json.get("model") or self.model_name),
            "prompt": self._build_prompt(payload_json),
            "size": str(payload_json.get("size") or "1024x1024"),
            "n": 1,
            "response_format": "b64_json",
        }

    def _build_debug_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(payload)
        prompt = snapshot.get("prompt")
        if isinstance(prompt, str) and len(prompt) > 300:
            snapshot["prompt"] = prompt[:300] + "..."
        return snapshot

    async def generate(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
        source_image_bytes: bytes | None = None,
    ) -> ProviderResult:
        del source_image_bytes
        request_payload = self._build_json_payload(payload_json)

        if settings.provider_debug_log:
            logger.info(
                "OpenAI image generation request debug url=%s mode=%s auth=%s payload=%s",
                self.request_url,
                "images_generations_json",
                self._mask_secret(self.api_key),
                json.dumps(self._build_debug_snapshot(request_payload), ensure_ascii=False),
            )

        response = await client.post(
            self.request_url,
            headers=self._headers(),
            json=request_payload,
        )

        if settings.provider_debug_log and response.is_error:
            logger.warning(
                "OpenAI image generation error status=%s body=%s",
                response.status_code,
                response.text[:2000],
            )

        response.raise_for_status()
        image_bytes, extract_meta = await extract_image_bytes(response, client)
        meta = {
            "provider_code": self.provider_code,
            "provider_route": self.provider_route.value,
            "request_url": self.request_url,
            "response_headers": dict(response.headers),
            "request_mode": "images_generations_json",
            **extract_meta,
        }
        return ProviderResult(image_bytes=image_bytes, meta=meta)
