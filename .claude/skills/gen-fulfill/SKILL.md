---
name: gen-fulfill
description: "Resolve queued local-Forge image-generation tickets on the home-server hub, one by one, with deep Forge expertise (NoobAI recipes, ADetailer, ControlNet, checkpoint/VAE switching, img2img, per-seed loops). Reads tickets from the external image-gen queue, generates, judges, writes results + a receipt back to each ticket's destination, and crystallizes winning recipes. USE THIS whenever Hải says 'fulfill the image queue', 'process gen tickets', 'gen-fulfill', 'drain the forge queue', 'resolve image requests', or after the gen-art skill reports it queued a Forge ticket. This is the ONLY place the hub's Forge expertise lives — satellites just file tickets."
argument-hint: "[--all] [--ticket <id|path>] [--max N] [--dry-run]"
allowed-tools: Bash, Read, mcp__haingt-brain__brain_recall, mcp__haingt-brain__brain_save
---

# gen-fulfill — Forge image-ticket fulfillment (home-server hub)

Drain the local-Forge request queue with the expertise that lives at the hub, so
satellite projects (chimera, future Godot games) never re-derive it. A satellite's
`gen-art` skill writes a self-contained ticket; this skill resolves it.

## 🔒 OPSEC contract — read first, it is load-bearing

This skill is committed to the **PUBLIC** `home-server` repo. It knows **HOW** to
drive Forge — generic recipes, ADetailer, ControlNet, VRAM, podman, the preset
library. It must contain **NO** project identity, character names, shipping titles,
or NSFW prompt text. All domain content arrives **inside the ticket** and is treated
as **opaque payload**.

- The raw 18+ prompt lives only in the external queue and is read **only** by
  `run_forge.py` (a subprocess). `queue_cli.py list/info` print **metadata only** —
  so the prompt never enters this conversation's context. **Do not** cat/Read a raw
  ticket JSON to inspect the prompt; you don't need it, and pulling it in defeats the
  firewall.
- Never copy ticket prompt text into any committed file, preset, receipt that lands
  in this repo, or brain memory. Brain/preset writes = **settings + verdict only,
  codename only**.

## Where things live

```
QUEUE (external, OPSEC-safe):  ~/.local/share/imagegen-queue/{inbox,processing,done,failed}/  + index.db
ENGINE:  imagegen.forge_engine  (the shared Forge client)   ·  imagegen.queue  (ticket/queue/index)
PRESETS: ~/Projects/home-server/imagegen/presets/<name>.toml  (generic recipes, public)
SCRIPTS: this skill's scripts/  →  queue_cli.py (queue + index)  ·  run_forge.py (gen driver)
```

`SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts`

## The resolve loop

Process tickets oldest/priority-first. For each: recall → guard → ensure Forge →
generate → judge → iterate → receipt → archive → learn. Drive it with the two
scripts; bring your judgment to the gen→judge→iterate part.

### 0. Survey the queue

```bash
python3 $SK/queue_cli.py sweep            # re-queue any crashed processing/ tickets (>1h)
python3 $SK/queue_cli.py list             # metadata-only JSON of pending tickets
```
Pick targets: `--ticket <id>` → that one; `--all` → every pending (cap with `--max`);
default → the single oldest. `--dry-run` → show what you'd do, generate nothing.

### 1. Recall (Component 4 — learn before redoing)

For the ticket's `preset` + `project_tag` + `spec_hash` (from `list`):

```bash
python3 $SK/queue_cli.py recall <project_tag> --hash <spec_hash>
```
- `exact` hit (same spec already fulfilled) → tell Hải; offer to **link the prior
  output instead of regenerating** unless he wants a fresh roll. (Forge has seeds, so
  this is true reuse.)
- `recent` rows → note what settings/verdicts worked before; **pre-apply winning
  knobs** rather than rediscovering (e.g. "last 3 Round-0s used cfg 7, cfg 6 drifted").

Then pull the *semantic* tier — recipes + cross-project lessons:
```
brain_recall("<preset> Forge NoobAI recipe <project_tag> what worked", project=<project_tag>)
```
The `preset` .toml carries the settled settings; brain carries the "why / what drifts".

### 2. Guard VRAM + ensure Forge is up

```bash
~/Projects/home-server/scripts/vram-guard.sh check forge   # exit≠0 = hard refuse
```
Hard-refuse → **do not fail the ticket**; leave it (or move back to inbox) and tell
Hải VRAM is tight (likely Jellyfin transcoding). Soft-warn → proceed.

Forge readiness (bring it up if needed):
```bash
curl -sf http://127.0.0.1:7860/sdapi/v1/sd-models >/dev/null \
  || ~/Projects/home-server/scripts/up.sh forge
# then poll until ready:
for i in $(seq 1 30); do curl -sf http://127.0.0.1:7860/sdapi/v1/sd-models >/dev/null && break; sleep 4; done
```

### 3. Claim + generate

```bash
CLAIMED=$(python3 $SK/queue_cli.py claim <ticket-path>)   # inbox → processing
RESULT=$(python3 $SK/run_forge.py "$CLAIMED")             # drives forge_engine; prints JSON
echo "$RESULT"                                             # {files, seeds, settings}
```
`run_forge.py` resolves the checkpoint, switches VAE/clip-skip, injects LoRA tokens
from the ticket, runs the per-seed `n_iter=1` loop with ADetailer/ControlNet/img2img
as the ticket specifies, and saves PNGs to the ticket's `dest`. It reads the raw
prompt itself — you never see it.

### 4. Judge + iterate

Read a sample of the produced `files` (use the Read tool on a couple of the PNGs) and
judge them against the ticket's **`judge`** criterion (from `list`/`info`). The judge
string is the requester's definition of "good" (e.g. "on-model + unambiguously adult;
reject schoolgirl drift") — apply it generically; do not inject your own aesthetic.

- Passes → go to step 5.
- Fails and `rounds < max_rounds` → re-roll. The cheapest lever is a fresh seed band:
  `python3 $SK/run_forge.py "$CLAIMED" --seed-offset <count*round>`. If the ticket's
  `notes` name a specific knob to nudge, follow it. Track how many rounds you used.
- Fails at `max_rounds` → archive `failed` with a short reason; tell Hải what drifted.

### 5. Receipt (loop-closer, written INTO the project)

Write a markdown receipt to the ticket's `receipt_dest` so the project accumulates its
own gen ledger. Settings come straight from `run_forge.py`'s `settings` — **no prompt
text**. Template:

```markdown
# Gen receipt — <id>
ticket: <id> · project: <project_tag> · preset: <preset>
checkpoint: <…> | vae: <…> | clip_skip: <…>
sampler: <…> | scheduler: <…> | steps: <…> | cfg: <…> | size: <…>
lora: <…> | adetailer: <…> | controlnet: <…> | img2img: <…>
seeds: <…>
rounds: <N> | verdict: <passed|partial|failed> (<kept>/<total> kept)
files:
  - <abs path>  (kept|rejected)
fulfilled: <iso>
```

### 6. Archive + log (Component 4 — the learning tier)

```bash
python3 $SK/queue_cli.py archive "$CLAIMED" done
python3 $SK/queue_cli.py record "$CLAIMED" --verdict passed --kept <K> --total <T> \
  --rounds <N> --settings-json '<settings from run_forge>' --files-json '<files>'
```
`record` writes the index row (hash + settings + verdict — never prompt). Then, **only
if a genuine pattern emerged** (a knob that reliably helps/hurts for this kind of
request), persist it:
- `brain_save(...)` — codename + settings/verdict only, e.g. "chimera Round-0: cfg7
  on-model, cfg6 drifts young; ADetailer hands mandatory". Tag it so the next recall
  finds it. **Never** dump a prompt.

### 7. Crystallize a preset (only when warranted)

If a run discovered or confirmed a reusable recipe not yet captured, update/create a
`presets/<name>.toml` (pure settings + generic tradeoff notes — see an existing preset
for the shape). This is the most-distilled, public tier. Domain-agnostic only.

## Notes & failure modes

- **One ticket at a time** — VRAM is a single GPU; serial resolution is correct and
  makes the stateful checkpoint switch race-free.
- **Forge won't come up / OOM (exit 137)** → check `mem_limit` (compose.yml) and that
  nothing else is on the GPU; report, leave the ticket in `inbox/`.
- **Checkpoint not found** → `run_forge.py` raises with the list of mounted models;
  the ticket's `checkpoint_match` is a substring — fix the ticket or mount the model.
- **ControlNet model mismatch** → `run_forge.py` resolves by substring against Forge's
  registered CN models; if it can't, Forge errors clearly. The control IMAGE is produced
  project-side and referenced by path in the ticket.
- Run the ticket's prompt/negative **faithfully** — the requester sets the content
  level (SFW or explicit) in the prompt/negative; the hub generates it as specified on
  the local GPU. The one hard wall, everywhere: no sexualization of minors — that is
  what the requesting project's age-firewall + age-QA exist to enforce.

## References
- Ticket / queue / index protocol + fields: `imagegen/src/imagegen/queue.py` (the `Ticket` dataclass is the contract).
- Forge client: `imagegen/src/imagegen/forge_engine.py`.
- Recipes: `~/Projects/home-server/imagegen/presets/` + haingt-brain.
