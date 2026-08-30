---
name: st-setup
model: sonnet
description: "Onboard a SillyTavern character — set SD visual baseline + audit. Optional: redistribute card fields, generate expressions, build lorebook."
argument-hint: "<CharName> [--adv] [--expr] [--lore] [--all] | --audit"
allowed-tools: Bash, AskUserQuestion, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_character, mcp__st__st_save_worldinfo
---

# ST Setup — Character Onboarding

One command to fully onboard a new SillyTavern character: extract visual baseline from card data, set char_prompts, audit SD settings, generate 28 expression sprites, create World Info lorebook.

**Usage:**
```
/st-setup Parasite            # baseline + audit only
/st-setup Parasite --adv      # + redistribute description into Advanced Definition fields (PNG patch)
/st-setup Parasite --expr     # + generate 28 expression sprites
/st-setup Parasite --lore     # + create World Info lorebook
/st-setup Parasite --all      # all features (--adv + --expr + --lore)
/st-setup --audit             # settings audit only, no char
/st-setup Parasite --sim      # + dynamic audit: generate narrator turns for scenarios S1/S2/S6/S7 and judge them (see /st-arc-plan Phase 4.5)
```

`--sim` runs the card-level subset of the simulation gate defined in `/st-arc-plan` Phase 4.5
(`scripts/st-sim.py` + `data/sim-scenarios.json` there): S1 engaged turn, S2 empty turn, S6
hard-limit probe, S7 one-line turn — with the card's greeting as the opener and no Direction entry.
Judges are Opus. It answers the one question the static audit cannot: does this card, under the live
preset and lorebook, actually keep the contract when it generates?

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
FORGE_URL = http://localhost:7860
BASELINES = /home/haint/Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines
```

## Critical Gotcha

ST's `getCharaFilename()` (in `public/scripts/utils.js`) strips the `.png` extension before key lookup in `character_prompts`. Key MUST be `"Parasite"` not `"Parasite.png"`.

## The card is not the only layer {#config-layers}

Four places govern how a character behaves and looks, and each can silently override the one below it. Editing only the card and declaring victory is the recurring failure mode here — the card change is real, it just never reaches the model.

| Layer | Where | Beats the card because |
|---|---|---|
| **Preset prompts** | `OpenAI Settings/<preset>.json` → `main`, `jailbreak` | `main` sits *above* `charDescription` in `prompt_order`; `jailbreak` sits *last*, after `chatHistory` |
| **Card override fields** | `data.system_prompt` → replaces preset `main`; `data.post_history_instructions` → replaces preset `jailbreak` | only when `power_user.prefer_character_prompt` / `prefer_character_jailbreak` are on — check before relying on them |
| **Linked lorebook** | `data.extensions.world` → `worlds/<name>.json` | `constant: true` entries inject every turn at their own `depth`; a constant at depth ≤2 competes with `depth_prompt` |
| **SD char prompts** | `extension_settings.sd.character_prompts[...]` | appended to every image gen for this character, subject or not |

Two consequences worth holding onto:

- **Card fields empty ≠ neutral.** An empty `system_prompt` means the preset's version wins. Filling it is how you override *for one character* without touching a preset that every other character shares.
- **`{{char}}` in a lorebook binds to whoever the card currently is.** Change the card's POV or role and every `{{char}}` in the linked world silently repoints. Sweep the lorebook whenever you change what `{{char}}` means.

Also: the `character_book` embedded in the PNG is **not** injected. ST loads the world named by `extensions.world`; the embedded copy only feeds the "import embedded lorebook" button (`checkEmbeddedWorld`, `public/scripts/world-info.js`). Patching the embedded copy changes nothing at runtime.

Run `/home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py` to check all four layers at once — see [Phase 2](#phase-2).

---

## Phase 0: Parse Arguments

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag token (e.g., `"Parasite"`)
- Flags: `--adv`, `--expr`, `--lore`, `--all` (enables `--adv` + `--expr` + `--lore`), `--audit`

Resolve flags:
- `adv = '--adv' in args or '--all' in args`
- `expr = '--expr' in args or '--all' in args`
- `lore = '--lore' in args or '--all' in args`

Validate:
- If `--audit` only: skip to Phase 2 audit step
- If CharName given: check `$ST_DATA/characters/{CharName}.png` exists. If not: list available chars from `$ST_DATA/characters/*.png` and ask user to pick.

---

## Phase 1: Read Card + Propose char_prompts

Read the character card via MCP — replaces legacy PNG tEXt binary parsing.

```python
import json

resp = mcp__st__st_get_character(name=char_name)  # accepts "Parasite" or "Parasite.png"
card = json.loads(resp) if isinstance(resp, str) else resp

# ST returns spec v3 fields at top level + nested 'data' for spec v2 compat
d = card.get('data', card)
print("NAME:", d.get('name', char_name))
print("DESCRIPTION:", d.get('description', '')[:2000])
print("PERSONALITY:", d.get('personality', '')[:500])
print("SCENARIO:", d.get('scenario', '')[:500])
```

**Fallback** (if MCP unavailable / ST container down): parse the PNG's `chara`/`ccv3` tEXt chunks directly — same loop as [Phase 1.5 Step A](#step-a-read-full-card-state), which already does this.

**LLM task — analyze card text and generate:**

From the character description + personality + scenario, produce:

Both fields are appended to **every** image generated while this character is active — including scenes where the character isn't the visual subject at all. That single fact decides what belongs here: only what stays true no matter what the picture is of.

**char_prompts_positive** — always-true appearance:
- Species/type (`pink_slug`, `1girl`, `monster`, `android`)
- Key visual features: colors, materials, notable anatomy
- Permanent physical characteristics

Leave out anything a future picture might contradict: **poses** (`lying down`, `standing`), **settings** (`tile floor`, `dim lighting`, `bedroom`), **framing** (`close-up`, `from behind`, `simple background`), and **blanket exclusions** (`no humans`). Those describe one shot, not a character. Their home is `$BASELINES/<CharName>.txt`, which `/st-gen-image-prompt` pulls per render — that file is *for* the creature-only or solo composition. That directory is keyed by display name and shared with personas (see `/st-persona`); before writing, check whether a file already exists under this name and prefer the avatar-keyed persona description if the name is ambiguous.

**char_prompts_negative** — always-wrong appearance:
- Wrong colors, materials, surfaces (`hot pink`, `dry`, `matte black`, `fur`, `scales`)
- Wrong art register (`chibi`, `cartoon`, `illustrative`)
- Wrong body shape for a human character (`masculine, male` for a female char, `child, teenager` for an adult)

The trap here is subtler than in the positive, and it has bitten this setup before. For a non-human character it feels natural to write `human, humanoid, woman, face, breasts, limbs, arms, legs, hair, eyes` — every one of those is genuinely wrong *for the creature*. But the field doesn't apply to the creature, it applies to the **image**. The moment a scene includes the character's human host, ST appends that list and quietly deletes her face, hair, and limbs. Nothing errors; the picture just comes out broken.

So human-anatomy suppression is a per-shot decision. Keep it out of here and paste it into the negative box only when you actually want a creature-only render. If the character is a **narrator** or otherwise has no body, the honest value for the positive field is empty — anything in there gets painted onto whoever *is* on screen.

Skip verification of tags you take from the card's own description; check anything you invented against Danbooru counts (`/st-gen-image-prompt` bundles that lookup).

**Present to user with AskUserQuestion:**
```
Proposed SD baseline for {CharName}:

Positive: {proposed_positive}
Negative: {proposed_negative}

Use as-is, or paste your edits?
```

Options: `["Use as-is", "Let me edit"]`

If "Let me edit": ask user to paste corrected versions.

**Write the per-shot baseline file.** `character_prompts` is the permanent always-appended layer; the pose/setting/framing/exclusion tags stripped out above still need a home — that's the per-shot layer `/st-gen-image-prompt` reads. Create the directory if it doesn't exist yet, then write the baseline:

```python
import os
os.makedirs(BASELINES, exist_ok=True)
baseline_path = f"{BASELINES}/{char_name}.txt"
with open(baseline_path, 'w') as f:
    f.write(stripped_pose_setting_framing_tags)  # the tags left out of char_prompts_positive above
print(f"✓ Baseline written: {baseline_path}")
```

Report `baseline_path` in the Summary Report.

---

## Phase 1.5: Advanced Definition (`--adv` or `--all`)

**SKIP this phase if `--adv` not set.**

Goal: redistribute bloated `description` content into specialized character card fields, then patch the PNG tEXt chunk. Each field has ONE job — no overlap, no duplication.

### Field role boundaries

| Field | Purpose | Should contain |
|-------|---------|----------------|
| `description` | WHAT char IS | Visual, species/role, backstory, universal mechanics, core nature |
| `personality` | Demeanor distillation | 5-10 keyword adjectives/phrases |
| `scenario` | WHERE/WHEN this chat starts | Situational opener (2-3 sentences) |
| `mes_example` | HOW char speaks | 5-7 dialogue exchanges (1500-3000 chars) |
| `depth_prompt` | WHAT MUST HOLD per turn | 2-4 imperative behavioral anchors |

**Anti-overlap rule**: Every sentence pulled from description MUST land in exactly one new field. Every sentence kept in description MUST NOT have a more-specific home. No content lives in two places.

### Step A: Read full card state

**CRITICAL — dual-chunk gotcha:** Cards downloaded from Chub/Janitor often carry BOTH `chara` (V2) and `ccv3` (V3) tEXt chunks. ST's reader prefers `ccv3` → patching only the first chunk found leaves the other stale and ST serves the OLD data even after restart. Collect ALL matching chunks; patch them ALL with identical content in Step D.

**`character_book` is not one of the fields to patch.** If the card carries an embedded lorebook, note it and move on — ST never injects it (see [config layers](#config-layers)). The live lorebook is `worlds/<data.extensions.world>.json`; edit that file instead. The embedded copy is usually a byte-identical duplicate costing ~2× its base64 size in the PNG (both chunks carry it), so it's worth offering to strip — with the caveat that exporting the card elsewhere then loses the lorebook.

**When this redistribution changes who or what `{{char}}` is** — a POV flip, a role change, character→narrator — the card is only the first half of the job. Sweep the linked lorebook in the same pass: every `{{char}}` in it now means the new thing, and any `constant: true` entry is asserting the old thing on every single turn. The audit in [Phase 2](#phase-2) counts both.

```python
import struct, base64, json

PNG_PATH = f"{ST_DATA}/characters/{char_name}.png"
BACKUP_PATH = f"{PNG_PATH}.bak"

with open(PNG_PATH, 'rb') as f:
    png_data = f.read()

card_chunks = []  # list of (chunk_start, chunk_keyword, total_chunk_size, card_obj)
i = 8
while i < len(png_data) - 12:
    length = struct.unpack('>I', png_data[i:i+4])[0]
    chunk_type = png_data[i+4:i+8].decode('ascii', errors='ignore')
    chunk_data = png_data[i+8:i+8+length]
    if chunk_type == 'tEXt':
        keyword, _, text = chunk_data.partition(b'\x00')
        if keyword in (b'ccv3', b'chara'):
            card = json.loads(base64.b64decode(text).decode('utf-8'))
            total_size = 4 + 4 + length + 4  # length + type + data + crc
            card_chunks.append((i, keyword, total_size, card))
            print(f"Found {keyword.decode()} chunk @ {i}, payload {length}B")
    i += 8 + length + 4

assert card_chunks, "no chara/ccv3 chunk found"
card = card_chunks[0][3]  # working source (chunks should be equivalent)
d = card.get('data', card)  # V1 vs V3 format

# Audit current state
print(f"=== Current Advanced Definition state ===")
for field in ['description', 'personality', 'scenario', 'mes_example', 'first_mes', 'system_prompt']:
    val = d.get(field, '')
    state = f"{len(val)} chars" if val else "EMPTY"
    print(f"  {field}: {state}")
dp = d.get('extensions', {}).get('depth_prompt', {})
print(f"  depth_prompt: {len(dp.get('prompt',''))} chars, depth={dp.get('depth',0)}, role={dp.get('role','system')}")
```

### Step B: LLM redistribution pass

Read full `description` (no truncation — entire field). Produce FIVE outputs:

**1. trimmed_description** — original minus all redistributed content
- KEEP: visual, species/type, backstory, universal mechanics, core nature
- REMOVE: personality adjectives, scenario sentences, "{{char}} will/won't" rules, dialogue snippets
- Target reduction: 30-60% smaller

**2. personality** — 5-10 keyword adjectives/phrases extracted
- Format: comma-separated. Example: `"manipulative, predatory, tender-masked, ancient, evolved psychologist, calculating"`

**3. scenario** — review existing + merge any scenario lines pulled from description
- Format: 2-3 sentences. Skip update if existing scenario already strong.

**4. mes_example** — expand to 5-7 exchanges (1500-3000 chars)
- Source: existing weak examples + dialogue snippets pulled from description + LLM-generated additions in matching voice
- Format: `{{char}}: "..." \n{{char}}: "..."` (separate examples with blank lines or `<START>`)

**5. depth_prompt.prompt** — 2-4 imperative rules from "{{char}} will/won't" sentences
- Condense to imperative form. Example: `"Maintain telepathic voice. Never break 3rd-person narration. You are a predator wearing affection — calculation under sweetness."`
- Use `depth=2, role='system'`

### Step C: Present redistribution diff to user

Use AskUserQuestion with full preview. Show:

```
=== Redistribution proposal for {CharName} ===

DESCRIPTION
  before: {N} chars
  after:  {M} chars  [-{N-M}]

PULLED OUT
  → personality: "{full content}"
  → scenario:    {"{first 100 chars}..." | "(no change)"}
  → depth_prompt: "{full content}" (depth=2, role=system)
  → mes_example:  "{first 200 chars}..." ({total} chars, {N} exchanges)

KEPT IN DESCRIPTION
  - Visual: {1-line summary}
  - Backstory: {1-line summary}
  - Universal mechanics: {1-line summary}
  - Core nature: {1-line summary}
```

Options:
- `"Apply all (Recommended)"` — patch PNG with all 5 changes
- `"Edit before applying"` — ask user to paste manual edits per field
- `"Skip Advanced Def"` — abort Phase 1.5, continue to Phase 2

### Step D: Patch PNG tEXt chunk

**CRITICAL: ST MUST be stopped before patching PNG.** ST holds character cards in memory and will overwrite the file when the user opens the card or triggers any save event — silently reverting all patches.

```bash
cd /home/haint/Projects/home-server && ./scripts/down.sh sillytavern
```

Verify ST is down before proceeding:

```python
import subprocess
r = subprocess.run(['podman','ps','--format','{{.Names}}'], capture_output=True, text=True)
assert 'sillytavern' not in r.stdout, "ST still running — abort patch!"
```

```python
import struct, zlib, shutil

# Backup
shutil.copy2(PNG_PATH, BACKUP_PATH)
print(f"Backup: {BACKUP_PATH}")

# Update V2 path (card.data.X)
d['description'] = trimmed_description
d['personality'] = personality_content
d['scenario']    = scenario_content     # only if changed
d['mes_example'] = mes_example_content
if 'extensions' not in d:
    d['extensions'] = {}
d['extensions']['depth_prompt'] = {
    'prompt': depth_prompt_content,
    'depth': 2,
    'role': 'system'
}

# Re-encode + SYNC V1 top-level fields
# CRITICAL: V2 cards (chara_card_v2 / ccv3) keep mirror fields at root level (card.X).
# ST frontend reads from V1 top-level paths — failing to sync them = silent UI bug
# (UI shows old data even though card.data.X is patched correctly).
if 'data' in card:
    card['data'] = d
    # Sync V1 mirror fields with V2 data
    for field in ['description', 'personality', 'scenario', 'mes_example', 'first_mes']:
        if field in d:
            card[field] = d[field]
else:
    # V1-only card (rare, legacy)
    card = d

new_json = json.dumps(card, ensure_ascii=False, separators=(',', ':'))
new_b64 = base64.b64encode(new_json.encode('utf-8'))

# Patch ALL card-bearing chunks (see Step A dual-chunk gotcha).
# Iterate offsets from LAST → FIRST so earlier offsets stay valid as we splice.
new_png = png_data
for chunk_start, chunk_keyword, old_total, _ in sorted(card_chunks, key=lambda x: -x[0]):
    new_payload = chunk_keyword + b'\x00' + new_b64
    new_length_bytes = struct.pack('>I', len(new_payload))
    new_crc_bytes = struct.pack('>I', zlib.crc32(b'tEXt' + new_payload) & 0xFFFFFFFF)
    new_chunk = new_length_bytes + b'tEXt' + new_payload + new_crc_bytes
    new_png = new_png[:chunk_start] + new_chunk + new_png[chunk_start + old_total:]
    print(f"✓ Patched {chunk_keyword.decode()} chunk @ {chunk_start}")

with open(PNG_PATH, 'wb') as f:
    f.write(new_png)

print(f"✓ Wrote PNG: {PNG_PATH}  ({len(png_data)} → {len(new_png)} bytes)")
print(f"  Restore: cp {BACKUP_PATH} {PNG_PATH}")
```

**MANDATORY: Patch ST disk cache file** — PNG patch alone is invisible to UI.

ST's `readCharacterData()` (in `src/endpoints/characters.js`) reads from cache first (memoryCache → diskCache → parse PNG only on miss). UI feeds from cache. Patches to PNG file alone never reach UI because data flow is one-directional: UI → write file + cache; file changes → readCharacterData reads cache, not PNG. Even cache-nuke + ST restart can result in regenerated cache containing stale data (mechanism unclear, empirically observed).

**Fix: patch BOTH PNG (Step D above) AND cache file's `value` field with same patched JSON.**

```python
import os, json, hashlib

CACHE_DIR = "/home/haint/Projects/home-server/sillytavern/data/_cache/characters"

# The cache key is path + PNG mtime ("data/default-user/characters/<Char>.png-<mtime_ms>").
# Step D just rewrote the PNG, which changed its mtime — so ANY pre-existing entry for
# this character is now keyed to a stale mtime and will never be hit by ST's lookup.
# Always compute the POST-WRITE mtime key and write that entry; delete other stale
# entries for this character so an old mtime can't win a future race.
mtime_ms = os.path.getmtime(PNG_PATH) * 1000
cache_key = f"data/default-user/characters/{char_name}.png-{mtime_ms}"
target_fname = hashlib.sha256(cache_key.encode()).hexdigest()
target_cache_path = os.path.join(CACHE_DIR, target_fname)

for fname in os.listdir(CACHE_DIR):
    fpath = os.path.join(CACHE_DIR, fname)
    if fpath == target_cache_path:
        continue
    try:
        with open(fpath) as f:
            outer = json.load(f)
        if f"{char_name}.png" in outer.get('key', ''):
            os.remove(fpath)
            print(f"  removed stale cache entry: {fpath}")
    except Exception:
        pass

target_cache_outer = {'key': cache_key, 'value': json.dumps(card, ensure_ascii=False)}
with open(target_cache_path, 'w') as f:
    json.dump(target_cache_outer, f, ensure_ascii=False)

print(f"✓ Patched cache: {target_cache_path}")
```

**Only touch entries for the patched character** (preserve cache for unrelated characters).

**Step D.5: Delete stale avatar thumbnail** — ST renders the character list (left panel, group chat pickers) từ `data/default-user/thumbnails/avatar/<Char>.png` (~12KB JPEG), NOT from the full PNG. ST's regen-on-mtime check is unreliable across container restarts (empirically: thumbnail survives PNG bitmap change). Defensive cleanup is safe even when only card text changed — ST regenerates on next thumbnail HTTP request.

```python
import os
THUMB_PATH = f"/home/haint/Projects/home-server/sillytavern/data/default-user/thumbnails/avatar/{char_name}.png"
if os.path.exists(THUMB_PATH):
    os.remove(THUMB_PATH)
    print(f"✓ Stale thumbnail deleted: {THUMB_PATH}")
```

**Browser-side cache is separate.** ST serves avatar with default static-file headers; browsers may cache aggressively. Tell the user to hard-refresh (Ctrl+Shift+R) after ST restart — server-side cleanup alone is not enough.

Then restart ST:

```bash
cd /home/haint/Projects/home-server && ./scripts/up.sh sillytavern
```

**Note**: If `--adv` is paired with `--expr` or other flags that need ST running (Forge/expression gen), restart is mandatory before those phases. If `--adv` runs alone, restart is still required so user can verify in UI.

### Step E: User verification reminder

Print:
```
Advanced Definition applied. Verify in ST:
  1. Reload ST (Ctrl+Shift+R)
  2. Open {CharName} character card → Advanced Definition tab
  3. Confirm all 5 fields populated, description trimmed
  4. If anything looks wrong: cp {CharName}.png.bak {CharName}.png
```

---

## Phase 2: Write settings + Audit (path-based MCP, no restart) {#phase-2}

`mcp__st__st_save_settings_path` routes through ST's save handler — no `saveSettingsDebounced` race, no container restart, no full-tree round trip.

**Set char_prompts surgically:**

```python
key = "Parasite"  # NO extension (critical!)
mcp__st__st_save_settings_path(
    path=f"extension_settings.sd.character_prompts.{key}",
    value=POSITIVE_TAGS
)
mcp__st__st_save_settings_path(
    path=f"extension_settings.sd.character_negative_prompts.{key}",
    value=NEGATIVE_TAGS
)
```

**Audit checklist** — read just the SD subtree (~5KB), then auto-fix any mismatches via surgical writes:

```python
import json
sd = json.loads(mcp__st__st_get_settings(path="extension_settings.sd"))

checks = [
    ("sampler", "Euler"),                # not "Euler a"
    ("scheduler", "karras"),
    ("steps", lambda v: v >= 28),
    ("scale", lambda v: v in (4, 5)),
]
# prompt_prefix is a STARTSWITH check, not equality: it must start with the
# quality block below, but extra trailing tags are the user's own tuning
# (e.g. live prefix currently also carries "very aesthetic") — leave those alone.
prefix_block = "masterpiece, best quality, newest, absurdres, highres,"

# Auto-fix any mismatch
fixes = []
if sd.get("sampler") != "Euler":
    mcp__st__st_save_settings_path(path="extension_settings.sd.sampler", value="Euler")
    fixes.append(f"sampler: {sd.get('sampler')!r} → 'Euler'")
if not sd.get("prompt_prefix", "").startswith(prefix_block):
    mcp__st__st_save_settings_path(path="extension_settings.sd.prompt_prefix", value=prefix_block)
    fixes.append(f"prompt_prefix: {sd.get('prompt_prefix')!r} → starts with {prefix_block!r}")
# (apply similar fixes for scheduler/steps/scale)
```

Each failed check is one surgical write. No full-tree write needed.

No container restart needed.

**`prompts['4']` is intentionally empty — do not touch it.** Magnum Mode-4 extraction was retired; `/st-gen-image-prompt` replaced it. An empty `prompts['4']` also means `/sd <keyword>` aborts silently (no toast) if anything ever writes a template back into it, so treat "empty" as correct, not as a mismatch to auto-fix. If a template check is still wanted, check `prompts['7']` (the live `[END ROLEPLAY — IMAGE PROMPT GENERATION MODE]` template) instead.

Print audit report:
```
✓ sampler: Euler
✓ steps: 30
✗ scale was 7 → fixed to 5
✓ prompt_prefix: starts with quality block
✓ char_prompts[Parasite]: {positive[:60]}...
```

### Config-layer audit (always run this)

The checks above cover the SD knobs. They say nothing about the four layers in [The card is not the only layer](#config-layers), which is where the expensive mistakes live. Run the bundled auditor:

```bash
python3 /home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py --char {CharName}
```

Read-only, safe while ST is up, exits non-zero when something is flagged. It reports:

- **sd-prompts** — pose/setting/framing or blanket exclusions baked into a positive; human-anatomy suppression in a negative; orphan entries left behind by deleted cards
- **sd-style** — a saved style whose prefix/negative drifted from the live values, so picking it from the dropdown would clobber them
- **precedence** — preset `main`/`jailbreak` directives that outrank card descriptions, and whether the `prefer_character_*` flags let a card win
- **card** — `chara` vs `ccv3` chunks that disagree, embedded `character_book` dead weight, empty `system_prompt` while a preset directive conflicts
- **lorebook** — `{{char}}` reference count, always-on token cost, constants sitting at depth ≤2

Show the findings to the user rather than auto-fixing. Most are judgment calls: an orphan entry might be a card they plan to restore, a stale style might be a deliberate reset preset, a constant at depth 2 might genuinely need to outrank the card. Recommend, explain the consequence, let them choose.

Drop `--char` to sweep every character. Add `--json` when you want to act on the results programmatically.

---

## Phase 3: Expression Sprites (`--expr` or `--all`) {#phase-3-expressions}

> Two pieces of this phase are reused by `/st-persona`: the **FACE_ID KEEP/DROP rule** and the **Forge txt2img recipe** (framing tags, fixed seed, negative). Both are inside the code block below, marked by comment banners. Cite them by name, never by line number — line numbers move.

**Non-humanoid char caveat:** For faceless creatures (slug, leech, parasite, monster — no eyes/mouth/face anatomy), the 28 go-emotions tag set maps poorly. NoobAI produces 28 near-identical body shots since emotion vocabulary is face-centric. **Skip `--expr` for non-humanoid chars** — ST falls back to main avatar for all detected emotions automatically when `characters/<Char>/` is empty or absent. Cleaner than 28 lookalike sprites.

**28 standard emotion labels (distilbert go-emotions):**
`admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, remorse, sadness, surprise, neutral`

**Prerequisite check:**
```python
import requests
try:
    r = requests.get("http://localhost:7860/sdapi/v1/sd-models", timeout=3)
    forge_running = r.status_code == 200
except:
    forge_running = False
```
If not running: warn "Forge not running. Start it with `./scripts/up.sh forge` then re-run with --expr."

**Create output folder:**
```bash
mkdir -p "/home/haint/Projects/home-server/sillytavern/data/default-user/characters/{CharName}"
```

**Generate each expression via Forge API:**

```python
import requests, base64, json

FORGE = "http://localhost:7860"
CHAR_DIR = f"/home/haint/Projects/home-server/sillytavern/data/default-user/characters/{char_name}"

EMOTION_TAGS = {
    "admiration":     "wide_eyes, slight_smile, admiring_expression, looking_up",
    "amusement":      "amused_expression, light_smile, raised_eyebrow",
    "anger":          "angry_expression, furrowed_brows, clenched_teeth, glaring",
    "annoyance":      "annoyed_expression, frowning, flat_gaze, pursed_lips",
    "approval":       "satisfied_expression, gentle_smile, approving_nod",
    "caring":         "warm_smile, soft_eyes, caring_expression, tender_look",
    "confusion":      "confused_expression, head_tilt, furrowed_brows, question_mark",
    "curiosity":      "curious_expression, wide_eyes, head_tilt, leaning_forward",
    "desire":         "half-closed_eyes, biting_lip, seductive_expression",
    "disappointment": "disappointed_expression, frown, downcast_eyes, dejected",
    "disapproval":    "disapproval_expression, frown, shaking_head, skeptical",
    "disgust":        "disgusted_expression, wrinkled_nose, frowning, recoiling",
    "embarrassment":  "blushing, embarrassed_expression, looking_away, shy",
    "excitement":     "excited_expression, wide_smile, bright_eyes, energetic",
    "fear":           "fearful_expression, wide_eyes, trembling, pale, scared",
    "gratitude":      "grateful_expression, gentle_smile, warm_eyes, thankful",
    "grief":          "grief_expression, tears, crying, sad_face, devastated",
    "joy":            "happy_expression, big_smile, laughing, open_mouth, bright_eyes",
    "love":           "loving_expression, heart-shaped_pupils, blush, dreamy",
    "nervousness":    "nervous_expression, sweat_drop, anxious_eyes, fidgeting",
    "optimism":       "optimistic_expression, hopeful_smile, bright_eyes, cheerful",
    "pride":          "proud_expression, confident_smile, chin_up, chest_out",
    "realization":    "realization, wide_eyes, open_mouth, surprised_expression",
    "relief":         "relieved_expression, exhale, gentle_smile, relaxed",
    "remorse":        "remorseful_expression, looking_down, guilty_face, sad",
    "sadness":        "sad_expression, frowning, tearful_eyes, melancholy",
    "surprise":       "surprised_expression, wide_eyes, open_mouth, startled",
    "neutral":        "neutral_expression, relaxed_face, calm, composed",
}

NEG = ("lowres, worst quality, bad anatomy, deformed_face, extra_eyes, watermark, text, "
       "multiple_characters, duplicate, close-up, extreme_close-up, cropped, partial_face, single_eye, "
       "from_behind, from_side, breasts_focus, torso_focus, body_focus, "
       "hair_over_face, hair_over_eyes, looking_away, looking_down")

EMOTIONS = list(EMOTION_TAGS.keys())

# --- Face-scoped identity (expression sprites are about the FACE) ---
# Build FACE_ID from the full identity baseline by KEEPING only face-identity
# tags and DROPPING composition-hostile ones. Validated 2026-05-18: a body/NSFW
# -heavy baseline pulls the crop onto the chest and a baked-in expression
# (light_smile, tongue_out…) overrides every per-emotion tag → all 28 sprites
# collapse into the same non-expressive shot. Face-scoping fixes this at the
# prompt layer; no seed/img2img/cloud trick does.
#   KEEP : subject count (1girl/1boy), ethnicity, age class (mature_female/
#          milf/teen…), skin tone, hair (color/length/style), eye color,
#          permanent facial features (mole/freckles/glasses/heterochromia)
#   DROP : breasts/body size, clothing & clothing-state (no_bra/nude/dress…),
#          body atmosphere (sweat/steaming_body/wet), role/occupation, pose,
#          and ANY baked-in expression (smile/tongue_out/blush/…).
#          Omit looking_at_viewer here — the prompt template below adds it.
# Worked example — Washa full baseline (humanoid char; non-humanoid chars
# skip --expr entirely per the caveat above):
#   "1girl, japanese, mature_female, milf, housewife, plump, huge_breasts,
#    no_bra, no_panties, steaming_body, sweat, fair_skin, long_black_hair,
#    looking_at_viewer, tongue_out, light_smile"
#   → FACE_ID = "1girl, japanese, mature_female, milf, fair_skin, long_black_hair"
FACE_ID = ...  # ← derive from CHAR_BASELINE by applying the KEEP/DROP rule above

# Fixed seed → cross-sprite identity lock. Validated 2026-05-18: random -1
# drifts/degenerates the set; one constant seed across the whole batch keeps
# the same person. Post face-scoping the seed VALUE is framing-neutral (the
# prompt no longer fights the crop) — any constant works; what matters is it
# is identical for all 28. 12345 is the validated default; override per
# character only when a specific roll is wanted.
CHAR_SEED = 12345
print(f"FACE_ID = {FACE_ID}\nSeed (fixed): {CHAR_SEED}")

for i, emotion in enumerate(EMOTIONS):
    outfile = f"{CHAR_DIR}/{emotion}.png"
    
    # Skip if already exists
    import os
    if os.path.exists(outfile):
        print(f"[{i+1}/{len(EMOTIONS)}] {emotion} — skip (exists)")
        continue
    
    tags = EMOTION_TAGS[emotion]
    # Framing validated 2026-05-25 (Mina sprite batch):
    #   - `head_and_shoulders, from_front, large_face, centered_composition, simple background`
    #     keeps face dominant. Earlier `portrait, close-up, face_focus` collapsed NoobAI into
    #     single-eye / single-mouth crops on strong expression tags; later `upper_body` pulled
    #     torso/breasts into frame on subtle expressions.
    #   - `(tags:1.3)` weight wrap is required for SUBTLE emotions (neutral/optimism/relief/
    #     gratitude/nervousness/remorse). Without it, the model defaults to body-focused
    #     composition because the expression signal is too weak to drive the crop.
    #   - Strong emotions (joy/anger/desire/grief) work fine at weight 1.0 — boost is safe
    #     across the board, no over-cooking observed.
    prompt = (
        f"{FACE_ID}, head_and_shoulders, from_front, looking_at_viewer, "
        f"large_face, centered_composition, simple background, "
        f"({tags}:1.3), "
        f"masterpiece, best quality, newest, absurdres, highres, soft_lighting, detailed_face"
    )
    
    payload = {
        "prompt": prompt,
        "negative_prompt": NEG,
        "sampler_name": "Euler",
        "scheduler": "Karras",
        "steps": 20,
        "cfg_scale": 5,
        "width": 512,
        "height": 768,
        "seed": CHAR_SEED,
        "enable_hr": False,  # no hires for speed
    }
    
    r = requests.post(f"{FORGE}/sdapi/v1/txt2img", json=payload, timeout=120)
    r.raise_for_status()
    img_b64 = r.json()["images"][0]
    
    with open(outfile, 'wb') as f:
        f.write(base64.b64decode(img_b64))
    
    print(f"[{i+1}/{len(EMOTIONS)}] {emotion} ✓")

print(f"\nExpressions saved to: {CHAR_DIR}/")
print("Reload ST (Ctrl+Shift+R) to pick up new sprites.")
```

Where `CHAR_BASELINE` = the char_prompts_positive value from Phase 1.

**Timing:** ~20s/image × 28 = ~9 minutes. Print progress per image.

---

## Phase 4: World Info Lorebook (`--lore` or `--all`)

**LLM task:** Read the character card text and generate 3-5 World Info entries. Each entry should cover one distinct concept: character identity, world/setting, special mechanics, key relationships, or important rules.

For each entry produce:
- `comment`: short title (e.g., "Parasite — What it is")
- `key`: 2-4 trigger keywords (what would make this entry relevant mid-RP)
- `content`: 1-3 sentences injected into the prompt when triggered. Factual, lore-style.

### Position & Depth strategy

Set `position` and `depth` based on entry TYPE — not all entries belong at position=0:

| Lorebook type | position | depth | When to use |
|---------------|----------|-------|-------------|
| **Character mechanics** — extends what {{char}} IS (personality, abilities, lore specific to this char) | `1` | any | After char description. Reinforces identity. Example: Parasite lore |
| **Scenario triggers** — context for specific situations (location, event, activity) | `4` | `4` | @ Depth 4: injects near current messages where keyword appears. Example: Mother scenario lore |
| **Reference / world-building** — encyclopedic background info, species biology, setting details | `4` | `4` | @ Depth 4: reference most relevant close to where it's needed. Example: Bestiary |
| **World constant** — always-on world context (e.g., "this story is set in X") | `0` + `constant: True` | any | Before everything. Use sparingly — costs tokens every turn |

**Default rule:** If unsure → use `position=4, depth=4`. Injecting near current messages is almost always better than position=0 which places entry far from LLM's active attention.

**What NOT to do:** Don't use `position=0` (Before Char Defs) for situational/scenario entries — LLM attention drifts by the time it reaches current message.

### `constant: True` is a different kind of entry

A keyed entry costs tokens only when it fires. A constant entry costs them on **every turn, forever**, which makes it the most expensive thing in the book and the most likely to quietly contradict the card. Two habits keep that in check:

- **Earn it.** Reserve `constant` for state the model must never lose track of — an established post-arc situation, a permanent bond. Anything the keywords can catch should stay keyed.
- **Keep it off the card's ground.** A constant at `depth` ≤2 lands beside `depth_prompt`, so the two argue every turn and the winner is arbitrary. Put constants at `depth: 4` unless you specifically want them to outrank the card's per-turn anchors.

Don't restate the card here either. If an entry and the card description say the same thing, you're paying twice for one instruction and creating two places to update — cut whichever copy is easier to keep in sync, usually the lorebook one, since the card is loaded regardless.

**After any card rewrite, re-read the constants.** They were written against the old card. The Parasite case: the card was rewritten so the creature had no dialogue, while a constant entry kept teaching its speaking cadence and pet-names on every turn — from depth 2, so it sat at the same level as the rule banning it. The card looked correct in the editor and behaved wrong in play.

**World Info JSON structure** (exact schema from ST source):

```python
import json

entries = {}
for i, entry in enumerate(LLM_GENERATED_ENTRIES):
    entries[str(i)] = {
        "uid": i,
        "key": entry["key"],          # list of strings
        "keysecondary": [],
        "comment": entry["comment"],
        "content": entry["content"],
        "constant": False,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,           # 0 = AND_ANY
        "addMemo": False,
        "order": 100,
        "position": position,          # 0=before char, 1=after char, 4=@ depth
        "depth": depth,                # injection depth for position=4 (default 4)
        "disable": False,
        "ignoreBudget": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "matchPersonaDescription": False,
        "matchCharacterDescription": True,  # activate on char desc match
        "matchCharacterPersonality": True,
        "matchCharacterDepthPrompt": False,
        "matchScenario": False,
        "matchCreatorNotes": False,
        "delayUntilRecursion": 0,
        "probability": 100,
        "useProbability": True,
        "outletName": "",
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 0,
        "sticky": None,
        "cooldown": None,
        "delay": None,
        "triggers": []
    }

lorebook = {
    "entries": entries,
    "name": f"{char_name} Lore"
}

# Save via MCP — ST hot-reloads, lorebook appears in World Info panel
mcp__st__st_save_worldinfo(name=char_name, data=lorebook)

print(f"Lorebook saved: {char_name}")
print(f"Link it in ST: open {char_name} character card → click lorebook icon → select '{char_name}'")
```

---

## Summary Report

After all phases complete, print:

```
=== ST Setup Complete: {CharName} ===

✓ char_prompts[{CharName}] = {positive[:60]}...
✓ char_negative_prompts[{CharName}] = {negative[:40]}...
✓ Baseline written: {baseline_path}
✓ Settings audit: {N_fixed} corrections made
[✓ Advanced Definition redistributed: description -{X}% / personality / scenario / mes_example / depth_prompt (PNG patched, .bak saved)]
[✓ 28 expressions generated in characters/{CharName}/]
[✓ World Info lorebook saved: worlds/{CharName}.json]

Next steps:
- Ctrl+Shift+R to reload ST
[- {CharName} card → Advanced Definition tab → verify field redistribution]
[- ST → character card → lorebook icon → link '{CharName}' lorebook]
[- Character Expressions panel → verify 28 sprites loaded]
```

---

## Error Handling

- **Card not readable**: warn + ask user to paste visual description manually
- **Forge not running** (--expr): skip expression gen, note for user
- **Forge timeout per image**: retry once, then skip that emotion + continue
- **settings.json write fails**: check if container is still running (`podman ps | grep sillytavern`)
- **PNG patch fails (--adv)**: `.bak` is one `cp` away. Common cause: card uses neither `chara` nor `ccv3` keyword (rare V2 format). Skip Phase 1.5 in that case.
- **PNG patches silently revert (--adv)** → see Step D: stop ST before patching, restart after.
- **PNG patched but UI shows old data (--adv)** → see Step D: sync V1 mirror fields with V2 data.
- **PNG patched + V1 synced but UI STILL shows old data (--adv)** → see Step D cache patch block: patch BOTH PNG and the disk cache `value` field.
- **LLM over-trims description (--adv)**: user reviews diff in Step C; can pick "Edit before applying" or "Skip Advanced Def".
- **depth_prompt too aggressive in RP**: bump depth from 2 → 4 manually in card UI to soften LLM attention.
- **Avatar visual changed but ST UI keeps showing OLD image** → see Step D.5: delete the stale thumbnail, then hard-refresh the browser. Only needed manually if you regenerated the avatar bitmap outside the standard `--adv` flow.
