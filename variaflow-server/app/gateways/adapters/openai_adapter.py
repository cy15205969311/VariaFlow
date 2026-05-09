from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.gateways.shared import ProviderResult
from app.gateways.shared import encode_local_image_to_data_url
from app.gateways.shared import extract_image_bytes
from app.models.enums import ProviderRoute


@dataclass(slots=True)
class OpenAIImageAdapter:
    """
    主链路图像适配器。

    兼容两种上游协议：
    - `/v1/images/generations`
    - `/v1/chat/completions`

    预期环境变量：
    - `VARIAFLOW_OPENAI_IMAGE_2_URL`
    - `VARIAFLOW_OPENAI_IMAGE_2_MODEL`
    - `VARIAFLOW_OPENAI_IMAGE_2_API_KEY`
    """

    provider_code: str = "openai_image_2"
    provider_route: ProviderRoute = ProviderRoute.PRIMARY
    request_url: str = settings.openai_image_2_url
    api_key: str = settings.openai_image_2_api_key
    model_name: str = settings.openai_image_2_model

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, image/*",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _uses_chat_completions(self) -> bool:
        return self.request_url.rstrip("/").endswith("/chat/completions")

    def _read_reference_image(self, payload_json: dict[str, Any]) -> str | None:
        reference_image_path = payload_json.get("reference_image_path")
        if not reference_image_path:
            return None
        path = Path(str(reference_image_path))
        if not path.exists() or not path.is_file():
            return None
        return encode_local_image_to_data_url(str(path))

    def _build_images_payload(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        request_payload = {
            "model": payload_json.get("model") or self.model_name,
            "prompt": payload_json.get("prompt", ""),
            "size": payload_json.get("size", "1024x1024"),
            "response_format": payload_json.get("response_format", "b64_json"),
        }
        if payload_json.get("negative_prompt"):
            request_payload["negative_prompt"] = payload_json["negative_prompt"]
        if payload_json.get("background"):
            request_payload["background"] = payload_json["background"]
        if payload_json.get("quality"):
            request_payload["quality"] = payload_json["quality"]
        if payload_json.get("metadata"):
            request_payload["metadata"] = payload_json["metadata"]
        return request_payload

    def _build_chat_completions_payload(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        prompt_text = payload_json.get("prompt", "")
        negative_prompt = payload_json.get("negative_prompt", "")
        size = payload_json.get("size", "1024x1024")
        reference_image_data_url = self._read_reference_image(payload_json)

        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "请基于参考图生成电商主图变体。"
                    f"\n正向提示词：{prompt_text}"
                    f"\n负向提示词：{negative_prompt}"
                    f"\n输出尺寸：{size}"
                    "\n要求：保持主体身份一致，避免畸形、模糊、水印、重复主体。"
                ),
            }
        ]
        if reference_image_data_url:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": reference_image_data_url,
                    },
                }
            )

        request_payload: dict[str, Any] = {
            "model": payload_json.get("model") or self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "你是电商主图变体生成助手，输出高质量图片结果。",
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "modalities": ["text", "image"],
        }

        if payload_json.get("metadata"):
            request_payload["metadata"] = payload_json["metadata"]

        return request_payload

    def _build_payload(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        if self._uses_chat_completions():
            return self._build_chat_completions_payload(payload_json)
        return self._build_images_payload(payload_json)

    async def generate(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
    ) -> ProviderResult:
        response = await client.post(
            self.request_url,
            json=self._build_payload(payload_json),
            headers=self._headers(),
        )
        response.raise_for_status()
        image_bytes, meta = await extract_image_bytes(response, client)
        meta.update(
            {
                "provider_code": self.provider_code,
                "provider_route": self.provider_route.value,
                "request_url": self.request_url,
                "response_headers": dict(response.headers),
                "request_mode": "chat_completions" if self._uses_chat_completions() else "images_generations",
            }
        )
        return ProviderResult(image_bytes=image_bytes, meta=meta)
