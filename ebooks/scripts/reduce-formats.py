#!/usr/bin/env python3
"""
Reduce multi-format library entries to a single "richest" format per book.

Rules:
  - Vietnamese books (lang=vie OR title/authors contain VN chars):
        EPUB > AZW3 > KEPUB > MOBI > TXT > RTF
  - Everything else (default English / WORDWISE collection):
        AZW3 > EPUB > KEPUB > MOBI > TXT > RTF
  - Comic books (CBZ/CBR present): keep comic + PDF (no text reduction)
  - PDF + text mix (no comic): flagged NEEDS_REVIEW — user decides whether PDF
        is a "designed" layout (keep PDF) or text fallback (keep text).

Requires home-ebooks DOWN. Runs via one-shot container (argv form, safe with
filenames containing quotes/apostrophes).

Usage:
  ./reduce-formats.py --dry-run
  ./reduce-formats.py --execute
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

VN_CHARS = set(
    'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ'
)
# Strong VN tokens — single occurrence is enough (non-English orthography).
VN_STRONG = {
    'khong', 'duoc', 'nguoi', 'nhung', 'tieng', 'dieu', 'cuoc', 'truyen',
    'nhieu', 'vao', 'viet', 'sach', 'thuyen', 'thuy', 'gioi', 'gioi',
    'thuong', 'truoc', 'thanh', 'minh', 'chung', 'nhau', 'biet', 'thuong',
    'cuoi', 'cuoc', 'phai', 'nuoc', 'thang', 'ngay', 'duong', 'thien',
    'vuong', 'hoang', 'phap', 'thuat', 'quoc', 'manh', 'chua', 'thuyen',
    'kinh', 'duc', 'dien', 'huu', 'vien', 'binh', 'tho', 'thoa', 'lien',
    'chan', 'than', 'tam', 'long', 'mau', 'mat', 'cong', 'pho', 'mon',
    'phu', 'cung', 'cuoc', 'thoi', 'thay', 'noi', 'tinh', 'song', 'tap',
    'phan', 'tien', 'tai', 'ngoai', 'hoa', 'sao', 'qua', 'roi', 'them',
    'choi', 'sang', 'hieu', 'nghe', 'chinh', 'vit', 'buoc', 'quan',
}
# Weak VN tokens — need ≥2 hits to count (ambiguous with English/other langs).
VN_WEAK = {
    'cua', 'voi', 'cho', 'mot', 'va', 'la', 'co', 'do', 'di', 'em',
    'anh', 'chi', 'ba', 'ong', 'cau', 'con', 'thu', 'mo', 'nha', 'doi',
    'lam', 'le', 'so',
}
# Vietnamese family-name patterns (stripped diacritics).
VN_SURNAMES = {
    'nguyen', 'tran', 'le', 'pham', 'hoang', 'huynh', 'phan', 'vu',
    'vo', 'dang', 'bui', 'do', 'ho', 'ngo', 'duong', 'ly', 'truong',
    'mai', 'dinh', 'cao', 'dao', 'chau', 'lam', 'thai', 'ta', 'luu',
    'kim', 'tang', 'kieu', 'doan', 'trinh', 'lai', 'lieu',
}
COMIC = {'cbz', 'cbr'}
TEXT_RANK_VN = ['epub', 'azw3', 'kepub', 'mobi', 'txt', 'rtf']
TEXT_RANK_EN = ['azw3', 'epub', 'kepub', 'mobi', 'txt', 'rtf']


def one_shot(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [
        "podman", "run", "--rm",
        "-v", f"{LIBRARY_HOST}:{LIBRARY_CTR}:z",
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
        "--fields=id,title,authors,languages,formats",
        "--for-machine", "--limit=999999",
    ])
    if cp.returncode != 0:
        sys.exit(f"calibredb list failed:\n{cp.stderr}")
    return json.loads(cp.stdout)


def is_vietnamese(book: dict) -> bool:
    # 1. Explicit Vietnamese language metadata
    langs = book.get('languages') or []
    if any(l.lower() in ('vie', 'vi', 'vietnamese') for l in langs):
        return True
    title = book['title']
    # calibredb returns authors as a "Author1 & Author2" string (NOT a list)
    raw_authors = book.get('authors') or ''
    authors = [a.strip() for a in raw_authors.split('&') if a.strip()] if isinstance(raw_authors, str) else list(raw_authors)
    text = title + ' ' + ' '.join(authors)
    # 2. Vietnamese-specific diacritics
    if any(c in VN_CHARS for c in text):
        return True
    # 3. Vietnamese author surname (first or last token of any author name)
    for a in authors:
        tokens = [t.lower().strip(",.") for t in a.split()]
        if tokens and (tokens[0] in VN_SURNAMES or tokens[-1] in VN_SURNAMES):
            return True
    # 4. Title tokens: 1 STRONG hit OR ≥2 WEAK hits = Vietnamese
    title_tokens = {t.lower().strip(",.!?;:()\"'-_") for t in title.split()}
    if title_tokens & VN_STRONG:
        return True
    if len(title_tokens & VN_WEAK) >= 2:
        return True
    return False


def format_ext(path: str) -> str:
    return path.rsplit('.', 1)[-1].lower()


def decide(book: dict) -> dict:
    """Return {'keep': set, 'drop': set, 'review': bool}."""
    exts = {format_ext(f) for f in book['formats']}

    # Comic books: keep CBZ/CBR + PDF, drop MOBI/text
    if exts & COMIC:
        keep = exts & (COMIC | {'pdf'})
        drop = exts - keep
        return {'keep': keep, 'drop': drop, 'review': False}

    # PDF mixed with text (and no comic) → manual review
    if 'pdf' in exts and (exts - {'pdf'}):
        return {'keep': exts, 'drop': set(), 'review': True}

    # PDF only → keep
    if exts == {'pdf'}:
        return {'keep': {'pdf'}, 'drop': set(), 'review': False}

    # Pure text → keep richest per language
    rank = TEXT_RANK_VN if is_vietnamese(book) else TEXT_RANK_EN
    winner = next((e for e in rank if e in exts), None)
    if winner is None:
        return {'keep': exts, 'drop': set(), 'review': False}
    return {'keep': {winner}, 'drop': exts - {winner}, 'review': False}


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

    plan_drop = []        # (book, [exts to drop])
    plan_review = []      # books needing manual decision
    skipped = 0

    for b in books:
        d = decide(b)
        if d['review']:
            plan_review.append(b)
        elif d['drop']:
            plan_drop.append((b, sorted(d['drop'])))
        else:
            skipped += 1

    fmt_count = sum(len(drops) for _, drops in plan_drop)
    print(f"\n=== Plan ===")
    print(f"  Books to reduce: {len(plan_drop)}  ({fmt_count} formats to remove)")
    print(f"  Books skipped (already 1 format): {skipped}")
    print(f"  Books needing review (PDF mix):  {len(plan_review)}")

    if plan_review:
        print(f"\n=== NEEDS_REVIEW (PDF + text, manual decision needed) ===")
        for b in plan_review:
            exts = sorted(format_ext(f) for f in b['formats'])
            print(f"  id={b['id']:5d}  [{'+'.join(exts)}]  {b['title'][:70]}")

    if args.dry_run:
        # Sample for each reduction type
        print(f"\n=== Sample reductions (5 per pattern) ===")
        by_pattern: dict[tuple, list] = {}
        for b, drops in plan_drop:
            kept = sorted(set(format_ext(f) for f in b['formats']) - set(drops))
            key = (tuple(kept), tuple(drops))
            by_pattern.setdefault(key, []).append(b)
        for (kept, drops), bs in sorted(by_pattern.items(), key=lambda x: -len(x[1]))[:8]:
            print(f"\n  Pattern: keep [{'+'.join(kept)}] drop [{'+'.join(drops)}]  ({len(bs)} books)")
            for b in bs[:3]:
                vn = "VN" if is_vietnamese(b) else "EN"
                print(f"    [{vn}] id={b['id']:5d}  {b['title'][:60]}")
        print("\nDry-run complete — re-run with --execute to apply.")
        return

    # Execute
    print(f"\n=== Executing ===")
    for i, (b, drops) in enumerate(plan_drop, 1):
        if i % 100 == 0 or i == 1:
            print(f"  [{i}/{len(plan_drop)}] id={b['id']} -{drops}", file=sys.stderr)
        for ext in drops:
            cp = one_shot([
                "remove_format",
                f"--library-path={LIBRARY_CTR}",
                str(b['id']),
                ext.upper(),  # Calibre format codes are uppercase
            ])
            if cp.returncode != 0:
                print(f"  WARN id={b['id']} remove_format {ext} failed: {cp.stderr[:200]}",
                      file=sys.stderr)
    print(f"\n✓ Done. Removed {fmt_count} format files from {len(plan_drop)} books.")
    print(f"  {len(plan_review)} PDF-mix books left for manual review.")


if __name__ == "__main__":
    main()
