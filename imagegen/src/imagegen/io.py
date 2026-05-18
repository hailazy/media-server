"""Generic I/O: env loading, output-path resolution, byte writes.

No provider knowledge, no prompt knowledge. Ported from the generic blocks of
IronCradle/tools/concept_gen.py (load_dotenv, resolve_output_path).
"""

from __future__ import annotations

import os
import time
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Best-effort .env loader. setdefault — never clobber an exported var."""
    if not path or not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def resolve_output_path(out: Path | None, fmt: str, idx: int = 0) -> Path:
    """Resolve where image `idx` is written.

    --out given  → use it (append _NN only for idx>0 batch members).
    --out absent → IMAGEGEN_OUT_DIR (or cwd) / imagegen_<ts>[_NN].<fmt>.
    """
    if out is not None:
        if idx and out.suffix:
            return out.with_name(f"{out.stem}_{idx:02d}{out.suffix}")
        return out
    base = Path(os.environ.get("IMAGEGEN_OUT_DIR", ".")).resolve()
    base.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{idx:02d}" if idx else ""
    return base / f"imagegen_{ts}{suffix}.{fmt}"


def write_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
