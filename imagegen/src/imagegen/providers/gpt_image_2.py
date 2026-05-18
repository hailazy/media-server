"""GPT Image 2 provider (OpenAI). The first-class provider for v1.

Ports the SDK transport from IronCradle/tools/concept_gen.py — the exact churn
surface this tool exists to contain. The openai dependency is PINNED in
pyproject.toml; the images.generate vs images.edit param split below is
version-sensitive (see README "Gotchas" before bumping the pin).
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator

from ..spec import GenSpec, ImageResult
from . import ImageProvider, register

# Provider-level pricing (gpt-image-2 at 1024x1024; scales with pixel count).
# This is provider knowledge, correctly owned here — NOT in any consumer skill.
_COST_PER_IMAGE = {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053}


@register
class GPTImage2Provider(ImageProvider):
    name = "gpt-image-2"
    default_model = "gpt-image-2"

    def _client(self):
        if "OPENAI_API_KEY" not in os.environ:
            raise RuntimeError(
                "OPENAI_API_KEY not set — export it, or pass --env-file"
            )
        from openai import OpenAI

        return OpenAI()

    def _request_kwargs(self, spec: GenSpec) -> dict:
        kw: dict = {
            "model": spec.model or self.default_model,
            "prompt": spec.prompt,
            "size": spec.size,
            "quality": spec.quality,
            "n": spec.n,
            "output_format": spec.output_format,
            "output_compression": spec.output_compression,
            "moderation": spec.moderation,
        }
        if spec.stream:
            if spec.n > 1:
                kw["n"] = 1  # stream + n>1 is ambiguous
            kw["stream"] = True
            kw["partial_images"] = spec.partial_images
        kw.update(spec.extra)
        return kw

    def generate(self, spec: GenSpec) -> Iterator[ImageResult]:
        if spec.edit_ref:
            yield from self.edit(spec)
            return
        client = self._client()
        result = client.images.generate(**self._request_kwargs(spec))
        yield from self._consume(result, spec)

    def edit(self, spec: GenSpec) -> Iterator[ImageResult]:
        ref = spec.edit_ref
        if ref is None or not ref.exists():
            raise FileNotFoundError(f"edit-ref not found: {ref}")
        client = self._client()
        kw = self._request_kwargs(spec)
        # images.edit() does NOT accept `moderation` (generate-only). Other
        # params (output_format/compression/stream/partial_images) ARE accepted
        # per SDK signature inspection 2026-05-14 (brain 83769887d0a6).
        edit_kw = {k: v for k, v in kw.items() if k != "moderation"}
        with open(ref, "rb") as fh:
            edit_kw["image"] = fh
            result = client.images.edit(**edit_kw)
            yield from self._consume(result, spec)

    def _consume(self, result, spec: GenSpec) -> Iterator[ImageResult]:
        if spec.stream:
            final_b64: str | None = None
            for event in result:
                etype = getattr(event, "type", "")
                b64 = getattr(event, "b64_json", None) or getattr(
                    event, "partial_image_b64", None
                )
                if etype.endswith("partial_image") and b64:
                    idx = getattr(event, "partial_image_index", 0)
                    yield ImageResult(
                        base64.b64decode(b64), is_partial=True, partial_index=idx
                    )
                    final_b64 = b64
                elif etype.endswith("completed") and b64:
                    final_b64 = b64
            if final_b64:
                yield ImageResult(base64.b64decode(final_b64))
        else:
            for idx, item in enumerate(result.data):
                if not getattr(item, "b64_json", None):
                    continue
                yield ImageResult(base64.b64decode(item.b64_json), index=idx)

    def estimate_cost(self, spec: GenSpec) -> float:
        base = _COST_PER_IMAGE.get(spec.quality, 0.05)
        if "x" in spec.size:
            w, h = (int(v) for v in spec.size.split("x"))
        else:
            w, h = 1024, 1024
        return base * ((w * h) / (1024 * 1024)) * spec.n
