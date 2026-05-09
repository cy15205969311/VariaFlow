from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.gateways.shared import ProviderResult
from app.gateways.shared import download_image_from_url
from app.models.enums import ProviderRoute


@dataclass(slots=True)
class WanxiangAdapter:
    """
    阿里万相真实适配器。

    预期环境变量：
    - `VARIAFLOW_ALIYUN_WANX_URL` 或 `WANX_BASE_URL`
    - `VARIAFLOW_ALIYUN_WANX_API_KEY` 或 `WANX_API_KEY`
    - 也兼容 `DASHSCOPE_API_KEY`
    """

    provider_code: str = "aliyun_wanx"
    provider_route: ProviderRoute = ProviderRoute.FALLBACK
    request_url: str = settings.aliyun_wanx_url
    api_key: str = settings.aliyun_wanx_api_key

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, image/*",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, payload_json: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": payload_json.get("model", "wanx-v1"),
            "input": {
                "prompt": payload_json.get("prompt", ""),
                "negative_prompt": payload_json.get("negative_prompt", ""),
            },
            "parameters": {
                "size": payload_json.get("size", "1024*1024").replace("x", "*"),
            },
        }

    async def _poll_task_result(
        self,
        *,
        client: httpx.AsyncClient,
        task_id: str,
        max_polls: int = 20,
        interval_seconds: float = 2.0,
    ) -> dict[str, Any]:
        task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        last_payload: dict[str, Any] = {}

        for _ in range(max_polls):
            response = await client.get(task_url, headers=self._headers())
            response.raise_for_status()
            payload = response.json()
            last_payload = payload

            task_status = (
                payload.get("output", {}).get("task_status")
                or payload.get("output", {}).get("status")
                or payload.get("status")
            )
            if task_status in {"SUCCEEDED", "succeeded"}:
                return payload
            if task_status in {"FAILED", "failed"}:
                raise ValueError(f"万相任务执行失败：{payload}")

            await asyncio.sleep(interval_seconds)

        raise TimeoutError(f"万相任务轮询超时：{last_payload}")

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

        created_payload = response.json()
        task_id = (
            created_payload.get("output", {}).get("task_id")
            or created_payload.get("task_id")
        )
        if not task_id:
            raise ValueError(f"万相响应中缺少 task_id：{created_payload}")

        result_payload = await self._poll_task_result(client=client, task_id=str(task_id))
        output = result_payload.get("output", {})
        results = output.get("results") or output.get("images") or []
        image_url = None

        if results and isinstance(results[0], dict):
            image_url = results[0].get("url") or results[0].get("image_url")
        elif results and isinstance(results[0], str):
            image_url = results[0]

        if not image_url:
            image_url = output.get("image_url")
        if not image_url:
            raise ValueError(f"万相结果中缺少可下载图片地址：{result_payload}")

        image_bytes = await download_image_from_url(client, image_url)
        meta = {
            "http_status": response.status_code,
            "content_type": "image/*",
            "provider_code": self.provider_code,
            "provider_route": self.provider_route.value,
            "request_url": self.request_url,
            "task_id": str(task_id),
            "response_json": result_payload,
        }
        return ProviderResult(image_bytes=image_bytes, meta=meta)
