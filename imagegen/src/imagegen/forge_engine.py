#!/usr/bin/env python3
"""Minimal Stable Diffusion WebUI Forge (A1111-compatible) REST client.

The shared, DOMAIN-AGNOSTIC Forge engine for the home-server image-gen hub —
the single Forge client of record. The `gen-fulfill` skill imports this directly
for the multi-step expert lane (per-seed loops, model switching, ADetailer /
ControlNet / img2img orchestration); the thin `ForgeProvider` is built on the
same payload shapes for the simple single-shot cacheable lane.

Talks to the local Forge at localhost:7860 (override via FORGE_URL). The ai-dock
container is old → **epsilon-prediction only** (V-pred is broken); stick to eps
checkpoints. Stdlib only — no external deps so it runs anywhere Python 3 does.

VAE note: pass vae="None" to force a checkpoint's BAKED VAE; pass a filename
(e.g. "sdxl.vae.safetensors") only for bases that need an external VAE.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path

URL = os.environ.get("FORGE_URL", "http://localhost:7860").rstrip("/")


def api(path: str, payload: dict | None = None, timeout: int = 600) -> dict | list:
    """GET (payload=None) or POST a JSON body to the Forge API; return decoded JSON."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{URL}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def resolve_model(match: str) -> str:
    """Resolve a checkpoint substring to Forge's full model title, or fail with what IS present."""
    models = api("/sdapi/v1/sd-models")
    for m in models:
        if match.lower() in m["title"].lower():
            return m["title"]
    have = [m["model_name"] for m in models]
    raise SystemExit(f"[!] checkpoint not found (match='{match}'). Mounted: {have}")


def set_options(model_title: str, vae: str, clip_skip: int) -> None:
    """Switch the loaded checkpoint + VAE + clip-skip via the options endpoint (verified path)."""
    api("/sdapi/v1/options", {
        "sd_model_checkpoint": model_title,
        "sd_vae": vae,
        "CLIP_stop_at_last_layers": clip_skip})


def txt2img(prompt: str, negative: str, *, sampler: str, scheduler: str, steps: int,
            cfg: float, width: int, height: int, seed: int, n_iter: int = 1,
            batch_size: int = 1, alwayson: dict | None = None,
            override_settings: dict | None = None) -> list[str]:
    """txt2img → list of base64 PNG strings (n_iter increments the seed for reproducible variety).

    alwayson: optional alwayson_scripts payload (e.g. the ADetailer face/hands pass). When ADetailer
    runs, Forge returns 1 image = the ADetailer-applied final (index 0) — no separate raw or crop image
    (verified on this Forge, brain f7933abb2dca).
    override_settings: per-request option overrides, self-restored after. On Forge this is the
    reliable way to bind a VAE/text-encoder for ONE gen via `forge_additional_modules` (the classic
    `sd_vae` option and a bare reload-checkpoint do NOT re-bind it — model-select reads it fresh).
    """
    payload = {
        "prompt": prompt, "negative_prompt": negative,
        "sampler_name": sampler, "scheduler": scheduler,
        "steps": steps, "cfg_scale": cfg, "width": width, "height": height,
        "seed": seed, "n_iter": n_iter, "batch_size": batch_size}
    if alwayson:
        payload["alwayson_scripts"] = alwayson
    if override_settings is not None:
        payload["override_settings"] = override_settings
        payload["override_settings_restore_afterwards"] = True
    res = api("/sdapi/v1/txt2img", payload)
    return res["images"]


def img2img(init_png: Path, prompt: str, negative: str, *, denoise: float, sampler: str,
            scheduler: str, steps: int, cfg: float, width: int, height: int, seed: int,
            n_iter: int = 1, batch_size: int = 1) -> list[str]:
    """img2img from a base frame at `denoise` → base64 PNGs. For holding identity while varying."""
    init_b64 = base64.b64encode(init_png.read_bytes()).decode()
    res = api("/sdapi/v1/img2img", {
        "init_images": [init_b64], "denoising_strength": denoise,
        "prompt": prompt, "negative_prompt": negative,
        "sampler_name": sampler, "scheduler": scheduler,
        "steps": steps, "cfg_scale": cfg, "width": width, "height": height,
        "seed": seed, "n_iter": n_iter, "batch_size": batch_size})
    return res["images"]


def save_images(b64list: list[str], out_dir: Path, stem: str, start: int = 0) -> list[Path]:
    """Decode + write each base64 PNG as <out_dir>/<stem>_<start+i>.png; return the written paths.

    `start` lets a per-iteration caller (n_iter=1 loop, e.g. the ADetailer path) keep a contiguous
    <stem>_<j> naming instead of every call resetting to _0.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, b in enumerate(b64list):
        p = out_dir / f"{stem}_{start + i}.png"
        p.write_bytes(base64.b64decode(b.split(",", 1)[-1]))
        paths.append(p)
    return paths
