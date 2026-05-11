from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.gateways.shared import ProviderResult, extract_image_bytes
from app.models.enums import ProviderRoute

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAIImageAdapter:
    provider_code: str = "openai_image_edit"
    provider_route: ProviderRoute = ProviderRoute.PRIMARY
    request_url: str = settings.openai_image_edit_url
    api_key: str = settings.openai_image_api_key
    model_name: str = settings.openai_image_model

    def _mask_secret(self, value: str | None) -> str:
        if not value:
            return "<empty>"
        if len(value) <= 10:
            return value
        return f"{value[:6]}...{value[-4:]}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _detect_mime_type(self, source_image_name: str) -> str:
        suffix = Path(source_image_name).suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")

    def _build_form_payload(
        self,
        payload_json: dict[str, Any],
        source_image_bytes: bytes,
    ) -> tuple[dict[str, str], dict[str, tuple[str, bytes, str]]]:
        prompt_text = str(payload_json.get("prompt", "") or "").strip()
        source_image_name = str(payload_json.get("source_image_name") or "source.png")
        mask_image_bytes = payload_json.get("mask_image_bytes")
        mask_image_name = str(payload_json.get("mask_image_name") or "mask.png")

        data_payload: dict[str, str] = {
            "model": str(payload_json.get("model") or self.model_name),
            "prompt": prompt_text,
            "size": str(payload_json.get("size") or "1024x1024"),
            "n": "1",
            "response_format": "b64_json",
        }

        files_payload = {
            "image": (
                source_image_name,
                source_image_bytes,
                self._detect_mime_type(source_image_name),
            )
        }
        if isinstance(mask_image_bytes, bytes) and mask_image_bytes:
            files_payload["mask"] = (
                mask_image_name,
                mask_image_bytes,
                self._detect_mime_type(mask_image_name),
            )
        return data_payload, files_payload

    def _build_debug_snapshot(
        self,
        data_payload: dict[str, str],
        files_payload: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = dict(data_payload)
        prompt = snapshot.get("prompt")
        if isinstance(prompt, str) and len(prompt) > 300:
            snapshot["prompt"] = prompt[:300] + "..."

        snapshot["files"] = {
            field_name: {
                "filename": file_info[0],
                "bytes": len(file_info[1]),
                "content_type": file_info[2],
            }
            for field_name, file_info in files_payload.items()
        }
        return snapshot

    async def generate(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
        source_image_bytes: bytes | None = None,
    ) -> ProviderResult:
        if not source_image_bytes:
            raise ValueError("OpenAI image edit request requires source_image_bytes")

        data_payload, files_payload = self._build_form_payload(payload_json, source_image_bytes)

        if settings.provider_debug_log:
            logger.info(
                "OpenAI image edit request debug url=%s mode=%s auth=%s payload=%s",
                self.request_url,
                "images_edits_multipart",
                self._mask_secret(self.api_key),
                json.dumps(
                    self._build_debug_snapshot(data_payload, files_payload),
                    ensure_ascii=False,
                ),
            )

        response = await client.post(
            self.request_url,
            headers=self._headers(),
            data=data_payload,
            files=files_payload,
        )

        if settings.provider_debug_log and response.is_error:
            logger.warning(
                "OpenAI image edit error status=%s body=%s",
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
            "request_mode": "images_edits_multipart",
            **extract_meta,
        }
        return ProviderResult(image_bytes=image_bytes, meta=meta)
