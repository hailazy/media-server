# SD Prompt Playbook — NoobAI XL + ST RP Image Gen

**Verified through 22+ tests on 2026-05-05.** All findings reproducible with seed 12345 unless noted.

Stack: NoobAI-XL v1.1 (epsilon prediction) + Forge + ADetailer (face_yolov8n.pt) + SillyTavern QR pipes on a single DeepSeek profile (Magnum retired 2026-08-28, gotcha 5.44).

---

## 1. Sampler & Settings (do not change)

```
sampler:    Euler          (NoobAI requires exact Euler, NOT Euler a)
scheduler:  Karras
steps:      30
cfg_scale:  5
prompt_prefix: masterpiece, best quality, newest, absurdres, highres,
```

Quality gap với reference images là 100% prompt construction, không phải settings.

---

## 2. Aspect Ratio Decision Tree

| Use case | Aspect | Why |
|----------|--------|-----|
| Solo character close-up | **832×1216** | Portrait native — face/body emphasis |
| Solo + body focus (butt, pose) | **832×1216** or **896×1152** | Vertical body shape |
| Multi-char emotion (1 main + 1-2 chibi) | **1024×1024** | Square balanced |
| Multi-char (chibi reactions both sides) | **1152×896** | Mild landscape — winner aspect |
| Wide cinematic background | 1216×832 | Last resort, multi-char unreliable |
| Avoid: 1344+ wide | — | Entity duplication artifact |
| Avoid: 768×1344 + girl tags | — | Schoolgirl bias collapse |

Sweet spot zone for multi-char: **1024×1024 → 1152×896**.

---

## 3. Naoko Mature Lock-in Tag Combo

NoobAI XL has STRONG schoolgirl bias. Without these tags Naoko collapses into schoolgirl appearance.

**Positive (mandatory):**
```
(milf, mom_(mature), mature_female, housewife:1.4-1.5),
35yo, japanese_woman, plump, voluptuous, large_breasts, fair_skin,
long_black_hair, black_hair
```

**Negative (mandatory):**
```
schoolgirl, school_uniform, sailor_uniform, serafuku, teenager, child, young_girl,
slim, skinny, flat_chest
```

Drop these = Naoko becomes 17-year-old schoolgirl in sailor uniform within 2 gens.

---

## 4. Composition Pattern Reliability

| Pattern | Reliability | Production use |
|---------|------------|----------------|
| Solo character + emotion | ⭐⭐⭐⭐⭐ | Default for 90% RP scenes |
| Solo + 1 animal/object | ⭐⭐⭐⭐⭐ | Subway shiba, parasite creature |
| Solo NSFW (masturbation, body focus) | ⭐⭐⭐⭐ | Self-pleasure scenes |
| Solo + creature on lips/mouth | ⭐⭐⭐⭐ | Parasite oral encounter |
| Solo + creature on body (chest) | ⭐⭐⭐ | Need force tags + retry |
| 2-char physical merge (kiss, embrace) | ⭐⭐⭐⭐⭐ | **Yuri/intimate scenes — winner** |
| Hetero side-view fellatio | ⭐⭐⭐⭐ | Profile angle hides oral anatomy difficulty |
| Hetero oral aftermath/anticipation | ⭐⭐⭐⭐ | Mouth closed/about-to → no oral anatomy challenge |
| Hetero pulled-back POV oral | ⭐⭐⭐⭐ | Less extreme close-up = cleaner anatomy |
| Hetero extreme-close POV with active oral | ⭐⭐⭐ | AVOID — mouth/tongue connection often broken |
| Hetero cowgirl/woman-on-top | ⭐⭐⭐⭐ | Naoko dominant + male implied |
| Multi-char via chibi reaction | ⭐⭐⭐⭐ | Witnesses, secondary chars |
| 2-char same-gender separate poses | ⭐⭐ | AVOID — entity bleed |
| 3+ char wide spatial | ⭐ | AVOID — duplication |

**Core principle:** design 2-char scenes around CONTACT not SPACE.

---

## 5. The 18 Gotchas

### 5.1 Negative prompt over-blocking
Tags like `humanoid_parasite, large_creature, monster` → cause creature to drop entirely. Keep exclusions specific:
- ✅ `multiple_creatures, human_creature` (specific)
- ❌ `monster, humanoid_parasite, large_creature` (over-broad)

### 5.2 Color binding for small creatures unreliable
`pink_slug` may render green/brown. Force with `(bright_pink_color:1.4), (pink_creature_color:1.3)` repeated, or accept shape over color.

### 5.3 View direction: positive > negative
`back_view` in negative prompt unreliable. Use:
```
(front_view:1.4), (looking_at_viewer:1.3), facing_viewer, frontal_pose
```

### 5.4 Body color bleed from creature
Creature pink can tint Naoko's whole body. Block with negative:
```
pink_skin, pink_body, pink_hair, body_color_pink, parasite_fusion
```

### 5.5 Spontaneous lore detail (parasite antenna/horns)
When `parasite` tagged, model auto-adds pink antenna/horns on Naoko's head. Feature for parasite RP (matches infection lore). To suppress: add `pink_antenna, horn_on_head` to negative.

### 5.6 Object placement on body parts
Reliability ranking:
- **Reliable:** lips, mouth, tongue (`slug_on_lips, creature_on_mouth, worm_in_mouth`)
- **Medium:** chest/cleavage broad (creature on cleavage works with retry)
- **Low:** specific nipple emergence (worm-from-nipple unreliable even with 1.6 weights — Section 5.21)
- **Unreliable:** specific cheek, neck, exact position → use img2img inpaint with mask

### 5.7 Spatial steering negative
For approximate placement, use negative to push creature out of unwanted positions:
```
snail_on_chest, snail_on_hand, snail_below_face, snail_in_background
```
Combined with `extreme_close_up, face_only, no_body_visible` reduces canvas → creature gets pushed to face area.

### 5.8 Wide aspect ratio = entity duplication
1344×768 and wider → model splits brain, renders 2 Naokos side by side. Avoid for multi-char.

### 5.9 Tall aspect + girl tag = schoolgirl collapse
768×1344 vertical body shape + "girl" tag triggers schoolgirl prior strongly. Avoid for Naoko scenes.

### 5.10 Schoolgirl bias gravity well
Any "girl" tag in wide composition → schoolgirl stereotype pulled in. Counter with mature lock-in (Section 3).

### 5.11 Forge Couple regional split DOESN'T solve multi-char
Tested 5 variations. Regional binding works mechanically (verified line swap), but NoobAI dataset bias overpowers regional attention. One region always drops or merges. Installed but unused.

### 5.12 Anime convention compresses multi-char effectively
Use these for "additional characters" in scene:
- `(shocked_chibi_face:1.2), super_deformed_witness, in_corner_of_frame` — chibi reaction
- `train_passengers_silhouettes, blurred_figures, defocused_bystanders` — implied population
- `over_the_shoulder_pov, foreground_arm_visible, partial_body_in_frame` — implied character via body part

### 5.13 Emotion-first prompt order
Lead prompt with feeling tags before subject details:
```
1. Subject count (1girl, 2girls)
2. Encounter/scene type (intimate, confrontation, masturbation)
3. Emotion (shocked_expression, blissed_out, ahegao)
4. Mature lock-in (milf, mom_(mature)...)
5. Specific details (clothing, pose, action)
6. Setting (blurred or detailed)
7. Lighting/mood
```
Tags positioned at 4-5 weight stronger than at 10+.

### 5.14 2-char physical merge unlocks reliable composition
Kiss, embrace, scissoring, intimate touch → high success rate.
Side-by-side seated, separate poses → low success.
Image #12 reference proven: design 2-char scenes around CONTACT.

### 5.15 Adult woman partner without schoolgirl bias
For 2-char Naoko+female scenes (yuri):
```
(adult_woman_partner, twenty_something, college_age, mature_adult:1.3),
slimmer_than_naoko, NOT_schoolgirl, office_attire
```
Plus heavy schoolgirl negative. Tested in yuri kiss → partner rendered as adult woman.

### 5.16 Hetero composition: dominant-pose framing > both-visible
Cowgirl/POV oral leverage solo gen quality with one dominant subject + partner as implicit context. Missionary/doggystyle untested but likely weaker.

### 5.17 Hand anatomy weakness
ADetailer face_yolov8n.pt only fixes faces. Masturbation/fingering scenes have hand issues.
Fix available: chain `hand_yolov8n.pt` second pass (model already in Forge), but ST doesn't send by default. Defer unless becomes pain point.

### 5.18 Parasite intimate scenes: simpler tags > custom phrases
- ✅ `slug_on_lips, creature_on_mouth, parasite_on_tongue` (known booru)
- ❌ `parasite_emerging_from_mouth_intimately` (too specific, drops creature)

### 5.19 Extreme close-up active oral anatomy weakness
ADetailer face_yolov8n.pt fixes faces broadly but NOT specific oral cavity details (mouth+penis interaction, tongue connection). Clean alternatives ranked:
- ✅ **Side/profile angle fellatio** — angle hides difficult details
- ✅ **Aftermath framing** — post-act with drool/cum aesthetic, mouth closed/sensual smile
- ✅ **Anticipation framing** — about_to_lick, holding_penis_near_face, mouth_slightly_open
- ✅ **Pulled-back POV** — less extreme close-up, mouth not center focus, tongue inside mouth
- ❌ **Extreme close-up POV with active oral** — tongue reaching outside mouth toward penis often produces broken anatomy

Production rule: for NSFW oral scenes, treat active extreme close-up as last resort. Default to anticipation/aftermath/side view.

### 5.20 Body horror + multi-creature → comic panel format trigger
Body horror prompts với extreme_close_up + multiple worm tags làm model render thành comic/manga panel layout (multi-frame trong 1 image). Negative `comic_panel` chưa đủ. Stronger fix:
```
Negative: comic, comic_panel, panels, multi_panel, split_panel, frame_borders, manga_panel, panel_borders
Positive: (single_image:1.3), single_frame, full_canvas
```
Side effect: `single_frame` weight cao có thể drift hair/eye color. Use `(single_image:1.3)` (lighter) và explicit color lock `(black_hair:1.3), long_black_hair`.

### 5.26 X-ray cross-section + bukkake = additional NoobAI sweet spots
**X-ray internal view** (cross-section showing internal anatomy):
- Vaginal x-ray cum: ⭐⭐⭐⭐⭐
- Anal x-ray cum: ⭐⭐⭐⭐⭐ (more confirmation anal content works fine)
- Oral/throat x-ray cum: ⭐⭐⭐⭐⭐
- Tags: `x-ray, internal_view, cross-section, internal_cumshot, semen_in_uterus, semen_in_rectum, throat_bulge`

**External cum/bukkake genre:**
- Cum on face: ⭐⭐⭐⭐⭐ (facial bukkake)
- Cum on breasts: ⭐⭐⭐⭐⭐ (paizuri aftermath, breast bukkake)
- Cum on body: ⭐⭐⭐⭐⭐ (full body bukkake, multiple cumshots)
- Tags: `cum_on_face, cum_on_breasts, cum_on_body, bukkake, multiple_cumshots, semen_dripping, cum_strings`

Both genres are dense in Danbooru → NoobAI handles them with high reliability.

### 5.27 Top-down view > POV for rimjob
For hetero rimjob composition:
- Top-down view (`top-down_view, from_above`): ⭐⭐⭐⭐ — clear rendering, ass focus + ahegao
- POV (`pov, pov_male`): ⭐⭐⭐ — composition becomes "ass dominate" without action contact
- Side-view (`side_view, three_quarters_view`): ⭐⭐⭐ — sometimes triggers comic panel layout

Production: default to top-down for hetero rimjob, side-view as alternative with strong panel negative.

### 5.32 POV/view tag stacking → split composition (verified 2026-05-05)
**THE GOTCHA underlying many "duplicate subject" + "extra male" reports.**

When prompt stacks 3+ POV/view tags (especially mixing internal + external views), SDXL renders **inset panels / split composition / duplicate subjects**.

**Example failure:**
```
1girl, solo, vaginal_sex, cross_section, internal_view, x-ray, close-up, ...
```
→ split into 2 panels: one solo subject + one inset showing internal anatomy. Inset panel often gets filled with action-tag's natural visualization (hetero action → phallic shape in inset). User reads as "extra male appeared despite solo".

**Verification (A/B isolation, 2026-05-05):**
- Test A: `1girl, solo, masturbation, cross_section, internal_view, x-ray, close-up, bedroom` → ❌ split composition + inset panel
- Test B: `1girl, solo, masturbation, internal_view, bedroom` → ✅ clean single composition
- Test C: `1girl, solo, vaginal_sex, lying_on_back, bedroom` (no POV stack) → ✅ clean solo (mature lock-in suppresses force-fill)
- Test D: `1girl, solo, vaginal_sex` + 4-POV stack → split with hetero phallic inset

**Production rule (Mode 4 v7.1):**
- ✅ External view: pick ONE → close-up OR wide_shot OR pov OR side_view OR top-down
- ✅ Internal view: pick ONE → x-ray OR internal_view OR cross-section
- ❌ NEVER stack `cross_section + internal_view + x-ray + close-up` — guaranteed split
- ❌ Don't stack 3+ view tags from any combo

**Cascade clarification:** "Action tag overrides solo" was earlier hypothesis — proven WRONG in isolation. `vaginal_sex + solo` alone with mature baseline renders clean (test C). Male appearance only emerges as DOWNSTREAM effect of POV stacking creating split → inset filled with hetero visualization. Fix POV stack → action tag becomes safe.

### 5.33 STscript path silently breaks `/summarize` → use `/dom action=click` workaround (verified 2026-05-05)

**The gotcha:** `/summarize` slash command via STscript chain (Quick Reply, manual typing, or any pipe-based invocation) silently fails — no toast, no error, textarea stays empty. Console shows profile switch + dryRun events but `'sending summary prompt'` never logs.

**Root cause:** `/summarize` callback → `forceSummarizeChat` → `summarizeChatMain` → `getSummaryPromptForNow` calls `await waitUntilCondition(() => is_send_press === false, 30000, 100)`. STscript executor sets `is_send_press=true` while running the slash command chain. `/summarize` waits up to 30s for the lock to release — but it never does until the entire chain finishes → silent timeout → empty return → silent exit. No `'sending summary prompt'` log because that line is reached only AFTER `getSummaryPromptForNow` returns non-empty.

**Verification (2026-05-05):**
- Path A — manual: switch profile via UI dropdown, then click "Summarize now" button in Extensions → Summarize panel → ✅ works (button click is direct function call, no slash command lock)
- Path B — slash command: `/summarize ""` typed in chat OR via QR pipe → ❌ fails silently (slash command path locks `is_send_press`)
- Disabling GuidedGenerations Extension does NOT fix Path B → not a GG issue, the lock is intrinsic to STscript executor.

**Workaround — programmatic DOM click via LALib:**
```
/dom action=click "#memory_force_summarize"
```

LALib's `/dom action=click` dispatches native DOM `pointerdown`/`click`/`pointerup` events on the panel button → fires `forceSummarizeChat(false)` in user-event context (NOT slash-command context) → bypasses `is_send_press` lock. `/delay 30000` reserves 30s for Magnum 72B to finish before profile switches back.

**Side dependencies:**
- LALib must be enabled (provides `/dom`)
- Summary uses `prompt_builder: 1` (RAW_BLOCKING) to bypass prompt manager — clean prompt, no WI/persona injection (DEFAULT path adds `personaDescription` system message that biases Magnum back into RP voice)
- Summary auto-trigger DISABLED (`promptInterval: 0`) — manual control only via QR button. Auto-fire would use whatever connection is active at trigger moment → likely DeepSeek RP-tuned → continuation prose instead of structured summary.
- ~~DeepSeek RP-tuned IGNORES "STOP. END OF ROLEPLAY" directives~~ — held for v4 Chat on a random OpenRouter provider. Since 2026-08-28 the summary runs on the main DeepSeek profile with native providers pinned (gotcha 5.44); the profile switch is gone.

**Stored config (settings.json):**
```
extension_settings.memory.prompt_builder: 1       # RAW_BLOCKING
extension_settings.memory.SkipWIAN: True          # bypass WI/AN
extension_settings.memory.promptInterval: 0       # disable auto-trigger
extension_settings.memory.source: "main"          # uses active connection (binds to QR-controlled profile)
```

### 5.34 ST silently overwrites character card PNG when running (verified 2026-05-05) — *superseded by 5.46 while ST is running; keep for the ST-down fallback*

**The gotcha:** Patching character PNG `tEXt` chunk (CCv3 / V1 chara JSON) WHILE ST is running → patches silently revert. ST holds character cards in memory after load; opening the card UI or any action that triggers card-save event causes ST to write its in-memory (pre-patch) version back to disk, overwriting your changes. No error, no toast — just disappeared.

**Verification (2026-05-05, /st-setup --adv on Parasite):**
- Step 1: ST running. Patched Parasite.png: description 5325 → 4134 chars, populated personality (165), mes_example (651 → 1767), depth_prompt (382). Read-back verify: ✅ all fields correct.
- Step 2: User reloaded ST → opened card UI → saw trimmed description ✅
- Step 3: Some interaction triggered ST card-save → file rewritten with pre-patch in-memory data
- Step 4: Re-read PNG: description back to 5281 chars (close to original 5325, ST normalized whitespace), personality empty, mes_example back to 651, depth_prompt empty. `.bak` (2000722 bytes) stayed intact.

**Root cause:** Same family as `saveSettingsDebounced` for settings.json. ST treats character cards as live mutable state — UI edits / extension calls / lorebook re-bind events all flow through `saveCharacter()` which writes the in-memory representation, NOT a fresh read from disk.

**Fix (mandatory workflow for PNG patches):**
```bash
./scripts/down.sh sillytavern    # stop ST cleanly
# patch PNG via Python tEXt rewrite
./scripts/up.sh sillytavern      # restart, ST loads patched data fresh
```

**Skill enforcement (`/st-setup --adv` Phase 1.5 Step D):**
- Asserts `'sillytavern' not in podman ps` before patching
- Aborts if ST detected running
- Restarts ST after patch
- Same pattern as Phase 2 settings.json edit (already had this guard)

**Recovery if patch reverted:** `.bak` is one cp away — `cp Parasite.png.bak Parasite.png` (with ST DOWN), then re-run patch.

**Generalizable rule:** Any file ST loads into memory at startup (`settings.json`, `characters/*.png`, possibly `worlds/*.json` under some conditions) requires ST stopped before file-level patching. Lorebook JSON appears safe to edit live in current testing, but consider stopping for any non-trivial multi-file patch.

### 5.35 V2 character cards: must sync V1 mirror fields when patching (verified 2026-05-05) — *superseded by 5.46 while ST is running; keep for the ST-down fallback*

**The gotcha:** V2 character cards (`spec: chara_card_v2`, `spec_version: 2.0`) store fields TWICE — at top-level root (V1 path: `card.description`) AND inside `data` namespace (V2 path: `card.data.description`). The two paths are mirror copies of the same content. Patching ONLY the V2 path leaves V1 stale → ST frontend reads from V1 → UI shows old data even though `data.X` is patched correctly.

**Verification (2026-05-05, /st-setup --adv on Parasite):**
- After patch (V2 only), file inspection:
  - `card.description`: 5281 chars (UNCHANGED, original)
  - `card.data.description`: 4134 chars (patched ✓)
  - `card.personality`: 0 chars (UNCHANGED, empty)
  - `card.data.personality`: 165 chars (patched ✓)
  - `card.mes_example`: 651 chars (UNCHANGED, old)
  - `card.data.mes_example`: 1767 chars (patched ✓)
- UI displayed V1 data (untrimmed description, empty personality, old 3-example dialogue)
- Hard reload + cache clear + char re-select did nothing — because the file genuinely had old V1 data

**Why two paths exist:** Backwards compatibility. Older clients (pre-spec_v2) read top-level fields. ST exporters write both paths to ensure cards work in both ecosystems. ST frontend reads V1 paths first (legacy code path).

**Fix:** Always sync V1 ↔ V2 fields when patching V2 cards.

```python
if 'data' in card:
    card['data'] = d  # V2 update
    # Sync V1 mirror fields
    for field in ['description', 'personality', 'scenario', 'mes_example', 'first_mes']:
        if field in d:
            card[field] = d[field]
else:
    card = d  # V1-only card (rare/legacy)
```

**Verification one-liner (after patching):**
```python
assert card['description'] == card['data']['description']
assert card['personality'] == card['data']['personality']
assert card['mes_example'] == card['data']['mes_example']
```

**Affected fields with V1 mirrors:** `description`, `personality`, `scenario`, `mes_example`, `first_mes`. Fields ONLY in V2 (no V1 mirror): `creator_notes`, `system_prompt`, `post_history_instructions`, `alternate_greetings`, `tags`, `creator`, `character_version`, `extensions`, `character_book`. These don't need sync.

**Skill enforcement (`/st-setup --adv` Phase 1.5 Step D):** dual-write loop added.

### 5.36 ST disk cache is the source of truth — PNG patches alone are invisible to UI (verified 2026-05-05) — *superseded by 5.46 while ST is running; keep for the ST-down fallback*

**The gotcha:** ST treats character PNG as **export-only** format. The actual data UI reads from comes from `data/_cache/characters/<sha256>` JSON files. Patches to PNG file alone never reach UI because the data flow is one-directional: UI → write to both PNG + cache; file changes → readCharacterData reads cache first (line 182 `endpoints/characters.js`):

```javascript
async function readCharacterData(inputFile) {
    const cacheKey = `${inputFile}-${stat.mtimeMs}`;
    if (memoryCache.has(cacheKey)) return memoryCache.get(cacheKey);
    if (useDiskCache) {
        const cachedData = await cache.getItem(cacheKey);
        if (cachedData) return cachedData;
    }
    return await parse(inputFile);  // ← only on cache miss
}
```

Even after restart + cache nuke, the next ST start may regenerate cache from internal state (not from re-parsing PNG) — exact mechanism unclear but verified empirically.

**User's diagnosis (correct):** *"patch chỉ hoạt động một chiều từ UI → image chứ không phải ngược lại"* — patches only flow UI → file, not file → UI.

**Verification (2026-05-05):**
- Patched Parasite.png: V1+V2 both = trimmed 4134 chars, personality/mes_example/depth_prompt populated
- Stopped ST → patched PNG → nuked 44 stale cache entries → restarted ST
- ST recreated 1 cache entry — but with **STALE data** (5281 chars, "persuasive abilities" present, personality empty)
- `/characters/Parasite.png` HTTP endpoint correctly served patched 2001158-byte PNG → ST IS aware of patched file
- But UI rendered cache content = stale
- **Fix that worked**: stopped ST → manually patched cache file's `value` field with patched JSON → restarted ST → UI rendered patched data ✓

**Correct fix workflow (4 steps, both PNG + cache patched):**

```bash
./scripts/down.sh sillytavern
```

```python
import struct, base64, json, zlib, os, re

PNG_PATH = f"{ST_DATA}/characters/{char_name}.png"
CACHE_DIR = f"{ST_DATA}/_cache/characters"

# 1) Patch PNG (for V1+V2 field sync — keeps PNG export-correct)
# ... (existing tEXt chunk rewrite + V1+V2 sync) ...

# 2) Patch the cache file's value field
target_cache = None
for fname in os.listdir(CACHE_DIR):
    fpath = os.path.join(CACHE_DIR, fname)
    try:
        with open(fpath) as f: outer = json.load(f)
        if f"{char_name}.png" in outer.get('key', ''):
            target_cache = (fpath, outer)
            break
    except: pass

if target_cache is None:
    # No cache yet — create one with current PNG mtime
    mtime_ms = os.path.getmtime(PNG_PATH) * 1000
    cache_key = f"data/default-user/characters/{char_name}.png-{mtime_ms}"
    # Use sha256 of cache_key as filename (need to verify actual ST hash function)
    import hashlib
    fname = hashlib.sha256(cache_key.encode()).hexdigest()
    target_cache = (os.path.join(CACHE_DIR, fname), {'key': cache_key, 'value': ''})

cache_path, cache_outer = target_cache
cache_outer['value'] = json.dumps(patched_card, ensure_ascii=False)
with open(cache_path, 'w') as f:
    json.dump(cache_outer, f, ensure_ascii=False)
print(f"✓ Patched cache: {cache_path}")
```

```bash
./scripts/up.sh sillytavern
```

**Skipping cache patch = PNG patch invisible to UI.**

**Other ST persistent caches to be aware of:**
- `data/_cache/deepseek.json`, `qwen2.json` — tokenizer caches (irrelevant for char patches)
- `data/_cache/Cohee/` — user-namespaced cache (similar disk cache for other users)
- `data/default-user/thumbnails/avatar/<char>.png` — visual avatar thumbnail only (no card data, safe)
- `data/default-user/image-metadata.json` — file hash + dimension metadata (no card data, safe)

**Related ST source paths:** `/home/node/app/src/endpoints/characters.js:166-209` (cache + readCharacterData), `:38-159` (DiskCache class).

### 5.37 Magnum Mode 4 image-prompt extraction retired (2026-05-06)

**Decision:** Replaced Magnum 72B (RAW_BLOCKING) Mode 4 prompt extraction with Claude skill `/st-gen-image-prompt`. Magnum profile chỉ còn cần cho `/summarize` compliance (gotcha 5.33).

**Rationale:**
- Magnum context cứng 16K → chỉ thấy `{{summary}}` + last message → output thiếu ổn định, sai tag, hallucination POV stacking, drift khỏi scene thực tế
- Đã iterate template từ v1 → v8.2 (4258 → 2144 chars, 5 hard rules) — vẫn chưa đủ tin cậy
- Claude (Opus 4.7, 1M context) đọc full chat — instruction-following mạnh hơn cho structured output
- Tách prompt-eng khỏi RP loop → dễ debug, dễ iterate

**Workflow change:**
1. User runs `/st-gen-image-prompt [CharName]` trong Claude Code
2. Skill đọc chat last N msgs + char card + persona + identity baseline → generate booru tags
3. Tags verified qua Danbooru DB (~5MB lazy fetch vào `~/.cache/st-gen-image-prompt/`)
4. User copy → paste vào ST input → click `🎨 Freestyle` button
5. ST forwards qua Forge với pass-through Mode FREE (no LLM processing)

**QR cleanup (ImageGen.json):**
- Removed: 📷 Scene, 👤 Char, 😊 Face, 🎭 Imp (Magnum-dependent)
- Kept: 🌅 BG (Mode 7 still LLM-handled), 📝 Summary (Magnum compliance) — both moved to DeepSeek on 2026-08-28, see gotcha 5.44
- Added: 🎨 Freestyle (`/sd {{input}}` pass-through)

### 5.38 char_prompts emptied + Mode 0/1/2/4/5 templates emptied (2026-05-06)

Migrated SD config to skill-controlled prompts:

**character_prompts**: emptied for all chars. Identity baselines moved to `~/Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines/<CharName>.txt`. Skill injects identity per-scene (skip for BG-only, skip outfit for bath/nude scenes).

**Mode templates emptied** (no longer used since skill provides full prompt):
- prompts["0"] CHARACTER (1289 → 0)
- prompts["1"] USER (827 → 0)
- prompts["2"] SCENARIO (1456 → 0)
- prompts["4"] NOW (2264 → 0, was v8.2 production)
- prompts["5"] FACE (1282 → 0)

**Kept intact:**
- prompts["7"] BACKGROUND (1259 chars) — BG button still LLM-handled via Mode 7
- prompts["8-11"] multimodal (caption modes) — separate use case
- prompts["-1", "-2", "3"] meta — internal
- character_negative_prompts — universal filter (muscular, child, schoolgirl, etc.) auto-prepended by ST
- All production sampler/CFG/HR settings (Euler, Karras, 35 steps, CFG 5, hr_scale 1.5) — verified, untouched

**Backup**: `settings.json.bak.pre-magnum-retire`. Restore = 1 cp.

**Critical**: Skill output MUST inject identity baseline cho char-present scenes — without it, Naoko regenerates as schoolgirl in 2-3 gens (gotcha 5.3 mature lock-in still applies).

### 5.39 `/sd <prompt>` defaults to Mode FREE (pass-through) — no LLM extraction

Verified in ST source `public/scripts/extensions/stable-diffusion/index.js`:

```javascript
const generationMode = {
    TOOL: -2, MESSAGE: -1, CHARACTER: 0, USER: 1, SCENARIO: 2,
    RAW_LAST: 3, NOW: 4, FACE: 5, FREE: 6, BACKGROUND: 7,
    CHARACTER_MULTIMODAL: 8, USER_MULTIMODAL: 9,
    FACE_MULTIMODAL: 10, FREE_EXTENDED: 11,
};

function getGenerationType(prompt) {
    let mode = generationMode.FREE;  // default
    for (const [key, values] of Object.entries(triggerWords)) {
        for (const value of values) {
            if (value.toLowerCase() === prompt.toLowerCase().trim()) {
                mode = Number(key);
                break;
            }
        }
    }
    // ... (multimodal + free_extend overrides)
    return mode;
}

const triggerWords = {
    [generationMode.CHARACTER]: ['you'],
    [generationMode.USER]: ['me'],
    [generationMode.SCENARIO]: ['scene'],
    [generationMode.RAW_LAST]: ['raw_last'],
    [generationMode.NOW]: ['last'],
    [generationMode.FACE]: ['face'],
    [generationMode.BACKGROUND]: ['background'],
};
```

**Behavior:**
- `/sd you` / `/sd last` / `/sd face` / `/sd background` / `/sd scene` / `/sd me` / `/sd raw_last` → match trigger → LLM-extract prompt qua Mode template
- `/sd <anything else>` → no match → Mode FREE = 6 → **pure pass-through**, no LLM call

**Implication for QR `🎨 Freestyle` button:**
- Message: `/sd {{input}}` (NOT `/sd freestyle {{input}}` — `freestyle` không phải trigger word, chỉ là tên đặt cho button)
- User pastes booru tags → ST sends raw tags + prompt_prefix + character_prompts (empty) + character_negative_prompts → Forge

**Edge case**: nếu user paste prompt mà text trùng exact một trigger word (vd `/sd "you"`) → mode chuyển CHARACTER (LLM-process). Nhưng `value.toLowerCase() === prompt.toLowerCase().trim()` là EXACT match — paste full booru prompt không bao giờ collide.

### 5.40 ADetailer hand_yolov8n.pt enabled via ST patch (2026-05-06)

**The gotcha:** ST source `index.js:3831` hardcoded chỉ gửi `face_yolov8n.pt` trong alwayson_scripts.ADetailer.args. Để add hand model phải bind-mount patched index.js — ST không expose `adetailer_hand` setting.

**Fix applied:**

1. Copy ST source: `podman cp home-sillytavern:/home/node/app/public/scripts/extensions/stable-diffusion/index.js sillytavern/patches/sd-index.js`
2. Patch payload (line 3835-3845): args array thêm hand model dict + explicit confidence/denoising:
   ```js
   args: [
       true, true,
       { 'ad_model': 'face_yolov8n.pt', 'ad_confidence': 0.3, 'ad_denoising_strength': 0.4 },
       { 'ad_model': 'hand_yolov8n.pt', 'ad_confidence': 0.3, 'ad_denoising_strength': 0.4 },
   ]
   ```
3. Bind mount in `sillytavern/compose.yml`:
   ```yaml
   volumes:
     - ./data:/home/node/app/data:z
     - ./patches/sd-index.js:/home/node/app/public/scripts/extensions/stable-diffusion/index.js:ro,z
   ```
4. Forge `ui-config.json`: `txt2img/ADetailer detector 2nd/value` = `"hand_yolov8n.pt"` (UI default)
5. Restart ST + Forge

**Verification (2026-05-06):**
- API smoke test: payload với 2 models → HTTP 200 21s, metadata returns `ADetailer confidence 2nd: 0.3, denoising strength 2nd: 0.4` for both slots
- Hands giờ được second-pass inpaint mỗi gen → finger anatomy fixed automatically

**Tradeoffs:**
- Patch sẽ break nếu ST upgrade thay đổi block `if (extension_settings.sd.adetailer_face)`. Khi update SillyTavern image, re-copy index.js và re-patch
- Total gen time +5-8s per image (hand pass adds ~1 inpaint step at base resolution)
- Confidence 0.3 = aggressive detection. Higher 0.5+ = miss small/blurry hands. Lower 0.2 = false positives on background details
- Denoising 0.4 = safe sweet spot. >0.6 destroys hand identity (skin tone/length drift)

**Related**: gotcha 5.x ADetailer face setup (already auto-via `adetailer_face: true`). With this patch, BOTH passes fire automatically per gen.

### 5.41 Forge launch args — drop `--cuda-malloc / --cuda-stream / --pin-shared-memory` for 16GB+ cards (2026-05-06)

3 args added by ai-dock image template chỉ có gain cho low-VRAM cards (6-8GB):
- `--cuda-malloc`: ~0.1s/image gain, can crash randomly per Forge maintainer warning
- `--cuda-stream`: 15-25% speed for SDXL on 6-8GB. 16GB không gain.
- `--pin-shared-memory`: VRAM tradeoff helpful for low-VRAM. 16GB không cần.

For RTX 4070 Ti SUPER 16GB, lean to: `--listen --api --xformers --ui-settings-file ... --ui-config-file ...`. Same speed, no random crash risk.

### 5.43 Forge InputAccordion master toggles không persist qua container restart (2026-05-07)

**The gotcha:** `Hires. fix` và `ADetailer` master enable checkbox dùng `InputAccordion` component. Khi check trong UI rồi click "Settings → Defaults → Apply", Forge ghi `txt2img/Hires. fix/value: True` + `customscript/!adetailer.py/txt2img/ADetailer/value: True` vào `ui-config.json`. NHƯNG khi container restart, ui_loadsave đọc lại file và `setattr(component, value, True)` SAU khi gradio đã render từ constructor's hardcoded `value=False` → checkbox về unchecked.

**Why reload browser không mất state:** Forge process vẫn running, component runtime memory intact, tab reconnect → state still there. Container restart kills process → RAM wiped → init từ source code hardcoded defaults.

**Symptom:** sau mỗi restart, Hai phải tự click ADetailer enable + Hires fix enable lại (irritating cho manual UI gen). ST API workflow KHÔNG bị ảnh hưởng vì alwayson_scripts payload có `ad_enable: true` override.

**Fix:** Source patch — change `InputAccordion(False, ...)` → `InputAccordion(True, ...)`.

```bash
# 1. ADetailer (extension đã bind-mounted via data/forge/extensions/)
podman unshare sed -i 's/value=False,$/value=True,/' \
  /home/haint/Projects/home-server/forge/data/forge/extensions/adetailer/aaaaaa/ui.py
# Line 132: with InputAccordion(value=True, ...) wrapping ADetailer master toggle

# 2. Forge core ui.py (không bind, cần copy + bind mount)
mkdir -p /home/haint/Projects/home-server/forge/patches
podman cp home-forge:/opt/stable-diffusion-webui-forge/modules/ui.py \
  /home/haint/Projects/home-server/forge/patches/ui.py
# Edit line 329: InputAccordion(False, label="Hires. fix", ...) → InputAccordion(True, ...)
```

Add bind mount trong `forge/compose.yml` volumes section:
```yaml
- ./patches/ui.py:/opt/stable-diffusion-webui-forge/modules/ui.py:ro,z
```

**Verification (2026-05-07):** Forge restart → reload browser tab → Hires fix + ADetailer master toggle default-checked. Persist qua mọi restart.

**Tradeoffs:**
- Patch break nếu Forge upgrade thay đổi block. Khi `./scripts/update.sh` pull new image, re-copy + re-patch.
- ADetailer extension upgrade (rare) cũng cần re-patch — extension folder mounted, sed edit gets overwritten only if user manually re-installs ADetailer.

### 5.42 Forge UI config persistence (2026-05-06)

**The gotcha:** `config.json` + `ui-config.json` ở root webui dir (`/opt/stable-diffusion-webui-forge/`) KHÔNG nằm trong default bind mounts (which only cover `models/`, `embeddings/`, `outputs/`, `extensions/`, `config/` subdir). Settings (ADetailer panels, sampler defaults, hires defaults) reset mỗi container restart.

**Fix:** redirect via CLI flags trong `forge_args.conf`:
```
--ui-settings-file /opt/stable-diffusion-webui-forge/config/config.json
--ui-config-file /opt/stable-diffusion-webui-forge/config/ui-config.json
```
Container's `config/` is mounted (`./data/forge/config:/opt/stable-diffusion-webui-forge/config:z`), so files written there persist.

Migration step: `podman cp home-forge:/opt/.../config.json` ra host trước khi áp dụng (otherwise Forge starts với empty config and overrides defaults).

### 5.31 Niche fetish genres = Parasite RP arc support
NoobAI XL has strong training for niche hentai fetish genres. All verified at ⭐⭐⭐⭐ to ⭐⭐⭐⭐⭐.

**Hypnosis:** `hypnosis, hypnotized, hypno_eye, spiral_eyes, dazed_expression, empty_eyes, mesmerized, dazed`
- Spiral eye patterns render correctly
- Use for Parasite pheromone control stage

**Mind control:** `mind_control, controlled, possessed, glowing_eyes, purple_glowing_eyes, corrupted_eyes, possessed_pupils, marionette_pose, purple_aura, dark_corruption`
- Glowing eye effects + corruption aura render perfectly
- Use for Parasite Stage 2 (behavioral assertion)

**Brain wash:** `brainwashing, brainwashed, mental_invasion, indoctrination, glowing_screen_reflection, tv_static_eyes, screens_floating, mind_being_invaded, mental_corruption`
- TV/screen objects with eye reflection render
- Use for Parasite Stage 3 (neural rewiring) or sci-fi/cyberpunk variants

**Mind break:** `mind_break, mindbreak, broken, ahegao, vacant_eyes, broken_expression, tongue_out, drool, eyes_rolled_back, exhausted_pose, surrendered_completely, body_limp, disheveled_hair`
- Classic mindbreak aesthetic — all expected elements render
- Use for Parasite climactic surrender

**Oviposition / Egg laying:** `oviposition, egg_laying, eggs, multiple_eggs, slimy_eggs, swollen_belly, distended_stomach, laying_eggs`
- Eggs render as surrounding objects, body distention works
- Use for Parasite reproduction climax

**Combo templates for Parasite RP late-stage:**

```
# Mind control + tentacles (climax)
mind_control, possessed, glowing_purple_eyes, marionette_pose,
+ tentacles, controlled_by_tentacles, tentacle_around_neck

# Brain wash + parasite (neural takeover)
brainwashing, glowing_screen_reflection, mental_invasion,
+ parasite_controlling_mind, slimy_creature_on_head

# Mind break + bukkake (public infection climax)
mind_break, mindbreak, ahegao, vacant_eyes, drool,
+ cum_on_face, bukkake, gangbang_focus, multiple_penises

# Oviposition + tentacles (reproduction)
oviposition, egg_laying, eggs_emerging, swollen_belly,
+ tentacles, tentacle_in_pussy, parasite_birth
```

### 5.30 Context/setting tag reliability
NoobAI XL handles aesthetic/setting contexts strongly when they're established booru genres.

**Verified reliable ⭐⭐⭐⭐⭐:**

**Public/exhibitionism:**
```
exhibitionism, public_indecency, public_nudity, flashing, lifting_skirt,
+ crowd_silhouettes, faceless_bystanders, train_passengers_silhouettes, blurred_crowd
```
Settings work: train_station, urban_street, shopping_district, public_setting

**Live stream / streaming:**
```
live_stream, streaming, webcam_focus, looking_at_camera,
chat_messages_overlay, viewer_count_visible, donation_alerts_floating,
ring_light, gaming_chair, computer_setup
```
NoobAI renders streaming UI overlays (donation text, viewer count) — strong genre training.

**Phone selfie / mirror selfie:**
```
selfie, taking_picture, smartphone, holding_phone, mirror_selfie,
phone_in_hand, bathroom_mirror, full_body_mirror,
looking_at_phone_screen
```
Phone object placement works reliably (unlike specific-body-part placement).

**Less reliable ⭐⭐⭐ — Cuckold/Cuckqueen:**

Same multi-char limit issue. Secondary watching/watched character doesn't render strongly. Workarounds:
1. Use **implied multi-char** technique (Section 5.29):
   - Cuckold: `faceless_husband_silhouette, husband_in_doorway_silhouette, watching_silhouette`
   - Cuckqueen: `faceless_couple_in_background, hands_grabbing_each_other_in_background, body_parts_other_couple`
2. Accept aesthetic-alone rendering + RP narrative carries dynamic
3. Render multiple separate scenes (Naoko alone with watching expression, then partner+other scene)

### 5.29 Implied multi-character via body parts = MAJOR unlock
NoobAI XL has dedicated genre support for "implied multi-character" composition — render only body parts of additional characters while focusing on the main subject. This solves the multi-char entity bleed problem.

**Verified working tags (all ⭐⭐⭐⭐⭐):**
```
faceless_male, headless_male, only_body_parts_visible, only_penises_visible, only_hands_visible,
multiple_penises, multiple_hands, multiple_cocks_pointing, surrounded_by_hands,
gangbang_focus, body_parts_only, partial_male_bodies, cropped_male_bodies,
out_of_frame_male, partial_body
```

**Production scenarios:**
1. Naoko + multiple penises around face (gloryhole/multi-penis)
2. Double blowjob (2 girls + 1 implied man)
3. Gangbang focus on Naoko (multiple penises + hands without full bodies)
4. Implied crowd grabbing (many hands from all directions)
5. Public scenes with active crowd interaction

**Why this works:**
- Bypasses NoobAI multi-char entity bleed limit
- Mature lock-in survives because main subject is solo focus
- Common Danbooru genre with strong tag support
- Compatible with all aspect ratios (square 1024×1024 ideal)

**Combination with other patterns:**
- + `cum_on_X` tags → bukkake group scenes
- + `train_passengers_silhouettes` → public crowd subway scenes
- + `mind_break, surrendered` → climactic group humiliation
- + parasite tags → infection-controlled hosts surrounding Naoko

This is the answer to "fake crowd scenes without rendering full extras" — NoobAI handles it as a first-class genre.

### 5.28 Comic panel triggers expanded
Body horror, side-view rimjob, and other intimate-but-unusual compositions can trigger comic/manga panel layout. Universal negative should include:
```
comic, comic_panel, panels, multi_panel, split_panel, frame_borders, manga_panel, panel_borders, multi_frame_layout
```
Add positive `(single_image:1.3)` if panel format persists.

### 5.25 Tentacle genre = NoobAI XL sweet spot
NoobAI XL has strong tentacle hentai training (Danbooru tentacle genre is dense). Reliability ranking:

- Multi-tentacle restraint (body wrap, breast squeeze): ⭐⭐⭐⭐⭐
- Multi-tentacle penetration (oral + vaginal + anal simultaneously): ⭐⭐⭐⭐⭐
- Single large tentacle creature grab: ⭐⭐⭐⭐
- Tentacle + emotion combo (ahegao, surrendered, blissed): ⭐⭐⭐⭐⭐

**Production tag template (verified working):**
```
1girl, solo, tentacles, [scene type],
mature_female, milf, plump, large_breasts, black_hair,
nude, [pose: legs_spread/restrained/lifted],
[specific: tentacle_in_mouth, tentacle_in_pussy, tentacle_in_anus, multiple_tentacles, slimy_tentacles, slime],
ahegao OR blissed OR shocked_yet_blissed, parted_lips, drool, deep_blush, eyes_rolled_back,
dim_lighting, bokeh_background, body_horror_atmosphere
```

**Implication cho Parasite RP:** Swap "horsehair_worm" or "pink_slug" with "tentacles" for late-stage infection scenes. Model renders tentacles much more reliably than worms/slugs. Lore can describe parasite creature with tentacle protrusions for stronger visual.

### 5.24 Hetero rimjob ambiguity vs yuri rimjob
NoobAI handles yuri rimjob better than hetero rimjob due to training data distribution (more yuri rimjob art on Danbooru than hetero).

**Reliability:**
- Yuri rimjob (2girls): ⭐⭐⭐⭐ — common booru genre, well-bound
- Hetero rimjob Naoko-giving-to-man: ⭐⭐⭐ — model defaults to blowjob interpretation when seeing `1girl + 1boy + oral`
- Hetero rimjob Naoko-receiving-from-man: ⭐⭐⭐ — renders 2 separate bodies without action contact

**Workarounds:**
1. **Single subject focus** (POV-style): frame as Naoko's POV with man's ass as focus — `1boy bent over, ass focus, woman's tongue licking from below`
2. **Side view 3/4 angle**: physical contact merge easier to render than front-view
3. **Stronger position tags**: `man_face_in_woman_ass, woman_face_in_man_ass, prone_position`
4. **Accept yuri substitute**: if RP narrative only needs "Naoko being eaten out", yuri version (verified working) gives aesthetic equivalent

### 5.21 Prompt weight stacking overflow (CORRECTED hypothesis 2026-05-05)
**THE REAL GOTCHA underlying many "structural limit" claims.**

When prompt has 5+ parenthesized weights stacked, especially in 1.3-1.6 range:
```
(milf, mom_(mature), housewife:1.5) + (huge_ass:1.3) + (horsehair_worm:1.5) +
(worm_emerging_from_anus:1.6) + (worm_in_anus:1.5) + (long_thin_worm:1.4) +
(visible_worm_protruding:1.4) + (shocked_yet_blissed:1.3) + ...
```
→ attention overflow → **abstract noise output** (literal static pattern, not an image)

This was previously misdiagnosed as "anal-oral content suppression" or "worm-from-anus structural limit". Verification with SIMPLE prompts (no heavy weight stacking) showed the same content (yuri rimjob, worm-from-anus, anal close-up) renders cleanly.

**Production rule:**
- ✅ Use Magnum-style minimal tag lists without excessive parenthesizing
- ✅ Reserve `(tag:1.3+)` weighting for 1-2 critical anchors per prompt (e.g., mature lock-in, primary action)
- ❌ Don't stack 5+ heavy weights — model breaks down
- ✅ Trust Magnum's natural booru-tag output (cleaner than over-engineered manual prompts)

**Worm/creature emergence reliability — REVISED:**
- Mouth/lips/tongue: ⭐⭐⭐⭐⭐ reliable
- Anus (with simple prompts): ⭐⭐⭐⭐ reliable (verified)
- Cleavage/breast broad: ⭐⭐⭐⭐
- Nipple specific (any prompt complexity): ⭐⭐ — this one IS structurally hard, not just weight-related
- General skin slime trails: ⭐⭐⭐⭐

---

### 5.44 Magnum profile retired entirely — DeepSeek single-profile + native provider pin (2026-08-28)

**Decision:** Connection profile "Magnum — Image Gen" deleted. Every QR now runs on `DeepSeek daily` (`deepseek/deepseek-v4-pro-0813`). Preset `MagnumStrict` rebuilt as `OpenAI Settings/ImageGen.json` on DeepSeek (temp 0.7, reasoning low, max_tokens 4096, ctx 16384). QR set:
- 🌅 BG → `/preset ImageGen | /sd background | /preset Default` (preset switch, no profile switch)
- 📝 Summary → `/dom action=click "#memory_force_summarize"` (main API)
- 🎨 Freestyle → `/sd {{input}}` (unchanged)

**Root cause of the "DeepSeek can't summarize / blank swipes" incidents (08-26, 08-28) = OpenRouter provider roulette, not DeepSeek.** Non-stream responses log `provider:` in the ST container log; the Summary word-salad came from **DeepInfra** (fp8, uptime ~76%), the blank swipes from **GMICloud**. Replay ×6 on DeepInfra with ST's exact params: 1 refusal, 3 blank (reasoning 4–7k tokens → `finish=length`), 2 OK. Native endpoints (Alibaba, DeepSeek, StreamLake) were clean every time and are the cheapest ($0.58–0.66/M prompt vs $1.30–1.45).

**Fix (live `oai_settings` + preset Default + preset ImageGen — preset trap):**
- `openrouter_providers: ["StreamLake"]`, `openrouter_allow_fallbacks: false` — **a single provider, on purpose.** Multi-provider order pins DO NOT survive a page load (2026-08-30): `openai.js` runs `$('#openrouter_providers_chat').trigger('change')` on settings load, and the handler stores `$(this).val()` — the selected options in DOM (alphabetical) order — then autosaves. So `["StreamLake","DeepSeek"]` silently becomes `["DeepSeek","StreamLake"]` after every reload (log showed `order: [ 'DeepSeek', 'StreamLake' ]` → 3 empty swipes in 0.6–3 s). Fallbacks off because every other provider has a failure mode that looks like success (DeepSeek: empty 200; Alibaba: mid-stream moderation; DeepInfra/GMICloud: salad/blank) — a StreamLake outage should surface as an error toast, not a silent swap. Verify what is actually sent: `podman logs --since 5m home-sillytavern | grep -A2 'provider: {'`.
- **Alibaba dropped (2026-08-28, same night):** it runs output content moderation — an explicit RP stream dies mid-reply with `finish_reason: "error"` / `Upstream error from Alibaba: Output data may contain inappropriate content.` (HTTP 502 in the SSE, shown as an ST error toast). Intermittent (1 of 3 replays), and `allow_fallbacks` cannot rescue a stream that already started. DeepSeek + StreamLake finished the same prompt every time. Alibaba is fine for SFW/non-stream jobs only — never in the RP pin.
- **DeepSeek native also filters, but silently (2026-08-28, Guided Impersonate ×2 "no result"):** on a full 21k-token explicit context it returns `finish_reason: stop`, **empty content, no usage/cost** in ~2.5s — a successful-looking response, so `allow_fallbacks` never triggers and ST shows nothing. Replay of the exact request: DeepSeek 0/3 (all empty), StreamLake 3/3 (2.8k chars). Short explicit prompts passed on DeepSeek, so the filter is context/content-dependent. Hence StreamLake is first; DeepSeek is the fallback for outages only. Symptom = "Streaming request finished" 2–3 s after start, empty swipe.
- `openrouter_quantizations: []` — **the pin is silently useless while this is non-empty**: ST sends `provider.quantizations: [fp8, fp16, bf16]`, the native endpoints report quant `unknown`, get filtered out, and the request falls back to GMICloud/DeepInfra anyway.
- `power_user.prefer_character_prompt = true` → a card's `system_prompt` overrides the preset Main Prompt, so ImageGen's extractor instruction lives in custom prompt `imagegen_override` (system, injection depth 0) which cards cannot override. Without it DeepSeek narrated the scene instead of returning tags.
- Memory prompt says "integrate prior summary" → a salad summary left in the box poisons the next run. Clear the Current summary box before re-summarizing.

**Backups:** `settings.json.bak-2026-08-28-magnum-removal`, `OpenAI Settings/Default.json.bak-2026-08-28`. Supersedes the "GIỮ DUAL" verdict of 2026-05-05 and the "Magnum non-negotiable for summary" rule in 5.33.

### 5.45 Direction entries are menus, not scripts — and the Author's Note outlives its chat (2026-08-30)

**Symptom:** Arc 3 (Naoko) — the narrator ran the arc on its own for four consecutive turns while Hải sent empty turns; every beat landed in order, none of his turns bent anything.

**Cause (three layers, all verified):** (1) `/st-arc-plan` wrote a 518-word `constant` Direction entry at `order: 110` with eight numbered "beats to reach, in order" and a "CENTRE OF THE ARC — give it room" — injected every turn, it is a script, and nothing told the model that the user's turn outranks a beat. (2) The persona was oblivious-by-design and the guide character "tells, never asks", so the player was the only party without a lever. (3) An empty send appends NO user message (`send_if_empty` is `''`), so the model simply continues after its own message — with a beat sheet in context that means "next beat".

**Fix:** Direction template is now Destination · Forks (situations the persona decides, consequences the narrator owns) · Menu (any two reach the destination; a beat the player invents counts; unreached items are not owed) · Guards (N-GUARD yes-and if forced / H-LIMIT refuse), **≤ 120 words, order 100**. The card's `system_prompt` carries the voice fence (never write {{user}}'s speech, decisions, excuses or self-verdicts), the door rule (end every message on something unused), and the empty-turn rule phrased as "if the last message is your own". `audit-config.py` flags any Direction >120 words or containing "beats to reach / centre of the arc / give it room".

**Second gotcha found the same day:** `extension_settings.note.default` still carried `[Style: {{char}} addresses Helena as "you" …]` from May — injected at depth 2 on EVERY request of every new chat, directly under the card's depth prompt, contradicting the third-person narrator contract. Per-chat `chat_metadata.note_prompt` overrides it in old chats. Cleared; `st-sim.py build` shows the Author's Note as its own line so it can't hide again.

**Tooling:** `scripts/st-sim.py` (in `.claude/skills/st-arc-plan/`) rebuilds the exact OpenRouter body ST sends (validated 13/14 messages byte-identical against a logged request) and runs hypothetical player turns (`data/sim-scenarios.json` S1–S8) so Opus judges can score the narrator before a chapter is played. Guided Impersonate is `/impersonate <promptImpersonate1st>` on top of the global `oai_settings.impersonation_prompt` — neither knew the persona; `/st-persona --voice` now writes both plus the Guided Response/Continue wrappers.


**Third gotcha, same day (found by Hải in the persona panel):** the persona lorebook has TWO fields. ST injects from the GLOBAL `power_user.persona_description_lorebook` (`world-info.js` `getPersonaLorebook`); `persona_descriptions[avatar].lorebook` is only copied into it when the persona is picked in the UI dropdown (`personas.js` `loadPersona`). `/st-persona` set `user_avatar` via MCP → the global field stayed "Naoko" → every turn would have injected Naoko's Established State (~1.3k tok about a different woman) and skipped Mizuho's Direction. Fixed in `/st-persona`, `audit-config.py` (mismatch = FLAG) and `st-sim.py` (mirrors the global field, warns on mismatch).

**Sim gate results, Chapter 1 (2026-08-30, DeepSeek v4-pro via StreamLake, 3 rounds):** round 1 66/72 rules, round 2 45/54, round 3 35/36. What wording FIXED: (1) free-indirect self-verdicts ("She is fine.") — banned by naming the shapes incl. tense/hedge variants ("she would later put it down to", "everything she would call", "maybe X maybe Y"); (2) narrator re-placing the persona in a posture she left to land a planned beat — fixed by "{{user}} owns her position and state… move the beat to where she is, or let it wait" + "finished objects stay finished"; (3) the founding landing identically regardless of her turn — fixed by "arrivals are not owed to any single message… the outcome must visibly depend on what she did" (r2+: she leaves → nothing founds; she cuts to morning → delayed/displaced; she stays → in-sump); (4) default doors (tea/kettle/hatch 8/8, then the old man 3/6) — fixed by "never a door from the last three messages, never the same person twice"; (5) empty turn opening new body contact — fixed by "the beat belongs to the world or another person; her body registers duration only"; (6) an anal-canon breach (founding routed through the vagina in a limit probe) — fixed by an explicit ANATOMY CANON clause. STABLE model tendency wording only dampens (swipe when you see it): opening a turn by restating an image/prop from the previous message, and stacking 2–3 body sensations in one sexual beat. Held from round 1 without fixes: no second person, no Mizuho dialogue, insect never speaks, limits refused in-fiction, S4 new NPC/place and S5 time cut accepted whole.
### 5.46 `merge-attributes` supersedes the PNG-patch procedure while ST is running (2026-08-30)

**What changed:** ST's own character API is JSON and cache-aware, so the stop-ST → patch `chara`+`ccv3` tEXt → rewrite `_cache/characters/<sha>` → delete thumbnail dance (5.34–5.36) is only a fallback for when the container is down. The st-mcp server now wraps it: `st_create_character(name, fields)` → `POST /api/characters/create` (flat fields; `extensions` serialised to a JSON string; **`world` forced to `""`** because a non-empty value embeds a `character_book` copy that ST never injects but doubles the PNG); `st_merge_character(avatar, patch)` → `POST /api/characters/merge-attributes` (`deepMerge`, validator, then `writeCharacterData` = PNG + memory/disk cache in one write; ST invalidates the thumbnail itself); `st_delete_character(avatar, delete_chats)` → `POST /api/characters/delete`.

**The trap that survives:** `deepMerge` does NOT mirror V1↔V2. A patch that sets only `data.description` leaves top-level `description` stale — exactly the 5.35 symptom, now reachable through the API. Send both copies for description / personality / scenario / first_mes / mes_example. Arrays (`alternate_greetings`, `tags`) replace wholesale; the sentinel value `"__@@UNSET@@__"` deletes a key (e.g. strip an embedded `data.character_book`). Link a lorebook *after* create with `st_merge_character(avatar, {"data": {"extensions": {"world": "<Name>"}}})`.

**Where it is used:** `/st-cook` (card creation), `/st-setup --adv` Step D, `/st-arc-plan --openers-to-card`. Verified 2026-08-30 on a throwaway card: create → both mirrors present → merge changes both + `data.extensions.world` → delete removes PNG + chats dir, all without a container restart.

### 5.47 A persona switch has THREE settings fields — and an open ST tab clobbers every MCP settings write (2026-08-31, first real `/st-cook`)

**Symptom 1:** Mizuho active (avatar, description, lorebook all correct) but every user message in the chat is labelled **Naoko**. **Cause:** the name printed on user messages is `name1`, loaded from top-level `settings.username` (`public/script.js` ~7871). Only the persona dropdown's `setUserName()` (`personas.js` ~904) updates it; activating a persona through MCP (`user_avatar` + `power_user.persona_description_lorebook`, gotcha 5.45's two fields) leaves `username` on the previous persona. **Fix:** every MCP persona switch writes `username` too — `/st-persona` activation, `/st-cook`, `--close`; `audit-config.py` FLAGs `username != personas[user_avatar]`.

**Symptom 2:** mid-cook, the new persona, the voice contract and `character_prompts[<card>]` vanished from `settings.json` (00:17:57) while the card PNG, worlds and avatar stayed. **Cause:** the ST browser client keeps the entire settings tree in memory and POSTs it back whole on almost any UI event (`saveSettingsDebounced`); it never re-reads the server copy until reload. A tab opened *before* the MCP writes overwrites them the moment it is touched (it is not `beforeunload` — that handler only aborts streaming). **Rule:** close the ST tab (or reload it and don't touch it) before any skill that writes settings; the write-then-audit gate at the end of `/st-cook` is what catches it; re-apply from `_scripts/<slug>/rendered/` if bitten. Files under `data/` written by the server (cards via merge-attributes, worlds, avatars) are not affected.

## 6. Production Tag Templates

### Solo character emotion close-up (832×1216)
```
masterpiece, best quality, newest, absurdres, highres,
1girl, solo, close-up, face_focus,
(milf, mom_(mature), mature_female, housewife:1.4), 35yo, japanese_woman, plump, fair_skin, long_black_hair, black_hair,
[EMOTION TAGS HERE: gentle_smile / shocked_expression / blissed_out / etc.],
[SCENE/CONTEXT TAGS],
soft_lighting, bokeh_background, atmospheric, depth_of_field
```

### 2-char yuri intimate (1024×1024)
```
masterpiece, best quality, newest, absurdres, highres,
2girls, yuri, intimate_kiss, embracing, faces_pressed_together,
(milf, mom_(mature), housewife:1.5), 35yo, plump, voluptuous, large_breasts, black_hair,
(adult_woman_partner, twenty_something, mature_adult:1.3), slimmer_than_naoko, NOT_schoolgirl,
both_topless, breasts_pressed_together, saliva_trail, drool_strings, parted_lips_in_kiss,
half_lidded_eyes, deep_blush, ecstatic_expression, blissed_out_both,
warm_lighting, bokeh_background, intimate_framing
```

### Hetero oral — side view (1024×1024) — CLEANEST
```
masterpiece, best quality, newest, absurdres, highres,
1girl, 1boy, hetero, fellatio, blowjob, oral, side_view, three_quarters_view,
(milf, mom_(mature), housewife:1.5), 35yo, plump, large_breasts, long_black_hair, black_hair, kneeling, on_knees,
(penis_in_mouth:1.3), sucking, deepthroat, mouth_full, cheek_bulge,
(saliva_strings:1.2), drool, intimate_act,
half_lidded_eyes, deep_blush, ecstatic_expression, blissed_out, eyes_closed_in_pleasure,
dim_bedroom, warm_lighting, bokeh_background
```

### Hetero oral — anticipation/aftermath (1024×1024)
```
masterpiece, best quality, newest, absurdres, highres,
1girl, 1boy, hetero, pov, oral_aftermath, after_blowjob, intimate_close_up,
(milf, mom_(mature), housewife:1.5), 35yo, plump_face, voluptuous, large_breasts, long_black_hair, black_hair,
(licking_lips:1.3), tongue_out_seductively, sensual_smile, satisfied_expression,
(penis_near_face:1.2), held_penis,
(looking_up_at_viewer:1.4), half_lidded_eyes, deep_blush, lustful_expression, blissed_out,
(saliva_dripping:1.2), drool_on_chin,
dim_bedroom, warm_lighting, bokeh_background
```

### Solo masturbation (832×1216)
```
masterpiece, best quality, newest, absurdres, highres,
1girl, solo, solo_focus, masturbation, female_masturbation,
(milf, mom_(mature), housewife:1.5), 35yo, plump, voluptuous, huge_breasts, black_hair,
nude, lying_on_bed, on_back, legs_spread, (hand_between_legs:1.4), fingering, masturbating,
(blissed_out:1.4), eyes_half_closed, parted_lips, deep_blush, ahegao_partial, drool, intoxicated,
bedroom_setting, soft_sheets, warm_lighting, bokeh_background
```

### Parasite intimate (oral, 1024×1024)
```
masterpiece, best quality, newest, absurdres, highres,
1girl, solo, extreme_close_up, face_close_up,
(milf, mom_(mature), housewife:1.4), 35yo, japanese_woman, plump_face, fair_skin, long_black_hair, black_hair,
(small_pink_slug:1.6), (slug_on_lips:1.5), (creature_on_mouth:1.5), tiny_pink_creature, antennae, glossy_pink_creature, slimy_trail_on_lips,
(blissed_out:1.4), half_lidded_eyes, drooling, parted_lips, deep_blush, ecstatic_expression, intoxicated,
warm_lighting, bokeh_background, sensual_atmosphere
```

### Multi-char emotion via chibi (1152×896)
```
masterpiece, best quality, newest, absurdres, highres,
3girls, encounter_scene, dramatic_moment, intimate_framing, emotional_intensity,
(MAIN CHAR: milf mom_(mature) housewife:1.4) [+ scene-specific tags],
(another_mature_woman:1.2) [or implied OTS POV via foreground_arm_visible],
(schoolgirl_chibi_reaction:1.2), tiny_chibi, witness_face, shocked_chibi, in_corner_of_frame, super_deformed_witness,
bokeh_background, blurred_environment, defocused, dramatic_lighting, cinematic
```

---

## 7. Universal Negative Prompt Prefix

```
lowres, worst quality, bad anatomy, text, watermark, signature, speech_bubble, dialogue, caption, subtitle,
comic, comic_panel, panels, multi_panel, split_panel, frame_borders, manga_panel, panel_borders, multi_frame_layout,
deformed_face, mutated_hands, fused_fingers, fused_characters, extra_limbs, extra_fingers,
schoolgirl, school_uniform, sailor_uniform, serafuku, teenager, child, young_girl, slim, skinny, flat_chest,
identical_faces, twins, 3girls, 4girls, multiple_extra_characters, crowd,
pink_skin, pink_body, body_color_change
```

For SFW-only scenes add: `nsfw, nude, explicit, exposed_breasts, sex, genitalia`

For NSFW scenes drop those NSFW tags from negative.

For body horror/parasite scenes drop `pink_skin, pink_body` if you WANT body color change.

---

## 8. Mode 4 Template (for Magnum to follow)

When ST QR triggers `/sd last`, Magnum reads this template + chat last message and outputs booru tags. Production version: **v8.2** (2026-05-05, 2144 chars — stripped to hard rules only). Lives in `settings.json:extension_settings.sd.prompts["4"]` (gitignored — private RP config).

**Source context injection:** Template includes `{{summary}}` macro at top → injects current chat summary (from Summarize extension, manually maintained via QR Summary button — see [gotcha 5.33](#533-stscript-path-silently-breaks-summarize--use-dom-actionclick-workaround-verified-2026-05-05)). Combined with last message, gives Magnum scene context + recent state.

**5 hard rules (everything else is Magnum's judgment from booru training):**

**1. REQUIRED first tag — subject count** (composition primer):
- Solo character (parasite-inside doesn't count) → `1girl, solo`
- Female + 1 male partner → `1girl, 1boy`
- Female + parasite-inside + male partner → `1girl, 1boy` (creature ≠ subject)
- Female + 1 female partner → `2girls`

**2. POV DEDUP RULE** (load-bearing — see [gotcha 5.32](#532-povview-tag-stacking--split-composition-verified-2026-05-05)):
- External view: pick ONE → close-up | wide_shot | pov | side_view | from_below | from_above | dynamic_angle | foreshortening
- Internal view: pick ONE (optional) → x-ray | internal_view | cross-section
- NEVER stack 3+ view tags. NEVER stack `cross_section + internal_view + x-ray + close-up` — guaranteed split composition.

**3. SKIP identity tags** (auto-injected via char_prompts):
- Don't echo: japanese, mature_female, milf, mom_(mature), housewife, plump, voluptuous, large_breasts, fair_skin, long_black_hair, black_hair, brown_eyes
- Don't echo persona default outfit unless scene specifies different clothing

**4. MINIMUM 15 tags** (up to 30 if scene complex). Cover what's visually present: action, pose, clothing state, body fluids, expression, setting, lighting.

**5. ALWAYS END WITH:** `(((masterpiece,best quality,newest,absurdres,highres)))` — quality reinforcement at tail (prompt_prefix already injects at start = 2x emphasis).

**Format:** ONE continuous comma-separated line. No section labels in output. Weight syntax allowed: `(tag:1.2)`, `[tag]`, `[[tag]]`, `((tag))`, escape parens for franchise names. NEVER output: text, speech_bubble, dialogue, comic_panel, panels, prose.

**Correct examples:**

```
2girls, yuri, intimate_kiss, embracing, faces_pressed_together, both_topless, drool, deep_blush, ecstatic, warm_lighting, bokeh_background, (((masterpiece,best quality,newest,absurdres,highres)))

1girl, 1boy, hetero, pov, fellatio, tongue_out, licking, looking_up_at_viewer, blissed_out, deep_blush, dim_bedroom, warm_lighting, (((masterpiece,best quality,newest,absurdres,highres)))

1girl, solo, parasite_in_pussy, internal_view, cervix, lying_on_back, swollen_belly, blissed_out, bedroom, warm_lighting, (((masterpiece,best quality,newest,absurdres,highres)))
```

**Wrong:**
```
"Naoko was kissing the woman..."           ← narrative prose
1girl, schoolgirl, sailor_uniform          ← {{user}} is mature, schoolgirl bias
1girl, solo, vaginal_sex, x-ray, cross_section, internal_view, close-up   ← POV stack → split comp (gotcha 5.32)
```

**Iteration history:**
- v1-v5 (2026-05-05): over-long/example-heavy templates produced narrative prose, copy-verbatim outputs, persona echoes
- v6: added explicit subject count requirement (fixed 2-girls bug)
- v7: added action tag gender-prior consistency rule + POV dedup (over-engineered consistency layer)
- v7.1: softened — dropped consistency-enforcement (action tag bias proven downstream of POV stack), kept vocabulary buckets + POV dedup
- v8: added `{{summary}}` macro + 8-section structure + mood-aware artist pool (LLM picks)
- v8.1: dropped char name slot + artist pool (artist mix LLM-pick produced inconsistent style cross images; aesthetic dial-in not worth the noise — NoobAI baseline coherent enough)
- **v8.2 (current):** stripped to 5 hard rules. Removed vocabulary buckets, section ordering, mood mapping. Magnum picks tags from booru training. Result: 4258 → 2144 chars, predictable output, simpler debug surface

## 8.1. Summary Workflow (manual via QR button)

Mode 4 template injects `{{summary}}` macro — for it to be useful, the chat summary must be regenerated via the QR button (main DeepSeek profile, native providers pinned — gotcha 5.44) when scene shifts. Auto-trigger DISABLED (`promptInterval: 0`) because auto-fire uses whatever connection is active at trigger moment → likely DeepSeek → ignores summary directive → produces continuation prose instead of structured recap.

**Manual workflow:** Click `[📝 Summary]` button in ImageGen QR set. STscript chain:

```
/dom action=click "#memory_force_summarize"
```

**Why `/dom action=click` instead of `/summarize`:** /summarize via slash command path silently fails due to STscript executor's `is_send_press` lock — see [gotcha 5.33](#533-stscript-path-silently-breaks-summarize--use-dom-actionclick-workaround-verified-2026-05-05). DOM click on the panel button bypasses the lock entirely.

**Summary prompt** (in `extension_settings.memory.prompt`):
```
<task>
STOP. END OF ROLEPLAY. NEW TASK BEGINS HERE.
You are no longer {{char}} or any character. You are a structured summarizer.
Output a recap covering:
1. Setting · 2. Plot events · 3. Character state · 4. World facts · 5. Open threads
STRICT: Third-person past tense. NO dialogue. NO prose continuation. Maximum {{words}} words.
</task>
```

**Verified output (Magnum + RAW_BLOCKING, 2026-05-05):**
- ✅ 3rd person past tense
- ✅ 5 structured sections
- ✅ ~150-200 words (under limit)
- ✅ No verbatim dialogue, no RP voice

**Settings stack (all required for compliant summary):**
| Setting | Value | Why |
|---|---|---|
| `prompt_builder` | `1` (RAW_BLOCKING) | Bypass prompt manager — no WI/persona injection that biases Magnum back into RP |
| `SkipWIAN` | `True` | Belt-and-suspenders alongside RAW_BLOCKING |
| `promptInterval` | `0` | Disable auto-trigger (would fire on active connection = often DeepSeek = bad output) |
| `source` | `main` | Use active connection — `/profile` switch via QR controls which |
| `promptWords` | `700` | Was 500 → 900 → 700 (2026-08-29). The summary no longer feeds lore-baking, so it is sized for its only remaining job: in-chat injection at depth 2 on over-long chats |

**Prompt revision 2026-08-29 — repurposed for continuation, not retelling** (`extension_settings.memory.prompt`, live). `/st-arc-save` now reads the chat `.jsonl` directly, so the Summarize extension is out of the lore flow and is only a safety net when a single chat outgrows context. The prompt is rewritten for that job: **recency gradient** (§1 *Now* = exact state at the last message, present tense · §2 *Recent beats* = last ~10 messages one line each · §3 *Earlier* = 1–2 sentences per scene), then continuity tables (§4 *Cast* incl. every NPC with location · §5 *Knowledge* = who knows / is unaware of what · §6 *Standing facts* = rules, promises, transformations, running excuses). Rules: facts from this chat only (sheets + lore are already in context — RAW_BLOCKING hides WI from the summarizer, so it must not re-derive origins), "not shown" for anything unclear, ≤3 verbatim lines that act as standing rules, merge a prior summary by compressing its old material further while keeping Cast/Knowledge/Standing. Do NOT press Summarize now on a chat you will keep playing unless it is actually long — the injected block costs ~1k tok/turn and can drift from the baked Established State.

---

## 9. Char Prompts Setup

`extension_settings.sd.character_prompts` (in `settings.json`):

### For Parasite RP (host = Naoko):
```python
sd['character_prompts']['Parasite'] = (
    "1girl, japanese, mature_female, milf, mom_(mature), housewife, "
    "35yo, plump, voluptuous, large_breasts, fair_skin, "
    "long_black_hair, black_hair"
)
sd['character_negative_prompts']['Parasite'] = (
    "creature, monster, slug, non-human, animal, schoolgirl, teenager, slim"
)
```

For Mode 0 (creature portrait of Parasite itself), use Mode FREE with explicit creature tags instead.

### For "Your Oblivious Mother" (already correct):
```python
sd['character_prompts']['Your Oblivious Mother'] = (
    "1girl, japanese, mature_female, plump, voluptuous, large_breasts, "
    "curvy_figure, fair_skin, brown_eyes, black_hair, medium_hair"
)
```

**Critical gotcha (already documented):** ST's `getCharaFilename()` strips extension — key MUST be `"Parasite"` not `"Parasite.png"`.

---

## 10. Quick Reference — When Things Go Wrong

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Naoko looks like schoolgirl | Missing mature lock-in or schoolgirl negative | Apply Section 3 tags |
| Creature missing entirely | Negative prompt over-block | Drop `humanoid, monster, large_creature` from negative |
| Pink/colored body | Creature color bleed | Add `pink_skin, pink_body, parasite_fusion` to negative |
| Back view when wanted front | Negative direction unreliable | Use positive `(front_view:1.4), looking_at_viewer` |
| 2 Naokos rendered | Wide aspect (1344+) | Switch to 1024×1024 or 1152×896 |
| Split composition / inset panels / duplicate subject | POV/view tag stacking (3+) | Pick ONE primary view — see gotcha 5.32 |
| "Extra male" appears despite `solo` | Cascade from POV stack creating split → inset filled with hetero action | Fix POV dedup, not action tag — gotcha 5.32 |
| Faces merged in 2-char | Spatial separation issue | Use intimate physical merge (kiss/embrace) |
| Schoolgirl steals attributes | Multi-char with similar gender | Add `slimmer_than_naoko, NOT_schoolgirl` to partner tags |
| Hand anatomy off in masturbation | ADetailer face only | Accept or set up hand_yolov8n.pt second pass |
| Mouth/oral anatomy broken in POV blowjob | Extreme close-up active oral exceeds ADetailer | Use side view, anticipation, or aftermath framing instead |
| Text/speech bubbles in output | Negative missing | Add `text, speech_bubble, dialogue, caption` to negative |
| Object on wrong body part | SDXL placement limit | Use spatial negative steering or img2img inpaint |
| Summary textarea stays empty after `/summarize` | STscript executor locks `is_send_press` → /summarize times out silent | Use `/dom action=click "#memory_force_summarize"` (LALib) — see gotcha 5.33 |
| Summary returns RP prose / word-salad / blank | OpenRouter routed to a bad provider (DeepInfra, GMICloud) — `openrouter_quantizations` non-empty makes the provider pin useless | `openrouter_quantizations: []` + pin `["StreamLake"]` ONLY, `allow_fallbacks: false` (multi-provider order re-sorts alphabetically on page load → DeepSeek first → silent EMPTY; Alibaba moderates NSFW output mid-stream) in live + every preset; clear the summary box before retry — gotcha 5.44 |
| Summary contaminated by persona/WI context | Default `prompt_builder` injects prompt manager content | Set `extension_settings.memory.prompt_builder: 1` (RAW_BLOCKING) |

---

## 11. Tools Status

| Tool | State | Usage |
|------|-------|-------|
| ADetailer (face_yolov8n.pt) | Installed, ST auto-trigger | All gens benefit |
| ADetailer hand_yolov8n.pt | Available, not configured | Defer — chain manually if needed |
| Forge Couple | Installed, NoobAI incompatible | Don't use, leave installed |
| ControlNet | Loaded, models not downloaded | Defer — VRAM tight |
| img2img inpaint | Available via Forge UI | Manual workflow for precise placement |

---

## 12. Trigger Conditions to Revisit

- If hand anatomy becomes blocking issue → set up hand_yolov8n.pt second pass
- If FLUX models become preferred → migrate to ComfyUI (ST workflow rewrite needed)
- If multi-char distinct poses become critical → ControlNet OpenPose setup
- If dataset bias still strong after lock-in → train custom Naoko LoRA
