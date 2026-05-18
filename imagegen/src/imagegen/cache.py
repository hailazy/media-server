"""Content-hash dedup cache (SQLite + file store).

Purpose: cost dedup across runs and consumers. GPT Image 2 has no seed, so the
cache does NOT promise determinism — it returns the *previously generated* image
for an identical spec so the same request is never paid for twice (e.g. the same
hard-metaphor word imaged across LE deck rebuilds). Use --no-cache / --force for
a fresh roll.

v1 scope: only single-image, non-streaming requests are cached (n==1, no
--stream). Batch and streaming bypass — documented limitation in README.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import time
from pathlib import Path

from .spec import GenSpec


def data_dir() -> Path:
    """Resolve the data root. IMAGEGEN_DATA_DIR overrides; default = package
    sibling `data/` (home-server/imagegen/data, kept under editable install)."""
    override = os.environ.get("IMAGEGEN_DATA_DIR")
    base = Path(override) if override else Path(__file__).resolve().parents[2] / "data"
    (base / "cache").mkdir(parents=True, exist_ok=True)
    return base


def _connect(name: str) -> sqlite3.Connection:
    return sqlite3.connect(data_dir() / name)


def _db() -> sqlite3.Connection:
    con = _connect("cache.db")
    con.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, path TEXT, created REAL)"
    )
    return con


def _ref_hash(p: Path | None) -> str:
    if not p or not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def is_cacheable(spec: GenSpec) -> bool:
    return spec.n == 1 and not spec.stream


def cache_key(spec: GenSpec) -> str:
    parts = [
        spec.provider,
        spec.model,
        spec.prompt,
        spec.size,
        spec.quality,
        spec.mode,
        spec.output_format,
        str(spec.output_compression),
        spec.moderation,
        str(spec.seed),
        spec.negative_prompt,
        _ref_hash(spec.edit_ref),
        repr(sorted(spec.extra.items())),
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def lookup(key: str) -> Path | None:
    con = _db()
    try:
        row = con.execute("SELECT path FROM cache WHERE key=?", (key,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    p = Path(row[0])
    return p if p.exists() else None


def store(key: str, src: Path, fmt: str) -> Path:
    dest = data_dir() / "cache" / f"{key}.{fmt}"
    shutil.copyfile(src, dest)
    con = _db()
    try:
        con.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
            (key, str(dest), time.time()),
        )
        con.commit()
    finally:
        con.close()
    return dest
