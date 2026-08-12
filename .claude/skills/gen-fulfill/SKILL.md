---
name: gen-fulfill
model: sonnet
description: "Drain the home-server local-Forge image-ticket queue with deep Forge expertise (NoobAI, ADetailer, ControlNet, img2img, per-seed loops). USE on 'fulfill the image queue', 'process gen tickets', 'gen-fulfill', 'drain the forge queue', 'resolve image requests', or after gen-art queued a Forge ticket. The ONLY place the hub's Forge expertise lives."
argument-hint: "[--all] [--ticket <id|path>] [--max N] [--dry-run]"
allowed-tools: Bash, Read, Write, Edit, mcp__haingt-brain__brain_recall, mcp__haingt-brain__brain_save
---

# gen-fulfill — Forge image-ticket fulfillment (home-server hub)

Drain the local-Forge request queue with the expertise that lives at the hub, so
satellite projects never re-derive it. A satellite's `gen-art` skill writes a
self-contained ticket, tagged with its `project_tag`; this skill resolves it.

## 🔒 OPSEC contract — read first, it is load-bearing

This skill is committed to the **PUBLIC** `home-server` repo. It knows **HOW** to
drive Forge — generic recipes, ADetailer, ControlNet, VRAM, podman, the preset
library. It must contain **NO** project identity, character names, shipping titles,
or NSFW prompt text. All domain content arrives **inside the ticket** and is treated
as **opaque payload**.

- Read tickets only through `queue_cli.py list/info`, which print metadata only —
  that is what keeps the raw 18+ prompt out of this conversation's context.
  `run_forge.py` reads it in a subprocess, so the firewall holds.
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

Shell state does not persist between Bash tool calls (only the working directory
does), so `SK` and `CLAIMED` below must be re-set in every Bash block that uses them —
open each block with `SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts`,
and in steps 4/6 re-derive the claimed ticket path (e.g.
`ls ~/.local/share/imagegen-queue/processing/*.json`) rather than assuming a variable
from an earlier call survived.

## The resolve loop

Process tickets oldest/priority-first. For each: recall → guard → ensure Forge →
generate → judge → iterate → receipt → archive → learn. Drive it with the two
scripts; bring your judgment to the gen→judge→iterate part.

### 0. Survey the queue

```bash
SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts
python3 $SK/queue_cli.py sweep            # re-queue any crashed processing/ tickets (>1h)
python3 $SK/queue_cli.py list             # metadata-only JSON of pending tickets
```
Pick targets: `--ticket <id>` → that one; `--all` → every pending (cap with `--max`);
default → the single oldest. `--dry-run` → show what you'd do, generate nothing.

### 1. Recall (Component 4 — learn before redoing)

For the ticket's `preset` + `project_tag` + `spec_hash` (from `list`):

```bash
SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts
python3 $SK/queue_cli.py recall <project_tag> --hash <spec_hash>
```
- `exact` hit (same spec already fulfilled) → tell Hải; offer to **link the prior
  output instead of regenerating** unless he wants a fresh roll. (Forge has seeds, so
  this is true reuse.) Caveat: the index stores the ticket's *base* seeds, not any
  `--seed-offset` a re-roll applied — so this reuse promise is only reproduction-accurate
  for a round-0 pass. If the prior fulfillment needed a re-roll, prefer the seeds on its
  receipt (written by `run_forge.py`, which are correct) over the indexed ones.
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
SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts
CLAIMED=$(python3 $SK/queue_cli.py claim <ticket-path>)   # inbox → processing
```
Before driving it, check the ticket's `preset` against its `.toml` in
`imagegen/presets/`: `run_forge.py` only knows the diffusion lane (txt2img/img2img) —
a processing recipe whose preset declares an `endpoint` other than those (today: only
`extras-upscale` → `/sdapi/v1/extra-single-image`) must be driven against that endpoint
directly (curl/python), skipping `run_forge.py` entirely, or it will silently load a
checkpoint and re-generate the image from the prompt instead of upscaling it in place.

Also check for a stem collision BEFORE running: `save_images` writes
`<dest>/<naming_stem>_<start+i>.png` and overwrites same-named files without warning.
Compare this ticket's `naming_stem` + `dest` against files already on disk and against
other pending tickets from `list` — gen-art's ticket builder can hand two distinct
tickets the same stem. On a collision, give this ticket a unique per-ticket stem (its
label/id) first.

For a normal diffusion ticket (fresh Bash call — re-derive both variables):
```bash
SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts
CLAIMED=$(ls ~/.local/share/imagegen-queue/processing/*.json)  # the one claimed ticket
RESULT=$(python3 $SK/run_forge.py "$CLAIMED")             # drives forge_engine; prints JSON
echo "$RESULT"                                             # {files, seeds, settings}
```
`run_forge.py` resolves the checkpoint, switches VAE/clip-skip, injects LoRA tokens
from the ticket, runs the per-seed `n_iter=1` loop, and saves PNGs to the ticket's
`dest`. It reads the raw prompt itself — you never see it. ADetailer/ControlNet are
only applied on the **txt2img** branch — on an img2img ticket the driver sends no
`alwayson` payload at all, so those toggles are silently skipped even though the
printed `settings` blob still echoes the ticket's `adetailer`/`controlnet` fields as if
they ran. Treat ADetailer/ControlNet as unverified on img2img tickets: eyeball the
result for the restore pass you expected, and say so in the receipt if it's missing.


### 4. Judge + iterate

Read a sample of the produced `files` (use the Read tool on a couple of the PNGs) and
judge them against the ticket's **`judge`** criterion (from `list`/`info`). The judge
string is the requester's definition of "good" (e.g. "on-model + unambiguously adult;
reject schoolgirl drift") — apply it generically; do not inject your own aesthetic.

- Passes → go to step 5.
- Fails and `rounds < max_rounds` → re-roll. The cheapest lever is a fresh seed band:
  `python3 $SK/run_forge.py "$CLAIMED" --seed-offset <count*round>`. If the ticket's
  `notes` name a specific knob to nudge, follow it. Track how many rounds you used.
- Fails at `max_rounds` → archive `failed` with a short reason, then `record` it too
  (`--verdict failed --kept 0 --total <T> --rounds <N>`, same archive→record ordering
  as step 6) — tell Hải what drifted. Logging failures is what lets step 1's recall
  say which knob drifted on the next ticket; an unlogged failure gets rediscovered.

### 5. Receipt (loop-closer, written INTO the project)

Write (with the Write tool) a markdown receipt to the ticket's `receipt_dest` so the
project accumulates its own gen ledger. Settings come straight from `run_forge.py`'s
`settings` — **no prompt text**. Template:

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

`archive` moves the ticket out of `processing/`, so `record` must reference the
*post-move* path, not `$CLAIMED` — pass `archive`'s own stdout straight into it:

```bash
SK=~/Projects/home-server/.claude/skills/gen-fulfill/scripts
CLAIMED=$(ls ~/.local/share/imagegen-queue/processing/*.json)  # re-derive: shell state does not survive
DONE=$(python3 $SK/queue_cli.py archive "$CLAIMED" done)
python3 $SK/queue_cli.py record "$DONE" --verdict passed --kept <K> --total <T> \
  --rounds <N> --settings-json '<settings from run_forge>' --files-json '<files>'
```
`record` writes the index row (hash + settings + verdict — never prompt). Then, **only
if a genuine pattern emerged** (a knob that reliably helps/hurts for this kind of
request), persist it:
- `brain_save(...)` — codename + settings/verdict only, e.g. "<project_tag> Round-0: cfg7
  on-model, cfg6 drifts young; ADetailer hands mandatory". Tag it so the next recall
  finds it. **Never** dump a prompt.

### 7. Crystallize a preset (only when warranted)

If a run discovered or confirmed a reusable recipe not yet captured, update (Edit) or
create (Write) a `presets/<name>.toml` (pure settings + generic tradeoff notes — see an
existing preset for the shape). This is the most-distilled, public tier. Domain-agnostic
only.

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
