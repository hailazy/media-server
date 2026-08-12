---
name: st-gen-image-prompt
model: sonnet
description: "Build ST image gen prompt — booru tags from chat scene"
argument-hint: "[CharName] [--describe '<text>'] [--last N] [--no-clipboard]"
allowed-tools: Bash, Read, mcp__st__st_get_character, mcp__st__st_get_settings, mcp__st__st_get_recent_chat
---

# ST Gen Image Prompt — booru-tag prompt builder for /sd FREE

Generate complete booru-tag image prompt cho SillyTavern. Replaces Magnum Mode 4 extraction. Output paste-ready for ST `🎨 Freestyle` button (Mode FREE=6 pass-through).

**Workflow:**
1. Read chat context (last N msgs từ ST chat .jsonl) HOẶC `--describe '<custom>'`
2. Read identity baseline từ `data/identity-baselines/<CharName>.txt`
3. Generate booru tags theo NoobAI XL conventions
4. Verify tags qua Danbooru DB (lazy fetch ~5MB CSV vào `~/.cache/`)
5. Output paste-ready prompt + verification report

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
SKILL_DIR = ~/Projects/home-server/.claude/skills/st-gen-image-prompt
SKILL_DATA = $SKILL_DIR/data
CACHE_DIR = ~/.cache/st-gen-image-prompt
DEFAULT_LAST_N = 10
TAG_DB_URL = https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/main/tags/danbooru.csv
TAG_DB_TTL_DAYS = 30
MIN_TAG_COUNT = 50
```

---

## Phase 0: Parse Arguments

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag positional. If absent → auto-detect from latest `chats/<dir>/*.jsonl` mtime.
- `--describe '<text>'` → custom scene (overrides chat reading)
- `--last N` → number of chat messages to read (default 10)
- `--no-clipboard` → skip auto-copy to clipboard (default = auto-copy enabled)

Validate:
- Char folder `chats/<CharName>/` exists OR `--describe` given. If neither → error.

---

## Phase 1: Gather Context

**Step 0 — Ensure tag DB cache:**

```python
import urllib.request, time
from pathlib import Path

CACHE = Path.home() / ".cache/st-gen-image-prompt"
CACHE.mkdir(parents=True, exist_ok=True)
csv_path = CACHE / "danbooru.csv"
ts_path = CACHE / ".last_fetch"

needs_fetch = not csv_path.exists()
if not needs_fetch and ts_path.exists():
    needs_fetch = (time.time() - ts_path.stat().st_mtime) > 30 * 86400

if needs_fetch:
    print("Fetching Danbooru tag DB (~5-10MB, one-time, cached 30d)...")
    url = "https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/main/tags/danbooru.csv"
    urllib.request.urlretrieve(url, csv_path)
    ts_path.touch()
    print(f"✓ Cached: {csv_path} ({csv_path.stat().st_size // 1024}KB)")
```

**Step 1 — Read char card via MCP** (replaces legacy PNG tEXt parse):

```python
import json

resp = mcp__st__st_get_character(name=CharName)
card = json.loads(resp) if isinstance(resp, str) else resp
d = card.get('data', card)  # spec v3 nests under 'data'
print(f"NAME: {d.get('name', CharName)}")
print(f"DESCRIPTION: {d.get('description', '')[:1500]}")
print(f"PERSONALITY: {d.get('personality', '')[:300]}")
print(f"SCENARIO: {d.get('scenario', '')[:300]}")
```

**Step 2 — Read persona via path-based MCP** (each call returns a small subtree):

```python
import json

avatar = json.loads(mcp__st__st_get_settings(path="user_avatar")) or ''
# Avatar filenames contain dots ("... (Persona).png"). The MCP path parser splits
# on every bare dot, so a dotted path DIES INSIDE THE KEY and silently returns
# empty — the persona branch would always read as "no persona". Bracket-escape
# any leaf key that contains a dot: parent.["literal.key"].
try:
    persona_name = json.loads(mcp__st__st_get_settings(path=f'power_user.personas.["{avatar}"]'))
except Exception:
    persona_name = ''
try:
    persona_desc = json.loads(mcp__st__st_get_settings(path=f'power_user.persona_descriptions.["{avatar}"].description'))
except Exception:
    persona_desc = ''
print(f"PERSONA: {persona_name} (avatar={avatar})")
print(f"PERSONA_DESC: {persona_desc[:1000]}")
```

**Step 3 — Read identity baseline**:

```python
from pathlib import Path
BASELINE_DIR = Path.home() / "Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines"

char_baseline = ""
char_baseline_file = BASELINE_DIR / f"{CharName}.txt"
if char_baseline_file.exists():
    char_baseline = char_baseline_file.read_text(encoding='utf-8').strip()
    print(f"CHAR_BASELINE: {char_baseline}")
else:
    print(f"WARN: No per-shot baseline for {CharName}. Deriving identity from the card description (Step 1) instead.")

persona_baseline = ""
if persona_name:
    persona_baseline_file = BASELINE_DIR / f"{persona_name}.txt"
    if persona_baseline_file.exists():
        persona_baseline = persona_baseline_file.read_text(encoding='utf-8').strip()
        print(f"PERSONA_BASELINE: {persona_baseline}")
```

**Precedence**: `persona_desc` (Step 2, avatar-keyed `power_user.persona_descriptions.<avatar>.description`) is authoritative for persona visuals. Persona *display* names are not unique — two personas can share one — so `persona_baseline_file` above is keyed by display name and can serve a namesake's body. Treat it as a convenience copy only: when it disagrees with `persona_desc`, trust `persona_desc` and report the conflict in the output instead of silently using the `.txt`. (Baselines are keyed by CHARACTER name for cards, DISPLAY name for personas — know which one you're reading.)

**Step 3a — Read permanent layer** (ST auto-appends this to EVERY gen for this character — the skill must never duplicate it):

```python
import json

try:
    permanent_positive = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_prompts.{CharName}"))
except Exception:
    permanent_positive = ''
try:
    permanent_negative = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_negative_prompts.{CharName}"))
except Exception:
    permanent_negative = ''
print(f"PERMANENT_LAYER (auto-appended, do NOT re-emit): {permanent_positive}")
print(f"PERMANENT_NEGATIVE (auto-appended): {permanent_negative}")
```

**Step 4 — Read chat context via MCP** (skip if `--describe`):

```python
import json

# /api/chats/recent returns a list of {file_name, file_size, last_mes, ...}
recent_list = mcp__st__st_get_recent_chat(char_name=CharName)
recent_meta = json.loads(recent_list) if isinstance(recent_list, str) else recent_list
if not recent_meta:
    print("ERROR: No chat files found. Use --describe '<text>' instead.")
else:
    # Take top entry (most recent). To fetch full message array, use /api/chats/get
    # via a thin Bash curl call (not yet exposed as MCP tool):
    import subprocess
    file_name = recent_meta[0].get('file_name', '').rsplit('.jsonl', 1)[0]
    print(f"CHAT_FILE: {file_name}.jsonl")

    # Fallback to direct file read for full chat content (the lightweight option until
    # we add an st_get_chat MCP tool returning the full messages array):
    from pathlib import Path
    chat_path = Path("/home/haint/Projects/home-server/sillytavern/data/default-user/chats") / CharName / f"{file_name}.jsonl"
    msgs = []
    with open(chat_path, encoding='utf-8') as f:
        for line in f:
            try:
                m = json.loads(line)
                if 'mes' not in m or m.get('is_system'):
                    continue
                role = "USER" if m.get('is_user') else "CHAR"
                msgs.append(f"[{role}] {m['mes']}")
            except Exception:
                continue
    LAST_N = parsed_last or DEFAULT_LAST_N  # parsed_last = Phase 0's --last N, else the Constants default
    recent = msgs[-LAST_N:]
    print(f"\n=== Recent {len(recent)} messages ===")
    for m in recent:
        print(m[:500])
```

**When no baseline file exists**, after deriving identity from the card, offer to write it: propose the derived tags as `data/identity-baselines/<CharName>.txt` content, and on user confirmation write the file so future runs read it directly. (`/st-setup` writes this file for characters it onboards — Phase 1 strips per-shot tags out of `character_prompts` and lands them here — so a missing file just means the character predates that flow or was never onboarded; creating it here is the same contract, not a workaround.)

**Note:** `mcp__st__st_get_recent_chat` returns chat metadata (file names, sizes), not full message bodies. The direct `chats/{CharName}/{file}.jsonl` read above pulls the actual messages. A future `st_get_chat(char, file)` MCP tool would replace this fully.

**Step 5 — Read reference docs**:

Use `Read` tool to load:
- `~/Projects/home-server/forge/knowledge/noobai-conventions.md` — tag escape, prompt order, quality block (SHARED hub knowledge, also used by `/gen-art`)
- `~/Projects/home-server/.claude/skills/st-gen-image-prompt/data/prompt-template.md` — canonical example

---

## Phase 2: Generate Prompt (LLM task)

You (Claude) have all context. Now produce a NoobAI XL-compatible booru-tag prompt.

### Formatting & order

Tag formatting (underscore/space, paren escaping, artist prefix), the 9-slot prompt order, and the quality block are defined in `noobai-conventions.md` (loaded Step 5) — follow it as-is, don't re-derive here. Skill-specific on top of that: tag-count bands (Phase 2.5), identity injection (below), POV dedup (below).

### Identity injection rules

The identity baseline (`data/identity-baselines/<CharName>.txt`) is the per-shot layer. It stacks on top of the PERMANENT_LAYER (Step 3a, auto-appended by ST to every gen) — never re-emit a tag already present in PERMANENT_LAYER.

- **DEFAULT**: Prepend full identity baseline RIGHT after subject count.
- **NARRATOR/creature cards** (e.g. Parasite): the card narrates rather than appears on-screen, and its baseline may open with `no humans, 1other` for creature-only shots — that contradicts a `1girl` subject count when the persona is the one visible. Decide the subject from the scene: persona-present scenes take the persona baseline plus only the creature tags the shot needs; use the full char baseline only when the creature itself is the subject.
- **SKIP identity** for background-only scenes:
  - User `--describe` chứa "no people", "empty", "background only", "no characters" → skip identity
  - Detected via chat context: scene clearly setting-focused without {{char}} present
- **SKIP outfit** when scene shows different clothing state:
  - Bath/shower → skip clothing baseline (`naked`, `nude` from scene)
  - Different outfit specified in scene → use scene outfit, skip baseline outfit
- **PERSONA identity**: If scene includes {{user}} (NSFW interaction, dialogue with user), prepend persona identity baseline too.

### POV dedup (gotcha 5.32)

Pick AT MOST:
- ONE external view: `close-up | wide_shot | pov | side_view | from_below | from_above | dynamic_angle | foreshortening`
- ONE internal view (optional): `x-ray | internal_view | cross-section`

NEVER stack 3+ view tags. Stacking causes split composition / inset panels / duplicate subjects.

### Output discipline

- ONE continuous comma-separated line of booru tags
- NO prose, NO English explanations, NO section labels (`Action:`, `Scene:`)
- Emit only visual tags: anything that renders words or frames (`text`, `speech_bubble`, `dialogue`, `comic_panel`, `panels`, `watermark`) makes the model draw a comic page instead of a scene — the global negative already fights these too.
- End with: `(((masterpiece,best quality,newest,absurdres,highres)))`

---

## Phase 2.5: Tag Verification

For EACH tag in the draft prompt:

```python
def normalize_tag(tag):
    """Strip weights, escape, convert to canonical form."""
    import re
    t = tag.strip()
    # Strip weight syntax
    t = re.sub(r'^\(+', '', t)
    t = re.sub(r'\)+$', '', t)
    t = re.sub(r':\d+\.?\d*$', '', t)
    t = re.sub(r'^\[+', '', t)
    t = re.sub(r'\]+$', '', t)
    # Strip escape backslashes
    t = t.replace('\\(', '(').replace('\\)', ')')
    # Skip artist: prefix
    if t.startswith('artist:'):
        t = t[7:]
    # Convert spaces → underscores for CSV lookup
    return t.lower().replace(' ', '_').strip()

def load_tag_db(csv_path):
    db = {}
    with open(csv_path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip().split(',', 3)
            if len(parts) < 3:
                continue
            try:
                tag, cat, count = parts[0], int(parts[1]), int(parts[2])
            except ValueError:
                continue
            db[tag] = (cat, count)
            # Index aliases too
            if len(parts) > 3:
                aliases = parts[3].strip('"').split(',')
                for alias in aliases:
                    a = alias.strip()
                    if a:
                        db[a] = (cat, count)  # alias maps to same metadata
    return db

# Verify each tag
db = load_tag_db(csv_path)
verified, rare, removed = [], [], []
SKIP_VERIFY = {'masterpiece', 'best_quality', 'newest', 'absurdres', 'highres'}

for tag in draft_tags:
    norm = normalize_tag(tag)
    if norm in SKIP_VERIFY:
        verified.append(tag)
        continue
    if norm in db:
        cat, count = db[norm]
        if count >= 50:
            verified.append(tag)
        else:
            rare.append((tag, count))
    else:
        removed.append(tag)
```

**Skip verification** for:
- Quality block tags (`masterpiece`, `best_quality`, etc.)
- Identity baseline tags (already curated, trust source)
- Custom tags từ `--describe` user input (assume user knows)

**Offline fallback**: If `~/.cache/st-gen-image-prompt/danbooru.csv` không tồn tại + no internet → skip verification, warn user "VERIFICATION SKIPPED".

---

## Phase 2.6: LoRA Injection

Read `~/Projects/home-server/forge/knowledge/lora-catalog.md` (SHARED hub knowledge) để biết LoRAs nào available + scene triggers nào → inject `<lora:name:weight>` syntax + trigger words vào prompt.

### Logic

1. **Always-on quality LoRAs** — append to every gen:
   - `<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails`
   - These reinforce `prompt_prefix` ("masterpiece, very aesthetic") + add fine detail.

2. **Concept-triggered LoRAs** — scan verified scene tags (Phase 2.5 output) against catalog:
   - For each catalog row, check if ANY trigger keyword appears in scene tags (case-insensitive substring match, allow underscore↔space variants).
   - Match → add LoRA + add tags listed in catalog row.
   - **Cap**: max 2 concept LoRAs simultaneously (catalog rule). If >2 match, pick by scene tag count (more matches = more relevant).

3. **Compatibility check**:
   - Arachne + MGE Slime — pick stronger match, drop other.
   - Parasite + Oviposition — STACK OK (common scenario).
   - Tentacle + Oviposition — STACK OK.

4. **Inject order** in final prompt (after scene tags, before quality block):
   ```
   [scene tags from Phase 2 + verification]
   ,
   [concept LoRAs + their add_tags]
   ,
   [always-on quality LoRAs + their triggers]
   ,
   (((masterpiece,best quality,newest,absurdres,highres)))
   ```

5. **If no match found** → only inject always-on quality LoRAs.

### Display in output (Phase 3)

Add to verification report:
```
═══ LoRA Injection ═══
✓ Always-on (2): Aesthetic Quality, Add Micro Details
✓ Concept matches (1): Parasite Horror Transformation [keywords: parasite, transformation]
⊘ No match: Oviposition (no egg/ovi keywords in scene)
```

---

## Phase 3: Display Output + Auto-Copy to Clipboard

### Auto-copy helper

Unless `--no-clipboard` was passed, copy `final_prompt` to the clipboard: try `wl-copy` first (Wayland/KDE default), fall back to `xclip` then `xsel` (X11). If none are installed, warn with the install hint (`sudo dnf install wl-clipboard` for Wayland, `xclip` for X11). Report the outcome as `clipboard_status` — which tool succeeded, the warning, or "skipped (--no-clipboard)".

### Output format

```
═══════════════════════════════════════
GENERATED IMAGE PROMPT — {CharName}
Context: {chat ({N} msgs from {chat_file}) | --describe '{text}'}
═══════════════════════════════════════

{final verified prompt with quality block}

═══════════════════════════════════════
TAG VERIFICATION
═══════════════════════════════════════
✓ Verified ({N} tags, count ≥50)
⚠ Rare ({M} tags, count <50): {tag1 (count), tag2 (count), ...}
✗ Removed ({K} tags, not in DB): {tag1, tag2, ...}

═══════════════════════════════════════
CLIPBOARD: {clipboard_status}
═══════════════════════════════════════
NEXT STEPS
═══════════════════════════════════════
1. ST: paste into input box (Ctrl+V — clipboard already has prompt)
2. Click 🎨 Freestyle button (or type /sd <Ctrl+V>)

NOTE: ST sẽ auto-prepend prompt_prefix + character_prompts[{CharName}] (positive) + character_negative_prompts[{CharName}] (negative) — this output must not duplicate PERMANENT_LAYER tags (Step 3a)
═══════════════════════════════════════
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| `mcp__st__st_get_character` returns nothing | Name mismatch — run `mcp__st__st_list_characters` and retry with the exact key |
| LLM hallucinates >5 tags | Show all in `Removed` section, suggest user override với `--describe` |
| Persona not set | Skip persona identity injection, output scene-only prompt |
| `--describe` rỗng | Same as no `--describe` flag |

---

## Related Skills

- `/st-setup <CharName>` → sets the permanent `character_prompts` layer (ST auto-appends it to every gen; read live in Step 3a) AND writes `data/identity-baselines/<CharName>.txt` (the per-shot layer this skill reads). When the `.txt` is missing — character predates the flow or was never onboarded — this skill offers to write it from the card description (user confirms).
- `/st-persona <CharName>` → convert char → persona (also creates persona baseline)
- `/st-arc-save` → bake RP arc into lorebook (independent, separate from image gen)

## References

- NoobAI XL Quick Guide (Laxhar Dream Lab, 2024-11): tag escape, prompt order, sampler defaults
- Danbooru tag DB: a1111-sd-webui-tagcomplete project (https://github.com/DominikDoom/a1111-sd-webui-tagcomplete)
- ST source `public/scripts/extensions/stable-diffusion/index.js` `getGenerationType()` — `/sd` mode dispatcher
- `sillytavern/PROMPT-PLAYBOOK.md` gotchas 5.32 (POV dedup), 5.37 (Magnum retired), 5.39 (Mode FREE pass-through) — 5.38 is historical only (char_prompts were emptied 2026-05, since repopulated by `/st-setup`); for current state read `extension_settings.sd.character_prompts` live (Step 3a), don't trust the gotcha text.
