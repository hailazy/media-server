---
name: st-audit
model: sonnet
description: "Audit current SillyTavern config — explain settings, surface non-defaults, recommend changes for a goal. Read-only."
argument-hint: "[<setting-key> | goal \"<text>\"]"
allowed-tools: Bash, Read, mcp__st__st_get_settings
---

# ST Audit — Discover & Explain Current Config

Read-only audit of SillyTavern configuration. Surfaces what's currently configured, why each knob matters, and what to change for a given goal. **Does NOT modify anything** — feeds context into conversation so user decides next move. Bash is present for the auditor script, `podman exec` source lookups, and playbook greps — read-only invocations only. Config changes are handed to `/st-setup`, `/st-persona`, or `/st-arc-save`, which own the write paths.

**Why this exists:** ST has 100KB+ settings.json + 10+ extensions, each with sub-config. Most users don't know which knobs are load-bearing vs cargo-cult. This skill closes the discovery gap.

**Usage:**
```
/st-audit                          # full sweep, grouped by domain
/st-audit <setting-key>            # explain one setting (current value + what it does + safe range)
/st-audit goal "<natural language>" # goal-driven: list relevant settings + recommendations
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
SETTINGS = $ST_DATA/settings.json   # fallback only; prefer mcp__st__st_get_settings
PLAYBOOK = /home/haint/Projects/home-server/sillytavern/PROMPT-PLAYBOOK.md
```

## Knowledge Source Order

1. `PROMPT-PLAYBOOK.md` — the canonical local gotcha log (section 5). Cite the gotcha number when one applies.
2. **Live settings via `mcp__st__st_get_settings()`** — current state (ground truth). Works while ST runs (no file-lock risk). Falls back to `Read SETTINGS` if MCP unavailable (ST container down).
3. ST source defaults (read from `/home/node/app/public/scripts/extensions/<name>/index.js` via `podman exec` if needed).
4. Built-in skill knowledge below (curated facts about load-bearing knobs).

If knowledge sources conflict → live settings wins for "current value", playbook wins for "why it matters".

**Treat the playbook's dates as load-bearing.** It is a snapshot, not a mirror — a gotcha recorded months ago may describe a config that has since been deliberately retired. Anything it asserts about a *current value* (a template's length, which mode is active, how many entries a map has) must be re-read live before you repeat it; only the *reasoning* travels reliably. When the playbook and live state disagree on a value, the interesting output is the divergence itself: say what changed and when, rather than flagging live state as wrong.

---

## Mode 1: Full Sweep (`/st-audit` no args)

Read each domain via path-based MCP calls (full-tree read returns 70KB+, exceeds Claude's MCP token cap). Each call returns a JSON string of the subtree at that path.

Pseudocode below — issue these as MCP tool calls, not as a runnable script:

```python
import json

# Per-domain reads (compose a full audit without ever loading the full tree)
sd          = json.loads(mcp__st__st_get_settings(path="extension_settings.sd"))
memory      = json.loads(mcp__st__st_get_settings(path="extension_settings.memory"))
conn_mgr    = json.loads(mcp__st__st_get_settings(path="extension_settings.connectionManager"))
power_user  = json.loads(mcp__st__st_get_settings(path="power_user"))
ext_all     = json.loads(mcp__st__st_get_settings(path="extension_settings"))

# Disabled extensions live in TWO places and neither is authoritative alone:
#   - extension_settings.disabledExtensions — the aggregate list ST maintains
#   - extension_settings.<name>.disabled    — a per-extension flag some set themselves
# Check both and union them; reporting from only one silently under-reports.
disabled_exts = sorted(set(ext_all.get("disabledExtensions") or []) | {
    k for k, v in ext_all.items() if isinstance(v, dict) and v.get("disabled") is True
})
```

Produce a grouped report. Skip categories where everything is at default — focus attention on non-defaults.

**Start with the layer auditor.** The per-domain reads above show each setting's value; they can't see when two settings *contradict* each other across layers, which is where the costly problems live (a preset directive outranking a card, a lorebook constant asserting what the card just banned, a permanent SD negative deleting anatomy from every scene). Run it first and fold the findings in:

```bash
python3 /home/haint/Projects/home-server/.claude/skills/st-setup/scripts/audit-config.py --json
```

Read-only. Covers preset↔card precedence, card chunk consistency, lorebook `{{char}}` binding and always-on cost, and SD `character_prompts` hygiene. Detail on what each layer does: `/st-setup` → *The card is not the only layer*.

### Categories to audit

**[1] Image Generation** (`extension_settings.sd`)
- `source` — Forge URL backend
- `sampler` (expect `Euler` for NoobAI, NOT `Euler a`)
- `scheduler` (expect `karras`)
- `steps`, `scale` (CFG)
- `prompt_prefix` (must start with quality tags)
- `prompts` — a dict keyed by generation mode (`0`=CHARACTER, `1`=USER, `2`=SCENARIO, `3`=RAW_LAST, `4`=NOW, `5`=FACE, `7`=BACKGROUND, `8`–`10`=multimodal, `11`=FREE_EXTENDED, `-1`=MESSAGE, `-2`=TOOL). `6`=FREE has no template by design — it passes the prompt through. Report which modes have content and which are empty; **an empty template means that `/sd <mode>` aborts silently** (`generatePicture` returns early on an empty trigger with no toast), so an empty entry is either a retired mode or a broken command with no symptom.
- `character_prompts` / `character_negative_prompts` — count + keys, and whether each key still has a `characters/<key>.png`; hygiene comes from the layer auditor above.

**[2] Memory / Summary** (`extension_settings.memory`)
- `source` (`main` = uses primary LLM, `extras` = separate)
- `prompt_builder` (`0`=DEFAULT/generateQuietPrompt, `1`=RAW_BLOCKING, `2`=RAW_NON_BLOCKING)
- `SkipWIAN` (true = exclude WIAN from summary prompt)
- `promptInterval` (`0` = manual-only, N = auto every N messages)
- `position`, `depth`, `role` (where summary injects)
- `promptWords` (max summary length)

**[3] Connection Profiles** (`extension_settings.connectionManager.profiles`)
- List each profile: name, preset, model, api
- Active profile (`extension_settings.connectionManager.selectedProfile`)

**[4] RP Behavior** (`power_user.*`)
- `instruct.preset_name` + `instruct.enabled`
- `context.preset` (context template)
- `max_context`, `response_length`
- `prefer_character_prompt` / `prefer_character_jailbreak`
- Active persona: TOP-LEVEL `user_avatar` in settings.json — NOT under `power_user` (reading `power_user.user_avatar` always returns null and reads as "no persona selected" while one is active)

**[5] Extensions State**
- Walk `extension_settings.<name>.disabled` — list every extension with `disabled: true`
- Highlight notable ones: `LALib` (slash command lib), `GuidedGenerations-Extension`, `memory`

**[6] Quick Replies** (`extension_settings.quickReplyV2`)
- `config.setList` — the globally visible sets. Each element is `{set: "<name>", isVisible: bool}` where `set` is a **name string**, not the set object.
- The buttons themselves live in `QuickReplies/<name>.json` (`qrList[]`), not in settings.json — read those files to report labels and commands.
- `characterConfigs[<avatar>.png]` — per-character overrides. ST auto-creates an entry with an empty `setList` for every character it loads, so an empty one means nothing; don't report it as a finding.
- Worth surfacing for any QR whose command uses `{{input}}`: that macro reads the message textarea (`macros.js`), so the button does nothing at all when the box is empty — and `/sd` swallows the empty case without a toast.

**[7] Persona** (`power_user.personas`, `power_user.persona_descriptions`)
- Active persona + linked lorebook
- Total persona count
- Report personas by avatar key, not display name — names are not unique and the avatar-keyed `persona_descriptions[<avatar>].description` is authoritative for visuals. When a display name maps to more than one avatar, flag it: any `identity-baselines/<DisplayName>.txt` is ambiguous for that pair. Leaf keys ending `.png` need the bracket form — see Mode 2.
- `user_avatar` (top-level key, not `power_user.user_avatar`) can be `null`, meaning no persona is currently selected — report that state rather than showing a blank field.

**[8] Language (vi campaigns)** (`oai_settings.prompts`, `oai_settings.prompt_order`, active card, persona, lorebooks)
- `lang_vi` entry present + `enabled` ⇔ campaign is Vietnamese — the single source of truth for campaign language when no `--lang` flag or recipe is given
- `lang_vi` LAST in every `oai_settings.prompt_order[*].order` — an earlier position reads "write Vietnamese" as an instruction to translate whatever follows it (gotcha 5.51 leak)
- `openai_max_tokens` ≥ 6144 when vi — Vietnamese runs ~2 tok/word vs ~1.25 for English, truncates mid-page below that
- active card `mes_example`/`first_mes` carry Vietnamese diacritics when vi — the voice anchor must already be in the target language or the model under-anchors and drifts back to English
- active persona's `[Voice — …]` description block + `oai_settings.impersonation_prompt` name Vietnamese explicitly — a bare "write Vietnamese" with no POV line breaks {{user}}'s turns to third person or the narrator's to first
- `power_user.persona_description_lorebook` + the card's linked world: every keyed entry has a Vietnamese key, and none is a bare monosyllable (bò, cá, rắn, mực, sán, gián, ong, bọ, dê, ốc) — ST whole-word match splits on `\W`, so a monosyllable fires inside unrelated compounds
- Executable version of this whole category: `python3 st-setup/scripts/audit-config.py --only language`

### Output format

```
## ST Config Audit — [date]

### 🟢 Image Gen
- sampler: Euler ✓ (correct for NoobAI epsilon-pred)
- scheduler: karras ✓
- steps: <live> (compare to playbook baseline; note divergence + when, do not flag live as wrong)
- scale: 5 ✓ (CFG 4-5 for NoobAI)
- prompt_prefix: "masterpiece, best quality..." ✓
- prompts: modes with content = [-2 TOOL, -1 MESSAGE, 7 BACKGROUND]; empty = [0,1,2,3,4,5,8,9,10,11] — 4/NOW empty by design since Magnum extraction retired
- char_prompts: <N> entries [<keys>] — card-on-disk check per key

### 🟡 Memory/Summary
- source: main ✓ (uses primary LLM)
- prompt_builder: 1 (RAW_BLOCKING) ✓ (gotcha 5.33)
- SkipWIAN: true ✓
- promptInterval: 0 ✓ (manual-only, gotcha 5.33)
- position: ?, depth: ?, role: ?

### 🔴 Extensions
- DISABLED: <union of disabledExtensions and per-extension disabled flags, or "none">
- ENABLED, notable: LALib (backs the /dom summarize workaround), GuidedGenerations-Extension

### 🟢 Language (vi)
- lang_vi: enabled, LAST in prompt_order ✓
- openai_max_tokens: 6144 ✓ (vi threshold)
- mes_example/first_mes: Vietnamese diacritics ✓
- voice block + impersonation_prompt: name Vietnamese ✓
- lorebook keys: compound forms, no bare monosyllables ✓

### Connection Profiles
| Name | Preset | Model | API |
|------|--------|-------|-----|
| ...  | ...    | ...   | ... |

Active: DeepSeek daily

### Findings
- Non-default values: N
- Settings flagged: M
- Suggested next checks: [...]
```

Use `🟢` (looks correct), `🟡` (notable but intentional), `🔴` (worth attention).

---

## Mode 2: Single Setting (`/st-audit <key>`)

Parse `<key>` — accept dot-path (`sd.sampler`) or last segment (`prompt_builder` matches `extension_settings.memory.prompt_builder`).

Leaf keys containing a dot — persona avatars, anything ending `.png` — must be addressed with the bracket form `parent.path.["literal.key"]`. A bare dot-path splits inside the key and silently returns nothing, which reads as unset.

If ambiguous (multiple matches) → list candidates, ask user to disambiguate.

### Output

```
## Setting: extension_settings.memory.prompt_builder

**Current value**: 1 (RAW_BLOCKING)

**What it does**: Controls which generation path the Summarize extension uses.
- 0 (DEFAULT) → generateQuietPrompt → routes through prompt manager → injects WIAN, persona, char defs into summary prompt
- 1 (RAW_BLOCKING) → generateRaw → bypasses prompt manager → clean summary prompt only ✓ recommended
- 2 (RAW_NON_BLOCKING) → generateRaw async → faster but less reliable for long chats

**Why current value matters**: Setting 0 caused WIAN contamination in Magnum's summary output (gotcha 5.33). Switched to 1 to route through generateRaw.

**Depends on / affects**:
- Pairs with `SkipWIAN: true` (redundant safety — RAW_BLOCKING already bypasses WIAN)
- If you switch back to 0, restore SkipWIAN check

**Source**: PROMPT-PLAYBOOK.md gotcha 5.33; ST source `extensions/memory/index.js` → `prompt_builders` enum + the `RAW_BLOCKING` branch in `summarizeChat`

**Safe to change**: Only if changing summary architecture. Current value is load-bearing.
```

---

## Mode 3: Goal-Driven (`/st-audit goal "<text>"`)

Parse natural language goal. Match against known goal categories:

| Goal pattern | Relevant settings |
|-------------|-------------------|
| "image gen quality" / "ảnh đẹp hơn" | sd.sampler, scheduler, steps, scale, prompt_prefix, char_prompts, identity-baselines/<Char>.txt + /st-gen-image-prompt, sd.styles (drift check) |
| "summary clean" / "summary không bị bẩn" | memory.prompt_builder, SkipWIAN, promptInterval, source |
| "RP voice" / "ít interrupt" / "tone" | instruct preset, context preset, char card PHI, AN, model temperature |
| "model switching" / "profile" | connectionManager.profiles, selectedProfile, /profile slash command |
| "function calling" / "tool calling" | enableFunctionCalling, model api support, prompts |
| "context window" / "token budget" | max_context, response_length, summary depth, lorebook entry budgets |
| "persona setup" / "user persona" | power_user.personas, persona_descriptions, user_avatar, linked lorebook |
| "lorebook" / "world info" | worlds/*.json, character lorebook linkage, depth, position, scanDepth |
| "tiếng Việt" / "language" / "POV tôi" / "xưng hô" | Language category (above) + Playbook 5.51 |

For each match, output:
1. Current state of relevant settings (live read)
2. Common recommendations (with rationale + gotcha refs)
3. Risks of changing each
4. Suggested order of changes (start with lowest-risk)

### Output

```
## Goal: "summary không bị bẩn"

Matched category: Memory/Summary

### Current state
- prompt_builder: 1 (RAW_BLOCKING) ✓
- SkipWIAN: true ✓
- promptInterval: 0 (manual-only) ✓
- source: main ✓

### Status
**Already optimized.** All 4 load-bearing settings match recommended values from gotcha 5.33.

### If still seeing problems
- Check which OpenRouter provider served it — ST log prints `provider:` for the non-stream summary response. DeepInfra/GMICloud produce prose, word-salad or blank; the fix is `oai_settings.openrouter_quantizations: []` + `openrouter_providers: [StreamLake]` + `openrouter_allow_fallbacks: false` — single provider only: a multi-provider order is re-sorted alphabetically by the ST client on every page load (`trigger('change')` → `$(this).val()`), so "StreamLake first" never survives a reload (Alibaba moderates NSFW output → mid-stream `finish_reason: error`; DeepSeek native silently returns empty content on explicit full-context prompts, 2–3 s "finished") in live settings AND every preset (PROMPT-PLAYBOOK gotcha 5.44).
- Check chat metadata — old `extra.memory` entries from prior bad summaries can contaminate next regen. Inspect `chats/<char>/<chat>.jsonl`.

### Reference
PROMPT-PLAYBOOK.md gotcha 5.33; section 8.1 (Summary Workflow)
```

---

## Built-in Knowledge (curated facts)

Embedded so skill works without re-reading PROMPT-PLAYBOOK every invocation. Update this list when new gotchas added.

**Image gen knobs**
- NoobAI XL = epsilon-prediction → Euler/Karras/CFG5/steps≥28. NOT Euler a.
- NoobAI-XL v1.1 is epsilon-prediction; v-prediction checkpoints have not been validated on this Forge build — verify before recommending one.
- prompt_prefix MUST start with `masterpiece, best quality, newest, absurdres, highres,`
- char_prompts key = char filename WITHOUT `.png` (gotcha: `getCharaFilename()` strips ext)
- char_prompts/negatives are appended to **every** gen for that character, subject or not. They hold only always-true appearance — pose, setting, framing and human-anatomy suppression are per-shot and belong in `.claude/skills/st-gen-image-prompt/data/identity-baselines/<Char>.txt`. Full reasoning: `/st-setup` → *The card is not the only layer*.
- `sd.styles[]` records a saved prefix/negative pair. If a style has drifted from the live `prompt_prefix`/`negative_prompt`, selecting it from the dropdown overwrites them. Only `onStyleSelect` applies it, so a stale style is dormant, not active — report it as a trap rather than a fault.

**Memory/Summary**
- prompt_builder=1 (RAW_BLOCKING) bypasses prompt manager → clean summary prompt
- promptInterval=0 → manual only (recommended). Auto-trigger contaminates context unpredictably.
- Prose/salad/blank summary → bad OpenRouter provider, not the model. Pin native providers + empty quantizations filter (gotcha 5.44). Magnum profile no longer exists (retired 2026-08-28).
- Bad prior summary in `extra.memory` chat metadata → contaminates next regen. Clear it before retry.

**STscript / Slash commands**
- `is_send_press` lock → `/summarize` via QR pipe silent fails (gotcha 5.33)
- LALib `/dom action=click "#memory_force_summarize"` bypasses lock via native DOM event
- Profile switch via `/profile timeout=5000 <name>` — needs delay before next command

**Extensions**
- Third-party extensions live in `data/default-user/extensions/`, NOT `public/extensions/third-party/` (legacy path)
- LALib provides `/dom`, `/regex`, `/runc`, `/db`, `/fetch`, etc.
- GuidedGenerations adds Quick Reply hooks on GENERATION_AFTER_COMMANDS

**Language (vi campaigns)**
- The switch lives in one place: `lang_vi`, a preset custom prompt phrased as a switch ("from this page on, write in Vietnamese…"), LAST in `prompt_order` — not a language field anywhere else.
- Only output-shaping anchors (`mes_example`, `first_mes`, persona `[Voice…]` block, `impersonation_prompt`) follow campaign language; the instruction layer (system_prompt, lore content, Direction) stays English regardless.
- Lorebook keys go in compound forms (*con bò*, not *bò*) — ST's whole-word regex splits on `\W`, so bare Vietnamese monosyllables fire inside unrelated words.
- Write reefs (Playbook 5.51): one settings write at a time, close every ST tab first, verify on disk not on the tool's "OK", restart the container after preset writes.

**Persona vs Character**
- char_prompts has NO persona equivalent → visual tags must embed in `persona_descriptions[avatar].description` text
- Active persona = TOP-LEVEL `user_avatar` in settings.json (filename of avatar PNG). It is NOT under `power_user` — `power_user.user_avatar` resolves to null even while a persona is active.
- Persona-bound lorebook = `power_user.persona_descriptions[avatar].lorebook`

---

## Implementation Steps

For any mode:

1. **Read live state via path-based MCP calls**, as shown in Mode 1 — one call per domain. Reading `settings.json` off disk works too and is the fallback when the container is down, but prefer MCP: it reflects unsaved in-memory state and avoids loading a 70KB+ tree to answer a question about one subtree.

2. **Read PROMPT-PLAYBOOK.md** (skim relevant sections only — file is ~700 lines):
   - Mode 1 full sweep → read sections 1-3 (settings baseline), 8.1 (summary workflow), 5 (gotcha log — scan headings, read only what matches), 11 (tools status)
   - Mode 2 single setting → grep playbook for the setting key
   - Mode 3 goal → match goal to playbook section, read that section

3. **Cross-reference current value vs recommended**:
   - Match → 🟢
   - Different but documented choice → 🟡
   - Different and undocumented → 🔴 (flag for user attention)

4. **Output report** (markdown table or structured sections, scannable)

5. **Read-only by design** — never writes to settings.json.

---

## Edge Cases

| Case | Handling |
|------|----------|
| settings.json not found | ST data not at expected path. Check container running, paths correct. |
| ST container running while reading | Safe — read-only. But warn that values may change if user edits via UI mid-audit. |
| Setting key ambiguous in mode 2 | List candidates, ask user to pick. |
| Goal text doesn't match any category | Show available categories, ask user to rephrase or pick closest. |
| PROMPT-PLAYBOOK.md missing | Skill still works using built-in knowledge above; note playbook unavailable. |
| `lang_vi` present but disabled while card anchors (mes_example/first_mes) are Vietnamese, or the reverse | Report as a mismatch between the language switch and the campaign's actual anchors; do not auto-fix. |
