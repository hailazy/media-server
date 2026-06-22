#!/usr/bin/env python3
"""Deterministic Forge gen driver for the `gen-fulfill` skill.

Given a CLAIMED ticket JSON, drive `imagegen.forge_engine` to produce the requested
PNGs at the ticket's dest, then print a JSON summary on stdout (files, seeds,
settings) for the skill to parse, judge, and log.

Pure mechanics — NO judgment, NO prompt construction (the ticket is already fully
constructed by the requester). The skill owns the gen→judge→iterate loop; this
script is one gen pass.

OPSEC: the printed `settings` summary deliberately OMITS prompt/negative and the
ControlNet base64 image — only the knobs worth recording in the receipt/index.

Usage:  python run_forge.py <claimed-ticket.json> [--seed-offset N]
        --seed-offset shifts seed_base (for an iteration re-roll without editing the ticket).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from imagegen.forge_engine import (
    api, resolve_model, set_options, txt2img, img2img, save_images,
)
from imagegen.queue import read_ticket

# Short ControlNet type → substring to resolve against Forge's registered CN models.
CN_TYPE_MATCH = {
    "openpose": "openpose",
    "lineart": "lineart",
    "depth": "depth",
    "canny": "canny",
}


def adetailer_payload(which: list[str]) -> dict | None:
    """ADetailer face/hands restore pass. Forge returns 1 image = the applied final
    (index 0), verified on this Forge (brain f7933abb2dca)."""
    common = {"ad_denoising_strength": 0.4, "ad_inpaint_only_masked": True}
    models = {"face": "face_yolov8n.pt", "hands": "hand_yolov8n.pt", "hand": "hand_yolov8n.pt"}
    units = [{"ad_model": models[w], **common} for w in which if w in models]
    if not units:
        return None
    # args = [enabled, skip_img2img, unit0, unit1, ...]
    return {"ADetailer": {"args": [True, False, *units]}}


def resolve_cn_model(spec: dict) -> str:
    """Resolve the ControlNet model title. Accept an explicit `model` (substring) or a
    short `type`; match against Forge's registered CN models so the caller need not
    know the hash suffix."""
    want = spec.get("model") or CN_TYPE_MATCH.get(spec.get("type", ""), spec.get("type", ""))
    try:
        models = api("/controlnet/model_list")
        names = models.get("model_list", models) if isinstance(models, dict) else models
        for n in names:
            if want.lower() in str(n).lower():
                return str(n)
    except Exception:
        pass
    return want  # fall back to the literal string; Forge will error clearly if wrong


def controlnet_payload(spec: dict) -> dict:
    img = Path(spec["image"])
    b64 = base64.b64encode(img.read_bytes()).decode()
    return {"controlnet": {"args": [{
        "enabled": True,
        "image": b64,
        "module": spec.get("module", "none"),     # pre-processed image → skip detector
        "model": resolve_cn_model(spec),
        "weight": spec.get("weight", 0.5),
        "resize_mode": "Crop and Resize",
        "control_mode": spec.get("control_mode", "Balanced"),
        "pixel_perfect": True,
    }]}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticket")
    ap.add_argument("--seed-offset", type=int, default=0)
    args = ap.parse_args()

    t = read_ticket(Path(args.ticket))
    w, h = (int(x) for x in t.size.lower().split("x"))

    checkpoint = resolve_model(t.checkpoint_match)
    set_options(checkpoint, t.vae, t.clip_skip)

    # LoRA tokens come from the structured field (single source of truth); trigger
    # words live in the prompt proper (assembled by the requester).
    lora_tokens = " ".join(
        f"<lora:{spec}>" if ":" in spec else f"<lora:{spec}:1.0>" for spec in (t.lora or [])
    )
    prompt = (f"{lora_tokens} {t.prompt}".strip() if lora_tokens else t.prompt)

    alwayson: dict = {}
    if t.adetailer:
        ad = adetailer_payload(t.adetailer)
        if ad:
            alwayson.update(ad)
    if t.controlnet:
        alwayson.update(controlnet_payload(t.controlnet))

    dest = Path(t.dest)
    files: list[str] = []
    seeds: list[int] = []
    base = t.seed_base + args.seed_offset
    for j in range(t.count):
        seed = base + j
        seeds.append(seed)
        if t.img2img:
            imgs = img2img(
                Path(t.img2img["init"]), prompt, t.negative,
                denoise=t.img2img.get("denoise", 0.35),
                sampler=t.sampler, scheduler=t.scheduler, steps=t.steps, cfg=t.cfg,
                width=w, height=h, seed=seed, n_iter=1)
        else:
            imgs = txt2img(
                prompt, t.negative,
                sampler=t.sampler, scheduler=t.scheduler, steps=t.steps, cfg=t.cfg,
                width=w, height=h, seed=seed, n_iter=1,
                alwayson=alwayson or None)
        paths = save_images(imgs[:1], dest, t.naming_stem, start=(args.seed_offset + j))
        files.extend(str(p) for p in paths)

    # Settings summary for the receipt + index — NO prompt, NO CN base64.
    settings = {
        "checkpoint": checkpoint,
        "vae": t.vae,
        "clip_skip": t.clip_skip,
        "sampler": t.sampler,
        "scheduler": t.scheduler,
        "steps": t.steps,
        "cfg": t.cfg,
        "size": t.size,
        "lora": t.lora,
        "adetailer": t.adetailer,
        "controlnet": ({"type": t.controlnet.get("type"), "weight": t.controlnet.get("weight")}
                       if t.controlnet else None),
        "img2img": ({"denoise": t.img2img.get("denoise")} if t.img2img else None),
    }
    print(json.dumps({"files": files, "seeds": seeds, "settings": settings}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
