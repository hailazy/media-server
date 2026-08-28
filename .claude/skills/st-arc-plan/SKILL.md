---
name: st-arc-plan
model: sonnet
description: "Open the next RP arc: temporary steering lorebook entry + narrator-voice opener for the new chat. Use when Hải asks where the next arc/chapter should go. Run after /st-arc-save."
argument-hint: "[<premise>] [--persona <Name>] [--char <CharName>] [--no-opener] [--no-brain]"
allowed-tools: Bash, Read, AskUserQuestion, mcp__st__st_get_settings, mcp__st__st_get_worldinfo, mcp__st__st_save_worldinfo, mcp__st__st_get_character, mcp__haingt-brain__brain_save, mcp__haingt-brain__brain_recall
---

# ST Arc Plan — Open the Next Arc

Lifecycle of one arc: `/st-arc-plan` (steer) → play → `/st-arc-save` (bake, and disable the steering).

Hải's flow: previous arc is baked → he decides where the next one goes (with Claude as navigator, or
already decided) → this skill writes a **Direction** entry the narrator sees every turn, plus an
**opener** in the narrator's voice that Hải pastes as the first message of the new chat. Guided
Impersonate can't do this job: a guide arrives as one trailing system line on one turn and gets
diluted; a constant lorebook entry steers every turn.

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
WORLDS  = $ST_DATA/worlds
```

## Phase 0: Args + Context

- `premise` = everything in `$ARGUMENTS` that isn't a flag (may be empty → Phase 2 brainstorm)
- `persona` = `--persona <Name>`, else the active persona (`settings.json` top-level `user_avatar` →
  `power_user.personas[avatar]`; see `/st-arc-save` Phase 0 for the gotcha)
- `char` = `--char <Name>`, else the char of the newest chat on disk (`chats/*/*.jsonl` by mtime)
- `no_opener`, `no_brain` flags

Load the persona's lorebook (`st_get_worldinfo(persona)`) and pull:
- the **Established State** entry (comment contains `Established State` and the persona name) — the
  arc's starting facts and its "Open:" line
- the highest **Arc N** entry — `N + 1` is this arc's number
- any entry whose comment contains `Direction` and is not disabled — a previous plan that was never
  closed. Show it and ask: disable it, or keep both (rare).

Load the char card (`st_get_character(char)`) for `first_mes` and one alternate greeting: the
opener in Phase 4 must match that voice (tense, italics convention, paragraph rhythm, whether the
char speaks). For a wordless-narrator card, the opener has no narrator dialogue at all.

## Phase 1: Diagnose Before Proposing

Read the previous arc(s) as a curve, not a list: which axis did each arc escalate on (number of
partners, intensity, new abilities, new locations)? Another step on the same axis has falling
returns. Name the axes the story hasn't touched yet — space (home vs. public), time (a skip that
makes slow changes visible), knowledge (someone who knows more than the protagonist), point of view
(the protagonist seen from outside), friction (someone the antagonist force cannot move). List the
lore entries that have never fired (keys never matched) — they are pre-paid material.

Present this in five to eight lines. It is the input for both Phase 2 and Phase 3.

## Phase 2: Premise (only when `premise` is empty)

Offer two or three directions, each in one paragraph: the axis it opens, the new element it
introduces, the image it builds toward, the risk. Recommend one. AskUserQuestion with those as
options. Iterate once or twice — Hải sets the destination; the skill charts it.

## Phase 3: Compose the Direction Entry

One constant entry, written for the model that plays `{{char}}`, in English, present tense,
imperative where it steers. Structure:

```
**Arc {N} direction — "{Title}" (temporary steering; active until the arc is saved)**

Premise: {who/what is new, in 3–5 sentences — the facts the narrator must treat as true}

Shape: {the arc's register: quiet/escalating/outside-POV; how much time it covers; where the
tension lives; what stays in the background. If the previous arc was a crescendo, say so and
lower the register.}

Beats to reach, in order — pace them, give each its own scene:
1. …            (6–8 beats; each one is a scene the narrator can land on)
5. CENTRE OF THE ARC: …   (mark the beat the arc exists for, and say "give it room")
8. …

Ending, only after beat {last}: {the closing image / the question the arc asks and does not answer}

Guards: {what must NOT happen or resolve this arc — one line each}
```

Write every beat as a double where the story runs on dramatic irony: what the protagonist believes
‖ what is actually happening. Keep the entry between 350 and 500 words — it costs ~1.3 tok/word on
every turn for the whole arc; that is the price of steering, and it is temporary.

Entry fields: `constant: true`, `selective: false`, `key: []`, `position: 1` (after char defs),
`order: 110` (lands after Established State at 100), `depth: 4`, `role: 0`,
`comment: "{persona} — Arc {N} Direction (temporary steering, disable at arc save)"`. Use the
`make_entry` schema from `/st-arc-save` Phase 4. Back up the book first
(`{WORLDS}/{persona}.json.bak-arc{N}plan`), then `st_save_worldinfo` with the full data
(it replaces the file). Entry count must not decrease.

## Phase 4: Opener (skip with `--no-opener`)

Write the first message of the new chat in `{{char}}`'s voice, picking up exactly where the
Established State's final scene stopped. 350–500 words. It introduces the new element (beat 1 or the
lead-in to it) and ends on something `{{user}}` has to answer — a line addressed to them, a choice, a
hand held out. Match the card's greeting conventions from Phase 0. Sex stays at the register the
Direction entry sets for this arc.

Save to `{scratchpad}/arc{N}_opener.txt` and copy it: `wl-copy < arc{N}_opener.txt`.

## Phase 5: Report

```
=== Arc {N} planned: {persona} × {char} — "{Title}" ===

✓ Direction entry [uid {u}]: constant, ~{w} words (~{t} tok/turn for the length of the arc)
✓ Backup: worlds/{persona}.json.bak-arc{N}plan
✓ Opener: {scratchpad}/arc{N}_opener.txt — on the clipboard
[! Previous Direction [uid {v}] disabled]

In ST:
1. Select {char} → New chat. The card's greeting appears (it is the Arc-1 opener).
2. Edit that first message (pencil icon) → select all → paste → save.
3. Reply as {persona}. The Direction entry steers every narrator turn from here.
4. When the arc ends: /st-arc-save "<title>" — it bakes the arc and disables this Direction entry.

Cost now: {persona} constant entries = Established State + Direction ≈ {sum} tok/turn.
```

Mention the card's `scenario` field if it still describes an earlier arc — it injects every chat and
can pull the narrator backwards; it can only be cleared in the ST UI (no MCP write for cards).

## Phase 6: Brain (skip with `--no-brain`)

```python
brain_save(
    content=f"{persona} Arc {N} plan: {title} — {premise in 2 lines}; beats: {one line}; ending: {one line}",
    type="decision", tags=["roleplay", "st-arc", persona.lower(), "arc-plan"],
    project="home-server",
    metadata={"source": "st-arc-plan", "lorebook": persona, "arc_num": N},
)
```

## Edge cases

| Case | Handling |
|---|---|
| No Established State in the book | The persona has no baked arc yet — point to `/st-arc-save` (or `/st-setup` for a fresh char) and stop |
| Open Direction from an earlier arc | Show it; default = disable it (the arc it steered is over) |
| Premise contradicts Established State | Say which fact conflicts; ask whether the Direction should override it (write the override into the Premise explicitly) or the premise changes |
| `wl-copy` missing | Print the opener in full so Hải can copy from the terminal |

## Related

- `/st-arc-save` → closes the loop: bakes the arc and disables the Direction entry
- `/st-audit` → prices the constant entries after planning (Direction is the most expensive kind)
