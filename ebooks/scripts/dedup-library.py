#!/usr/bin/env python3
"""
Merge duplicate library entries (same title+authors) into a single entry.

Strategy per duplicate group:
  1. Pick keeper: most formats > newest last_modified > lowest id
  2. For each non-keeper (dropper): add_format any extension the keeper lacks
  3. Remove dropper

Runs via the same one-shot container pattern as bulk-import.py — requires
home-ebooks to be DOWN (SQLite write conflict otherwise).

Usage:
  ./dedup-library.py --dry-run
  ./dedup-library.py --execute
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

IMAGE        = "docker.io/crocodilestick/calibre-web-automated:latest"
EBOOKS_CTR   = "home-ebooks"
LIBRARY_HOST = Path("/home/haint/Data/Calibre Library")
LIBRARY_CTR  = "/calibre-library"


def one_shot(args: list[str], extra_mounts: list[tuple[str, str]] = None) -> subprocess.CompletedProcess:
    """Run calibredb directly via argv (no shell parsing) — safe for paths with quotes."""
    cmd = [
        "podman", "run", "--rm",
        "-v", f"{LIBRARY_HOST}:{LIBRARY_CTR}:z",
    ]
    for host, ctr in (extra_mounts or []):
        cmd += ["-v", f"{host}:{ctr}:ro,z"]
    cmd += [
        "-e", "PATH=/app/calibre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "-e", "LD_LIBRARY_PATH=/app/calibre/lib",
        "--entrypoint", "/app/calibre/bin/calibredb",
        IMAGE,
    ] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def list_library() -> list[dict]:
    cp = one_shot([
        "list",
        f"--library-path={LIBRARY_CTR}",
        "--fields=id,title,authors,formats,last_modified",
        "--for-machine", "--limit=999999",
    ])
    if cp.returncode != 0:
        sys.exit(f"calibredb list failed:\n{cp.stderr}")
    return json.loads(cp.stdout)


def find_dups(books: list[dict]) -> list[list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for b in books:
        key = (b['title'].strip().lower(),
               tuple(sorted(a.lower() for a in b['authors'])))
        groups.setdefault(key, []).append(b)
    return [v for v in groups.values() if len(v) > 1]


def pick_keeper(entries: list[dict]) -> tuple[dict, list[dict]]:
    """Sort: most formats first, then newest mtime, then lowest id."""
    s = sorted(entries, key=lambda e: (-len(e['formats']), e['last_modified'], -e['id']), reverse=False)
    # reverse=False with negated num_formats works correctly; mtime ascending so newest needs descending — fix:
    s = sorted(entries, key=lambda e: (-len(e['formats']),
                                       -ord_mtime(e['last_modified']),
                                       e['id']))
    return s[0], s[1:]


def ord_mtime(ts: str) -> int:
    """Compare ISO datetimes as ordered integers (drop 'Z', 'T', '-', ':')."""
    return int(''.join(c for c in ts if c.isdigit())[:14] or '0')


def format_ext(path: str) -> str:
    return path.rsplit('.', 1)[-1].lower()


def plan_actions(dups: list[list[dict]]) -> list[dict]:
    """Return list of {keeper_id, dropper_id, formats_to_add: [path,...]}."""
    actions = []
    for entries in dups:
        keeper, droppers = pick_keeper(entries)
        keeper_exts = {format_ext(p) for p in keeper['formats']}
        for d in droppers:
            adds = []
            for fmt_path in d['formats']:
                ext = format_ext(fmt_path)
                if ext not in keeper_exts:
                    adds.append(fmt_path)
                    keeper_exts.add(ext)
            actions.append({
                "keeper_id": keeper['id'],
                "keeper_title": keeper['title'],
                "dropper_id": d['id'],
                "dropper_formats": d['formats'],
                "formats_to_add": adds,
            })
    return actions


def execute(actions: list[dict]) -> None:
    for i, a in enumerate(actions, 1):
        print(f"  [{i}/{len(actions)}] keep={a['keeper_id']} drop={a['dropper_id']} — {a['keeper_title'][:60]}",
              file=sys.stderr)
        for fmt_path in a['formats_to_add']:
            print(f"      + add_format {fmt_path}", file=sys.stderr)
            # fmt_path is the in-container path, already under LIBRARY_CTR, no extra mount needed
            cp = one_shot([
                "add_format",
                f"--library-path={LIBRARY_CTR}",
                str(a['keeper_id']),
                fmt_path,   # passed as standalone argv — quotes/apostrophes safe
            ])
            if cp.returncode != 0:
                print(f"      WARN add_format failed: {cp.stderr[:200]}", file=sys.stderr)
        cp = one_shot([
            "remove",
            f"--library-path={LIBRARY_CTR}",
            str(a['dropper_id']),
        ])
        if cp.returncode != 0:
            print(f"      WARN remove failed: {cp.stderr[:200]}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    if not (args.dry_run or args.execute):
        sys.exit("Pass --dry-run or --execute")

    cp = subprocess.run(
        ["podman", "ps", "--filter", f"name={EBOOKS_CTR}", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    if EBOOKS_CTR in cp.stdout:
        sys.exit(f"{EBOOKS_CTR} is running — stop it first: ./scripts/down.sh ebooks")

    print("→ Loading library…", file=sys.stderr)
    books = list_library()
    print(f"  {len(books)} entries", file=sys.stderr)

    dups = find_dups(books)
    print(f"→ {len(dups)} duplicate groups", file=sys.stderr)

    actions = plan_actions(dups)
    print(f"→ {len(actions)} merge actions ({sum(len(a['formats_to_add']) for a in actions)} add_format ops)",
          file=sys.stderr)

    print("\n=== Plan ===")
    for a in actions:
        adds = f" +{len(a['formats_to_add'])} fmt" if a['formats_to_add'] else ""
        print(f"  keep={a['keeper_id']:5d}  drop={a['dropper_id']:5d}{adds}  {a['keeper_title'][:70]}")

    if args.dry_run:
        print("\nDry-run complete — re-run with --execute to apply.")
        return

    print("\n=== Executing ===")
    execute(actions)
    print(f"\n✓ Done. Removed {len(actions)} duplicate entries. Restart ebooks.")


if __name__ == "__main__":
    main()
