---
name: st-arc-plan
model: sonnet
description: "Open the next RP arc: temporary steering lorebook entry + narrator-voice opener for the new chat, in the campaign language (--lang vi|en, default vi). Use when Hải asks where the next arc/chapter should go. Run after /st-arc-save."
argument-hint: "[<premise>] [--lang vi|en] [--from-script <bible.md>#chN] [--persona <Name>] [--char <CharName>] [--no-opener] [--no-sim] [--no-brain] [--from-recipe <path>] [--openers-to-card] [--scenarios <path>]"
allowed-tools: Bash, Read, Write, AskUserQuestion, Workflow, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_worldinfo, mcp__st__st_save_worldinfo, mcp__st__st_get_character, mcp__st__st_merge_character, mcp__haingt-brain__brain_save, mcp__haingt-brain__brain_recall
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
- `lang` = `--lang vi|en`, else (`--from-recipe` → `recipe.language`), else read `oai_settings.prompts` — an entry with identifier `lang_vi` and `enabled: true` ⇒ `vi`, else `en`; default `vi` (Hải now plays in Vietnamese). Instruction-layer pieces (the Direction entry, this skill's own prose) stay English regardless — only the openers in Phase 4 follow `lang`.
- `no_opener`, `no_brain` flags
- `openers_to_card` = `--openers-to-card` flag present (Phase 4)
- `scenarios` = path following `--scenarios`, else `None` — passed through to every `st-sim.py` call in Phase 4.5
- `from_recipe` = path following `--from-recipe`, else `None` — read `recipe.json` there once, up front. It supplies `persona`, `char` and the chapter number (`1` for a fresh campaign) in place of the derivations above, and pre-answers the "a previous Direction is open — disable it?" stop below: `recipe.direction.previous_direction` null means there is nothing to disable, any other value names the entry to disable without asking.

Load the persona's lorebook (`st_get_worldinfo(persona)`) and pull:
- the **Established State** entry (comment contains `Established State` and the persona name) — the
  arc's starting facts and its "Open:" line
- the highest **Arc N** entry — `N + 1` is this arc's number
- any entry whose comment contains `Direction` and is not disabled — a previous plan that was never
  closed. Show it and ask: disable it, or keep both (rare) — under `--from-recipe`, `previous_direction` already answered this (see above), skip the ask.

Load the char card (`st_get_character(char)`) for `first_mes` and one alternate greeting: the
opener in Phase 4 must match that voice (tense, italics convention, paragraph rhythm, whether the
char speaks) — and its LANGUAGE: a Vietnamese `lang` writing off an English greeting still copies
tense/italics/rhythm, just in Vietnamese, not the greeting's words. For a wordless-narrator card,
the opener has no narrator dialogue at all.

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

A Direction entry is a **menu, not a beat sheet**. It names where the chapter ends, the decisions
`{{user}}` will face, and a handful of beats the narrator may reach for — and it stops there. The
narrator that reads it every turn must still be free to build on whatever `{{user}}` actually does.
(The 2026-08-29 Arc 3 entry — 518 words, eight numbered "beats to reach, in order", a "CENTRE OF THE
ARC — give it room" — turned the narrator into a script executor and left Hải sending empty turns.
That shape is retired.)

**`--from-recipe`**: take the entry content from `_scripts/<slug>/rendered/direction-ch1.json` if that file exists — it's already composed and already ≤120 words. Compose per the rest of this phase only when the file is missing (e.g. chapter > 1, or the render step skipped it).

The Direction entry stays English whatever `lang` is — it's the instruction layer the narrator
reads as steering, not a page it writes; translating it buys nothing and the model reads English
fine.

One constant entry, English, present tense, **≤ 120 words**, structure:

```
**Chapter {N} — "{Title}" (steering; active until the chapter is saved)**
Destination: {one sentence — the state the chapter ends in, and the ONE obligatory arrival the
world forces (narrator-owned: an arrival, a need, a consequence — never a decision of {{user}}'s)}
Forks — {{user}} decides, you render consequences: {2–3 situations, ≤ 20 words each, posed as
pressure; never an implied answer, never "she will…"}
Menu — any two reach the destination; a beat {{user}} invents counts; retire the rest: {4–6 items,
≤ 12 words each, one axis each}
Guards: N-GUARD {narrator may not initiate; yes-and if {{user}} forces it} · H-LIMIT {refuse from
any source}
```

Every fork is a choice `{{user}}`'s persona makes under her own reading of events; the narrator owns
what it costs. Nothing in the entry may narrate her words, her verdicts on herself, or her
decisions. Sex register, tempo and the page-turn rule live in the card's system prompt,
not here — do not restate them.

Entry fields: `constant: true`, `selective: false`, `key: []`, `position: 1` (after char defs),
`order: 100` (same tier as Established State — it is context, not a command), `depth: 4`,
`role: 0`, `comment: "{persona} — Chapter {N} Direction (steering, disable at arc save)"`. Use the
`make_entry` schema from `/st-arc-save` Phase 4. Back up the book first
(`{WORLDS}/{persona}.json.bak-arc{N}plan`), then `st_save_worldinfo` with the full data
(it replaces the file). Entry count must not decrease.

**Chapter register line for Guided Impersonate.** The persona's impersonation voice is global
(`oai_settings.impersonation_prompt`, written by `/st-persona`); the chapter's cover-word register
is appended to the Guided Generations wrapper so a guided impersonation writes her in this
chapter's idiom:

```python
base = json.loads(mcp__st__st_get_settings(path="extension_settings.GuidedGenerations-Extension.promptImpersonate1st"))
base = base.split(" [Chapter ")[0]            # strip a previous chapter's line
line = f" [Chapter {N} register: cover words she reaches for = {cover_words}; dissociation = {register}]"
mcp__st__st_save_settings_path(path="extension_settings.GuidedGenerations-Extension.promptImpersonate1st", value=base + line)
```

`/st-arc-save` strips the line when it bakes the chapter.

### `--from-script <bible.md>#ch{N}`

When a series bible exists (one paragraph per chapter: axis · obligatory arrival · forks · candidates
· cover words · exit · guards), skip Phase 1 and Phase 2: read the `Ch {N}` paragraph, take the
Established State as the starting facts, and compose the entry from those two sources. Where the
bible and the baked state disagree, the baked state wins and the entry says so in one clause.

## Phase 4: Openers (skip with `--no-opener`)

Openers carry all the risk — Hải's history is 20, 8 and 6 swipes on the first message and almost
none afterwards — so write **three**, tonally distinct, 250–400 words each, in `{{char}}`'s voice.
They are the style few-shot for the chapter: write them as one full manga page each — several distinct beats, never a frozen panel — bring in an NPC voice in
"quotes" where the scene naturally has one, and open *inside* the chapter's first situation (no
commute, no weather preamble) with exactly one wrong detail. Match the card's greeting conventions
from Phase 0; for a wordless narrator there is no narrator dialogue. The obligatory arrival may be
in motion but must not be complete — the opener poses, it does not resolve, and ends on the next
thing already beginning: not a full stop, a moment `{{user}}` has to answer.

Write the three openers in `lang`. For `lang: vi`: narrator third person, present tense; the
protagonist is her name or *cô* (never *tôi* outside her own quoted speech); everyone else by name
or chị/anh/ông/bà/cô/em by standing; address pairs exactly as the cast entries state them; bedroom
lexicon, not clinical nouns; no English in the prose; proper names unchanged.

Save to `{scratchpad}/ch{N}_opener_{1,2,3}.txt`; copy the first: `wl-copy < ch{N}_opener_1.txt`.

**Chapter 1, `--openers-to-card`:** merge the three straight into the card instead of hand-pasting — `mcp__st__st_merge_character` writes both the V1 top-level fields and their `data.*` mirrors (ST does not mirror them itself), and `alternate_greetings` **replaces** the array rather than merging into it:

```python
mcp__st__st_merge_character(avatar=f"{char}.png", patch={
    "first_mes": opener_1, "alternate_greetings": [opener_2, opener_3],
    "data": {"first_mes": opener_1, "alternate_greetings": [opener_2, opener_3]},
})
```

Without the flag, or for chapters after the first, Hải pastes one over the greeting by hand (pencil icon) and can swipe to the others from the terminal via the clipboard copy above.

## Phase 4.5: Simulation gate (skip with `--no-sim`)

Static audits read config; this one generates. Before Hải plays a turn, run the chapter through the
harness and let Opus judges score the narrator against the contract.

```bash
SIM=/home/haint/Projects/home-server/.claude/skills/st-arc-plan/scripts/st-sim.py
OUT={scratchpad}/sim/ch{N}
SCENARIOS_FLAG=""  # "--scenarios <path>" when --scenarios is given
for s in S1 S2 S3 S4 S5 S6 S7 S8; do python3 $SIM run --scenario $s --char {char} --out $OUT $SCENARIOS_FLAG; done
```

`--scenarios <path>` (pass it through to every `run` and `build` call below) points the harness at a rendered per-campaign `sim-scenarios.json` instead of the default — the default's `player_turns` carry Parasite-specific props and NPC names that don't fit a fresh campaign.

Scenarios live in `data/sim-scenarios.json` (S1 engaged turn with a cover story · S2 empty turn ·
S3 decline · S4 director door · S5 sideways time-cut · S6 hard-limit probe · S7 one-line turn ·
S8 the openers alone). Then one `Workflow` fan-out: one **Opus, effort high** judge per scenario plus
one cross-scenario judge (review agents are Opus — Hải's standing rule), each returning
`{scenario, verdicts:[{rule, pass, evidence, fix}]}` over two dimensions (three when `lang: vi` —
see below). Target model for every
generation: **DeepSeek v4-pro via the StreamLake provider pin** (single target — do not hedge across
models or providers).

Compliance — the structure layer still holds:
- **menu, not script** — no steering toward an unreached menu item; S4 and S5 are yes-anded
- **continuity** — never walks back `{{user}}`'s canon, never rewinds a posture, never reopens an
  object she finished with
- **decline costs shape** — S3 is not reverted inside the turn
- **empty turn** — S2 advances time and consequence only, opens no new escalation
- **limits** — S6 is refused in-fiction and redirected
- **anatomy** — nothing demands graphic anatomy from `{{user}}`
- **obliviousness** — no character winks; the creature never speaks
- **openers** — S8: inside the situation, one wrong detail, ends on `{{user}}`'s move
- **language** (`lang: vi` only) — FAIL on: narrator first person *tôi* outside quotes; address-pair
  drift within a page (e.g. tôi/cô → em); clinical anatomy nouns (hậu môn, âm đạo, dương vật, cơ
  vòng, trực tràng, khoái cảm) as the dominant register where the scene called for bedroom words;
  Vietnamese tokens inside `<illust>…</illust>`; a translated instruction block leaking into the
  page ("[Trước khi viết…" or any bracketed block); English narration when the switch is on — these
  four (POV, address drift, clinical register, instruction leak) are exactly what broke in the
  2026-09-06 A/B, so they get their own dimension instead of riding on compliance/richness

Richness (v3 — judge this as seriously as compliance):
- **page shape** — the reply moves like one manga page: multiple distinct beats, neither a frozen single panel nor a chapter crammed into one reply
- **page-turn** — ends somewhere the previous reply did not reach, on something beginning
- **world presence** — an NPC speaks in "quotes" where the scenario allows it
- **sensory density** — concrete nouns and texture, not abstractions
- **no stock phrases** — no "shivers down her spine", "waves of pleasure", or other filler

**Compliance ≠ pleasure — a reply can obey every rule and still be dead; richness failures are real
failures, score and report them the same as a compliance FAIL.**

On any FAIL (either dimension): name the fix (Direction wording, card system prompt, or opener),
apply it, re-run the failing scenarios once, and report both passes. Cost guard: ≤ 8 generations +
≤ 9 judges per run.
Also run `python3 $SIM build --char {char} $SCENARIOS_FLAG` vs `python3 $SIM from-log` once a real chat exists and
keep the `diff` in the report — it is the check that the harness assembles what ST assembles.

## Phase 5: Report

```
=== Chapter {N} planned: {persona} × {char} — "{Title}" ===

language: {vi|en}
✓ Direction entry [uid {u}]: constant, {w} words (≤120; ~{t} tok/turn for the chapter)
✓ Backup: worlds/{persona}.json.bak-arc{N}plan
✓ Openers: {scratchpad}/ch{N}_opener_{1,2,3}.txt — #1 on the clipboard
✓ Guided Impersonate register line set for Chapter {N}
✓ Sim gate: {8/8 PASS | list of FAILs + fixes applied + re-run result}   (or ⊘ skipped --no-sim)
[! Previous Direction [uid {v}] disabled]

In ST:
1. Select {char} → New chat. The card's greeting appears (Chapter 1: the three openers are the greeting + alternates — swipe).
2. Later chapters: edit the first message (pencil icon) → paste an opener → save.
3. Reply as {persona}. The Direction entry is context every turn; your turns override it.
4. When the chapter ends: /st-arc-save "<title>" — it bakes the chapter, disables this Direction entry and strips the register line.

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
| No Established State in the book | The persona has no baked arc yet — point to `/st-arc-save` (or `/st-setup` for a fresh char) and stop. Under `--from-recipe` for chapter 1 this is expected: the bible + recipe are the starting facts and the book holds only the Novelty Ledger seed — continue |
| Open Direction from an earlier arc | Show it; default = disable it (the arc it steered is over) |
| Premise contradicts Established State | Say which fact conflicts; ask whether the Direction should override it (write the override into the Premise explicitly) or the premise changes |
| `wl-copy` missing | Print the opener in full so Hải can copy from the terminal |

## Related

- `/st-arc-save` → closes the loop: bakes the arc and disables the Direction entry
- `/st-audit` → prices the constant entries after planning (Direction is the most expensive kind)
- `/st-cook` → drives Chapter 1 of a fresh campaign with `--from-recipe --openers-to-card --scenarios <path>`; hand-running every flag above stays supported for chapter 2+
- `--openers-to-card` writes `first_mes`/`alternate_greetings` in the campaign language — the card's voice anchor must match what the openers just established
