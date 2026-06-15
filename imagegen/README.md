# imagegen

Shared, provider-pluggable **cloud** image-gen core with a content-hash cache
and a cost ledger. One hardened place for the fragile bits, so every consumer
repo doesn't re-hand-roll (and re-break) the same SDK transport.

> **This README is the contract.** If you are a skill author (or a future Claude
> session) integrating or extending `imagegen`, read §3 (DO/DON'T) and §7
> (Extending) before writing code. The seam is deliberate; honoring it is what
> keeps this tool thin.

---

## 1. What imagegen is / is NOT

**IS**

- A provider-pluggable transport: `GenSpec` in → image files out.
- A cost-dedup **cache** (identical request → never paid twice).
- A **cost ledger** (per-`--project` spend, one query away).
- The single owner of the `openai` SDK churn surface.

**IS NOT**

- A prompt builder. It does not know your domain. Callers pass a
  fully-constructed prompt.
- A router. It does not decide "Forge vs cloud" — the *caller's skill* does.
- A Forge/local replacement. Forge stays where it is; `imagegen` is the cloud
  lane only. (A `ForgeProvider` *could* be added — see §7 — but is intentionally
  not built in v1.)
- A daemon. It's a CLI. State lives in SQLite, not a process.

Why a CLI and not an MCP server: image gen is an occasional, explicit action,
not an always-available capability. A CLI costs zero idle context and is shelled
out exactly like the script it replaced. An MCP tool would load into context for
its whole registered scope and imply a persistent process — rejected.

---

## 2. Quickstart

```bash
# install (editable — source stays in this repo)
cd ~/Projects/home-server/imagegen && pip install --user -e .

# generate (key must be in the environment; see §6)
imagegen "a weathered brass key on black velvet, studio light" \
  --quality low --project demo --out /tmp/key.jpg

# estimate only, no spend
imagegen "..." --quality high --count 4 --dry-run
```

`imagegen` lands at `~/.local/bin/imagegen`.

---

## 3. The Contract — DO / DON'T for skill authors

**DO**

- **Pass a fully-constructed prompt.** Build it in your skill/repo.
- **Put style anchors in YOUR repo** and pass `--prepend-file PATH`. The anchor
  is your domain knowledge; it must not live in this core. (IC does exactly
  this: `.claude/skills/concept-gen/ic_anchor.txt`.)
- **Tag every call with `--project`.** It's the only thing that makes the cost
  ledger useful across consumers.
- **Check the exit code** (§8). Don't parse stdout for success.
- **Treat the cache as automatic.** Identical spec is deduped for free; reach
  for `--no-cache` only when you explicitly want a fresh roll.
- **Own the Forge-vs-cloud decision in your skill.** `imagegen` is the cloud
  lane; if a task should go to local Forge, your skill calls Forge directly.

**DON'T**

- **Don't add prompt/anchor/routing logic to this package.** That's the seam.
  If you feel the urge, you're solving it in the wrong layer.
- **Don't assume `--seed` or `--negative-prompt` do anything.** They're in
  `GenSpec` for forward-compat; GPT Image 2 ignores both. Only rely on a field
  if the *target provider* documents it.
- **Don't hardcode model names in skills.** Let the provider default win; pass
  `--model` only for a deliberate override.
- **Don't unpin `openai`** to fix an unrelated problem. See §9.
- **Don't bypass the cache "to be safe."** That defeats the one feature that
  pays for this tool's existence on a paid API.

---

## 4. CLI reference

| Flag | Default | Notes |
|---|---|---|
| `prompt` (positional) | — | Fully-constructed. Caller owns content. |
| `--provider` | `gpt-image-2` | Registered providers only. |
| `--model` | provider default | Deliberate override only. |
| `--out PATH` | `./imagegen_<ts>.<fmt>` | `IMAGEGEN_OUT_DIR` sets the default dir. |
| `--quality` | `low` | Provider tier (gpt-image-2: `low\|medium\|high\|auto`). |
| `--size` | `1024x1024` | `WxH` or provider keyword. |
| `--count N` | `1` | >1 bypasses cache (see §5). |
| `--format` | `jpeg` | `jpeg\|png\|webp`. |
| `--compression` | `85` | JPEG/WebP 0–100. |
| `--moderation` | `low` | Ignored by providers without moderation. |
| `--seed` | none | Ignored unless provider supports it. |
| `--negative-prompt` | "" | Ignored unless provider supports it. |
| `--stream` | off | Partial previews; bypasses cache. |
| `--partial-images` | `2` | 0–3 when streaming. |
| `--edit-ref PATH` | — | Reference/img2img mode. |
| `--prepend-file PATH` | — | Prepend caller's anchor text + blank line. |
| `--project TAG` | "" | Ledger attribution. Always set it. |
| `--no-cache` / `--force` | off | Skip lookup **and** store. |
| `--env-file PATH` | — | `setdefault` load a `.env` (never clobbers exported vars). |
| `--dry-run` | off | Print spec + cost, no call. |

### 4a. Batch mode (50% cost discount, 24h async)

Use when you have N prompts known ahead of time and can wait up to 24h.
Image gen Batch API gives 50% off vs sync. Skip for interactive iteration.

```bash
# 1. Write prompts.jsonl — one JSON spec per line
echo '{"prompt": "iron cradle moss-covered phase A", "quality": "low"}' > prompts.jsonl
echo '{"prompt": "iron cradle exposed phase B", "quality": "medium", "size": "1536x1024"}' >> prompts.jsonl

# 2. Submit
imagegen batch submit prompts.jsonl --project IC --env-file .env
# → prints batch_id, n_requests, estimated cost

# 3. Check status anytime
imagegen batch status batch_abc123 --env-file .env
# → "in_progress | completed | failed", progress counts

# 4. Fetch when status=completed
imagegen batch fetch batch_abc123 --out-dir ./out/ --env-file .env
# → saves images as <custom_id>.jpeg
```

JSONL fields (`prompt` required, rest optional with GenSpec defaults):
`prompt`, `model`, `size`, `quality`, `n`, `output_format`, `output_compression`,
`moderation`, `extra`. `edit_ref` NOT supported (Batch API can't upload refs).

---

## 5. Caching & cost ledger

**Cache key** = SHA-256 over: provider, model, prompt, size, quality, mode,
format, compression, moderation, seed, negative_prompt, **edit-ref file hash**,
sorted `extra`. Files live in `data/cache/<key>.<fmt>`, indexed in
`data/cache.db`.

**Not determinism — cost dedup.** GPT Image 2 has no seed. The cache returns the
*previously generated* image for an identical spec so the same request is never
paid for twice (e.g. a recurring hard-metaphor word across LE deck rebuilds).
Want a different image? `--no-cache`.

**v1 limitation:** only `count==1`, non-streaming requests are cached. `--count
> 1` and `--stream` always hit the provider.

**Ledger** — one row per invocation:

```bash
sqlite3 data/ledger.db \
  "select project,count(*),round(sum(est_cost),4) from calls group by project"
```

`data/` is gitignored. `IMAGEGEN_DATA_DIR` relocates both DBs + the cache store.

---

## 6. Configuration

`OPENAI_API_KEY` is read from the process environment **first**.

**Locked convention — per-repo `--env-file`** (decided 2026-05-18): each
consumer keeps its key in its OWN repo `.env` (gitignored) and passes
`--env-file /path/to/that/repo/.env`. The IC `concept-gen` skill does exactly
this (`--env-file "$HOME/Projects/IronCradle/.env"`). New consumers (ST, LE)
**follow this same pattern** — do not centralize into `home-server/.env`.

Rationale: `imagegen` is shelled out from arbitrary repo directories. A central
`home-server/.env` only reaches the process env when the shell happened to
source it (claude.sh / zsh autoload, both cwd-gated to home-server) — fragile
across repos. Explicit `--env-file` is reliable from anywhere and keeps each
consumer's spend boundary obvious.

Loading is `setdefault` — an already-exported `OPENAI_API_KEY` always wins, so
`export` still works for ad-hoc use. Never commit a real key; `.env.example` is
the only tracked env file.

---

## 7. Extending

### Add a provider — worked example: `ForgeProvider` (intentionally not in v1)

This is the LE local lane (`Learning_English/scripts/sd_client.py`, Forge A1111
`POST /sdapi/v1/txt2img`). Building it later requires **no change to the core or
to `GenSpec`** — that's the proof the seam is right:

```python
# src/imagegen/providers/forge.py
import base64, os, requests
from collections.abc import Iterator
from ..spec import GenSpec, ImageResult
from . import ImageProvider, register

@register
class ForgeProvider(ImageProvider):
    name = "forge"
    default_model = "NoobAI-XL-v1.1"

    def generate(self, spec: GenSpec) -> Iterator[ImageResult]:
        url = os.environ.get("FORGE_URL", "http://localhost:7860").rstrip("/")
        payload = {
            "prompt": spec.prompt,
            "negative_prompt": spec.negative_prompt,   # Forge USES this
            "width": int(spec.size.split("x")[0]),
            "height": int(spec.size.split("x")[1]),
            "seed": spec.seed if spec.seed is not None else -1,  # Forge USES this
            **spec.extra,                                # steps/cfg/sampler...
        }
        r = requests.post(f"{url}/sdapi/v1/txt2img", json=payload, timeout=300)
        r.raise_for_status()
        yield ImageResult(base64.b64decode(r.json()["images"][0]))

    # edit() not overridden → ABC raises a clear NotImplementedError.

    def estimate_cost(self, spec: GenSpec) -> float:
        return 0.0  # local GPU, no per-call cost
```

Then register it by importing in `providers/__init__.py` (bottom, alongside
`gpt_image_2`). Note how `seed` / `negative_prompt` — dead for GPT Image 2 —
come alive here with **no GenSpec edit**. That's the union-superset design
working as intended.

### Add a mode

Modes are derived, not enumerated: `GenSpec.mode` is `"edit"` iff `edit_ref` is
set, else `"generate"`. A genuinely new mode (e.g. `inpaint` needing a mask)
adds an optional `GenSpec` field + a provider method — keep the field optional
so existing providers and callers are untouched.

---

## 8. Stability contract

**Stable** (consumers may depend on these; breaking them is a major bump):

- CLI flag names + semantics in §4.
- `GenSpec` field names + meaning in `spec.py`.
- Exit codes: `0` ok · `1` config/usage error · `2` provider/API failure ·
  `3` no images produced · `4` unknown provider.

**Internal** (may change without notice): cache file layout, DB schemas,
provider internals, module boundaries below the CLI.

Versioning intent: semver-ish. v1 = this contract. Deferred to a later version
(documented here so nobody re-litigates): retry/backoff, OpenAI Batch API,
multi-store dedup, `ForgeProvider`.

---

## 9. Gotchas — *why this tool exists*

The `openai` SDK **churns and silently changes image API signatures**. Observed
in this codebase (brain `83769887d0a6`, verified 2026-05-14 via
`inspect.signature`):

- `images.edit()` accepts `{image, mask, input_fidelity}`; `images.generate()`
  accepts `{moderation, style}`. They are **not** interchangeable.
- An earlier note claiming `input_fidelity` crashes `images.edit` was *wrong*
  for the current SDK — it's edit-only.
- `output_compression` / `moderation` were missing from earlier integrations and
  silently dropped.

Every consumer hand-rolling this = re-hitting these the day the SDK moves.
Therefore:

- **`openai` is pinned exact** in `pyproject.toml` (`==2.36.0`).
- **Do not bump the pin to fix something unrelated.** A bump is its own task:
  re-verify *both* `images.generate` and `images.edit` paths
  (`--dry-run` then a real `low`-quality call, then an `--edit-ref` call), then
  update this section with the newly verified version + date.
- The single moderation-filter for the edit path lives in one place
  (`providers/gpt_image_2.py::edit`). If the SDK changes which params `edit`
  rejects, that's the **only** line to touch — across all consumers.

---

*Provenance: extracted from `IronCradle/tools/concept_gen.py` (GPT Image 2) +
informed by `Learning_English/scripts/sd_client.py` (Forge) — the two real
hand-rolled duplicates. Plan: `~/.claude/plans/update-l-n-l-t-gdd-merry-dahl.md`.
Research: brain `3da4805e0c0b`.*
