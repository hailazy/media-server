# Prompt Templates — Canonical Examples

Reference templates cho skill output. Skill copy structure, fill in specific tags theo scene context.

## Template 1: Standard scene (char + scene)

```
1girl, [identity baseline tags],
[location/setting], [time of day],
[action], [pose], looking at viewer,
[expression], [eye state], [mouth state],
[outfit / clothing state],
[lighting], [atmosphere], depth of field,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 2: Char close-up (face focus)

```
1girl, [identity baseline],
close-up, face focus,
[expression], [emotion], [eye contact],
[hair state], [skin detail],
[lighting], bokeh, [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 3: Background only (no char)

NO `1girl`/`1boy`. NO identity baseline.

```
[location/setting] [no humans],
[notable elements], [composition tags],
[lighting], [atmosphere], depth of field, bokeh,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 4: NSFW interaction (char + persona)

```
1girl, [char identity baseline],
[persona/{{user}} interaction context],
[scene location], [intimate setting],
[action / pose], [body interaction],
[expression], [reaction state],
[clothing state — usually undressed/disheveled],
[lighting], [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example (Parasite + Naoko)
```
1girl, japanese, mature_female, milf, plump, fair skin, long black hair,
parasite, slug, on body, intimate,
bedroom, dim light, night,
lying on back, parted thighs, body trembling,
flushed cheeks, half-closed eyes, mouth open, drooling,
disheveled clothing, naked breasts, exposed,
soft lamp light, sweat, body fluids,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 5: Multiple chars

```
2girls, [each char identity baseline],
[interaction tags: standing together, hugging, etc.],
[scene location],
[mutual action], [mutual expression],
[outfit per char if needed],
[lighting], [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 6: Max-feel fetish (hero shot)

Crank intensity when the kink is the focal point. Bump concept LoRA to **0.85–0.9**, pile on
fluid + density + cinematic vocab. See `lora-catalog.md` → "Max-Feel Intensity".

```
1girl, [identity baseline],
[scene/setting], [cinematic lighting], dramatic shadow, dim lighting,
[dynamic lewd pose: bent over, from behind, ass up, arched back],
[concept: multiple tentacles, wrapped in tentacles, tentacle sex, tentacle penetration],
excessive fluid, cum, cum overflow, saliva trail, drooling, dripping, wet, sweat,
rolling eyes, ahegao, open mouth, tongue out, blush,
[outfit / undressed state],
<lora:CONCEPT:0.9>, [concept add_tags],
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example (Tifa — hospital tentacle, validated)
```
1girl, tifa lockhart, long hair, dark brown hair, red eyes, large breasts,
hospital room, hospital bed, teal theme, cinematic lighting, dramatic shadow, dim lighting,
bent over, from behind, ass up, arched back, looking back,
multiple tentacles, wrapped in tentacles, tentacle sex, tentacle in mouth, deepthroat, tentacle penetration, restrained,
excessive fluid, cum, cum overflow, saliva trail, drooling, dripping, wet, sweat,
rolling eyes, ahegao, open mouth, tongue out, blush,
white crop top, black harness, black microskirt, black thighhighs, red gauntlet,
<lora:oviposition_anima:0.9>, tentacle sex, transparent tentacles,
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Extreme close-up variant (anatomy focus)
For tight close-ups on the penetration/insertion itself (cropped, no face):
```
[no 1girl face — crop tight], ass focus, close-up, from behind, presenting,
huge ass, thick thighs, anus, pussy, gaping,
multiple tentacles, thick tentacles, tentacle penetration, anal, double penetration, suction cups,
excessive fluid, cum overflow, cumdrip, slimy, mucus, dripping, soaking wet, glistening, juicy,
<lora:oviposition_anima:0.9>, tentacle sex,
<lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Oviposition / larvae example (vivid creatures, wet, no gore)
```
ass focus, close-up, from behind, presenting, spreading own ass, gaping anus, spread anus,
oviposition, insect larvae, pale yellow maggots, cream grubs, mealworms, plump larvae, segmented larvae,
detailed larvae, glossy larvae, wriggling, writhing, many larvae, larvae crawling on body,
soaking wet, glistening, slimy, mucus, dripping fluid, juicy,
<lora:Oviposition_xray_illus-000040:0.75>, oviposition, insect eggs,
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.5>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```
(Keep Oviposition_xray at ~0.75 in this skill's output — `/sd` Mode FREE carries no negative channel, so the `x-ray, cross-section` negative that would clean up the cutaway can't be attached here. That negative route only exists generating through Forge directly — see `/gen-fulfill`. Bump to 0.9 only there, if you WANT the cutaway.)

## Permanent Layer (auto-appended by ST — read live, never hardcode)

ST auto-applies, to EVERY gen for a character: global `prompt_prefix` + `negative_prompt`, plus that character's `extension_settings.sd.character_prompts[CharName]` (positive) and `character_negative_prompts[CharName]` (negative). These are read live via `mcp__st__st_get_settings(path=...)` in SKILL.md Phase 1 Step 3a (PERMANENT_LAYER) — never re-emit a tag already present there, and never hardcode this section's contents in a template, since it drifts every time `/st-setup` runs.

Standing rule: never emit gore tags (`blood, gore, bleeding`) — they're in the global negative and Hải wants wet, not bloody.

## Tag count guidelines

| Scene complexity | Tag count |
|------------------|-----------|
| Simple portrait | 12-18 tags |
| Standard scene | 18-25 tags |
| Complex action | 22-30 tags |
| Multi-char NSFW | 25-35 tags |

Below 12 → underspecified, output bland. Above 35 → diluted attention, detail blur.

## Common booru tag categories

### Subject count (FIRST)
`1girl`, `1boy`, `2girls`, `2boys`, `solo`, `multiple_girls`, `1girl, 1boy`

### Body framing
`upper body`, `lower body`, `cowboy shot`, `full body`, `face focus`, `cropped legs`

### POV (pick ONE max)
`close-up`, `wide shot`, `pov`, `side view`, `from below`, `from above`, `dynamic angle`, `foreshortening`

### Internal POV (optional, ONE max)
`x-ray`, `internal view`, `cross-section`

### Expression
`smile`, `light smile`, `smug`, `blush`, `flushed cheeks`, `tears`, `crying`, `angry`, `surprised`, `scared`, `confused`, `sad`, `embarrassed`

### Eye state
`eye contact`, `looking at viewer`, `half-closed eyes`, `closed eyes`, `wide eyes`, `glaring`, `looking down`, `looking away`

### Mouth state
`open mouth`, `parted lips`, `closed mouth`, `tongue out`, `drooling`, `biting lip`, `smiling`

### Fluids / intensity (NSFW — pile on for max-feel; Hải likes WET, not bloody)
`soaking wet`, `glistening`, `slimy`, `mucus`, `slick`, `juicy`, `slime`, `transparent fluid`, `excessive fluid`, `cum`, `cum overflow`, `cumdrip`, `saliva`, `saliva trail`, `drooling`, `dripping`, `wet`, `sweat`, `body fluids`
> **No gore**: never emit `blood, gore, bleeding` — they're in the global negative (Hải pref).

### Lewd pose / framing (NoobAI nails these natively)
`bent over`, `from behind`, `ass up`, `arched back`, `spread legs`, `presenting`, `ass focus`, `gaping`, `top-down bottom-up`

### Concept density (tentacle / parasite hero shots)
`multiple tentacles`, `thick tentacles`, `wrapped in tentacles`, `restrained`, `covered in <X>`, `tentacle penetration`, `double penetration`, `suction cups`

### Cinematic mood (works in anime — no realism needed)
`cinematic lighting`, `dramatic lighting`, `dramatic shadow`, `dim lighting`, `volumetric lighting`, `<scene> theme` (e.g. `teal theme`), `depth of field`

### Hair states
`hair over one eye`, `messy hair`, `bedhead`, `wet hair`, `hair down`, `ponytail`, `bun`

### Lighting
`soft lighting`, `cinematic lighting`, `rim lighting`, `backlighting`, `golden hour`, `blue hour`, `dappled sunlight`, `harsh light`, `dim light`, `candlelight`, `lamp light`

### Atmosphere
`depth of field`, `bokeh`, `light particles`, `light leaks`, `dust particles`, `ray tracing`, `volumetric lighting`, `god rays`

### Setting (Japanese contexts)
`japanese garden`, `traditional house`, `tatami room`, `shoji screen`, `bedroom`, `bathroom`, `kitchen`, `living room`, `genkan`, `engawa`

### Time
`morning`, `afternoon`, `evening`, `night`, `dusk`, `dawn`

### Quality block (LAST, always)
```
(((masterpiece,best quality,newest,absurdres,highres)))
```
