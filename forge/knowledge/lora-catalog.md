# LoRA Catalog — Forge / NoobAI EPS 1.1 stack

Maps scene keywords → LoRA injection. Skill (Phase 2.5) checks scene tags against catalog, appends matching `<lora:name:weight>` syntax + trigger words.

**Lookup logic**: scene tag is "match" if the scene/chat context contains ANY of the keywords (case-insensitive substring or token match). Multiple matches → multiple LoRAs (max 4 simultaneously to avoid prompt dilution).

**Weight ranges**:
- Quality LoRAs: 0.4–0.6 (always-on, low impact)
- Concept LoRAs: 0.7–0.9 (scene-specific). **Default 0.8**; push **0.85–0.9 for fetish hero/close-up shots** where the concept IS the subject.
- Style LoRAs: 0.3–0.7 (subtle to medium)

---

## Max-Feel Intensity (fetish hero shots) — the recipe that lands

When a scene is ABOUT the fetish (the kink is the focal point, not background), crank the *feel*.
Verified to reproduce the lewd/depraved taste of the reference set:

1. **Concept LoRA weight → 0.85–0.9** (vs the table defaults below). The fetish LoRAs are anime-trained,
   so on the NoobAI base they express hardest — don't be shy.
2. **WET, not bloody** (Hải taste: prefers wet/slimy, no gore): pile on `soaking wet, glistening,
   slimy, mucus, slick, juicy, slime, transparent fluid, dripping, cum, cum overflow, saliva, drooling, sweat`.
   **NEVER emit `blood, gore, bleeding`** — Hải doesn't want gore; those live in the global negative.
3. **Vivid creatures** (larvae / eggs / parasites — must look ALIVE, not fake/CG): `detailed, segmented,
   plump, glossy, pale yellow maggots / cream grubs / mealworms, wriggling, writhing, squirming, many`.
   Avoid the smooth-uniform "fake egg" look + color drift (don't let larvae go green — state the color).
4. **Density tags** — for tentacles/parasites: `multiple tentacles, wrapped in tentacles, restrained,
   covered in <X>`. More coverage = more intense.
5. **Cinematic mood** (works fully in anime, no realism needed): `cinematic lighting, dramatic lighting,
   dramatic shadow, dim lighting, teal theme / <scene color>, depth of field, close-up`.
6. **Dynamic lewd pose** — NoobAI nails these natively: `bent over, from behind, ass up, arched back,
   spread legs, presenting`.

**`Oviposition_xray` x-ray inset gotcha**: at 0.85–0.9 this LoRA injects an x-ray cutaway INSET panel
(cross-section of the egg/larvae cluster). For a clean single-view (no inset): drop weight to ~0.75
AND add `x-ray, cross-section, multiple views, inset` to the negative.

See `prompt-template.md` → "Max-feel fetish" example.

---

## Always-On Quality (auto-include every gen)

| LoRA | Trigger words | Weight | Notes |
|------|--------------|--------|-------|
| `anima-preview-3-masterpieces-v5` | `masterpiece, very aesthetic` | 0.5 | Already in `prompt_prefix` — LoRA reinforces. ID #929497 |
| `AddMicroDetails_Illustrious_v6` | `addmicrodetails` | 0.4 | Universal detail boost. ID #1377820 |

**Always inject these 2 LoRAs at end of prompt** (before quality block):
```
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails
```

---

## Concept-Triggered (inject when scene matches)

### Parasite / Body Horror

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `parasite, infection, body_horror, takeover, transformation, corruption, eldritch, skin_change, changed` | `<lora:Parasite_horror_transformation_IL_port:0.8>` | `changed, horror, parasite, takeover, transformation, body horror, corruption` |

### Oviposition / Egg-laying

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `oviposition, egg_laying, ovipositor, egg, eggs, frog_eggs, insect_eggs, spider_eggs, alien_eggs` | `<lora:Oviposition_xray_illus-000040:0.8>` | `oviposition, frog eggs, insect eggs, spider eggs, silk, spiderweb, fish eggs, alien eggs` |
| _(stack with above for tentacle ovi):_ `tentacle_ovi, ovipositor_tentacle` | `<lora:oviposition_anima:0.8>` | `tentacle sex, oviposition, implanting eggs, transparent tentacles` |

### Tentacles (general)

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `tentacle, tentacles, tentacle_sex` | `<lora:oviposition_anima:0.8>` | `tentacle sex, transparent tentacles` |

### Monstergirl / MGE

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `monstergirl, monster_girl, mge, monster_girl_encyclopedia, slime_carrier, parasite_slime, dark_matter, barometz` | `<lora:MGE_SlimeCarrier_v4.1_IL:0.7>` | _(no required triggers — LoRA infers from concept tags)_ |

### Arachne / Spider Yuri

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `arachne, spider_girl, arachnesex, spider_yuri, web, spiderweb` | `<lora:Arache_sex_illus-000037:0.8>` | `purple arachne, arachnesex, interspecies, tentacle sex, monstergirl, restrained, spiderwebs, silk, yuri` |

### Bioluminescence / Iridescent Glow

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `bioluminescence, iridescent, glow, glowing, shimmer, rainbow_egg, glowing_egg, firefly, sea_slug, mermaid` | `<lora:noobai_epred_11_bioluminescence_v15:0.35>` | `bioluminescence, blue glow` (swap color per scene: `cyan glow`, `green glow`, `red glow`). Creator motimalu (same as #929497). ID #554006 |

### Slime Transformation / Sentient Onahole

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `slime_girl, translucent_body, onahole, personality_excretion, anal_birth, quadruple_amputee, torso_grab, sentient_onahole, slime_excretion` | `<lora:transformation_onahole_noobai:0.7>` | `slime girl, translucent body, slime excretion` (add `anal birth, torso grab, minigirl, carrying person` per scene). ID #246523 |

### Insects / Worms / Bugs — creature toolkit (added 2026-06-05)

Well-defined articulated creatures (segmentation, legs, antennae) — the "vivid not fake" look Hải wants
(creatures must look alive/detailed, not smooth/CG). **Behavior gotcha**: ALL of these render creatures as *surface/discrete
subjects* (on skin, floor, around body) — they do NOT densely pack a cavity on their own. For a
**cavity packed full** (anus/pussy stuffed): combine with `Oviposition_xray` @0.7–0.8 (it supplies the
stuffed-hole composition; the creature LoRA upgrades the egg-blobs into defined creatures). Best combo
found: **Ovi 0.8 + creature 0.7**. For a *truly* packed hole → inpaint the hole region with the creature LoRA @0.9.

| Trigger keywords (any) | LoRA | Add tags | Base | Notes |
|------------------------|------|----------|------|-------|
| `maggot, maggots, larvae, grub` | `<lora:Maggots_anima_v2:0.8>` | `maggot, segmented body, plump, glossy, pale yellow maggots, writhing` | Anima | Best-defined grubs. ID #2642042 |
| `worm, worms, infested, covered in worms, fate_crest` | `<lora:Crest_Worms2:0.85>` | `fate_crest_worms, heavily covered in worms, on skin, several, multiple, segmented worms` | Illustrious | Many small worms on skin/surface (infestation). ID #2062975 |
| `earthworm, realistic worm, segmented worm, worm coil` | `<lora:Earthworm_UHD_Pony:0.85>` | `1earthworm, brown dark realistic earthworm, segmented body, long earthworm coil` | Pony (transfers to NoobAI ✓) | Realistic brown segmented earthworms. ID #955127 |
| `giant worm, worm vore, monster worm, carnictis` | `<lora:WMV_IL_D4_v1:0.8>` | `giant worm, worm vore, worm coil, coiled, monster worm, carnictis` | Illustrious | Giant worm / coil / vore. ID #1911293 |
| `worm monster, small monster, monster crawling in` | `<lora:worm_tentacle_ill-10:0.8>` | `worm_tentacle_ill, creature, green monster, monster sex` | Illustrious | Small worm-monsters into orifice. ID #1044535 |
| `spider, spiders, arachnid` | `<lora:Spiders_anima_v15:0.8>` | `spider, many spiders` | Anima | Spiders. ID #716179 |
| `fly, flies, fly sex` | `<lora:Fly_illustrious:0.8>` | `flysex, fly, insect, swarm of flies` | Illustrious | Flies. ID #916569 |
| `cockroach, roach, radroach` | `<lora:cockroach_anima_v2:0.8>` | `cockroach, many cockroaches` | Anima | Roaches. ID #480476 |

All by Huevoasesino2 except Crest Worms (Grimtale), Earthworm (hex1c), Worm Monster Vore (magnoveradium),
worm tentacle monster (shiashibaK). Anima/Pony bases load on NoobAI (verified).

---

## Stacking Rules

1. **Max 4 LoRAs simultaneously** — beyond 4 dilutes prompt adherence + may exceed VRAM.
2. **Always-on quality (2)** + max 2 concept LoRAs.
3. **Compatible categories**: Parasite + Oviposition can stack (body horror with egg implant). Tentacle + Oviposition stack natural. Bioluminescence stacks with most (subtle @ 0.3-0.4).
4. **Conflicting**: Arachne + MGE Slime — pick one dominant theme per gen. Sentient Onahole biases toward armless/torso compositions — don't stack with Arachne or full-body scene tags.
5. **Order in prompt**: scene tags first → concept LoRAs → quality LoRAs → quality block.

## Output format example

For scene "naoko bị parasite kí sinh, tentacle ovi":
```
1girl, [identity baseline], indoors, bedroom, lying on bed, naked,
parasite, body horror, transformation, tentacle sex, oviposition, implanting eggs, transparent tentacles,
<lora:Parasite_horror_transformation_IL_port:0.8>, changed, horror, takeover, corruption,
<lora:oviposition_anima:0.8>, transparent tentacles,
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```

---

## Maintenance

When adding/removing LoRAs:
1. Place file ở `forge/data/forge/models/Lora/` (qua `/civitai-model download <id>`)
2. Update this file: add/remove section
3. Note trigger words from Civitai page (qua `mcp__civitai__get_model`)

Verify file presence: `ls /home/haint/Projects/home-server/forge/data/forge/models/Lora/*.safetensors`
