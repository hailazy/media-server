---
name: st-persona
model: sonnet
description: "Convert a SillyTavern character into a user persona — or create a new persona from scratch with --new. Migrates/builds visuals, lorebook link, avatar."
argument-hint: "<CharName> [--new | --remove]"
allowed-tools: Bash, AskUserQuestion, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_character
---

# ST Persona — Character → Persona Migration (or scratch build)

Two modes:
- **Convert** (default): Hai's flow — import char from Chub/Janitor → find interesting → decide "this is my persona" → convert. Migrates an existing `{{char}}` into a user persona.
- **New** (`--new`): build a brand-new persona from scratch with no source character. Interactive Q&A for fields + Forge txt2img for the avatar.

ST has no built-in equivalent for `char_prompts` on the persona side, so visual baseline must move INTO `persona_description` text (LLM extracts during Mode 4). This skill automates either path.

**Usage:**
```
/st-persona Parasite             # convert, KEEP original char file (default safe)
/st-persona Parasite --remove    # convert AND delete original char file
/st-persona DemonLord --new      # create brand-new persona — Q&A + Forge avatar gen
```

`--new` and `--remove` are mutually exclusive (nothing to remove when creating from scratch).

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
```

---

## Phase 0: Parse + Validate

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag token
- `new_mode` = `--new` flag present
- `remove_original` = `--remove` flag present

**Flag validation:**
- `--new` and `--remove` are **mutually exclusive** → abort with: *"--new creates from scratch; nothing to --remove. Pick one."*

**Convert-mode validation** (when `--new` is absent):
- `$ST_DATA/characters/{CharName}.png` must exist (source character) — abort with hint to use `--new` if Hai meant to create fresh

**New-mode validation** (when `--new` is present):
- `$ST_DATA/characters/{CharName}.png` must NOT exist — if it does, abort: *"Char file already exists. Drop --new to convert it, or pick a different persona name."*

**Both modes:**
- `$ST_DATA/User Avatars/{CharName} (Persona).png` must NOT exist — if it does, ask user: overwrite, rename (e.g. `(Persona 2)`), or abort

---

## Phase 1: Gather Source Data

**Branch by mode:**
- `new_mode == True` → jump to **Phase 1-new** below; skip the rest of Phase 1 and all of Phase 2 (no card to transform).
- `new_mode == False` → continue with the convert-mode flow immediately below.

### Phase 1 (convert mode)

**Read existing char_prompts via MCP** (path-based, may be empty/missing if /st-setup not yet run):

```python
import json

try:
    char_visual_pos = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_prompts.{CharName}"))
except Exception:
    char_visual_pos = ''  # key absent

try:
    char_visual_neg = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_negative_prompts.{CharName}"))
except Exception:
    char_visual_neg = ''

print(f"char_prompts found: {bool(char_visual_pos)}")
```

**Read char card via MCP** — replaces legacy PNG tEXt parse:

```python
resp = mcp__st__st_get_character(name=CharName)
card = json.loads(resp) if isinstance(resp, str) else resp
d = card.get('data', card)  # spec v3 nests under 'data', v2 flat
# Use d['name'], d['description'], d['personality'], d['scenario'], d.get('creator_notes', '')
```

**Branch logic:**
- If `char_visual_pos` exists → use it for visual block
- Else → LLM analyze card description and extract visual booru tags on the fly (positive only — negatives less critical for persona)

---

## Phase 1-new: Interactive Q&A (new mode only)

Run this section instead of Phase 1 + Phase 2 when `--new` is set. The output is a `PERSONA_DESC` string in the **same shape** the convert flow produces (so Phase 3 stays unified), plus a `FACE_ID` tag string used by Forge in Phase 3-new.

Gather fields via `AskUserQuestion` (one question per group — Hai's free-text "Other" answer is the actual input; the listed options are just shortcuts for common cases). Suggested groups:

1. **Identity basics** — Hai pastes one block:
   ```
   Name:       {default = CharName}
   Age:        {e.g. 27, late 30s, ancient}
   Gender:     {e.g. female, male, nonbinary}
   Ethnicity:  {optional — e.g. Japanese, Nordic, demonic}
   ```

2. **Appearance** — 1–3 sentences. Visual identity, body, hair, eyes, distinctive features, style/outfit.

3. **Demeanor** — 1–2 sentences. First-impression vibe; how `{{char}}`s should perceive `{{user}}` (e.g. *"sweet, oblivious, easily flustered"* or *"imposing, speaks with authority, cold gaze"*). See Phase 2's Demeanor/Social-context rationale for why this matters.

4. **Social context** — 1 sentence. Role/position shaping NPC reactions (e.g. *"Japanese housewife, late 30s, suburban home"* or *"ruler of the seven hells"*).

5. **Personality keywords** — optional, 1–2 anchors if Hai wants a specific feel. Skip → leave blank.

6. **Visual booru tags (FACE_ID)** — REQUIRED for Forge avatar gen. Apply the face-scoping KEEP rules from `/home/haint/Projects/home-server/.claude/skills/st-setup/SKILL.md` lines 472–491:
   - **KEEP**: subject count (`1girl`/`1boy`), ethnicity, age class (`mature_female`/`milf`/`teen`…), skin tone, hair (color/length/style), eye color, permanent facial features (mole/freckles/glasses/heterochromia)
   - **DROP**: breasts/body size, clothing & clothing-state, body atmosphere (sweat/steaming), role/occupation, pose, baked-in expressions (smile/blush/tongue_out…)
   - Example: `1girl, japanese, mature_female, fair_skin, long_black_hair, brown_eyes`
   Show those rules inline in the prompt so Hai doesn't have to context-switch.

7. **Negative tags** — optional. Default to st-setup's `NEG` constant (updated 2026-05-25 with framing guards): `lowres, worst quality, bad anatomy, deformed_face, extra_eyes, watermark, text, multiple_characters, duplicate, close-up, extreme_close-up, cropped, partial_face, single_eye, from_behind, from_side, breasts_focus, torso_focus, body_focus, hair_over_face, hair_over_eyes, looking_away, looking_down`.

**Assemble `PERSONA_DESC`** (same shape as Phase 2):
```
Name: {name}
Age: {age}
Gender: {gender}
Appearance: {appearance}
Demeanor: {demeanor}
Social context: {social_context}
{optional keywords line — omit if blank}

[Visual reference for image generation:
{FACE_ID}]
```

**Confirm with `AskUserQuestion`:**

Display:
```
PROPOSED PERSONA DESCRIPTION:
{assembled block}
```

Options:
- "Use as-is"
- "Let me edit" → ask Hai to paste preferred version, then re-confirm

Store `PERSONA_DESC` + `FACE_ID` + `NEG` for Phase 3-new. **Do not run Phase 2.**

---

## Phase 2: Transform Card → Persona Description

Char card text ≠ persona description. Need to **transform**, not just copy:

| Aspect | Char card has | Persona needs |
|--------|---------------|---------------|
| **POV** | 3rd person ("she thinks X", "he reacts by Y") | 1st person OR neutral self-insert framing |
| **RP mechanics** | "Always speaks formal Japanese", "Never breaks character" | Removed — these direct LLM behavior, not persona identity |
| **Backstory** | Multi-paragraph history, lore, relationships | Trimmed to identity-defining basics |
| **Behavioral lock-ins** | "Submissive type, always defers" | Removed unless Hai genuinely wants persona to act this way |
| **Pronouns lock** | Card may assume "{{user}} is male" or vice versa | Verified compatible — flag conflicts |
| **Visual** | Often buried in prose | Explicit at top + Booru tag block |

**LLM transformation task:**

Given the raw char description, produce a **compact persona description** with this structure:

```
Name: {name}
Age: {age}
Gender: {gender}
Appearance: {1-3 sentences — visual identity, body, ethnicity, style}
Demeanor: {1-2 sentences — first-impression vibe, how others perceive {{user}}}
Social context: {1 sentence — role/position that shapes how NPCs treat {{user}}}
{Optional 1-2 lines of personality keywords if Hai wants persona to feel a certain way}

[Visual reference for image generation:
{char_visual_pos from char_prompts, or LLM-derived if not set}]
```

**Why "Demeanor" + "Social context" sections?**
When other {{char}} encounters this persona in a new chat, they need enough signal to react authentically. Without these, {{char}} treats {{user}} as a blank slate. Examples:

- *Naoko persona*: Demeanor = "sweet, oblivious, easily flustered". Social context = "Japanese housewife, late 30s, lives in suburban home". → A {{char}} like a sleazy stranger reads this as "easy target", a {{char}} like a kind neighbor reads "warm, caring lady". Both react authentically.
- *Demon Lord persona*: Demeanor = "imposing, speaks with authority, cold gaze". Social context = "ruler of the seven hells". → {{char}} reactions auto-calibrate (fear/reverence/defiance).

These traits SHAPE how {{char}} reacts but DON'T direct {{char}}'s behavior verbatim. Difference:
- ✅ "Demeanor: sweet and oblivious" → {{char}} chooses how to react
- ❌ "Other characters always find {{user}} attractive" → directing {{char}}'s response (RP-mechanic, drop)

**What to drop during transformation:**
- LLM directive language ("always X", "never Y", "responds with Z")
- Extended backstory (parents, occupation history, past trauma) unless identity-critical
- Combat/skill descriptions
- World-building paragraphs (those belong in lorebook)
- POV-locked phrases ({{user}} assumed male/female that conflicts)

**What to keep:**
- Name, age, gender, ethnicity
- Physical appearance (height, body, hair, eyes, distinctive features)
- 1-2 personality anchors if Hai wants persona to read a certain way (e.g., "sweet, oblivious")
- Current outfit/style if defining

**Show user with AskUserQuestion:**

Display side-by-side:
```
ORIGINAL CARD DESCRIPTION:
{first 500 chars of card description...}

PROPOSED PERSONA DESCRIPTION:
{transformed compact version}
```

Options:
- "Use proposed"
- "Use original verbatim"
- "Let me edit"

If "edit": ask user to paste their preferred version.

**Pronoun lock check:**
Scan card for hardcoded `{{user}}` gender assumptions ("{{user}}'s cock", "her boobs press against him", etc.). If found, flag to Hai: *"Card assumes {{user}} = {male/female}. Persona inherits this — OK or remove?"*

---

## Phase 3: Migrate (via MCP, no container restart)

`mcp__st__st_save_settings` routes through ST's save handler — no race with `saveSettingsDebounced`. Container stays up.

### Avatar source

Branch by `new_mode`:
- `new_mode == False` → run **Phase 3 file ops (convert)** below — copy existing PNG.
- `new_mode == True` → run **Phase 3-new (Forge gen)** below — generate avatar via Forge txt2img before anything else. Bail early if Forge isn't up so no half-state is written.

#### Phase 3 file operations — convert mode (PNG copy)

```python
import shutil, os

CHARACTERS = "/home/haint/Projects/home-server/sillytavern/data/default-user/characters"
USER_AVATARS = "/home/haint/Projects/home-server/sillytavern/data/default-user/User Avatars"

src_png = f"{CHARACTERS}/{CharName}.png"
persona_avatar = f"{CharName} (Persona).png"
dst_png = f"{USER_AVATARS}/{persona_avatar}"

os.makedirs(USER_AVATARS, exist_ok=True)

# Copy avatar to User Avatars (direct file op — no API for this)
shutil.copy2(src_png, dst_png)

# Remove original IF --remove flag
if remove_original:
    os.remove(src_png)
    # Note: expressions folder characters/{CharName}/ stays — user may want to restore later
```

#### Phase 3-new: Avatar via Forge txt2img (new mode)

Reuses the established pattern from `/home/haint/Projects/home-server/.claude/skills/st-setup/SKILL.md` lines 414–533. **Pre-flight first** — if Forge is down, abort BEFORE writing any ST settings (no orphaned persona).

```python
import requests, base64, os

USER_AVATARS = "/home/haint/Projects/home-server/sillytavern/data/default-user/User Avatars"
persona_avatar = f"{CharName} (Persona).png"
dst_png = f"{USER_AVATARS}/{persona_avatar}"
os.makedirs(USER_AVATARS, exist_ok=True)

FORGE = "http://localhost:7860"

# Pre-flight — bail clean if Forge not up
try:
    r = requests.get(f"{FORGE}/sdapi/v1/sd-models", timeout=3)
    assert r.status_code == 200
except Exception:
    raise RuntimeError("Forge is not running. Start it with `./scripts/up.sh forge`, then re-run /st-persona <Name> --new. No settings were written.")

CHAR_SEED = 12345  # framing-neutral; override per persona if Hai wants a specific roll
# Framing validated 2026-05-25 (mirrors /st-setup Phase 3 sprite recipe):
#   - `head_and_shoulders, large_face, simple background` keeps face dominant.
#   - Earlier `portrait, close-up, face_focus` collapsed NoobAI into single-eye
#     crops — Naoko avatar gen burned 3 regen attempts before headshot landed.
prompt = (
    f"{FACE_ID}, head_and_shoulders, from_front, looking_at_viewer, neutral_expression, "
    f"large_face, centered_composition, simple background, "
    f"masterpiece, best quality, newest, absurdres, highres, soft_lighting, detailed_face"
)

payload = {
    "prompt": prompt,
    "negative_prompt": NEG,          # from Phase 1-new step 7 (default = st-setup NEG)
    "sampler_name": "Euler",
    "scheduler": "Karras",
    "steps": 20,
    "cfg_scale": 5,
    "width": 512,
    "height": 768,
    "seed": CHAR_SEED,
    "enable_hr": False,
}

def gen_once():
    r = requests.post(f"{FORGE}/sdapi/v1/txt2img", json=payload, timeout=120)
    r.raise_for_status()
    img_b64 = r.json()["images"][0]
    with open(dst_png, "wb") as f:
        f.write(base64.b64decode(img_b64))
    return dst_png

gen_once()
print(f"Avatar written: {dst_png}")
```

**Then ask via `AskUserQuestion`:** *"Avatar OK? (preview the PNG in your file manager)"* — options `Keep` / `Regenerate (new seed)` / `Save anyway and I'll swap manually`. On `Regenerate`, bump `payload["seed"]` to a fresh value (e.g. `random.randint(1, 999_999_999)`) and call `gen_once()` again. Cap at 1–2 regen attempts to keep it simple; after that, save and move on.

### Settings edits via path-based MCP writes

Each binding is one surgical call — no full-tree round trip needed. Behavior branches lightly by `new_mode`.

**Path gotcha:** `persona_avatar` ends in `.png`, and `_set_path` splits on `.` — naked `power_user.personas.{persona_avatar}` corrupts the tree. Use bracket-escape syntax `["..."]` for any leaf key that contains dots. The st-mcp parser supports `parent.path.["literal.key"]` (the dot before the bracket is optional).

```python
import json

if new_mode:
    # New persona has no source char and no prior lorebook expected.
    linked_book = ''
else:
    # Convert mode: auto-link if a lorebook with this name already exists.
    world_names = json.loads(mcp__st__st_get_settings(path="world_names")) or []
    linked_book = CharName if CharName in world_names else ''

persona_desc_obj = {
    'description': PERSONA_DESC,   # text built in Phase 2 (convert) or Phase 1-new (new)
    'position': 0,                 # 0 = before char defs
    'depth': 2,                    # @ depth 2
    'role': 0,                     # 0 = system role
    'lorebook': linked_book,       # auto-link if lorebook exists
    'title': '',
    'connections': []
}

# Bracket-escape leaf keys that contain '.' (the avatar filename ends in .png)
persona_key = f'["{persona_avatar}"]'

# 1. Register persona name → avatar mapping
mcp__st__st_save_settings_path(path=f"power_user.personas.{persona_key}", value=CharName)

# 2. Persona description object
mcp__st__st_save_settings_path(path=f"power_user.persona_descriptions.{persona_key}", value=persona_desc_obj)

# 3. Cleanup char_prompts ONLY if --remove (convert mode, char file deleted → no longer a {{char}}).
#    Skipped entirely in new mode — no source char ever existed.
#    CharName typically has no dots — plain dotted path is fine here.
if remove_original and not new_mode:
    mcp__st__st_save_settings_path(path=f"extension_settings.sd.character_prompts.{CharName}", value="")
    mcp__st__st_save_settings_path(path=f"extension_settings.sd.character_negative_prompts.{CharName}", value="")
    print(f"Cleared char_prompts['{CharName}'] (char file deleted)")
elif not new_mode:
    print(f"Kept char_prompts['{CharName}'] (char file still usable as {{{{char}}}} in other chats)")
```

**Ask user with AskUserQuestion:** "Set this as active persona now?" → if yes:
```python
mcp__st__st_save_settings_path(path="user_avatar", value=persona_avatar)
```

No container restart needed.

---

## Phase 4: Report

**Convert mode:**
```
=== Persona Migration: {CharName} → User Persona ===

✓ Avatar copied: characters/{CharName}.png → User Avatars/{CharName} (Persona).png
[✓ Original char file removed (--remove flag) | ⚠ Original kept — char_prompts intact for future {{char}} RP]
✓ Persona description: {len(PERSONA_DESC)} chars (visual block embedded)
[✓ Lorebook linked: {CharName}.json | ⊘ No lorebook found — create with /st-setup --lore first]
[✓ Removed char_prompts['{CharName}'] (--remove flag) | ⊘ Kept char_prompts (char still available for {{char}} use)]
[✓ Set as active persona | ⊘ Active persona unchanged]

Next:
- Reload ST (Ctrl+Shift+R)
- Top-right persona dropdown → select '{CharName}' if not auto-active
- Test image gen with Mode 4: persona visual tags should appear in prompt
```

**New mode (`--new`):**
```
=== New Persona Created: {CharName} ===

✓ Avatar generated via Forge: User Avatars/{CharName} (Persona).png
✓ Persona description: {len(PERSONA_DESC)} chars (visual block embedded)
⊘ No lorebook linked — use /st-setup --lore later once you have RP material to bake
[✓ Set as active persona | ⊘ Active persona unchanged]

Next:
- Reload ST (Ctrl+Shift+R)
- Top-right persona dropdown → select '{CharName}' if not auto-active
- Test image gen with Mode 4: persona visual tags should appear in prompt
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| char_prompts not set yet (convert) | LLM derives visual tags from card description on the fly |
| Persona avatar already exists (both modes) | Ask user: overwrite, rename (e.g., "(Persona 2)"), or abort |
| Lorebook doesn't exist (convert) | Skip lorebook link, suggest `/st-setup --lore` first |
| Expression folder exists (convert) | Keep — `characters/{CharName}/` survives even if char file removed (some forks render persona expressions) |
| User wants to revert | Manual: delete persona avatar, copy from char folder back (convert), or just delete the generated PNG + drop the two `power_user.persona*` keys via MCP (new). Not implementing reverse — rare case, error-prone |
| `--new` + `--remove` both passed | Abort with: *"--new creates from scratch; nothing to --remove. Pick one."* |
| `--new` but `characters/{CharName}.png` exists | Abort: *"Char file already exists. Drop --new to convert it, or pick a different persona name."* |
| Forge not running in `--new` mode | Pre-flight check in Phase 3-new bails BEFORE any ST settings write — hint: `./scripts/up.sh forge` |
| Avatar gen result looks wrong (`--new`) | Offer 1–2 regen attempts with fresh seed; if still wrong, save anyway and tell Hai to swap the PNG manually |

---

## Related Skills

- `/st-setup <CharName>` → run first (convert flow) to establish char_prompts + (optional) lorebook before converting
- Convert flow:
  ```
  /st-setup Parasite --all       # baseline + 28 expressions + lorebook
  [RP for a while, decide it's the persona]
  /st-persona Parasite --remove  # migrate, delete original
  ```
- New-persona flow:
  ```
  ./scripts/up.sh forge          # Forge must be up for avatar gen
  /st-persona DemonLord --new    # Q&A + Forge txt2img → persona registered
  [RP for a while, optionally /st-arc-save to build a lorebook later]
  ```
