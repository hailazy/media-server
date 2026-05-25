#!/usr/bin/env python3
"""
Bulk-import ebooks from extracted ZIP staging into the CWA library, with
strict mtime overwrite policy.

Bypasses CWA's inotify ingest pipeline — uses `calibredb` directly inside a
one-shot container that mounts both the library and the staging folder.
Much faster than dropping 3000+ files into the watch folder.

Policy:
  NEW:      title+author not in library              → add
  NEWER:    in library AND staging mtime > lib mtime → remove old + add
  OLDER:    in library AND staging mtime ≤ lib mtime → skip
  (SAME treated as OLDER since equal mtime = no benefit)

Usage:
  ./bulk-import.py --dry-run                  # classify + report, no changes
  ./bulk-import.py --execute                  # do the work
  ./bulk-import.py --execute --limit 50       # safety throttle
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────
IMAGE        = "docker.io/crocodilestick/calibre-web-automated:latest"
EBOOKS_CTR   = "home-ebooks"
LIBRARY_HOST = Path("/home/haint/Data/Calibre Library")
SOURCE_HOST  = Path("/home/haint/Downloads/Ebook-extracted")
LIBRARY_CTR  = "/calibre-library"
SOURCE_CTR   = "/staging"
EBOOK_EXTS   = {'.epub', '.mobi', '.azw3', '.azw', '.pdf', '.fb2',
                '.lit', '.lrf', '.rtf', '.djvu', '.cbz', '.cbr'}


# ─── Helpers ──────────────────────────────────────────────────────────────
def normalize(s: str) -> str:
    """Collapse to lowercase ASCII alphanumeric for robust matching.

    Strips Calibre's "[LastName, FirstName]" sort-form suffix that ebook-meta
    sometimes emits — same author, different surface text would otherwise
    miss the match.
    """
    if not s:
        return ""
    # Drop "[...]" sort-form bracketed suffix (Calibre author convention)
    import re
    s = re.sub(r'\s*\[[^\]]*\]', '', s)
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    return ''.join(c for c in s.lower() if c.isalnum())


def container_path(host_path: Path) -> str:
    """Map a host extracted-staging path to its container mount path."""
    rel = host_path.relative_to(SOURCE_HOST)
    return f"{SOURCE_CTR}/{rel}"


def run_one_shot(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Run `cmd` inside a fresh container with library + staging mounted.

    Uses --entrypoint bash to bypass s6 init (which doesn't survive in a
    non-default userns — same issue we documented in ebooks/README.md).
    """
    podman_cmd = [
        "podman", "run", "--rm",
        "-v", f"{LIBRARY_HOST}:{LIBRARY_CTR}:z",
        "-v", f"{SOURCE_HOST}:{SOURCE_CTR}:ro,z",
        "-e", "PATH=/app/calibre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "-e", "LD_LIBRARY_PATH=/app/calibre/lib",
        "--entrypoint", "/bin/bash",
        IMAGE, "-c", " ".join(cmd),
    ]
    return subprocess.run(podman_cmd, capture_output=capture, text=True)


def calibredb_list_all() -> list[dict]:
    """Return [{id, title, authors, last_modified}, ...] for the whole library."""
    cp = run_one_shot([
        "calibredb", "list",
        f"--library-path={LIBRARY_CTR}",
        "--fields=id,title,authors,last_modified",
        "--for-machine", "--limit=999999",
    ])
    if cp.returncode != 0:
        sys.exit(f"calibredb list failed:\n{cp.stderr}")
    return json.loads(cp.stdout)


def extract_meta_batch(files: list[Path]) -> dict[Path, tuple[str, str]]:
    """Run ebook-meta on every staged file in a single container invocation.

    Output format (one block per file, separated by ---):
        <relpath>
        TITLE: <title>
        AUTHOR: <author>
        ---
    """
    rels = [str(f.relative_to(SOURCE_HOST)) for f in files]
    list_input = "\n".join(rels)

    bash_script = f"""
        cd {SOURCE_CTR}
        while IFS= read -r rel; do
            echo "===PATH==="
            echo "$rel"
            ebook-meta "$rel" 2>/dev/null | grep -E '^(Title|Author\\(s\\))[[:space:]]*:'
            echo "===END==="
        done <<'PATHS_EOF'
{list_input}
PATHS_EOF
    """
    cp = subprocess.run(
        [
            "podman", "run", "--rm", "-i",
            "-v", f"{SOURCE_HOST}:{SOURCE_CTR}:ro,z",
            "-e", "PATH=/app/calibre/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "-e", "LD_LIBRARY_PATH=/app/calibre/lib",
            "--entrypoint", "/bin/bash",
            IMAGE, "-c", bash_script,
        ],
        capture_output=True, text=True,
    )
    if cp.returncode != 0:
        sys.exit(f"ebook-meta batch failed:\n{cp.stderr[:500]}")

    result: dict[Path, tuple[str, str]] = {}
    blocks = cp.stdout.split("===PATH===\n")
    for blk in blocks:
        if not blk.strip():
            continue
        lines = blk.splitlines()
        rel = lines[0].strip()
        title = author = ""
        for line in lines[1:]:
            if line.startswith("===END==="):
                break
            if line.startswith("Title"):
                title = line.split(":", 1)[1].strip()
            elif line.startswith("Author"):
                author = line.split(":", 1)[1].strip()
        result[SOURCE_HOST / rel] = (title, author)
    return result


# ─── Classification ───────────────────────────────────────────────────────
def parse_iso(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))


def classify(files: list[Path], library: list[dict],
             meta: dict[Path, tuple[str, str]]) -> list[tuple]:
    """Return [(category, file, title, author, lib_id_or_None), ...]."""
    lookup = {}
    for b in library:
        key = (normalize(b['title']), normalize(' '.join(b['authors'])))
        lookup.setdefault(key, []).append((b['id'], parse_iso(b['last_modified'])))

    plan = []
    for f in files:
        title, author = meta.get(f, ("", ""))
        if not title:
            title = f.stem  # fallback
        key = (normalize(title), normalize(author))
        matches = lookup.get(key)
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)

        if not matches:
            plan.append(("NEW", f, title, author, None))
        else:
            # Multiple library entries with same title+author = use newest
            lib_id, lib_mtime = max(matches, key=lambda x: x[1])
            if mtime > lib_mtime:
                plan.append(("NEWER", f, title, author, lib_id))
            else:
                plan.append(("OLDER", f, title, author, lib_id))
    return plan


# ─── Execution ────────────────────────────────────────────────────────────
def execute_plan(plan: list[tuple]) -> None:
    """Run remove+add for NEWER, add for NEW, skip OLDER."""
    new_files   = [container_path(p[1]) for p in plan if p[0] == "NEW"]
    newer       = [(p[4], container_path(p[1])) for p in plan if p[0] == "NEWER"]

    # 1. Remove outdated library entries first (NEWER replacements)
    if newer:
        ids = ",".join(str(i) for i, _ in newer)
        print(f"  Removing {len(newer)} outdated library entries...", file=sys.stderr)
        cp = run_one_shot([
            "calibredb", "remove",
            f"--library-path={LIBRARY_CTR}",
            ids,
        ])
        if cp.returncode != 0:
            sys.exit(f"calibredb remove failed:\n{cp.stderr}")

    # 2. Add NEW + (now-clean) NEWER files in batches of 100
    to_add = new_files + [path for _, path in newer]
    BATCH = 100
    for i in range(0, len(to_add), BATCH):
        chunk = to_add[i:i+BATCH]
        print(f"  Adding {i+1}-{i+len(chunk)} of {len(to_add)}...", file=sys.stderr)
        # Quote each path (filenames have spaces, parens)
        quoted = " ".join(f"'{p}'" for p in chunk)
        cp = run_one_shot([
            "calibredb", "add",
            f"--library-path={LIBRARY_CTR}",
            "--automerge=ignore",  # safety net — should not trigger after NEWER removals
            quoted,
        ])
        if cp.returncode != 0:
            print(f"  WARN batch {i}: {cp.stderr[:300]}", file=sys.stderr)


# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--samples", type=int, default=5)
    args = p.parse_args()

    if not (args.dry_run or args.execute):
        sys.exit("Pass --dry-run or --execute")

    # Pre-flight: home-ebooks must be DOWN (avoid SQLite lock with calibredb)
    cp = subprocess.run(
        ["podman", "ps", "--filter", f"name={EBOOKS_CTR}", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    if EBOOKS_CTR in cp.stdout:
        sys.exit(f"{EBOOKS_CTR} is running — stop it first: ./scripts/down.sh ebooks")

    print("→ Scanning source for ebooks…", file=sys.stderr)
    files = sorted(
        f for f in SOURCE_HOST.rglob('*')
        if f.is_file() and f.suffix.lower() in EBOOK_EXTS
    )
    if args.limit:
        files = files[:args.limit]
    print(f"  {len(files)} files", file=sys.stderr)

    print("→ Listing library…", file=sys.stderr)
    library = calibredb_list_all()
    print(f"  {len(library)} books", file=sys.stderr)

    print("→ Extracting metadata (this is the slow step)…", file=sys.stderr)
    # Run ebook-meta in chunks of 500 to avoid one-block heredoc bloat
    meta: dict[Path, tuple[str, str]] = {}
    CHUNK = 500
    for i in range(0, len(files), CHUNK):
        chunk = files[i:i+CHUNK]
        print(f"  meta {i+1}-{i+len(chunk)} of {len(files)}…", file=sys.stderr)
        meta.update(extract_meta_batch(chunk))

    print("→ Classifying…", file=sys.stderr)
    plan = classify(files, library, meta)

    # Summary
    counts = {"NEW": 0, "NEWER": 0, "OLDER": 0}
    for entry in plan:
        counts[entry[0]] = counts.get(entry[0], 0) + 1
    print("\n=== Classification ===")
    for k in ("NEW", "NEWER", "OLDER"):
        print(f"  {k:6s}: {counts.get(k, 0)}")

    # Samples
    print(f"\n=== Samples (up to {args.samples} per category) ===")
    for cat in ("NEW", "NEWER", "OLDER"):
        samples = [p for p in plan if p[0] == cat][:args.samples]
        for s in samples:
            mtime = datetime.fromtimestamp(s[1].stat().st_mtime, tz=timezone.utc)
            print(f"  [{cat}] {s[1].name}")
            print(f"           title={s[2]!r}")
            print(f"           author={s[3]!r}")
            print(f"           file_mtime={mtime.date()}")

    if args.dry_run:
        print("\nDry-run complete — re-run with --execute to apply.")
        return

    print("\n=== Executing plan ===")
    execute_plan(plan)
    print("\n✓ Done. Restart ebooks: ./scripts/up.sh ebooks")


if __name__ == "__main__":
    main()
