from __future__ import annotations

import asyncio
import io
import random
from datetime import datetime
from typing import Any

import httpx
from PIL import Image, ImageDraw

from app.core.config import settings
from app.gateways.adapters.openai_adapter import OpenAIImageAdapter
from app.gateways.adapters.wanxiang_adapter import WanxiangAdapter
from app.gateways.shared import ProviderResult
from app.models.enums import ProviderRoute

FALLBACK_HTTP_STATUS_CODES = {429, 502, 503, 504}
MOCK_IMAGE_WIDTH = 1536
MOCK_IMAGE_HEIGHT = 1536


def _build_mock_image_bytes(provider_code: str, provider_route: ProviderRoute) -> bytes:
    """
    生成一张足够大的测试图片，确保能通过当前规则质检。
    """

    image = Image.new("RGB", (MOCK_IMAGE_WIDTH, MOCK_IMAGE_HEIGHT), color=(28, 78, 138))
    draw = ImageDraw.Draw(image)

    for y in range(0, MOCK_IMAGE_HEIGHT, 12):
        color = (
            (40 + y // 8) % 255,
            (120 + y // 5) % 255,
            (180 + y // 7) % 255,
        )
        draw.line((0, y, MOCK_IMAGE_WIDTH, y), fill=color, width=12)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle((60, 60, 1200, 280), fill=(255, 255, 255))
    draw.text((90, 90), f"VariaFlow Mock Provider: {provider_code}", fill=(10, 10, 10))
    draw.text((90, 150), f"Route: {provider_route.value}", fill=(10, 10, 10))
    draw.text((90, 210), f"Generated At: {timestamp}", fill=(10, 10, 10))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


class MockAIAdapter:
    """
    环境变量驱动的混沌 Mock 适配器。

    - 模拟 2~5 秒网络耗时
    - 按故障率随机抛出超时或 502
    - 成功时动态生成符合 QC 要求的图片
    """

    def __init__(self, provider_route: ProviderRoute) -> None:
        self.provider_route = provider_route
        self.provider_code = "mock_openai_image_2" if provider_route == ProviderRoute.PRIMARY else "mock_aliyun_wanx"
        self.request_url = f"mock://{provider_route.value}"

    async def generate(
        self,
        *,
        client: httpx.AsyncClient,
        payload_json: dict[str, Any],
    ) -> ProviderResult:
        del client, payload_json
        await asyncio.sleep(random.uniform(2.0, 5.0))

        if random.random() < settings.mock_failure_rate:
            if random.random() < 0.5:
                raise httpx.TimeoutException(f"Mock {self.provider_code} 超时")

            request = httpx.Request("POST", self.request_url, json={"mock": True})
            response = httpx.Response(
                status_code=502,
                request=request,
                json={"error": "mock_bad_gateway"},
            )
            raise httpx.HTTPStatusError(
                f"Mock {self.provider_code} 返回 502",
                request=request,
                response=response,
            )

        image_bytes = _build_mock_image_bytes(self.provider_code, self.provider_route)
        meta = {
            "provider_code": self.provider_code,
            "provider_route": self.provider_route.value,
            "request_url": self.request_url,
            "http_status": 200,
            "content_type": "image/png",
            "mock": True,
        }
        return ProviderResult(image_bytes=image_bytes, meta=meta)


def _build_adapter(provider_route: ProviderRoute) -> Any:
    if settings.use_mock_ai:
        return MockAIAdapter(provider_route)
    if provider_route == ProviderRoute.FALLBACK:
        return WanxiangAdapter()
    return OpenAIImageAdapter()


async def _call_single_provider(
    *,
    client: httpx.AsyncClient,
    payload_json: dict[str, Any],
    provider_route: ProviderRoute,
) -> tuple[bytes, dict[str, Any]]:
    adapter = _build_adapter(provider_route)
    try:
        result = await adapter.generate(client=client, payload_json=payload_json)
        return result.image_bytes, result.meta
    except Exception as exc:
        setattr(exc, "provider_route", provider_route.value)
        setattr(exc, "provider_code", getattr(adapter, "provider_code", "unknown_provider"))
        raise


async def call_ai_provider(
    payload_json: dict[str, Any],
    provider_route: ProviderRoute = ProviderRoute.PRIMARY,
) -> tuple[bytes, dict[str, Any]]:
    """
    优先调用主链路，并在可重试的上游异常下透明切换到兜底链路。

    开启 Mock 时，真实 HTTPX 调用会被混沌 Mock 适配器接管，
    但对执行器暴露的返回接口保持不变。
    """

    timeout = httpx.Timeout(settings.provider_request_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if provider_route == ProviderRoute.FALLBACK:
            return await _call_single_provider(
                client=client,
                payload_json=payload_json,
                provider_route=ProviderRoute.FALLBACK,
            )

        switch_reason: str | None = None
        try:
            return await _call_single_provider(
                client=client,
                payload_json=payload_json,
                provider_route=ProviderRoute.PRIMARY,
            )
        except httpx.TimeoutException:
            switch_reason = "primary_timeout"
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in FALLBACK_HTTP_STATUS_CODES:
                raise
            switch_reason = f"primary_http_{exc.response.status_code}"
        except httpx.HTTPError:
            switch_reason = "primary_transport_error"
        except ValueError:
            switch_reason = "primary_invalid_payload"

        try:
            image_bytes, meta = await _call_single_provider(
                client=client,
                payload_json=payload_json,
                provider_route=ProviderRoute.FALLBACK,
            )
        except Exception as exc:
            setattr(exc, "switch_reason", switch_reason)
            raise

        meta["switch_reason"] = switch_reason
        return image_bytes, meta
