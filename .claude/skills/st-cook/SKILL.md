---
name: st-cook
description: "Cook a one-line RP idea into a complete SillyTavern setup (concept → card, persona, lorebooks, voice contract, Chapter-1 Direction, sim gate), reusing bricks on disk and dispatching /st-setup, /st-persona, /st-arc-plan for the rest. `--close` archives a finished scenario."
argument-hint: "\"<idea>\" [--full] [--panel] [--slug <s>] [--dry-run] | --close <slug> [--yes]"
allowed-tools: Bash, Read, Write, AskUserQuestion, Skill, Agent, Workflow, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_list_characters, mcp__st__st_get_character, mcp__st__st_create_character, mcp__st__st_merge_character, mcp__st__st_delete_character, mcp__st__st_get_worldinfo, mcp__st__st_save_worldinfo, mcp__haingt-brain__brain_recall, mcp__haingt-brain__brain_save, mcp__haingt-brain__brain_update
---

# ST Cook — idea → complete RP setup

Hải starts every RP from an idea of his own and plays a scenario roughly once. This skill is the front door for that: it turns the idea into a concept sheet, works out which bricks already on disk can be reused, and dispatches the existing skills only for what is missing — then runs **one** audit and **one** simulation gate at the end. The three sub-skills stay usable by hand; this skill exists because every bug of the last hand-run setup lived in the *joints* between them (a global voice contract not re-applied after a persona switch; a persona lorebook that has two fields; a stale default Author's Note injecting into every chat).

```
/st-cook "a night-shift nurse who starts hearing the ward's ventilation as instructions"
/st-cook "<idea>" --panel          # 3 pitches + judge before the concept sheet
/st-cook "<idea>" --full           # + expression sprites, full lorebook, Forge card avatar
/st-cook "<idea>" --dry-run        # stop after the dispatch plan; write nothing to ST
/st-cook --close <slug>            # archive + remove a finished scenario
```

## Constants

```
ST_DATA   = /home/haint/Projects/home-server/sillytavern/data/default-user
SCRIPTS   = $ST_DATA/_scripts                      # gitignored (sillytavern/.gitignore: data/)
LEDGER    = $SCRIPTS/ledger.json                   # campaign ledger (cross-campaign novelty)
SKILL     = /home/haint/Projects/home-server/.claude/skills/st-cook
COOK      = python3 $SKILL/scripts/cook.py
AUDIT     = python3 /home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py
SIM       = python3 /home/haint/Projects/home-server/.claude/skills/st-arc-plan/scripts/st-sim.py
BASELINES = /home/haint/Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines
```

Two ledgers exist and the names matter: the **campaign ledger** (`ledger.json`, one row per scenario, prevents repeating a configuration across scenarios) and the **chapter ledger** (the constant "Novelty Ledger" lorebook entry `/st-arc-save` appends to, prevents repeating a configuration *within* a scenario).

## Reuse happens at the template level

Instances don't recur — the last persona, the last creature's lorebook, the last bible are all single-use. What *does* recur, and took the most tuning, is the structure: the narrator contract, the post-history checklist, the four-part Direction frame, the voice block, the generic lorebook mechanics, the sim scenarios. Those live as templates in `assets/` with `«PLACEHOLDER»` slots (guillemets, because card text is full of live `{{user}}`/`{{char}}` macros that must survive rendering). `cook.py render` fills them and refuses to emit anything with a `«` left over. `assets/` is tracked in a public repo, so templates carry no story nouns — the story lives in the gitignored `_scripts/<slug>/`.

---

## Pre-flight — no open ST tab

The ST browser client keeps the whole settings tree in memory and POSTs it back on almost any UI interaction (`saveSettingsDebounced`), so a tab opened before the cook silently overwrites every settings write made through MCP the moment Hải touches it (2026-08-31: a whole persona, the voice contract and `character_prompts` vanished mid-sim). Files on disk (card PNG, worlds, avatar) survive; settings do not. Ask Hải to **close the ST tab** (or reload it right before the cook and not touch it until the report says "F5"), and re-run the audit at the gate — a FLAG there after a green mid-run means the tab bit.

## Phase 0 — Parse + recall

Parse: `idea` (first quoted/non-flag text), `--full`, `--panel`, `--slug <s>` (default: kebab-case of 3–4 words from the idea), `--dry-run`, `--close <slug>` (→ jump to **Close**), `--yes`.

Recall before writing a word — the concept has to be *his*, and the brain holds what he has already told us:

```
brain_recall("roleplay kink profile taste corruption engine", type="preference", project="home-server", k=5)
brain_recall("st-ledger story campaign", tags/type="story", project="home-server", k=8)
```
plus `$COOK ledger list`. Read `references/corruption-engine.md` now; it is the craft brief for Phase 1 (the play gap, the self-blame engine, the six structural rules, tempo, sizing, axes, endings, and the checklist of what the concept sheet must set).

If `$SCRIPTS/<slug>/recipe.json` already exists with `status != closed`, say so and stop — cooking twice over the same slug would overwrite a live campaign.

## Phase 1 — Concept sheet (the writing that matters)

Write `$SCRIPTS/<slug>/bible.md` from `assets/bible.skeleton.md` — ≤ 1 page, coarse-to-fine: one paragraph per section, one paragraph per chapter. Then fill `recipe.concept` (`assets/recipe.schema.json`).

Size the campaign to the idea (`references/corruption-engine.md` §5): one-shot when the idea is one situation and one belief; three chapters for one household; five only when an institution or a city is in play. A five-chapter bible for a one-situation idea is effort that never gets played.

Ask Hải with `AskUserQuestion` only where two readings would produce materially different setups — typically: chapter count, which axes go on page, ending shape, any limit toggle the idea brushes against. Everything else is a routine call; make it and say so in the sheet.

**`--panel`** (when he has no concrete picture): one `Workflow` — three pitch agents (`model: "sonnet", effort: "medium"`), each briefed with the idea + the craft doc + the campaign ledger, each returning a ≤ 2 KB structured pitch (premise · protagonist + wound · engine · axes · chapters · ending) from a *different* angle (belief-first / setting-first / ending-first); one judge (`model: "opus", effort: "high"`) that scores the three against `references/corruption-engine.md` §8 and the ledger's novelty constraint and returns a ranked verdict. Present the ranking; Hải picks; write the sheet from the winner, grafting anything better from the runners-up. Keep every structured return small — large StructuredOutput payloads hang agents; big artifacts go to disk.

Write the sheet in the main loop. A subagent has none of this conversation and produces generic slop; the concept is the one place the orchestrator's context earns its cost.

## Phase 2 — Inventory & fit

```
$COOK inventory --json
```
It lists cards, personas (with both lorebook fields and the active `user_avatar`), worlds and who points at them, baselines, `character_prompts` keys, GG prompts, whether `note.default` is set, ledger rows — and flags orphans (a card with no recipe/ledger row, display-name collisions, worlds nobody points at, `character_prompts` keys with no PNG, baselines with no owner, stale `.bak-*`).

Score each brick as `reuse` / `adapt` / `cook` per `references/inventory-scoring.md` and record it in `recipe.reuse`. The short version: the persona avatar is reusable when the face tags overlap ≥ 80 % (`--avatar-file`); the two Guided-Generations narrator wrappers are generic and reuse verbatim; generic lorebook mechanics come from the *template*, never by copying another campaign's file (its nouns are bound); everything that names the persona or the creature is cooked fresh; orphans are offered to `--close`, never reused.

```
$COOK ledger novelty --recipe $SCRIPTS/<slug>/recipe.json
```
exits 1 and names the row when creature-form × orifice × partner-config × setting exactly repeats a prior scenario. Change an axis; a scenario that repeats a configuration is the one he will abandon.

## Phase 3 — Fill, render, plan, dispatch

Fill the LLM slots in `recipe.json`: `char.params` (the `«…»` bindings — creature noun, what it needs, anatomy canon, the words her register stops at, self-verdict examples, tempo line, limits), `char.scenario` slots, `persona.*` (all seven Q&A groups + `voice{pov_tense, register, she_owns, she_never_writes, anatomy_stop}`), `direction.ch1` (destination · 2–3 forks as situations · 4–6 menu beats · N-GUARD · H-LIMIT · cover words · dissociation), `lore.specific` (empty in `light`; 3–6 entries in `full`), `sd` (`""` for a narrator card). Then:

```
$COOK render   --recipe $SCRIPTS/<slug>/recipe.json    # fills assets/*, asserts, writes rendered/
$COOK validate --recipe $SCRIPTS/<slug>/recipe.json
$COOK plan     --recipe $SCRIPTS/<slug>/recipe.json    # the ordered dispatch list — read it
```

`render` writes `$SCRIPTS/<slug>/rendered/`: `card-fields.json` (flat create body) · `card-lorebook.json` (3 generic mechanics, ready for `st_save_worldinfo`) · `persona-lorebook.json` (Novelty Ledger seed only) · `direction-ch1.json` (the Direction entry — `/st-arc-plan --from-recipe` inserts it) · `persona-description.txt` · `gg.json` (`impersonation_prompt`, `promptImpersonate1st`, `promptGuidedResponse`, `promptGuidedContinue`, `register_line`) · `baseline.txt` · `sim-scenarios.json`. It asserts: zero `«` left; Direction ≤ 120 real words; voice block ≤ 90 words; PHI carries checks (0)–(7); every lore entry schema-complete; create body ⊆ ST's flat field list with `world == ""`. `plan` prints exactly what will be written, in order. Show Hải the plan output; with `--dry-run`, stop here.

Then execute the plan in this order. The order is the point — each step removes one joint bug by construction.

1. **Clear the default Author's Note**: `st_save_settings_path("extension_settings.note.default", "")`. A stale note injects into every new chat and contaminated the last sim run.
2. **Card** — `st_create_character(name, rendered create body)` (ST's default avatar; `world` forced to `""` so no dead `character_book` gets embedded), then `st_merge_character("<Char>.png", {"data": {"extensions": {"world": "<Char>"}}})`. `merge-attributes` does not mirror V1↔V2: whenever you patch description/personality/scenario/first_mes/mes_example, send both the top-level and the `data.*` copy.
   - `char.kind == "narrator"` (the usual case): write `extension_settings.sd.character_prompts["<Char>"] = ""` and `character_negative_prompts["<Char>"] = ""` yourself — a narrator has no body, and anything in that field is painted onto whoever *is* on screen — and write `$BASELINES/<Char>.txt` from the rendered creature-only baseline. No `/st-setup` call.
   - `char.kind == "embodied"`, or `--full`: `Skill("st-setup", "<Char> --from-recipe $SCRIPTS/<slug>/recipe.json --no-audit")`.
3. **Card lorebook** — `st_save_worldinfo("<Char>", rendered lore)` = the three generic mechanics (Progressive Dominance, Irreversible, Pressure Signature as the single constant) + `lore.specific` under `--full`.
4. **Persona** — `Skill("st-persona", "<Name> --new --from-recipe $SCRIPTS/<slug>/recipe.json [--avatar-file <png>]")`. The Q&A is pre-filled; the avatar keep/regenerate stop stays because a face is a judgement only Hải can make; activation writes all THREE switch fields — `user_avatar`, `power_user.persona_description_lorebook`, and top-level `username` (the name printed on every user message). Then, always, `Skill("st-persona", "<Name> --voice")` — the voice contract lives in global fields (`oai_settings.impersonation_prompt`, the three Guided-Generations prompts) and is the thing that silently stayed on the previous persona last time. Seed `worlds/<Name>.json` with the rendered Novelty Ledger constant (position 1, order 100) so post-history check (7) has something to point at.
5. **Direction, openers, sim gate** — `Skill("st-arc-plan", "--from-script $SCRIPTS/<slug>/bible.md#ch1 --from-recipe $SCRIPTS/<slug>/recipe.json --openers-to-card --scenarios $SCRIPTS/<slug>/rendered/sim-scenarios.json")`. It writes the ≤ 120-word menu Direction, three openers into the card (both mirrors, via merge-attributes), appends the chapter register line to `promptImpersonate1st`, and runs S1–S8 with Opus judges.
6. **`--full` only** — sprites are 28 Forge calls with no decisions: `Agent(model: "haiku")` running `Skill("st-setup", "<Char> --expr")` with the FACE_ID and seed in the prompt; card avatar via the `curl -F /api/characters/edit-avatar` recipe in `references/st-write-paths.md`.

Append every path/field touched to `recipe.writes[]` as you go — `--close` undoes only what is on that list.

## Phase 4 — Gate & report

```
$AUDIT --char <Char> --json      # exit 0 = green
$SIM build --char <Char> --persona <Name>   # outline: one card constant, Direction, Novelty Ledger, persona at depth 2
```
Green means: impersonation prompt names the new persona; both persona-lorebook fields equal; `note.default` empty; no Direction over 120 words; no constant at depth ≤ 2; no orphans. A FLAG here is a joint bug — fix it now, in the field the audit names, and re-run once.

Write `$SCRIPTS/<slug>/report.md`:

```
## <title> — cooked <date> (<profile>)
| brick | source | where |
| card | cook | characters/<Char>.png (default avatar) |
| card lorebook | template | worlds/<Char>.json (1 constant) |
| persona | cook | User Avatars/<Name> (Persona).png · lorebook <Name> (both fields) |
| voice contract | cook | impersonation_prompt · GG ×3 (+ ch1 register line) |
| Direction ch1 | cook | worlds/<Name>.json uid N (<n> words) |
| openers | cook | first_mes + 2 alternates |
| sim | S1–S8 | <pass>/<total> — <one line per FAIL, if any> |
| audit | exit <code> | <flags, if any> |
Play: F5 the ST tab → persona <Name> → <Char> → New chat → swipe the openers.
Next: /st-arc-save "Chap 1" → /st-arc-plan --from-script bible.md#ch2 · /st-cook --close <slug> when done.
```

Then `$COOK ledger add --recipe …`, `brain_save` (type `story`, tags `["st-ledger", "roleplay", "<slug>"]`, importance 0.8, content = the report's first table + the concept's one-line premise + belief ladder), and set `recipe.status = "played"` once Hải says he has started.

---

## Close — `/st-cook --close <slug>`

A finished scenario should leave nothing behind but its archive and its ledger row; one-shots otherwise pile up in the picker and the audit fills with orphans. Full checklist in `references/close-procedure.md`; the shape:

```
$COOK close --slug <slug> --dry-run     # always first: every copy, every delete, every MCP write
```
Read it with Hải. Without `--yes` it is always a dry run; with `--yes` it archives even an unplayed campaign (it warns). Then `$COOK close --slug <slug> --yes`, which archives to `$ST_DATA/backups/<slug>-<date>/` (card, chats, worlds + `.bak-*`, avatar + thumbnails, baselines, `settings.json.full` + a `settings-snapshot.json` of the persona/voice/sd/note subtrees, the active preset, and the whole `_scripts/<slug>/`), verifies byte counts, removes the files it owns, and prints an `mcp_todo` block. Perform those MCP writes yourself, in the printed order:

1. Switch away: `user_avatar`, `username` and `power_user.persona_description_lorebook` → the persona you are switching TO (all three, or the old name keeps printing on every message).
2. Strip the ` [Chapter ` register line from `promptImpersonate1st`, then `Skill("st-persona", "<Other> --voice")` so the voice contract belongs to the persona now active; clear `extension_settings.note.default`.
3. Delete the `character_prompts` / `character_negative_prompts` keys for the card (delete, not `""`, so the orphan audit stays quiet).
4. `st_delete_character("<Char>.png", delete_chats=True)`; remove `power_user.personas.["<avatar>"]` and `persona_descriptions.["<avatar>"]`.
5. `$COOK ledger set-status --slug <slug> --status closed --archive <path>`; `brain_update` the story memory with the archive path.
6. `$AUDIT --json` → no orphans, no FLAG. Rollback, if ever needed: stop ST, `cp backups/<slug>-<date>/settings.json.full $ST_DATA/settings.json`, restore the archived files, start ST.

`secrets.json` is in no copy list and no delete list. Only paths in `recipe.writes[]` that exist on disk are touched; anything unexpected is reported, not removed.

---

## Report format (end of a cook)

```
=== /st-cook <slug> — <light|full> ===
concept:   <one line> · <n> chapters · ending: <shape>
reuse:     <brick>: <reuse|adapt|cook> …
written:   card · lorebook <Char> (1 constant) · persona <Name> + lorebook (ledger seeded) · voice ×4 · Direction ch1 (<n> w) · openers ×3
gate:      audit exit <code> · sim <pass>/<total>
ledger:    row added (<slug>) · brain <id>
play:      F5 → <Name> → <Char> → New chat → swipe
```

## Related

- `/st-setup`, `/st-persona`, `/st-arc-plan` — the executors; each accepts `--from-recipe` and remains usable alone.
- `/st-arc-save` → `/st-arc-plan --from-script bible.md#chN` — the per-chapter loop after the cook.
- `references/st-write-paths.md` — every brick → its ST field, the three joint gotchas, the merge-attributes rules.
- `sillytavern/PROMPT-PLAYBOOK.md` 5.45 (menu Directions, sim gate) · 5.46 (merge-attributes supersedes PNG patching).
