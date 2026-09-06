---
name: st-persona
model: sonnet
description: "Convert a SillyTavern character into a user persona — or create a new persona from scratch with --new. Migrates/builds visuals, lorebook link, avatar. `--lang vi|en` sets the campaign language (default vi)."
argument-hint: "<CharName> [--new | --remove | --voice] [--lang vi|en] [--from-recipe <path>] [--no-activate] [--avatar-file <png>] [--avatar-seed <n>]"
allowed-tools: Bash, AskUserQuestion, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_character
---

# ST Persona — Character → Persona Migration (or scratch build)

Two modes:
- **Convert** (default): Hai's flow — import char from Chub/Janitor → find interesting → decide "this is my persona" → convert. Migrates an existing `{{char}}` into a user persona.
- **New** (`--new`): build a brand-new persona from scratch with no source character. Interactive Q&A for fields + Forge txt2img for the avatar.

ST has no built-in equivalent for `char_prompts` on the persona side, so the visual baseline must live in the `persona_description` text, where `/st-gen-image-prompt` reads it (avatar-keyed `power_user.persona_descriptions[<avatar>].description` is the authoritative visual source). This skill automates either path.

**Related:** `/st-cook` calls `--new --from-recipe`, then always `--voice` — every RP campaign needs the voice contract re-applied regardless of how the persona was built.

**Usage:**
```
/st-persona Washa                # convert, KEEP original char file (default safe)
/st-persona Washa --remove       # convert AND delete original char file
/st-persona DemonLord --new      # create brand-new persona — Q&A + Forge avatar gen
/st-persona Mizuho --voice       # re-apply the persona's voice contract to the global impersonate/guide prompts (after switching personas)
/st-persona DemonLord --new --from-recipe .../recipe.json                       # Q&A pre-filled, avatar via Forge, activates without asking
/st-persona DemonLord --new --from-recipe .../recipe.json --avatar-file old.png --no-activate  # reuse an archived avatar, don't switch personas
```

`--new` and `--remove` are mutually exclusive (nothing to remove when creating from scratch).

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
BASELINES = /home/haint/Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines  # owned by /st-gen-image-prompt
```

## What a persona actually spans

A persona is not one field. Four things carry persona state, and three of them are keyed differently from what you'd expect — which is where the mistakes come from. `/st-setup` → *[The card is not the only layer](#config-layers)* covers the character side; this is the persona-side counterpart.

| Piece | Keyed by | Watch for |
|---|---|---|
| `power_user.personas[<avatar>.png]` | **avatar filename** | value is the *display name*, and display names are not unique |
| `power_user.persona_descriptions[<avatar>.png]` | **avatar filename** | holds description + `lorebook` link; the visual tag block lives in the description text |
| `worlds/<lorebook>.json` | lorebook **name** | a full behavior layer — see below |
| `$BASELINES/<DisplayName>.txt` | **display name** | collides when two personas share a name |

**Display-name collision is the live hazard.** Two personas can both be named `Naoko` while pointing at different avatars and different bodies. Anything keyed by display name — the baseline `.txt`, a lorebook named after the persona — silently serves one persona's data to the other. When you need a persona's visuals, read the **avatar-keyed** `persona_descriptions[<avatar>].description` block; treat the `.txt` as a convenience copy that may be stale or belong to a namesake. When creating a persona whose display name already exists, say so and let the user pick a distinct name.

**`{{char}}` inside a persona lorebook does not mean the persona.** World Info macros resolve against the active chat: `{{user}}` is the persona, `{{char}}` is whatever character is loaded. So an entry written as "`{{char}}` resides inside her colon" only reads correctly while chatting with the one card the author had in mind, and turns into nonsense the moment that persona is used elsewhere. Name the entity explicitly in persona lorebooks — the whole point of binding a book to a persona is that it travels across characters.

**Constant entries follow the persona everywhere.** A `constant: true` entry in a persona lorebook injects on every turn of every chat that persona is active in. Established-state entries ("post-arc, already bonded") are the usual offenders: they contradict any fresh first-meeting greeting. Keep them keyed unless the state genuinely holds across all chats.

---

## Phase 0: Parse + Validate

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag token
- `new_mode` = `--new` flag present
- `remove_original` = `--remove` flag present
- `from_recipe` = path following `--from-recipe`, else `None` — read `recipe.json` there once, up front (`--new` only; a convert has no recipe)
- `no_activate` = `--no-activate` flag present — skips the "set active now?" question in Phase 3 and leaves the previous persona active
- `avatar_file` = path following `--avatar-file`, else `None` — a persona PNG to reuse (e.g. an archived avatar from a `--close`d campaign) instead of generating one
- `avatar_seed` = int following `--avatar-seed`, else `None` — seeds the first Forge generation instead of the default `12345`
- `lang` = value following `--lang` (`vi`/`en`), else derived: `--from-recipe` → `recipe.language`; else path-read `oai_settings.prompts` for an entry with identifier `lang_vi` — `enabled: true` ⇒ `vi`, else `en`. Default `vi` when nothing resolves.

**Flag validation:**
- `--new` and `--remove` are **mutually exclusive** → abort with: *"--new creates from scratch; nothing to --remove. Pick one."*
- `--avatar-file` and `--avatar-seed` only make sense with `--new`; `--from-recipe` only makes sense with `--new` (a convert reads the source card, not a recipe)

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
- Else → LLM analyze card description and extract visual booru tags on the fly (positive only — negatives less critical for persona). The visual block is permanent and appended to every render, so keep it to always-true appearance (body, hair, eyes, skin, permanent features) — pose, setting, framing, and blanket exclusions like "no humans" belong in the per-shot baseline `.txt` that `/st-gen-image-prompt` writes, not here.

---

## Phase 1-new: Interactive Q&A (new mode only)

Run this section instead of Phase 1 + Phase 2 when `--new` is set. The output is a `PERSONA_DESC` string in the **same shape** the convert flow produces (so Phase 3 stays unified), plus a `FACE_ID` tag string used by Forge in Phase 3-new.

**`--from-recipe <path>` skips the interactive gather below.** Map `recipe.persona.*` straight onto the seven groups — `name`/`age`/`gender`/`ethnicity` → group 1, `appearance` → group 2, `demeanor` → group 3, `social_context` → group 4, `keywords` → group 5, `face_id` → group 6, `negatives` → group 7 (fall back to the `NEG` constant if empty) — and skip the confirm at the end of this phase: the orchestrator already had Hải confirm the concept before dispatching. Take `PERSONA_DESC` from `_scripts/<slug>/rendered/persona-description.txt` if that file exists (already assembled, `[Voice: …]` block included from Phase 4); otherwise assemble it from the mapped fields in the shape below. Print the assembled block and continue straight to Phase 3-new.

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

6. **Visual booru tags (FACE_ID)** — REQUIRED for Forge avatar gen. Apply the face-scoping **KEEP/DROP rule** from `/st-setup` → *Phase 3: Expression Sprites* (find the `# --- Face-scoped identity` comment banner in that phase's code block):
   - **KEEP**: subject count (`1girl`/`1boy`), ethnicity, age class (`mature_female`/`milf`/`teen`…), skin tone, hair (color/length/style), eye color, permanent facial features (mole/freckles/glasses/heterochromia)
   - **DROP**: breasts/body size, clothing & clothing-state, body atmosphere (sweat/steaming), role/occupation, pose, baked-in expressions (smile/blush/tongue_out…)
   - Example: `1girl, japanese, mature_female, fair_skin, long_black_hair, brown_eyes`
   Show those rules inline in the prompt so Hai doesn't have to context-switch. This block becomes the permanent visual layer, appended to every future render of this persona — keep it to always-true appearance only; pose, setting, framing, and "no humans"-style exclusions belong in the per-shot baseline `.txt` that `/st-gen-image-prompt` writes, not here.

7. **Negative tags** — optional. Default = the `NEG` constant in `/st-setup` → *Phase 3: Expression Sprites* (read it from that code block at run time, don't copy it verbatim — it drifts).

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

**Confirm with `AskUserQuestion` (skip under `--from-recipe` — already printed and confirmed upstream):**

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

`mcp__st__st_save_settings_path` routes through ST's save handler — the MCP server re-fetches settings, sets one path, and POSTs the bare dict to `/api/settings/save`, so there's no full-tree round trip and no race with `saveSettingsDebounced`. Container stays up.

### Avatar source

Branch by `new_mode`:
- `new_mode == False` → run **Phase 3 file ops (convert)** below — copy existing PNG.
- `new_mode == True` → run **Phase 3-new (Forge gen)** below — generate avatar via Forge txt2img before anything else. Bail early if Forge isn't up so no half-state is written.

#### Phase 3 file operations — convert mode (PNG copy)

```python
import shutil, os

ST_DATA = "/home/haint/Projects/home-server/sillytavern/data/default-user"
CHARACTERS = f"{ST_DATA}/characters"
USER_AVATARS = f"{ST_DATA}/User Avatars"

src_png = f"{CHARACTERS}/{CharName}.png"
persona_avatar = f"{CharName} (Persona).png"
dst_png = f"{USER_AVATARS}/{persona_avatar}"

os.makedirs(USER_AVATARS, exist_ok=True)

# ST's thumbnail cache invalidates by mtime (originalStat.mtimeMs > cachedStat.ctimeMs).
# copy2 preserves the SOURCE file's mtime, which for an imported card is usually older
# than the cached thumb — the persona picker would keep showing the old face.
# Plain copy() stamps a fresh mtime instead.
if os.path.exists(dst_png):
    thumb = f"{ST_DATA}/thumbnails/persona/{persona_avatar}"
    if os.path.exists(thumb):
        os.remove(thumb)  # overwrite branch: force thumb regen even if mtime ties
shutil.copy(src_png, dst_png)

# Remove original IF --remove flag
if remove_original:
    os.remove(src_png)
    # Note: expressions folder characters/{CharName}/ stays — user may want to restore later
```

#### Phase 3-new: Avatar via Forge txt2img (new mode)

**`--avatar-file <png>` skips Forge entirely.** When reusing an already-approved avatar — typically one archived by a `--close` — copy it straight in, same reasoning as the convert path's file copy (see above): plain `shutil.copy` stamps a fresh mtime so ST's thumbnail cache invalidates.

```python
import shutil, os
USER_AVATARS = "/home/haint/Projects/home-server/sillytavern/data/default-user/User Avatars"
persona_avatar = f"{CharName} (Persona).png"
dst_png = f"{USER_AVATARS}/{persona_avatar}"
os.makedirs(USER_AVATARS, exist_ok=True)
shutil.copy(avatar_file, dst_png)
print(f"Avatar reused: {avatar_file} → {dst_png}")
```

No Keep/Regenerate question in this branch — the face was already judged before it was archived.
Skip straight to **Settings edits via path-based MCP writes** below.

Otherwise, reuse the **Forge txt2img recipe** from `/st-setup` → *Phase 3: Expression Sprites* (framing tags, fixed seed, negative constant). **Pre-flight first** — if Forge is down, abort BEFORE writing any ST settings (no orphaned persona).

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

CHAR_SEED = avatar_seed or 12345  # --avatar-seed overrides; 12345 is framing-neutral otherwise
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

world_names = json.loads(mcp__st__st_get_settings(path="world_names")) or []
if new_mode:
    # A scratch persona normally has no book yet — but /st-cook seeds worlds/<Name>.json
    # (Novelty Ledger) BEFORE dispatching this skill, so link it when it exists.
    linked_book = CharName if CharName in world_names else ''
else:
    # Convert mode: auto-link if a lorebook with this name already exists.
    linked_book = CharName if CharName in world_names else ''

persona_desc_obj = {
    'description': PERSONA_DESC,   # text built in Phase 2 (convert) or Phase 1-new (new)
    'position': 4,                 # AT_DEPTH — depth/role are only read when position is AT_DEPTH (4); other enum values (IN_PROMPT=0, TOP_AN=2, BOTTOM_AN=3, NONE=9) ignore both
    'depth': 2,                    # @ depth 2 — strong presence but competes with per-turn anchors (vs IN_PROMPT=0: stable but diluted at the top of the prompt)
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

Clearing to `""` rather than deleting the key leaves an entry with no card behind it. That's harmless at runtime but it accumulates, and it makes later audits noisier — a key with no `characters/<name>.png` reads as either "orphan to clean up" or "card I'm about to restore", and nobody remembers which. Mention it in the report so the user can decide now, while the context is fresh.

**The persona's visual block does not inherit the character's negative.** `char_prompts` has no persona equivalent — only the positive tags survive, embedded in the description text. If the source character's negative held anything load-bearing (body-shape guards like `masculine, male, flat_chest` for a female persona), it is simply gone after conversion. Say so explicitly rather than letting the user discover it through bad renders. If those guards matter, they belong in `sd.negative_prompt` (global) or in the per-shot negative — not silently dropped.

**Ask user with AskUserQuestion: "Set this as active persona now?"** — skip the question under `--no-activate` (stay on the previous persona) or under `--from-recipe` without `--no-activate` (activate without asking; the orchestrator already committed to this persona for the campaign). In every case where the answer is yes, write all THREE fields — ST injects the persona lorebook from the GLOBAL `power_user.persona_description_lorebook` (`world-info.js` `getPersonaLorebook`), and only the UI dropdown copies `descriptor.lorebook` into it (`personas.js` `loadPersona`). Setting `user_avatar` alone leaves the previous persona's book injecting on every turn (2026-08-30: Mizuho active, Naoko's constants still injected):
```python
mcp__st__st_save_settings_path(path="user_avatar", value=persona_avatar)
mcp__st__st_save_settings_path(path="power_user.persona_description_lorebook", value=linked_book)
mcp__st__st_save_settings_path(path="username", value=CharName)   # top-level `username` = name1, the name printed on every user message (script.js:7871); the UI dropdown sets it via setUserName, an MCP switch must do it by hand (2026-08-31: Mizuho active, every turn labelled "Naoko")
```

No container restart needed.

---

## Phase 3.5: Verify the config layers

Persona changes ripple outward — a converted character leaves `char_prompts` behind, a linked lorebook keeps whatever `{{char}}` meant before, a `--remove` empties keys without removing them. Run the shared auditor before reporting so the summary reflects reality rather than intent:

```bash
python3 /home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py
```

Read-only, safe while ST is up, non-zero exit when something is flagged. Relevant here: orphan `character_prompts` entries, persona-linked lorebooks that are missing or full of `{{char}}`, and constants injecting on every turn. Fold the findings into the report as recommendations — these are judgment calls, not auto-fixes.

Also confirm the `[Voice — …]` block and `oai_settings.impersonation_prompt` name the campaign language explicitly (`written in Vietnamese`/`written in English`, `in {language} — the language of the chat`) — a stale label after a language switch stays silent until read aloud.

If the persona's display name already existed before this run, re-check `$BASELINES/` for a `.txt` under that name; it now serves two personas and one of them will get the wrong body.

---

## Phase 4: Voice contract (both modes; alone with `--voice`)

A persona is also a *voice*: when Hải presses Guided Impersonate, ST writes `{{user}}`'s turn from
two global prompts that know nothing about who the persona is — `oai_settings.impersonation_prompt`
(ST core; the real instruction) and the Guided Generations wrapper `promptImpersonate1st`, which
runs `/impersonate <wrapper>`. Guided Response / Continue inject `promptGuidedResponse` /
`promptGuidedContinue` as a system line at depth 0 on the narrator side. This phase writes all
four from the persona so an impersonation and a guided page both read in her evolving register
instead of freezing at a fixed one. `impersonation_prompt` is an ENRICHMENT ENGINE, not a transcriber: it takes
whatever `{{user}}` sketched (or nothing) and grows it, at an EVOLVING register that climbs with
the story rather than a register fixed at chapter 1 (v3, PROMPT-PLAYBOOK.md gotcha 5.48). The
fields are global — re-run `/st-persona <Name> --voice` whenever the active persona changes.

**Compose the `[Voice — …]` block** (≤ 70 words) and keep it inside `PERSONA_DESC` after the visual
block, so `--voice` can regenerate everything from the persona alone. Voice is not fixed — it's a
register that erodes as the story climbs (v3, PROMPT-PLAYBOOK.md gotcha 5.48). Label the scope: the
persona description injects at depth 2 on narrator turns too, and an unlabelled first-person block
pulled the narrator into "tôi" in the 2026-09-06 test.

```
[Voice — {{user}}'s own turns only (impersonation), written in {Vietnamese|English}: first person
'{tôi|I}', present tense. Register: {2–4 words — e.g. controlled, self-critical, apologetic, files
everything under a category}. The register erodes as the story climbs: euphemism → naming → wanting
→ planning. She perceives everything; what she refuses is only ever the conclusion. The narrator's
pages are third person and follow their own contract.]
```

**`--from-recipe`** skips composing the four strings below: read them verbatim from `_scripts/<slug>/rendered/gg.json` (keys `impersonation_prompt`, `promptImpersonate1st`, `promptGuidedResponse`, `promptGuidedContinue`) if that file exists, and write them as-is. Compose from the persona (below) only when the file is missing.

Then write the four fields via `mcp__st__st_save_settings_path` (the GG key has a hyphen, no dot —
plain path is fine):

```python
name = CharName
register_early = REGISTER_EARLY  # the text after "Register:" in the [Voice — …] block above (2–4 words)
language = "Vietnamese" if lang == "vi" else "English"  # lang from Phase 0

IMPERSONATION = f"""[Write {{{{user}}}}'s next message as {name}, first person, present tense, in {language} — the language of the chat. Her voice grows with the story: early she is {register_early} — and her words for her own body stay small; as the creature earns more of her, her vocabulary follows — what she once filed she begins to name, then to want, then to plan. Match her current rung, not her first one.

If text is already drafted in the input field, treat it as {{{{user}}}}'s SKETCH — the skeleton of what {{{{user}}}} wants. Preserve every action, observation and decision in it; never delete, contradict or reverse them. Enrich around them: sensory atmosphere, body language, inner sensation, the excuse or the appetite she reaches for. You may extend the sketch by one organic beat that grows from what it set up — never override its direction or hijack the scene.

If no sketch is given, write her reply from the chat history under the same principles.

Style: *italics for action, sensation and inner experience*, "quotes for her spoken words". Concrete detail over abstraction. Explicit language is allowed at the rung she has reached. Write 1 reply only, strictly her POV — never write the narrator's arrivals or other characters' inner lives; what they do around her she may see, hear and feel.]"""

GG = "extension_settings.GuidedGenerations-Extension"
mcp__st__st_save_settings_path(path="oai_settings.impersonation_prompt", value=IMPERSONATION)
mcp__st__st_save_settings_path(path=f"{GG}.promptImpersonate1st",
    value=f"[Write {{{{user}}}}'s next message as {name}, first person, present tense, in her own voice, in {language} — the language of the chat. Guide: {{{{input}}}}]")
mcp__st__st_save_settings_path(path=f"{GG}.promptGuidedResponse",
    value="[Take the following into special consideration for your next message: {{input}}. Advance the scene at the pace it earns — consequences, arrivals, other characters, and {{user}}'s body and half-thoughts as far as the story has earned them. End on the page-turn.]")
mcp__st__st_save_settings_path(path=f"{GG}.promptGuidedContinue",
    value="[Continue the story based on the following input: {{input}}. Advance the scene honestly at the pace it earns. End on the page-turn.]")
```

`/st-arc-plan` appends a chapter register line to `promptImpersonate1st`; `/st-arc-save` strips it.
Never edit the preset's Main Prompt or PHI for this — they are shared by every card; the card's own
`system_prompt` / `post_history_instructions` carry the narrator-side contract.

**`--voice` alone:** skip Phases 0–3. Read `power_user.persona_descriptions[<avatar>].description`
for the active persona (`user_avatar`; bracket-escape the dotted key), take its `[Voice: …]` block
(if absent, compose one from the description and ask Hải to confirm), write the four fields, run the
Phase 3.5 audit, report.

## Phase 5: Report

**Convert mode:**
```
=== Persona Migration: {CharName} → User Persona ===

✓ Avatar copied: characters/{CharName}.png → User Avatars/{CharName} (Persona).png
[✓ Original char file removed (--remove flag) | ⚠ Original kept — char_prompts intact for future {{char}} RP]
✓ Persona description: {len(PERSONA_DESC)} chars (visual block embedded, position=AT_DEPTH depth=2)
language: {vi|en}
[✓ Lorebook linked: {CharName}.json | ⊘ No lorebook found — bind one later with /st-arc-save once you have RP material, or hand-write worlds/<Name>.json and set persona_descriptions[<avatar>].lorebook via st_save_settings_path]
[✓ Removed char_prompts['{CharName}'] (--remove flag) | ⊘ Kept char_prompts (char still available for {{char}} use)]
[✓ Set as active persona | ⊘ Active persona unchanged]

Next:
- Reload ST (Ctrl+Shift+R)
- Top-right persona dropdown → select '{CharName}' if not auto-active
- Run /st-gen-image-prompt, paste the output into the 🎨 Freestyle QR (Mode FREE=6 pass-through), confirm the persona's tags survive into the render
```

**New mode (`--new`):**
```
=== New Persona Created: {CharName} ===

✓ Avatar generated via Forge: User Avatars/{CharName} (Persona).png
✓ Persona description: {len(PERSONA_DESC)} chars (visual block embedded, position=AT_DEPTH depth=2)
language: {vi|en}
⊘ No lorebook linked — bind one later with /st-arc-save once you have RP material, or hand-write worlds/<Name>.json and set persona_descriptions[<avatar>].lorebook via st_save_settings_path
[✓ Set as active persona | ⊘ Active persona unchanged]

Next:
- Reload ST (Ctrl+Shift+R)
- Top-right persona dropdown → select '{CharName}' if not auto-active
- Run /st-gen-image-prompt, paste the output into the 🎨 Freestyle QR (Mode FREE=6 pass-through), confirm the persona's tags survive into the render
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| char_prompts not set yet (convert) | LLM derives visual tags from card description on the fly |
| Persona avatar already exists (both modes) | Ask user: overwrite, rename (e.g., "(Persona 2)"), or abort |
| Lorebook doesn't exist (convert) | Skip lorebook link; bind one later with `/st-arc-save` once there's RP material, or hand-write `worlds/<Name>.json` and set `persona_descriptions[<avatar>].lorebook` |
| Expression folder exists (convert) | Keep — `characters/{CharName}/` survives even if char file removed (some forks render persona expressions) |
| User wants to revert | Manual: delete persona avatar, copy from char folder back (convert), or just delete the generated PNG + drop the two `power_user.persona*` keys via MCP (new). Not implementing reverse — rare case, error-prone |
| `--new` + `--remove` both passed | Abort with: *"--new creates from scratch; nothing to --remove. Pick one."* |
| `--new` but `characters/{CharName}.png` exists | Abort: *"Char file already exists. Drop --new to convert it, or pick a different persona name."* |
| Forge not running in `--new` mode | Pre-flight check in Phase 3-new bails BEFORE any ST settings write — hint: `./scripts/up.sh forge` |
| Avatar gen result looks wrong (`--new`) | Offer 1–2 regen attempts with fresh seed; if still wrong, save anyway and tell Hai to swap the PNG manually |
| `--voice` on a persona whose block still reads "[Voice: first person…" (pre-2026-09-06) | Regenerate with the labelled `[Voice — …]` form |

---

## Related Skills

- `/st-setup <CharName>` → run first (convert flow) to establish char_prompts + (optional) lorebook before converting
- A narrator/creature card (e.g. Parasite) is not persona material — persona is the body `{{user}}` wears, and narrator cards are wordless by design.
- Convert flow:
  ```
  /st-setup <CharName> --lore    # baseline + lorebook (skip --expr/--all for non-humanoid — persona candidates are humanoid)
  [RP for a while, decide it's the persona]
  /st-persona <CharName> --remove  # migrate, delete original
  ```
- New-persona flow:
  ```
  ./scripts/up.sh forge          # Forge must be up for avatar gen
  /st-persona DemonLord --new    # Q&A + Forge txt2img → persona registered
  [RP for a while, optionally /st-arc-save to build a lorebook later]
  ```
