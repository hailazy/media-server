# ST write paths — brick → exact path/file/MCP call

Every write below goes through `mcp__st__*` (path-based, hot-reloads ST, no
stop/edit/start cycle) except the three noted as direct file operations (no ST API
equivalent exists for them). Every write a skill performs during Phase 3 gets
appended to `recipe.writes[]` — that list is `--close`'s only source of truth for
what to undo.

## Brick → path / call

| Brick | Where it lives | How it's written |
|---|---|---|
| Card fields (system_prompt, PHI, personality, scenario, depth_prompt, creator_notes, description, first_mes, alternate_greetings, mes_example, tags) | `characters/<Name>.png` (chara + ccv3 tEXt chunks) | `mcp__st__st_create_character(name, fields, file_name="")` at creation (forces `world: ""`); `mcp__st__st_merge_character(avatar, patch)` for every field added after (e.g. openers merged in by `/st-arc-plan --openers-to-card`). `mes_example` is REQUIRED (v3, §5.1) — 2 exchanges in the target voice, authored at cook time; send both the V1 top-level key and the `data.mes_example` mirror (see the No V1↔V2 field mirroring rule below) |
| Card lorebook link | `characters/<Name>.png` → `data.extensions.world` | `st_merge_character(avatar, {"data": {"extensions": {"world": "<LorebookName>"}}})` — **create with `world: ""`, link after**; a non-empty `world` at create time embeds a dead `character_book` copy inside the card that nothing reads afterward but that bloats the file |
| Card lorebook content | `worlds/<LorebookName>.json` | `mcp__st__st_save_worldinfo(name, data)` — REPLACES the whole file; always read-modify-write, never a partial patch (see `st-arc-save/SKILL.md`'s entry-count-never-decreases guard) |
| Persona description + visual/voice block | `settings.json` → `power_user.persona_descriptions["<Name> (Persona).png"].description` | `mcp__st__st_save_settings_path(path, value)` with the bracket-escape leaf (see gotcha 2 below) |
| Persona display name | `settings.json` → `power_user.personas["<Name> (Persona).png"]` | same, bracket-escape leaf |
| Persona lorebook content | `worlds/<PersonaName>.json` | `st_save_worldinfo` — Novelty Ledger (uid 0) + Chapter Direction (uid 1), both `constant: true` |
| Active persona | `settings.json` → top-level `user_avatar` | `st_save_settings_path("user_avatar", "<Name> (Persona).png")` |
| Persona lorebook binding (GLOBAL) | `settings.json` → `power_user.persona_description_lorebook` | `st_save_settings_path(...)` — see gotcha 1, this is the one everything forgets |
| Baseline `.txt` | `.claude/skills/st-gen-image-prompt/data/identity-baselines/<Name>.txt` | **Direct file write** — no ST API surface for this; it's a skill-local convention, not ST state |
| SD `character_prompts` entry | `settings.json` → `character_prompts["<CardName>"]` | `st_save_settings_path("character_prompts.[\"<CardName>\"]", "")` (narrator) or the SD tag string (embodied) — bracket-escape if the name contains a space+paren pattern that could be mis-split, though plain card names usually don't need it |
| Author's Note default | `settings.json` → `extension_settings.note.default` | `st_save_settings_path("extension_settings.note.default", "")` — **Phase 3 step 1, unconditionally**, before any other write (bug #3 fix by construction) |
| Author's Note per-chat override | chat file → `chat_metadata.note_prompt` | Not writable via `mcp__st__*` (no chat-metadata path exposed); `audit-config.py` WARNs if non-empty per chat — a human check, not an automated write |
| Voice contract — Guided Response/Continue | `settings.json` → `extension_settings.GuidedGenerations-Extension.promptGuidedResponse` / `promptGuidedContinue` | `st_save_settings_path(...)` only if `cook.py inventory` shows either has drifted from `assets/gg/prompts.json`'s verbatim value — normally untouched |
| Voice contract — Impersonate 1st + register line | `settings.json` → `extension_settings.GuidedGenerations-Extension.promptImpersonate1st` | `st_save_settings_path(...)` — written by `/st-persona --voice`, then `/st-arc-plan` appends ` [Chapter N register: ...]`, then `/st-arc-save` strips it back off |
| Voice contract — global impersonation prompt | `settings.json` → `oai_settings.impersonation_prompt` | `st_save_settings_path(...)` — written by `/st-persona --voice`; see gotcha 2, this is the OTHER thing everything forgets |
| Avatar image | `characters/<Name>.png` (the pixels, not the tEXt chunks) | `POST /api/characters/edit-avatar` via `curl -F` — see the recipe below; no `mcp__st__*` tool wraps this (image upload, not JSON) |
| Delete a character | `characters/<Name>.png` + `chats/<Name>/` | `mcp__st__st_delete_character(avatar, delete_chats=True)` |

## The 3 joint gotchas

These are the bugs that bit the 2026-08-30 reboot — every one of them a **seam**
between two skills, invisible to either skill's own audit. `/st-cook` exists partly
to make them structurally impossible (Phase 3's fixed step order), but the seam is
still real if a skill is ever run standalone.

1. **Two-field persona lorebook.** ST injects a persona's lorebook from the
   GLOBAL `power_user.persona_description_lorebook` — **not** from
   `persona_descriptions[<avatar>].lorebook`. Only the UI's persona dropdown syncs
   the two (`personas.js` `loadPersona`). Any script/MCP call that sets
   `user_avatar` (switches the active persona) MUST also set the global field in
   the same operation, or the *previous* persona's constant lorebook entries keep
   injecting into every turn. `audit-config.py` flags the mismatch, but only after
   the fact. **Bracket-escape**: `_parse_path`'s naive `path.split(".")` breaks on
   any key containing a literal dot — every avatar filename does
   (`"<Name> (Persona).png"`). Always address that leaf with bracket syntax:
   `power_user.persona_descriptions.["<Name> (Persona).png"].lorebook` (the dot
   before `[` is optional; the brackets are not).

2. **Global voice contract not re-applied after a persona switch.**
   `oai_settings.impersonation_prompt` and the three GG prompts
   (`promptImpersonate1st`, `promptGuidedResponse`, `promptGuidedContinue`) are
   GLOBAL settings, not per-persona — switching `user_avatar` does nothing to
   them. If `/st-persona --new` (or `--from-recipe`) runs without a follow-up
   `/st-persona <Name> --voice`, the new persona is played in the OLD persona's
   voice. `/st-cook` Phase 3 step 4 runs `--voice` unconditionally, every time,
   specifically because this is easy to forget when only bricks were "reused."

3. **Stale Author's Note.** `extension_settings.note.default` is a global
   Author's Note injected into every chat regardless of persona or card. A value
   left over from a previous campaign silently overrides card instructions.
   `audit-config.py`'s original static audit did not check this (fixed per the
   plan's implementation step 2); `/st-cook` clears it unconditionally as Phase 3's
   very first write, before card/persona/lorebook writes — order matters here,
   because a stale note can otherwise contradict the fresh voice contract for however
   many turns pass before someone notices.

## merge-attributes rules (`st_merge_character`)

`POST /api/characters/merge-attributes` → `{avatar, ...partial}` → ST's
`deepMerge` (`util.js:493`):

- **Nested objects merge** (a patch to `data.extensions` only touches the keys you
  send, others survive).
- **Arrays REPLACE wholesale** — there is no array-append. Sending
  `alternate_greetings: [a, b]` to a card that already had `[a, b, c]` leaves it
  with exactly `[a, b]`. Read-modify-write for any array field.
- **No V1↔V2 field mirroring.** ST's card format keeps two copies of several
  fields — top-level V1 (`description`, `personality`, `scenario`, `first_mes`,
  `mes_example`, `tags`, `creator_notes`) and the V2 `data.*` mirror. A merge patch
  MUST send both explicitly (`{"description": x, "data": {"description": x}}`) or
  the two drift and different UI surfaces show different content.
- **`"__@@UNSET@@__"` deletes a key** (`characters.js:1241`) — the sentinel value,
  not `null` and not omitting the key (omitting just leaves the old value alone).
- **Create-then-link, never create-with-world.** `st_create_character` always
  forces `world: ""`; link the lorebook afterward with a merge patch to
  `data.extensions.world`. A non-empty `world` at create time makes ST embed a
  dead `character_book` copy in the card that nothing reads but that bloats every
  future read of the card.

## `curl -F` recipe for `/api/characters/edit-avatar`

No `mcp__st__*` tool wraps avatar image upload (it's multipart, not JSON — the
`STClient` in `sillytavern/mcp/st-mcp/src/st_mcp/client.py` only ever POSTs
`json=payload`). Under `profile=full`, the skill uploads a fresh Forge headshot
directly via `curl`, following the SAME CSRF contract `client.py` uses:

1. `GET /csrf-token` → JSON `{"token": "..."}`. Keep the session cookie the server
   sets on this request — the token is bound to it (see `client.py`'s
   `_refresh_csrf`, which stores both on a persistent `httpx.AsyncClient`).
2. `POST /api/characters/edit-avatar` with:
   - Header `X-CSRF-Token: <token>` from step 1.
   - The SAME session cookie from step 1 (curl: `-c`/`-b` a cookie jar file across
     both requests, since curl doesn't persist cookies between invocations on its
     own).
   - Multipart field `avatar` = the image file.
   - Form field `avatar_url` = the target card's PNG filename (e.g. `The Organism.png`).
3. On a 403, `client.py`'s pattern is refresh-and-retry-once (the token can
   rotate) — do the same by hand: re-fetch `/csrf-token`, retry once.

This is a description of the contract, not a pasted-together command Hải should
run unverified — confirm the exact multipart field names against
`sillytavern/mcp/st-mcp/src/st_mcp/server.py` and the live ST source
(`src/endpoints/characters.js`, `edit-avatar` handler) before using it, since this
doc doesn't execute anything and can drift from the running container.

## Reefs found shipping Vietnamese mode (2026-09-06)

| Piece | Where it lives | How it's written |
|---|---|---|
| Language switch (the `lang_vi` custom prompt) | `settings.json` → `oai_settings.prompts` (list; the entry with `identifier == "lang_vi"`) | Read the whole list, flip that entry's `enabled` (`vi` → `true`, `en` → `false`), write the list back — `st_save_settings_path("oai_settings.prompts", <list>)`. If the entry doesn't exist yet, create it from `assets/preset/lang_vi.txt` (role `system`, `forbid_overrides: true`) first |
| Language switch position | `settings.json` → `oai_settings.prompt_order[*].order` (one array per connection profile) | Same read-modify-write per profile: the `lang_vi` order entry's `enabled` flips the same way; it must stay LAST, after `illust_contract` |
| Output length | `settings.json` → `oai_settings.openai_max_tokens` | `st_save_settings_path("openai_max_tokens", 6144)` for `vi` (leave the existing value for `en`) — computed directly from `recipe.language`, no rendered artifact |
| Global impersonation voice | `settings.json` → `oai_settings.impersonation_prompt` | `st_save_settings_path(...)` — carries "in «LANGUAGE» — the language of the chat" |
| Illustration identity | `settings.json` → `extension_settings.variables.global.illust_prefix` / `.illust_negative` | Read-merge-write `extension_settings.variables.global` in ONE `st_save_settings_path` call so other globals survive — `illust_prefix` built from persona `face_id` + body tags + always-on LoRAs, `illust_negative` from persona `negatives` |
| Persona description (bracket-escaped) | `settings.json` → `power_user.persona_descriptions.["<Name> (Persona).png"].description` | `st_save_settings_path(...)` with the bracket-escape leaf (dot before `[` is optional, brackets are not) — carries the labelled `[Voice…]` block |

Six write reefs (Playbook 5.51, verified 2026-09-06):

1. **Close every ST client first** — Hải's browser tab and any headless CDP tab. An open client rewrites the card on its next chat switch (`openCharacterChat` → `/api/characters/edit` with its cached copy) and settings on any UI event; files written server-side survive, in-memory clients don't.
2. **One `st_save_settings_path` per step, never parallel** — each call fetches the whole tree, sets one path, saves the whole tree back; two calls racing means the last writer wins and the other's change vanishes silently.
3. **Verify on disk, not from the tool's "OK"** — the PNG `ccv3` tEXt chunk for cards, `settings.json` for settings; the tool call succeeding proves the request was accepted, not that a later write didn't clobber it.
4. **Restart the container after preset/settings writes** — `./scripts/down.sh sillytavern && ./scripts/up.sh sillytavern` (~3 s). A fresh client can keep applying a stale `oai_settings` copy (`bind_preset_to_connection` re-applies what the running server still held) even though disk is already correct.
5. **Verify with a read-only client** — a branch/trigger smoke to check behavior is itself a write (it opens a chat, which is a UI event); do it once, from a client that booted after the restart, then re-check disk.
6. **Kill headless Chrome by PID** (`pgrep -f "user-data-dir=<unique dir>"`), never `pkill -f google-chrome` from the same script that launched it — the script's own command line matches the pattern and kills itself.

## Two more joint gotchas found on the first real cook (2026-08-31)

4. **A persona switch has THREE fields, not two.** Besides `user_avatar` and
   `power_user.persona_description_lorebook`, top-level `settings.username` is `name1` —
   the name ST prints on every user message (`public/script.js` ~7871 loads it; only the UI
   dropdown's `setUserName` updates it, `personas.js` ~904). Switching via MCP leaves the
   previous persona's name on every turn. `/st-persona` activation and `--close` write it;
   `audit-config.py` FLAGs a mismatch.
5. **An open ST tab clobbers MCP settings writes.** The client holds the full settings tree
   and POSTs it on UI events (`saveSettingsDebounced`); it never re-reads the server copy
   until reload. Any tab opened before the cook overwrites persona/voice/`character_prompts`
   the moment it is touched. Files (PNG, worlds, avatars) are safe; settings are not. Close
   the tab before cooking; re-run the audit at the gate; re-apply from `rendered/` if bitten.
