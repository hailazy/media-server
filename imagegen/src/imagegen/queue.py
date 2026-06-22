#!/usr/bin/env python3
"""Shared async request protocol for the image-gen hub: ticket + queue + index.

This is the seam between the REQUESTER (the global `gen-art` skill, running in any
project) and the FULFILLER (the home-server `gen-fulfill` skill). The requester
writes a self-contained ticket into the queue; the fulfiller claims, resolves, and
archives it. Both import THIS module so the protocol has a single source of truth.

A NEW hub-internal module (like `forge_engine`): it does NOT touch imagegen's
stable CLI / GenSpec / provider contract.

OPSEC (the queue carries 18+ prompt text for adult projects):
- The QUEUE lives OUTSIDE every git repo — default `~/.local/share/imagegen-queue/`
  (override `IMAGEGEN_QUEUE_DIR`). Raw prompts live ONLY here (inbox/processing/done).
- The INDEX (`index.db`) is the learning-log tier: it stores the spec HASH +
  settings + verdict — NEVER raw prompt text. The hash is one-way, so hashing the
  prompt to dedup is safe; the prompt itself is never written to the index.

Tickets are JSON (not md+YAML) on purpose: stdlib-only, robust for arbitrary prompt
text (commas, parens, newlines) with no PyYAML dependency. Receipts (written into the
project, for humans) are markdown — see `gen-fulfill`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── Queue location (OPSEC: outside any repo) ──────────────────────────────────

def queue_root() -> Path:
    root = Path(os.environ.get(
        "IMAGEGEN_QUEUE_DIR",
        Path.home() / ".local/share/imagegen-queue",
    ))
    return root


SUBDIRS = ("inbox", "processing", "done", "failed")


def ensure_queue() -> Path:
    root = queue_root()
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


# ── Ticket ────────────────────────────────────────────────────────────────────

# Fields that define the generation identity → fed into the dedup spec hash.
# `prompt`/`negative` ARE included (the hash is one-way, so this is OPSEC-safe and
# is what makes "same request → reuse" correct). The hash, not these fields, is
# what the index stores.
_HASH_FIELDS = (
    "checkpoint_match", "vae", "clip_skip", "lora",
    "sampler", "scheduler", "steps", "cfg", "size",
    "seed_base", "count", "prompt", "negative",
    "adetailer", "controlnet", "img2img",
)


@dataclass
class Ticket:
    """A self-contained image-generation request. The fulfiller never re-derives
    a prompt — everything it needs to drive Forge is here."""
    # identity / routing
    project_tag: str                       # codename only (e.g. "chimera"), never a real title
    backend: str = "forge"                 # this protocol is the local-Forge async lane
    preset: str = ""                       # provenance only; settings below are already resolved
    dest: str = ""                         # absolute dir where PNGs land (inside the project)
    receipt_dest: str = ""                 # absolute path for the markdown receipt
    # fully-constructed prompt (the 18+ payload — lives only in the external queue)
    prompt: str = ""
    negative: str = ""
    notes: str = ""                        # free-text guidance for the fulfiller
    # resolved generation settings (inlined so the ticket is self-contained)
    checkpoint_match: str = "NoobAI-XL-v1.1"
    vae: str = "None"
    clip_skip: int = 1
    sampler: str = "Euler a"
    scheduler: str = "Karras"
    steps: int = 28
    cfg: float = 7.0
    size: str = "832x1216"
    seed_base: int = 1000
    count: int = 1
    naming_stem: str = "gen"
    lora: list = field(default_factory=list)          # ["stem:weight", ...] or ["stem", ...]
    # expert toggles (None = off)
    adetailer: list | None = None                     # ["face", "hands"]
    controlnet: dict | None = None                    # {"type": "openpose", "image": "<abs>", "weight": 0.5}
    img2img: dict | None = None                       # {"init": "<abs>", "denoise": 0.35}
    # iteration / judging policy
    judge: str = ""                                   # what "good" means for this request
    max_rounds: int = 1
    priority: str = "normal"                          # high | normal | low
    # stamped on write
    id: str = ""
    created: str = ""

    def spec_hash(self) -> str:
        d = asdict(self)
        payload = {k: d.get(k) for k in _HASH_FIELDS}
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(s: str, n: int = 28) -> str:
    s = _SLUG_RE.sub("-", s.lower()).strip("-")
    return s[:n] or "ticket"


def write_ticket(ticket: Ticket, *, label: str = "") -> Path:
    """Stamp id+created, write the ticket JSON into inbox/, return its path."""
    ensure_queue()
    now = datetime.now(timezone.utc).astimezone()
    if not ticket.created:
        ticket.created = now.isoformat(timespec="seconds")
    if not ticket.id:
        stamp = now.strftime("%Y%m%dT%H%M%S")
        slug = _slug(label or ticket.naming_stem or ticket.project_tag)
        ticket.id = f"{stamp}__{_slug(ticket.project_tag,12)}__{slug}"
    path = queue_root() / "inbox" / f"{ticket.id}.json"
    path.write_text(json.dumps(asdict(ticket), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_ticket(path: Path) -> Ticket:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {f for f in Ticket.__dataclass_fields__}
    return Ticket(**{k: v for k, v in data.items() if k in known})


# ── Queue operations (claim / archive / stale sweep) ──────────────────────────

class Queue:
    """Filesystem state machine: inbox → processing → done | failed."""

    def __init__(self) -> None:
        self.root = ensure_queue()

    def _dir(self, name: str) -> Path:
        return self.root / name

    def list_inbox(self) -> list[Path]:
        """Pending tickets, oldest-first, high-priority first."""
        items = sorted(self._dir("inbox").glob("*.json"))
        def key(p: Path):
            try:
                t = read_ticket(p)
                pr = {"high": 0, "normal": 1, "low": 2}.get(t.priority, 1)
                return (pr, t.created or p.name)
            except Exception:
                return (1, p.name)
        return sorted(items, key=key)

    def sweep_stale(self, max_age_s: int = 3600) -> list[Path]:
        """Re-queue processing/ tickets older than max_age_s (assume a crashed run)."""
        moved = []
        now = time.time()
        for p in self._dir("processing").glob("*.json"):
            if now - p.stat().st_mtime > max_age_s:
                dst = self._dir("inbox") / p.name
                p.rename(dst)
                moved.append(dst)
        return moved

    def claim(self, path: Path) -> Path:
        """Atomically move a ticket inbox → processing (a crash leaves it visibly here)."""
        dst = self._dir("processing") / Path(path).name
        Path(path).rename(dst)
        return dst

    def archive(self, path: Path, status: str = "done", note: str = "") -> Path:
        """Move processing → done | failed. On failure, append a note to the ticket JSON."""
        assert status in ("done", "failed")
        path = Path(path)
        if note:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("_log", []).append(
                    {"at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                     "status": status, "note": note})
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        dst = self._dir(status) / path.name
        path.rename(dst)
        return dst


# ── Index (learning-log tier — settings/verdict/hash ONLY, never raw prompt) ──

class Index:
    """SQLite log over fulfilled tickets. The exact/structured tier of Component 4.

    Stores spec HASH + settings + verdict so the fulfiller can answer
    "what settings did <project>'s <kind> use last time, and did it pass?" — WITHOUT
    ever persisting raw 18+ prompt text. brain holds the semantic/cross-project tier."""

    def __init__(self) -> None:
        self.path = queue_root() / "index.db"
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        ensure_queue()
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS fulfilments (
                    id TEXT PRIMARY KEY,
                    fulfilled_at TEXT,
                    project_tag TEXT,
                    preset TEXT,
                    spec_hash TEXT,
                    settings_json TEXT,   -- sampler/steps/cfg/size/lora/adetailer... NO prompt
                    seeds TEXT,
                    verdict TEXT,         -- passed | failed | partial
                    kept INTEGER,
                    total INTEGER,
                    rounds INTEGER,
                    files_json TEXT
                )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_hash ON fulfilments(spec_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_project ON fulfilments(project_tag)")

    def find_exact(self, spec_hash: str) -> dict | None:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM fulfilments WHERE spec_hash=? ORDER BY fulfilled_at DESC LIMIT 1",
                (spec_hash,)).fetchone()
            return dict(row) if row else None

    def recent(self, project_tag: str, limit: int = 5) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM fulfilments WHERE project_tag=? ORDER BY fulfilled_at DESC LIMIT ?",
                (project_tag, limit)).fetchall()
            return [dict(r) for r in rows]

    def record(self, ticket: Ticket, *, verdict: str, kept: int, total: int,
               rounds: int, files: list, settings: dict) -> None:
        # Guard: never let raw prompt leak into the settings blob.
        clean = {k: v for k, v in settings.items() if k not in ("prompt", "negative", "notes")}
        with self._conn() as c:
            c.execute(
                """INSERT OR REPLACE INTO fulfilments
                   (id, fulfilled_at, project_tag, preset, spec_hash, settings_json,
                    seeds, verdict, kept, total, rounds, files_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ticket.id,
                 datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                 ticket.project_tag, ticket.preset, ticket.spec_hash(),
                 json.dumps(clean, ensure_ascii=False),
                 json.dumps([ticket.seed_base + i for i in range(ticket.count)]),
                 verdict, kept, total, rounds,
                 json.dumps([str(f) for f in files], ensure_ascii=False)))
