---
name: st-arc-save
model: sonnet
description: "Bake a completed RP arc into a SillyTavern lorebook as persistent memory. Run after each arc concludes."
argument-hint: "[<arc-title>] [--char-bound] [--char <CharName>] [--no-brain]"
allowed-tools: Bash, Read, AskUserQuestion, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_worldinfo, mcp__st__st_save_worldinfo, mcp__st__st_get_character, mcp__haingt-brain__brain_save
---

# ST Arc Save — Persistent Narrative Memory

Hai's flow: RP an arc with {{char}} → arc concludes → use Memory extension to summarize → run this skill to bake the summary into searchable lore. Future chats with the same persona/char auto-load this context.

## Architecture

Two complementary entry types per persona:

| Entry type | Mode | Position | When |
|-----------|------|----------|------|
| **{Persona} — Established State** | `constant=true` | After Char Defs (pos=1) | UPDATED each new arc — cumulative facts about persona's current state |
| **{Persona} Arc N — {Title}** | `selective=true` (~30 keys) | At Depth 4 (pos=4) | APPENDED per arc — full event narrative, triggers on backstory keywords |

Default target = persona-bound lorebook (`worlds/{PersonaName}.json`). Use `--char-bound` for arcs that are genuinely char-specific.

Universal {{char}} mechanics (parasite biology, etc.) belong in char's primary lorebook with `{{user}}` macros — NOT this skill's domain.

## Usage

```
/st-arc-save                                # prompt for arc title interactively
/st-arc-save "Subway Encounter"             # specify arc title
/st-arc-save "Arc 2 — Daughter Awakens"     # quoted multi-word title
/st-arc-save "Arc 1" --char-bound           # save to char primary book instead
/st-arc-save --char Parasite                # explicit char (skip auto-detect)
/st-arc-save "Arc 2" --no-brain             # skip brain_save followup
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
SETTINGS = $ST_DATA/settings.json
WORLDS = $ST_DATA/worlds
```

---

## Phase 0: Parse Args + Detect Context

Extract from `$ARGUMENTS`:
- `arc_title` = first quoted string OR first non-flag token (optional)
- `char_bound` = `--char-bound` flag present
- `explicit_char` = value of `--char <CharName>` if given
- `no_brain` = `--no-brain` flag present

Detect active persona:

```python
import json

with open("/home/haint/Projects/home-server/sillytavern/data/default-user/settings.json") as f:
    s = json.load(f)

# user_avatar is a TOP-LEVEL key of settings.json — NOT under power_user.
# Reading power_user.user_avatar always returns None and silently reports
# "no persona" while one is active.
active_avatar = s.get('user_avatar', '')
persona_name = s['power_user'].get('personas', {}).get(active_avatar, '')

print(f"Active persona: {persona_name!r} (avatar: {active_avatar!r})")
```

If `persona_name` is empty:
- AskUserQuestion: list all `power_user.personas.values()` + "no persona (skip persona binding)"
- If user picks "no persona" → fallback to `--char-bound` mode automatically

Detect char (only matters for `--char-bound`):
- If `explicit_char` given → use it
- Else: list `characters/*.png` (excluding folders), AskUserQuestion to pick

If `arc_title` not provided:
- AskUserQuestion: "Arc title? (e.g., 'Subway Encounter', 'Arc 2 — Family Reunion')"

---

## Phase 1: Get Summary

Most reliable path: ask user to paste from ST's Memory panel (Current summary box).

Use AskUserQuestion with body:
```
Paste the 5-section summary from ST's Memory panel:
(Setting / Plot Events / Character State / World Facts / Open Threads)

Skill will parse into Established State (cumulative facts) + Arc N (event log).
```

Validation: if pasted text < 200 chars → warn "summary looks too short, did Memory extension generate properly? Continue anyway?"

Optional advanced path (skip if too brittle): try to read summary from chat file metadata. ST stores Memory output in `chats/{CharName}/{chat}.jsonl` either as a system message or in chat_metadata. Pattern varies by ST version. For v1 of this skill, just rely on user paste.

---

## Phase 2: Determine Target Lorebook

```python
import json

if char_bound:
    # ST injects ONLY the world named by the card's data.extensions.world —
    # a book merely named after the char is never loaded. Read the link:
    char = explicit_char or active_char  # from Phase 0
    resp = mcp__st__st_get_character(name=char)
    card = json.loads(resp) if isinstance(resp, str) else resp
    target_name = (card.get('data', card).get('extensions') or {}).get('world', '')
    if not target_name:
        # Card has no linked book (e.g. a fresh import). Saving to worlds/<char>.json
        # would report success on a file ST never reads. Stop and ask: link a book
        # to the card first (in ST UI: card → lorebook icon), or switch to
        # persona-bound. Do not invent a target.
        ...
else:
    # persona-bound (default)
    target_name = persona_name

# Existence check = try to LOAD it. A name-list membership test has too many
# false-negative paths (case/spacing drift, response-wrapper shape, renamed
# persona) and a false negative here would later REPLACE a real book with a
# two-entry skeleton. Loading is the only test that can't lie:
try:
    wi_resp = mcp__st__st_get_worldinfo(name=target_name)
    lb = json.loads(wi_resp) if isinstance(wi_resp, str) else wi_resp
    target_exists = True
except Exception:   # explicit not-found only — any other error should surface
    lb = {"entries": {}, "name": f"{target_name} Lore"}
    target_exists = False

print(f"Target lorebook: {target_name} ({'existing, ' + str(len(lb['entries'])) + ' entries' if target_exists else 'NEW'})")

# Locate the existing Established State NOW — Phase 3 needs its content as input.
# Match on the full target_name, not a first-token substring: "Naoko" and
# "Naoko the Hive Queen" are different personas and must not update each other.
established_uid, established_old = None, ''
for uid, e in lb['entries'].items():
    c = e.get('comment', '')
    if 'Established State' in c and target_name in c:
        established_uid, established_old = uid, e.get('content', '')
        break
if established_old:
    print(f"Existing Established State [uid={established_uid}]:")
    print(established_old)
```

---

## Phase 3: LLM Parse Summary → 2 Entries

Given the pasted summary text, produce 2 distinct outputs.

### Established State (cumulative facts, ~150 words)

**Inputs: the pasted summary AND `established_old` from Phase 2.** This entry is cumulative across every arc — compose the NEW version by merging the old content with what this arc changed. Writing it from the new summary alone silently erases every fact arcs 1..N-1 established, which is exactly the loss this entry exists to prevent. When `established_old` is non-empty, start from it: keep every fact the new arc didn't change, update the ones it did, append the new ones.

Cover only state that *changes across arcs* — bond/relationship state, location, persistent conditions (pregnancies, transformations, oaths), compressed cumulative effects. Identity and appearance already live in `persona_descriptions[<avatar>].description`, which injects on every turn regardless; restating them here pays for the same tokens twice (same one-rule-one-home discipline as `/st-setup`'s lorebook phase).

**Tone:** factual, third-person, present-tense for ongoing state, past-tense for completed events.

**Example output structure:**
```
**{Persona}'s Current State (post-Arc {N}, established as ongoing context):**

- {Persona} is {{char}}'s {relationship}. {1-line bond description}.
- {Home base / current location}
- {Persistent condition 1}
- {Cumulative effect from prior arcs}
```

The composed content REPLACES the old entry body in Phase 4 — which is why the merge above is mandatory, and why Phase 5 prints old-vs-new for the user to eyeball before trusting it.

### Arc N — {Title} (event log, ~300-500 words)

Convert the Plot Events + Character State + Open Threads sections into chronological numbered list with bold section headers.

**Structure:**
```
**{Persona}'s {Arc N Title} — Detailed Events (chronological):**

1. **{Event 1 heading}**: {1-3 sentences, who/where/what/outcome}.

2. **{Event 2 heading}**: {1-3 sentences}.

...

8. **{Final event}**: {how arc concluded; what state persona ended in}.
```

### Trigger Keywords (~25-35 keys)

Extract distinctive content terms from summary:
- Proper nouns (names of NPCs encountered, locations, items)
- Theme keywords (in both English + Vietnamese — Hai uses both)
- Backstory triggers ("first encounter", "lần đầu", "remember when", "nhớ lúc", "the past", "hồi đó")
- Specific arc references ("arc {N}", "{Title}")

Avoid:
- Generic words ("said", "looked", "felt") — too broad
- {{char}} or {{user}} themselves — always present, useless as trigger

---

## Phase 4: Write Lorebook via MCP (no container restart)

ST hot-reloads on `mcp__st__st_save_worldinfo` and `mcp__st__st_save_settings` — no need to stop the container.

### Update or create entries

```python
import json, re, shutil

entries = lb['entries']   # lb, established_uid loaded in Phase 2

# Next arc number = max existing + 1, parsed from comments. len()+1 breaks the
# moment any arc was deleted or numbered by hand (two "Arc 3"s).
arc_nums = [int(m.group(1)) for e in entries.values()
            for m in [re.search(r'Arc (\d+)', e.get('comment', ''))] if m]
next_arc_num = max(arc_nums, default=0) + 1
arc_label = f"Arc {next_arc_num} — {arc_title}"

# Determine fresh uid for new entries
existing_uids = [e['uid'] for e in entries.values()]
next_uid = max(existing_uids) + 1 if existing_uids else 0

# Standard schema function
def make_entry(uid, comment, content, keys, constant, position, depth):
    return {
        "uid": uid, "key": keys, "keysecondary": [],
        "comment": comment, "content": content,
        "constant": constant, "vectorized": False,
        "selective": not constant, "selectiveLogic": 0,
        "addMemo": False, "order": 100, "position": position,
        "disable": False, "ignoreBudget": False,
        "excludeRecursion": False, "preventRecursion": False,
        "matchPersonaDescription": False, "matchCharacterDescription": False,
        "matchCharacterPersonality": False, "matchCharacterDepthPrompt": False,
        "matchScenario": False, "matchCreatorNotes": False,
        "delayUntilRecursion": 0, "probability": 100, "useProbability": True,
        "depth": depth, "outletName": "", "group": "",
        "groupOverride": False, "groupWeight": 100, "scanDepth": None,
        "caseSensitive": None, "matchWholeWords": None, "useGroupScoring": None,
        "automationId": "", "role": 0, "sticky": None, "cooldown": None,
        "delay": None, "triggers": []
    }

# Established State — UPDATE existing or CREATE new
established_comment = f"{target_name} — Established State (cumulative, always-on)"
if established_uid is not None:
    # Update content; keep uid + key=[] (constant doesn't use keys)
    entries[established_uid]['content'] = established_state_content
    entries[established_uid]['comment'] = established_comment
    print(f"Updated Established State entry [uid={established_uid}]")
else:
    new_uid = next_uid
    next_uid += 1
    entries[str(new_uid)] = make_entry(
        uid=new_uid, comment=established_comment,
        content=established_state_content, keys=[],
        constant=True, position=1, depth=4
    )
    print(f"Created Established State entry [uid={new_uid}]")

# Arc N — APPEND new
arc_comment = f"{target_name} {arc_label} (event log, selective)"
arc_uid = next_uid
entries[str(arc_uid)] = make_entry(
    uid=arc_uid, comment=arc_comment,
    content=arc_event_log_content, keys=trigger_keywords,
    constant=False, position=4, depth=4
)
print(f"Appended {arc_label} entry [uid={arc_uid}, {len(trigger_keywords)} keys]")

# st_save_worldinfo REPLACES the whole file — guard the write:
# 1. backup the current file (cheap, makes every mistake reversible)
# 2. entry count must never DECREASE — this skill only updates or appends,
#    so a shrinking book means something upstream went wrong; abort, don't save.
worlds_dir = "/home/haint/Projects/home-server/sillytavern/data/default-user/worlds"
if target_exists:
    shutil.copy2(f"{worlds_dir}/{target_name}.json",
                 f"{worlds_dir}/{target_name}.json.bak-arc{next_arc_num}")
    before = len(json.load(open(f"{worlds_dir}/{target_name}.json"))['entries'])
    assert len(entries) >= before, f"entry count would drop {before}→{len(entries)} — aborting"

mcp__st__st_save_worldinfo(name=target_name, data=lb)
```

### Bind lorebook to persona (if persona-bound + just created)

`active_avatar` ends in `.png` — the st-mcp path parser would split on the dot and corrupt the tree on a naked dotted path. Use bracket-escape syntax `["..."]` for the leaf key. (Background: `.claude/rules/sillytavern.md` — the path-based-MCP rule; parser source: `_parse_path` in `sillytavern/mcp/st-mcp/src/st_mcp/server.py`.)

```python
if not char_bound and not target_exists:
    # Surgical writes — no full-tree round-trip needed.
    avatar_key = f'["{active_avatar}"]'  # bracket-escape leaf with '.png'

    mcp__st__st_save_settings_path(
        path=f"power_user.persona_descriptions.{avatar_key}.lorebook",
        value=target_name,
    )
    mcp__st__st_save_settings_path(
        path="power_user.persona_description_lorebook",
        value=target_name,
    )
    print(f"Bound persona '{persona_name}' → lorebook '{target_name}'")
```

---

## Phase 5: Report

```
=== Arc Saved: {target_name} → Arc {N} — {arc_title} ===

✓ Established State entry: {UPDATED | CREATED} (constant=true, ~{N} words)
✓ Arc {N} entry: APPENDED (selective=true, {M} keys, ~{P} words)
✓ Lorebook: worlds/{target_name}.json ({total} entries total)
[✓ Persona binding: {persona} → {target_name}]

Established State — old vs new (print both in full so the user can catch a lost fact NOW, while the .bak is one `cp` away):

{established_old}
---
{established_state_content}

Then run the layer auditor — this skill just created/updated a `constant: true` entry, the most expensive kind, and the auditor prices exactly that (always-on chars/turn, depth vs depth_prompt):

```bash
python3 /home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py --json
```

Next:
- ST hot-reloaded automatically — no restart needed
- Verify in World Info panel → 2 new/updated entries visible
- Start new chat with {{char}} → Established State always injects; Arc {N} triggers on backstory keywords
- Rollback: `cp worlds/{target_name}.json.bak-arc{N} worlds/{target_name}.json`
```

---

## Phase 6: Optional Brain Save

If `--no-brain` not set:

```python
# Save to brain for cross-session reference
brain_save(
    content=f"{target_name} Arc {N}: {arc_title} — {1-line summary}",
    type="entity",
    tags=["roleplay", "st-arc", target_name.lower()],
    project="home-server",
    metadata={"source": "st-arc-save", "lorebook": target_name, "arc_num": N}
)
```

This makes arc summaries searchable via `brain_recall` from any future Claude session.

---

## Edge Cases

| Case | Handling |
|------|----------|
| No active persona AND no `--char-bound` | AskUserQuestion → pick from list, OR auto-fallback to char-bound |
| Persona-bound lorebook doesn't exist | Create new lorebook + bind in settings.json |
| Established State exists but for different name | Match requires the FULL `target_name` in the comment ("Naoko" must not update "Naoko the Hive Queen"); on mismatch, create new (don't conflate) |
| Arc number collision (Arc 3 exists, user titles new "Arc 3") | Numbering is `max(existing Arc N) + 1` parsed from comments — survives deleted or hand-numbered arcs; warn user when their title implies a different number |
| Summary is empty/too short | AskUserQuestion: continue anyway / abort / paste again |
| User pastes summary in non-5-section format | Best-effort parse; warn that structure may be incomplete |

---

## Related Skills

- `/st-setup <CharName>` → run BEFORE first arc to establish char's primary lorebook + char_prompts
- `/st-persona <CharName>` → convert char to persona before saving arcs to persona-bound book
- Recommended flow:
  ```
  /st-setup <CharName>                                  # baseline (+ --lore if the char needs a primary book)
  /st-persona <SourceChar>                              # convert a card into the user persona
  [RP arc 1, ~50-100 messages]
  Memory panel → Summarize now → copy 5-section summary
  /st-arc-save "<Arc Title>"                            # bake into the persona's book
  [start new chat → Established State auto-loads]
  ```
