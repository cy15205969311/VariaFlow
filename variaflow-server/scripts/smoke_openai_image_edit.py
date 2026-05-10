from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.gateways.adapters.openai_adapter import OpenAIImageAdapter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test the OpenAI image edit adapter with a local image.")
    parser.add_argument("image_path", help="Absolute or relative path to the local source image.")
    parser.add_argument(
        "--prompt",
        default=(
            "Keep the same main subject and composition, then make a subtle commercial-quality variant "
            "with polished lighting and a clean background integration."
        ),
        help="Edit prompt to send to the provider.",
    )
    parser.add_argument(
        "--out-dir",
        default="smoke_outputs",
        help="Directory to save the generated image and response metadata.",
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        help="Requested output size.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    image_path = Path(args.image_path).expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Source image not found: {image_path}")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    adapter = OpenAIImageAdapter()
    payload_json = {
        "prompt": args.prompt,
        "size": args.size,
        "source_image_name": image_path.name,
        "source_image_path": str(image_path),
        "model": settings.openai_image_model,
    }

    timeout = httpx.Timeout(settings.provider_request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        result = await adapter.generate(
            client=client,
            payload_json=payload_json,
            source_image_bytes=image_path.read_bytes(),
        )

    output_path = out_dir / "openai_image_edit_output.png"
    meta_path = out_dir / "openai_image_edit_meta.json"
    output_path.write_bytes(result.image_bytes)
    meta_path.write_text(json.dumps(result.meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved image: {output_path}")
    print(f"Saved meta: {meta_path}")
    print(f"HTTP status: {result.meta.get('http_status')}")
    print(f"Content type: {result.meta.get('content_type')}")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
