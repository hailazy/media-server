# Inventory scoring — Phase 2 reuse/adapt/cook table

`cook.py inventory --json` is read-only: it lists what's on disk and flags what's
orphaned. It does not decide anything. Phase 2's LLM step reads that JSON against
this table and writes `recipe.reuse` — one `{verdict, source}` per brick, where
`verdict` is `reuse` (use as-is), `adapt` (start from an existing asset, edit it),
or `cook` (write from a template, nothing existing qualifies).

**Why bricks don't recur.** Every /st-cook campaign is a new instance — a new
protagonist, a new creature, a new engine. Reuse in this pipeline is at the
**template** level (`assets/**`), which is why templates carry no instance content
and can live in the public repo. Nothing under `sillytavern/data/` recurs between
campaigns except the handful of bricks below, and even those only under narrow
conditions. Default to `cook` unless a row below names a specific reuse condition
you can verify against `cook.py inventory --json`.

| Brick | Default verdict | Reuse/adapt condition | Never |
|---|---|---|---|
| **Narrator/embodied card** | `cook` | — a card is the campaign's voice; no card from another campaign fits a new premise | Never reuse another campaign's card wholesale |
| **Persona** | `cook` | — same reasoning as the card: a persona is one protagonist, one voice | Never reuse another campaign's persona wholesale |
| **Avatar PNG** | `cook` (Forge, `profile=full` only; `profile=light` uses ST's default card avatar) | `adapt` via `--avatar-file <archived.png>` when an ARCHIVED avatar's `face_id` block overlaps the new persona's `face_id` at ≥80% tag match (same ethnicity, build class, hair/eye colour family) | Never reuse a *live* (non-archived) avatar — it belongs to its current campaign until that campaign is `--close`d |
| **Card lorebook** (`worlds/<Card>.json`) | `cook` from `assets/lore/generic-mechanics.json` + LLM `lore.specific` | The 3 generic-mechanics shells are the same template every time — that's the reuse. `lore.specific` entries are never copied from another campaign's world file | Never copy another campaign's lorebook file, even as a starting point — its content is instance-specific by construction |
| **Persona lorebook** (`worlds/<Persona>.json`) | `cook` (always) | — the Novelty Ledger and Chapter Direction are per-persona state from message one | Never reuse; a fresh persona always gets a fresh lorebook |
| **Voice contract — `promptGuidedResponse` / `promptGuidedContinue`** | `reuse` (global, unchanged) | Both prompts talk only about `{{user}}`/`{{char}}` in the abstract — no campaign-specific value has ever differed. Confirm via `cook.py inventory --json`'s `gg_prompts_present` before assuming; if Hải has hand-edited either, treat as `adapt` | — |
| **Voice contract — `promptImpersonate1st` / `oai_settings.impersonation_prompt`** | `cook` (always rewrite) | — these carry the persona's name and register; every campaign's persona differs | Never leave a *previous* persona's impersonation prompt in place — this is joint bug #1 from the 2026-08-30 reboot; `/st-persona --voice` runs unconditionally in Phase 3 step 4 specifically to prevent it |
| **Baseline `.txt`** (`identity-baselines/<Name>.txt`) | `cook` from `assets/baseline.tmpl` | — booru tags are persona/creature-specific | Never reuse another campaign's baseline file |
| **SD `character_prompts[<Card>]`** | `cook` (`""` for a narrator card, tags for an embodied card) | — a narrator card's `character_prompts` entry is deliberately empty so nothing is painted onto the host | — |
| **Sim scenarios** (`assets/sim-scenarios.tmpl.json`) | `reuse` for S2 (empty turn, `[""]`) and S8 (opener only, `[]`) — both are content-free by construction. `render` for S1, S3, S4, S5, S6 (world-specific placeholders). `reuse` for S7 (bare one-liner, generic) | — | — |

## Orphan flags (never reuse targets — offer to `--close` instead)

`cook.py inventory` computes these from disk + `settings.json`, no LLM needed.
Present them to Hải as **candidates for `--close`**, never as reuse sources — an
orphan by definition belongs to no recipe/ledger row, so nothing downstream can
account for it if Phase 3 quietly repoints it at a new campaign.

- **`cards_without_recipe_or_ledger`** — a card PNG in `characters/` whose name
  matches no `_scripts/<slug>/recipe.json`'s `char.name` and no ledger row's title.
  Leftover from before `/st-cook` existed, or from a closed campaign whose ledger
  row got hand-edited away.
- **`persona_name_collisions`** — two or more `power_user.personas` avatar keys
  sharing one display name. `st-gen-image-prompt`'s baseline lookup is keyed by
  display name (see the project's Baseline name collision gotcha) — a collision
  here silently corrupts image-gen prompts for both personas.
- **`worlds_nobody_points_at`** — a `worlds/*.json` file that no card's
  `data.extensions.world`, no `persona_descriptions[*].lorebook`, and no
  `power_user.persona_description_lorebook` names. Dead weight; either a stale
  reference book (e.g. a shared Bestiary — check before closing) or a true orphan.
- **`character_prompts_without_png`** — a `character_prompts` key with no
  matching card PNG. Always safe to delete; the card it painted no longer exists.
- **`baselines_without_owner`** — an `identity-baselines/*.txt` stem matching
  neither a card name nor a persona display name.
- **`world_backup_files`** — `worlds/*.json.bak-*` files. `st-arc-save` and
  `patch-card.py`-style scripts leave these behind deliberately (cheap undo); they
  accumulate forever unless something prunes them. Safe to delete once the campaign
  they belong to is `--close`d and archived — the archive already has the same
  history via `backups/<slug>-<date>/`.
