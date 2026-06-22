#!/usr/bin/env python3
"""Queue control surface for the `gen-fulfill` skill.

Thin CLI over `imagegen.queue` so the skill orchestrates the queue without writing
fragile python one-liners. CRUCIAL OPSEC PROPERTY: `list` / `info` print ticket
METADATA ONLY — never prompt/negative/notes. The raw 18+ prompt is read solely by
`run_forge.py` (a subprocess), so it never enters the orchestrating Claude's context.

Subcommands:
  list                       JSON array of inbox tickets (metadata only), oldest/priority first
  sweep [--max-age S]        re-queue processing/ tickets older than S seconds (default 3600)
  claim <ticket.json>        atomically move inbox → processing; print new path
  archive <ticket> <status> [note]   move processing → done|failed
  info <ticket.json>         metadata only for one ticket
  recall <project> [--hash H]   index: recent fulfilments for a project (+ exact-hash hit)
  record <ticket> --verdict V --kept K --total T --rounds R --settings-json '{...}' --files-json '[...]'
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from imagegen.queue import Queue, Index, read_ticket

# Metadata fields safe to surface to the orchestrator (NO prompt/negative/notes).
_META = (
    "id", "created", "project_tag", "preset", "backend", "dest", "receipt_dest",
    "size", "seed_base", "count", "naming_stem", "checkpoint_match", "vae",
    "clip_skip", "sampler", "scheduler", "steps", "cfg", "lora", "adetailer",
    "judge", "max_rounds", "priority",
)


def _meta(path: Path) -> dict:
    t = read_ticket(path)
    d = asdict(t)
    out = {k: d.get(k) for k in _META}
    out["path"] = str(path)
    out["spec_hash"] = t.spec_hash()
    out["controlnet"] = ({"type": t.controlnet.get("type"), "weight": t.controlnet.get("weight")}
                         if t.controlnet else None)
    out["img2img"] = ({"denoise": t.img2img.get("denoise")} if t.img2img else None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    p_sweep = sub.add_parser("sweep")
    p_sweep.add_argument("--max-age", type=int, default=3600)
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("ticket")
    p_arch = sub.add_parser("archive")
    p_arch.add_argument("ticket")
    p_arch.add_argument("status", choices=["done", "failed"])
    p_arch.add_argument("note", nargs="?", default="")
    p_info = sub.add_parser("info")
    p_info.add_argument("ticket")
    p_rec = sub.add_parser("recall")
    p_rec.add_argument("project")
    p_rec.add_argument("--hash", default="")
    p_rd = sub.add_parser("record")
    p_rd.add_argument("ticket")
    p_rd.add_argument("--verdict", required=True)
    p_rd.add_argument("--kept", type=int, required=True)
    p_rd.add_argument("--total", type=int, required=True)
    p_rd.add_argument("--rounds", type=int, default=1)
    p_rd.add_argument("--settings-json", default="{}")
    p_rd.add_argument("--files-json", default="[]")

    args = ap.parse_args()
    q = Queue()

    if args.cmd == "list":
        print(json.dumps([_meta(p) for p in q.list_inbox()], indent=2, ensure_ascii=False))
    elif args.cmd == "sweep":
        moved = q.sweep_stale(args.max_age)
        print(json.dumps({"requeued": [p.name for p in moved]}))
    elif args.cmd == "claim":
        print(str(q.claim(Path(args.ticket))))
    elif args.cmd == "archive":
        print(str(q.archive(Path(args.ticket), args.status, args.note)))
    elif args.cmd == "info":
        print(json.dumps(_meta(Path(args.ticket)), indent=2, ensure_ascii=False))
    elif args.cmd == "recall":
        idx = Index()
        out = {"recent": idx.recent(args.project)}
        if args.hash:
            out["exact"] = idx.find_exact(args.hash)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif args.cmd == "record":
        idx = Index()
        t = read_ticket(Path(args.ticket))
        idx.record(t, verdict=args.verdict, kept=args.kept, total=args.total,
                   rounds=args.rounds, files=json.loads(args.files_json),
                   settings=json.loads(args.settings_json))
        print(json.dumps({"recorded": t.id, "spec_hash": t.spec_hash()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
