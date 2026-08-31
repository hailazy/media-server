# `--close` procedure

`--close <slug>` retires a finished campaign: archive everything first, verify the
archive, THEN delete. `cook.py close` only ever touches the filesystem — every
`settings.json` edit and every ST API call is the skill's job, via `mcp__st__*`,
after `cook.py close` has printed what needs doing. This split exists so a
filesystem mistake and a live-ST mistake can never happen in the same step: the
archive is complete and verified before ST state changes at all.

`cook.py close --slug <s>` is a dry run unless `--yes` is given: it prints every copy,
every delete and the `mcp_todo` block and touches nothing. With `--yes` it executes even
when `recipe.status != "played"` (it prints a warning — closing an unplayed campaign is
usually a mistake, so the skill passes `--yes` only after Hải confirms, directly or via
AskUserQuestion).

## Ordered checklist

### 1. `cook.py close` does (filesystem only)

1. Read `_scripts/<slug>/recipe.json`. Build the candidate file list from
   `recipe.writes[]` — **only** paths that (a) are listed there and (b) still
   exist on disk. `secrets.json` is excluded from every glob, unconditionally, no
   matter what `writes[]` says.
2. Create `sillytavern/backups/<slug>-<date>/`, mirroring the `reboot-2026-08-30`
   archive shape: characters, worlds (+ any `.bak-*` siblings), chats, User
   Avatars, baselines, the active connection preset, a `settings.json` subtree
   snapshot for the fields this campaign touched, **and a full
   `settings.json.full`** (the whole file, for the rollback path below), plus the
   entire `_scripts/<slug>/` directory (recipe, bible, rendered/, sim/, report.md).
3. Copy each file, then verify: destination byte count must equal source byte
   count for every file. Any mismatch aborts before anything is deleted — copying
   is the ONLY step allowed to fail loudly without side effects.
4. With `--yes`: delete the filesystem-only subset —
   `worlds/<CardLorebook>.json`, `worlds/<PersonaLorebook>.json` (+ `.bak-*`
   siblings already backed up), `identity-baselines/<Name>.txt`, the avatar PNG,
   the persona thumbnail — then move `_scripts/<slug>/` into the backup (it's
   already copied there; moving instead of copy-then-separately-delete keeps the
   live `_scripts/` directory clean without a second pass).
5. Print the `mcp_todo` block (see below) as JSON and stop. `cook.py close` never
   opens `settings.json` for writing and never calls the ST API.

### 2. The skill does, via `mcp__st__*` (after reading `mcp_todo`)

Order matters — persona unbind before card delete, so nothing is left pointing at
an avatar that's about to disappear:

1. **Persona switch-away** — a persona switch has THREE fields (`st-write-paths.md`
   gotchas 1 and 4): write `user_avatar`, top-level `username` and
   `power_user.persona_description_lorebook` for the persona you switch TO, then clear
   `power_user.persona_descriptions["<closing avatar>"].lorebook`.
2. **Voice contract strip** — reset `oai_settings.impersonation_prompt` to the
   generic sketch-enrichment prompt (`assets/gg/prompts.json`'s
   `impersonation_prompt`, unparametrised, or blank); strip any trailing
   `[Chapter N register: ...]` off `promptImpersonate1st`; leave
   `promptGuidedResponse`/`promptGuidedContinue` alone (they're generic — see
   `inventory-scoring.md`).
3. **Note clear** — `extension_settings.note.default` → `""` (idempotent; Phase 3
   step 1 of the NEXT `/st-cook` run does this too, but leaving a stale note
   between campaigns is exactly bug #3, so clear it here as well).
4. **`character_prompts` key delete** — remove `character_prompts["<CardName>"]`.
5. **`st_delete_character(avatar, delete_chats=True)`** — removes the card PNG and
   its `chats/<Name>/` directory. Do this LAST; everything above assumes the card
   still exists (`st_get_character` reads are still possible mid-procedure for
   verification).
6. `cook.py ledger set-status --slug <s> --status closed --archive
   backups/<slug>-<date>/` then `brain_update` the campaign's `story` entry to
   reflect closure.
7. Run `audit-config.py` once more — it must come back orphan-free for everything
   this campaign owned. If it doesn't, something in `recipe.writes[]` was missed;
   fix `recipe.writes[]` retroactively before trusting the next `--close`.

## Rollback

The archive's `settings.json.full` is a complete pre-close snapshot. If step 2's
`settings.json` edits go wrong (wrong persona left active, a field cleared that
shouldn't have been), restore the whole file while ST is stopped — a partial
restore while ST is running risks a `saveSettingsDebounced` race clobbering it
right back:

```bash
./scripts/down.sh sillytavern
cp sillytavern/backups/<slug>-<date>/settings.json.full sillytavern/data/default-user/settings.json
./scripts/up.sh sillytavern
```

This only undoes step 2 (the `settings.json` edits). Deleted files from step 1.4
are recovered by copying them back out of the same backup directory; `st_delete_character`
from step 2.5 is recovered by restoring the archived PNG into `characters/` (ST
will pick it back up on next character-list read — no separate "undelete" call).
