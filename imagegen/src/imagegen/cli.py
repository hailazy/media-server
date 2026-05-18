"""imagegen CLI — the generic transport surface.

Owns: env, prompt assembly from --prepend-file, cache check/store, ledger,
output writes, dry-run. Does NOT own: prompt content, style anchors, the
Forge-vs-cloud routing decision. Those belong to the consuming skill.

Exit codes (STABLE — see README):
  0 ok | 1 config/usage error | 2 provider/API failure
  3 no images produced | 4 unknown provider
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, cache, ledger
from .io import load_dotenv, resolve_output_path, write_bytes
from .providers import available, get_provider
from .spec import GenSpec


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="imagegen",
        description="Shared cloud image-gen core (cache + cost ledger). "
        "Prompt construction and provider routing belong to the caller.",
    )
    p.add_argument("prompt", help="Fully-constructed prompt (caller owns content)")
    p.add_argument("--provider", default="gpt-image-2",
                   help=f"one of: {', '.join(available())}")
    p.add_argument("--model", default="", help="override provider default model")
    p.add_argument("--out", type=Path, default=None, help="output file path")
    p.add_argument("--quality", default="low",
                   help="provider quality tier (gpt-image-2: low|medium|high|auto)")
    p.add_argument("--size", default="1024x1024", help="WxH or provider keyword")
    p.add_argument("--count", type=int, default=1, dest="n")
    p.add_argument("--format", default="jpeg", dest="output_format",
                   help="jpeg|png|webp")
    p.add_argument("--compression", type=int, default=85,
                   dest="output_compression", metavar="0-100")
    p.add_argument("--moderation", default="low",
                   help="provider moderation level (ignored if unsupported)")
    p.add_argument("--seed", type=int, default=None,
                   help="ignored by providers without seed support")
    p.add_argument("--negative-prompt", default="", dest="negative_prompt",
                   help="ignored by providers without negative-prompt support")
    p.add_argument("--stream", action="store_true",
                   help="stream partial previews (bypasses cache)")
    p.add_argument("--partial-images", type=int, default=2,
                   dest="partial_images", metavar="0-3")
    p.add_argument("--edit-ref", type=Path, default=None,
                   help="reference image → edit/img2img mode")
    p.add_argument("--prepend-file", type=Path, default=None,
                   help="prepend this file's text + blank line to the prompt "
                        "(style anchors live in the CALLER's repo, not here)")
    p.add_argument("--project", default="",
                   help="cost-ledger attribution tag (e.g. IC, ST, LE)")
    p.add_argument("--no-cache", action="store_true", dest="no_cache",
                   help="skip cache lookup AND store (alias: --force)")
    p.add_argument("--force", action="store_true",
                   help="alias for --no-cache (fresh roll)")
    p.add_argument("--env-file", type=Path, default=None,
                   help="load OPENAI_API_KEY etc. from this .env (setdefault)")
    p.add_argument("--dry-run", action="store_true",
                   help="print spec + cost estimate, do not call the provider")
    p.add_argument("--version", action="version",
                   version=f"imagegen {__version__}")
    return p.parse_args(argv)


def _build_prompt(text: str, prepend_file: Path | None) -> str:
    if prepend_file is None:
        return text
    if not prepend_file.exists():
        raise FileNotFoundError(f"--prepend-file not found: {prepend_file}")
    return f"{prepend_file.read_text().strip()}\n\n{text}"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.env_file:
        load_dotenv(args.env_file)

    try:
        prompt = _build_prompt(args.prompt, args.prepend_file)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        provider = get_provider(args.provider)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    spec = GenSpec(
        prompt=prompt,
        provider=args.provider,
        model=args.model,
        size=args.size,
        quality=args.quality,
        n=args.n,
        output_format=args.output_format,
        output_compression=args.output_compression,
        moderation=args.moderation,
        seed=args.seed,
        negative_prompt=args.negative_prompt,
        stream=args.stream,
        partial_images=args.partial_images,
        edit_ref=args.edit_ref,
    )

    est = provider.estimate_cost(spec)
    print(f"[imagegen] provider={spec.provider} mode={spec.mode} "
          f"quality={spec.quality} size={spec.size} count={spec.n}")
    print(f"[imagegen] estimated cost: ~${est:.4f}")
    print(f"[imagegen] prompt preview: {prompt[:120].strip()}...")

    if args.dry_run:
        print("[imagegen] --dry-run, exiting")
        return 0

    no_cache = args.no_cache or args.force
    cacheable = cache.is_cacheable(spec) and not no_cache
    key = cache.cache_key(spec) if cacheable else ""

    # --- cache hit path ---
    if cacheable:
        hit = cache.lookup(key)
        if hit is not None:
            out_path = resolve_output_path(args.out, spec.output_format, 0)
            write_bytes(out_path, hit.read_bytes())
            ledger.record(provider=spec.provider, model=spec.model or provider.default_model,
                          quality=spec.quality, size=spec.size, n=spec.n,
                          project=args.project, est_cost=est, cache_hit=True)
            print(f"[imagegen] cache hit → {out_path} ($0.00)")
            return 0

    # --- generate path ---
    try:
        results = list(provider.generate(spec))
    except (RuntimeError, FileNotFoundError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — surface any SDK/provider failure
        print(f"ERROR: provider call failed: {exc}", file=sys.stderr)
        return 2

    saved: list[Path] = []
    final_for_cache: Path | None = None
    for res in results:
        if res.is_partial:
            base = resolve_output_path(args.out, spec.output_format, 0)
            ppath = base.parent / f"{base.stem}.partial_{res.partial_index}{base.suffix}"
            write_bytes(ppath, res.data)
            print(f"[imagegen] partial {res.partial_index}: {ppath}")
            continue
        out_path = resolve_output_path(args.out, spec.output_format, res.index)
        write_bytes(out_path, res.data)
        saved.append(out_path)
        final_for_cache = out_path
        print(f"[imagegen] saved: {out_path}")

    if not saved:
        print("ERROR: no images produced", file=sys.stderr)
        return 3

    if cacheable and final_for_cache is not None:
        cache.store(key, final_for_cache, spec.output_format)

    ledger.record(provider=spec.provider, model=spec.model or provider.default_model,
                  quality=spec.quality, size=spec.size, n=spec.n,
                  project=args.project, est_cost=est, cache_hit=False)
    print(f"[imagegen] done — {len(saved)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
