"""Forge (Stable Diffusion WebUI Forge, A1111-compatible) provider — the LOCAL lane.

Built on the shared `forge_engine` transport (the single Forge client of record). The
EXPERT multi-step lane (`gen-fulfill`) imports `forge_engine` directly; THIS provider
is the SIMPLE single-call cacheable lane reachable via the `imagegen` CLI / GenSpec.

Per README §7, adding this required NO change to the core or to GenSpec — that's the
proof the seam is right:
- `prompt` / `negative_prompt` / `size` / `seed` / `n` come from GenSpec fields
  (`seed` and `negative_prompt` — dead for GPT Image 2 — come alive here).
- Everything Forge-specific rides in `spec.extra`: `sampler_name`, `scheduler`,
  `steps`, `cfg_scale`, `override_settings` (per-request checkpoint/VAE/CLIP), and
  `alwayson_scripts` (ADetailer, single-image ControlNet). A multi-call / iterate /
  preprocess workflow is ORCHESTRATION → it belongs to `gen-fulfill`, not here.
- `edit_ref` set → img2img (the reuse of the existing GenSpec edit mode).
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path

from ..spec import GenSpec, ImageResult
from . import ImageProvider, register


def _wh(size: str) -> tuple[int, int]:
    if "x" in size.lower():
        w, h = size.lower().split("x")[:2]
        return int(w), int(h)
    return 1024, 1024


def _decode(images: list[str]) -> Iterator[ImageResult]:
    for idx, b64 in enumerate(images):
        yield ImageResult(base64.b64decode(b64.split(",", 1)[-1]), index=idx)


@register
class ForgeProvider(ImageProvider):
    name = "forge"
    default_model = "NoobAI-XL-v1.1"

    def generate(self, spec: GenSpec) -> Iterator[ImageResult]:
        if spec.edit_ref:
            yield from self.edit(spec)
            return
        from ..forge_engine import api
        w, h = _wh(spec.size)
        payload = {
            "prompt": spec.prompt,
            "negative_prompt": spec.negative_prompt,
            "width": w,
            "height": h,
            "seed": spec.seed if spec.seed is not None else -1,
            "n_iter": spec.n,
        }
        payload.update(spec.extra)   # sampler_name/scheduler/steps/cfg_scale/override_settings/alwayson_scripts
        res = api("/sdapi/v1/txt2img", payload)
        yield from _decode(res.get("images", []))

    def edit(self, spec: GenSpec) -> Iterator[ImageResult]:
        ref = spec.edit_ref
        if ref is None or not Path(ref).exists():
            raise FileNotFoundError(f"edit-ref not found: {ref}")
        from ..forge_engine import api
        w, h = _wh(spec.size)
        init_b64 = base64.b64encode(Path(ref).read_bytes()).decode()
        payload = {
            "init_images": [init_b64],
            "denoising_strength": spec.extra.get("denoising_strength", 0.35),
            "prompt": spec.prompt,
            "negative_prompt": spec.negative_prompt,
            "width": w,
            "height": h,
            "seed": spec.seed if spec.seed is not None else -1,
            "n_iter": spec.n,
        }
        payload.update(spec.extra)   # may re-set denoising_strength, add alwayson_scripts, etc.
        res = api("/sdapi/v1/img2img", payload)
        yield from _decode(res.get("images", []))

    def estimate_cost(self, spec: GenSpec) -> float:
        return 0.0  # local GPU, no per-call cost
