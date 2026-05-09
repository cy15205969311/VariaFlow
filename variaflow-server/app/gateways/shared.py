from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(slots=True)
class ProviderResult:
    image_bytes: bytes
    meta: dict[str, Any]


def encode_local_image_to_data_url(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    file_bytes = path.read_bytes()
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def download_image_from_url(client: httpx.AsyncClient, image_url: str) -> bytes:
    response = await client.get(image_url)
    response.raise_for_status()
    return response.content


async def extract_image_bytes(response: httpx.Response, client: httpx.AsyncClient) -> tuple[bytes, dict[str, Any]]:
    content_type = response.headers.get("content-type", "")
    meta: dict[str, Any] = {
        "http_status": response.status_code,
        "content_type": content_type,
    }

    if content_type.startswith("image/"):
        return response.content, meta

    payload = response.json()
    meta["response_json"] = payload

    data_items = payload.get("data") or payload.get("images") or payload.get("output", {}).get("images") or []
    if isinstance(data_items, dict):
        data_items = [data_items]

    if data_items:
        first_item = data_items[0]
        if isinstance(first_item, str):
            return await download_image_from_url(client, first_item), meta
        if first_item.get("b64_json"):
            return base64.b64decode(first_item["b64_json"]), meta
        if first_item.get("image_base64"):
            return base64.b64decode(first_item["image_base64"]), meta
        if first_item.get("url"):
            return await download_image_from_url(client, first_item["url"]), meta

    if payload.get("b64_json"):
        return base64.b64decode(payload["b64_json"]), meta
    if payload.get("image_base64"):
        return base64.b64decode(payload["image_base64"]), meta
    if payload.get("image_url"):
        image_url = payload["image_url"]
        if isinstance(image_url, str):
            return await download_image_from_url(client, image_url), meta
        if isinstance(image_url, dict) and image_url.get("url"):
            return await download_image_from_url(client, image_url["url"]), meta

    choices = payload.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        images = message.get("images") or []
        if isinstance(images, dict):
            images = [images]
        for image_item in images:
            if isinstance(image_item, str):
                return await download_image_from_url(client, image_item), meta
            if not isinstance(image_item, dict):
                continue
            if image_item.get("b64_json"):
                return base64.b64decode(image_item["b64_json"]), meta
            if image_item.get("image_base64"):
                return base64.b64decode(image_item["image_base64"]), meta
            if image_item.get("url"):
                return await download_image_from_url(client, image_item["url"]), meta

        content_items = message.get("content") or []
        if isinstance(content_items, str):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("b64_json"):
                return base64.b64decode(content_item["b64_json"]), meta
            if content_item.get("image_base64"):
                return base64.b64decode(content_item["image_base64"]), meta
            image_url = content_item.get("image_url")
            if isinstance(image_url, str):
                return await download_image_from_url(client, image_url), meta
            if isinstance(image_url, dict) and image_url.get("url"):
                return await download_image_from_url(client, image_url["url"]), meta

    raise ValueError("模型供应商响应中未包含图片字节流、Base64 数据或可下载图片地址。")
