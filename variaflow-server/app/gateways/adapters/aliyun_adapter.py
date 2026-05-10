from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx

try:
    from dashscope import ImageSynthesis
except ImportError:  # pragma: no cover
    ImageSynthesis = None

from app.core.config import settings
from app.gateways.shared import ProviderResult
from app.gateways.shared import download_image_from_url
from app.models.enums import ProviderRoute

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 250


@dataclass(slots=True)
class AliyunAdapter:
    provider_code: str = "aliyun_wanx"
    provider_route: ProviderRoute = ProviderRoute.PRIMARY
    request_url: str = settings.aliyun_wanx_url
    api_key: str = settings.aliyun_wanx_api_key
    model_name: str = settings.aliyun_wanx_model

    def _request_url_for_model(self, model_name: str) -> str:
        if "imageedit" in model_name.lower():
            return settings.aliyun_wanx_imageedit_url
        return self.request_url

    def _truncate_error(self, value: str) -> str:
        text = str(value)
        if len(text) <= MAX_ERROR_MESSAGE_LENGTH:
            return text
        return text[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."

    def _mask_secret(self, value: str | None) -> str:
        if not value:
            return "<empty>"
        if len(value) <= 10:
            return value
        return f"{value[:6]}...{value[-4:]}"

    def _detect_mime_type(self, source_image_name: str) -> str:
        suffix = Path(source_image_name).suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(suffix, "image/png")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-DashScope-Async": "enable",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _task_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _to_data_url(self, source_image_bytes: bytes, source_image_name: str) -> str:
        mime_type = self._detect_mime_type(source_image_name)
        encoded = base64.b64encode(source_image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _normalize_size(self, value: Any) -> str:
        raw_size = str(value or "1024x1024").strip().lower()
        return raw_size.replace("x", "*")

    def _build_payload(self, payload_json: dict[str, Any], source_image_bytes: bytes) -> dict[str, Any]:
        source_image_name = str(payload_json.get("source_image_name") or "source.png")
        image_data_url = self._to_data_url(source_image_bytes, source_image_name)
        prompt = str(payload_json.get("prompt") or "").strip()

        return {
            "model": str(payload_json.get("aliyun_model") or self.model_name),
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": image_data_url},
                            {"text": prompt},
                        ],
                    }
                ]
            },
            "parameters": {
                "size": self._normalize_size(payload_json.get("size")),
                "n": 1,
                "watermark": False,
            },
        }

    def _build_debug_snapshot(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = json.loads(json.dumps(request_payload))
        messages = snapshot.get("input", {}).get("messages") or []
        for message in messages:
            content = message.get("content") or []
            for item in content:
                if not isinstance(item, dict):
                    continue
                image_value = item.get("image")
                if isinstance(image_value, str) and image_value.startswith("data:"):
                    item["image"] = f"<data_url length={len(image_value)}>"
                text_value = item.get("text")
                if isinstance(text_value, str) and len(text_value) > 300:
                    item["text"] = text_value[:300] + "..."
        return snapshot

    def _build_sdk_debug_snapshot(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload_json.get("prompt") or "").strip()
        if len(prompt) > 300:
            prompt = prompt[:300] + "..."
        return {
            "model": str(payload_json.get("aliyun_model") or self.model_name),
            "prompt": prompt,
            "size": self._normalize_size(payload_json.get("size")),
            "source_image_path": str(payload_json.get("source_image_path") or ""),
            "mode": "dashscope_sdk_imageedit",
        }

    def _extract_image_url(self, payload: dict[str, Any]) -> str | None:
        output = payload.get("output", {})
        choices = output.get("choices") or []
        for choice in choices:
            message = choice.get("message") or {}
            content = message.get("content") or []
            for item in content:
                if not isinstance(item, dict):
                    continue
                image_value = item.get("image")
                if isinstance(image_value, str) and image_value:
                    return image_value
        return None

    def _raise_http_error_with_body(self, response: httpx.Response, label: str) -> None:
        body = self._truncate_error(response.text[:2000] or "<empty>")
        raise httpx.HTTPStatusError(
            f"{label} failed with status {response.status_code}: {body}",
            request=response.request,
            response=response,
        )

    def _should_use_sdk(self, model_name: str, provider_hint: str = "") -> bool:
        provider_hint = str(provider_hint or "").strip().lower()
        if provider_hint == "aliyun_wanx":
            return settings.aliyun_use_sdk_for_imageedit
        return settings.aliyun_use_sdk_for_imageedit and "imageedit" in model_name.lower()

    def _serialize_sdk_response(self, response: Any, image_url: str | None) -> dict[str, Any]:
        output = getattr(response, "output", None)
        return {
            "status_code": int(getattr(response, "status_code", 0) or 0),
            "request_id": getattr(response, "request_id", None),
            "code": getattr(response, "code", None),
            "message": getattr(response, "message", None),
            "task_id": getattr(output, "task_id", None) if output is not None else None,
            "task_status": getattr(output, "task_status", None) if output is not None else None,
            "image_url": image_url,
        }

    async def _generate_with_sdk(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
    ) -> ProviderResult:
        if ImageSynthesis is None:
            raise RuntimeError("dashscope is not installed")

        model_name = str(payload_json.get("aliyun_model") or self.model_name)
        request_url = self._request_url_for_model(model_name)
        prompt = str(payload_json.get("prompt") or "").strip()
        source_image_path = str(payload_json.get("source_image_path") or "").strip()
        if not source_image_path:
            raise ValueError("Aliyun SDK image edit request requires source_image_path")

        sdk_kwargs = {
            "model": model_name,
            "prompt": prompt,
            "function": str(payload_json.get("aliyun_function") or settings.aliyun_imageedit_function),
            "base_image_url": source_image_path,
            "size": self._normalize_size(payload_json.get("size")),
            "n": 1,
            "strength": settings.aliyun_imageedit_strength,
            "api_key": self.api_key,
        }

        if settings.provider_debug_log:
            logger.info(
                "Aliyun SDK image edit request debug auth=%s payload=%s",
                self._mask_secret(self.api_key),
                json.dumps(self._build_sdk_debug_snapshot(payload_json), ensure_ascii=False),
            )

        response = await asyncio.to_thread(ImageSynthesis.call, **sdk_kwargs)
        if getattr(response, "status_code", None) != HTTPStatus.OK:
            request = httpx.Request("POST", request_url, json=self._build_sdk_debug_snapshot(payload_json))
            response_payload = {
                "code": getattr(response, "code", None),
                "message": getattr(response, "message", None),
                "request_id": getattr(response, "request_id", None),
            }
            synthetic_response = httpx.Response(
                status_code=int(getattr(response, "status_code", 500) or 500),
                request=request,
                json=response_payload,
            )
            raise httpx.HTTPStatusError(
                self._truncate_error(
                    f"Aliyun SDK request failed: {response_payload.get('code')} - {response_payload.get('message')}"
                ),
                request=request,
                response=synthetic_response,
            )

        output = getattr(response, "output", None)
        task_status = str(getattr(output, "task_status", "") or "").upper()
        results = list(getattr(output, "results", []) or [])
        image_url = getattr(results[0], "url", None) if results else None
        if task_status and task_status != "SUCCEEDED":
            raise ValueError(self._truncate_error(f"Aliyun SDK task failed: {task_status}"))
        if not image_url:
            raise ValueError("Aliyun SDK response missing output image url")

        image_bytes = await download_image_from_url(client, image_url)
        return ProviderResult(
            image_bytes=image_bytes,
            meta={
                "http_status": int(getattr(response, "status_code", 200) or 200),
                "content_type": "image/*",
                "provider_code": self.provider_code,
                "provider_route": self.provider_route.value,
                "request_url": request_url,
                "task_id": getattr(output, "task_id", None),
                "response_json": self._serialize_sdk_response(response, image_url),
                "sdk_mode": True,
            },
        )

    async def generate_image_variation(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
        source_image_bytes: bytes,
    ) -> ProviderResult:
        request_payload = self._build_payload(payload_json, source_image_bytes)
        request_url = self._request_url_for_model(str(request_payload["model"]))
        if settings.provider_debug_log:
            logger.info(
                "Aliyun request debug url=%s model=%s auth=%s payload=%s",
                request_url,
                request_payload["model"],
                self._mask_secret(self.api_key),
                json.dumps(self._build_debug_snapshot(request_payload), ensure_ascii=False),
            )

        response = await client.post(
            request_url,
            headers=self._headers(),
            json=request_payload,
        )
        if settings.provider_debug_log and response.is_error:
            logger.warning(
                "Aliyun task creation error status=%s body=%s",
                response.status_code,
                response.text[:2000],
            )
        if response.is_error:
            self._raise_http_error_with_body(response, "Aliyun task creation")

        try:
            created_payload = response.json()
        except ValueError as exc:
            raise ValueError(self._truncate_error(f"Aliyun task creation returned non-JSON: {exc}")) from exc

        task_id = created_payload.get("output", {}).get("task_id") or created_payload.get("task_id")
        if not task_id:
            raise ValueError(self._truncate_error(f"Aliyun response missing task_id: {created_payload}"))

        result_payload = await self._poll_task_result(client=client, task_id=str(task_id))
        image_url = self._extract_image_url(result_payload)
        if not image_url:
            raise ValueError(self._truncate_error(f"Aliyun result missing image url: {result_payload}"))

        image_bytes = await download_image_from_url(client, image_url)
        return ProviderResult(
            image_bytes=image_bytes,
            meta={
                "http_status": response.status_code,
                "content_type": "image/*",
                "provider_code": self.provider_code,
                "provider_route": self.provider_route.value,
                "request_url": request_url,
                "task_id": str(task_id),
                "response_json": result_payload,
            },
        )

    async def _poll_task_result(
        self,
        *,
        client: httpx.AsyncClient,
        task_id: str,
        max_polls: int = 30,
        interval_seconds: float = 2.0,
    ) -> dict[str, Any]:
        task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        last_payload: dict[str, Any] = {}

        for _ in range(max_polls):
            response = await client.get(task_url, headers=self._task_headers())
            if settings.provider_debug_log and response.is_error:
                logger.warning(
                    "Aliyun task polling error status=%s body=%s",
                    response.status_code,
                    response.text[:2000],
                )
            if response.is_error:
                self._raise_http_error_with_body(response, "Aliyun task polling")

            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError(self._truncate_error(f"Aliyun task polling returned non-JSON: {exc}")) from exc

            last_payload = payload
            output = payload.get("output", {})
            task_status = str(output.get("task_status") or payload.get("task_status") or "").upper()

            if task_status == "SUCCEEDED":
                return payload
            if task_status in {"FAILED", "CANCELED", "CANCELLED"}:
                message = payload.get("message") or payload.get("code") or payload
                raise ValueError(self._truncate_error(f"Aliyun task failed: {message}"))

            await asyncio.sleep(interval_seconds)

        raise TimeoutError(self._truncate_error(f"Aliyun task polling timed out: {last_payload}"))

    async def generate(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
        source_image_bytes: bytes | None = None,
    ) -> ProviderResult:
        provider_hint = str(payload_json.get("provider_hint") or "").strip().lower()
        model_name = str(payload_json.get("aliyun_model") or self.model_name)
        if self._should_use_sdk(model_name, provider_hint):
            return await self._generate_with_sdk(client=client, payload_json=payload_json)
        if not source_image_bytes:
            raise ValueError("Aliyun request missing source_image_bytes")
        return await self.generate_image_variation(
            client=client,
            payload_json=payload_json,
            source_image_bytes=source_image_bytes,
        )
