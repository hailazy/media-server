# «CAMPAIGN_TITLE»
Series bible · «PROTAGONIST_NAME» × «CREATURE_NOUN» · «CHAPTER_COUNT» chapter(s) · written «DATE» (recipe: `_scripts/«SLUG»/recipe.json`)

This is the SHAPE of the story, not prose to paste. Chapter 1's paragraph becomes the ≤120-word Direction entry (`/st-arc-plan --from-script`) plus three openers; later chapters stay coarse until the one before them has been played. One-shot mode collapses §6 to a single chapter block and skips §7's "next chapter" framing — the ending sits inside that one chapter.

## 1. Protagonist — «PROTAGONIST_NAME», «PROTAGONIST_AGE»

«PROTAGONIST_ONE_LINE» — setting, household, work, the two things she is proud of. **Wound:** «WOUND» (the belief the corruption exists to disprove). Name every other person who appears on page with a one-line role; note who never gets interiority and who is a door, not a rescue.

## 2. The creature — "«CREATURE_NOUN»" (label never on page)

An ordinary, undocumented «CREATURE_KIND» written with the flatness of nature writing — no supernatural framing, no institution hunting it, nobody ever explains a word of it, no voice. List its life-stages/forms, one new form per chapter if the engine supports it: «CREATURE_FORMS». Host rule(s) never spoken aloud by any character: «HOST_RULES». Capabilities the host gains, one per chapter, cumulative: «CAPABILITIES_BY_CHAPTER».

## 3. The engine — «ENGINE» (self-blame edition)

The reader knows what it is; the protagonist concludes it is her own nature. State the axis (or axes) that must move monotonically chapter to chapter — never score lower than the last: «AXES». One belief destroyed per chapter: «BELIEFS_DESTROYED». Her self-verdict per chapter (Hải's lines, never the narrator's): «SELF_VERDICTS_BY_CHAPTER».

## 4. Six structural rules (override anything else)

1. **Steering, not fence.** The narrator writes the protagonist whole — body, half-thoughts, speech — as far as the creature has earned, ladder-gated inside the scene; her self-deception is narrated on the page, not reserved. {{user}} steers: anything {{user}} writes is canon and is never walked back, and marked forks are held open for {{user}}.
2. **Menu, not beat sheet.** Each chapter has ONE obligatory arrival (narrator-owned) plus candidate beats; any two or three reach the destination; a beat {{user}} invents counts; retire unreached items rather than steer toward them.
3. **Decline costs shape, not nothing.** No cure — but the creature never re-takes a decision made while lucid; refusal buys a slower, uglier, differently shaped chapter, never the same one repeated.
4. **Guards are addressed.** N-GUARD = narrator may not initiate a listed beat; if {{user}} forces it, yes-and, don't block, don't punish. H-LIMIT = refuse regardless of source: «LIMITS_LIST».
5. **The mirror is a posture, not a building.** The closing image is a posture, staged wherever the playthrough left her holding it — never a fixed room or prop the player might not have reached.
6. **Forks pose situations, not menus.** The message that raises a fork ends on the pressure, never on an implication; consequences live in a separate after-she-chooses block.

**Tempo:** «TEMPO_LINE» — open each chapter inside the situation, one set-piece within the first third, ~«MSGS_PER_CHAPTER» messages per chapter; each reply is one manga page ending on the page-turn (something beginning), and quiet pages between set-pieces are content, not filler.

## 5. Opening image

«OPENING_IMAGE» — place, time, what she is doing alone, what she notices and dismisses, who is nearby but not watching. [HẢI WRITES her first line.] Nobody pours her tea; nobody is coming to teach her anything.

## 6. Chapters

**Ch «N» — "«CHAPTER_TITLE»" (~«MSGS_PER_CHAPTER» msgs).** Axis: «CHAPTER_AXIS»; belief(s) destroyed: «CHAPTER_BELIEFS». Obligatory arrival: «OBLIGATORY_ARRIVAL». Candidates: «CANDIDATE_BEATS». Forks: «FORKS». Capability gained: «CAPABILITY». Cover words (hers): «COVER_WORDS». Exit: «EXIT». N-GUARD: «N_GUARD». H-LIMIT: «H_LIMIT».

*(Repeat this block once per chapter, in order. One-shot mode = exactly one block, and its Exit doubles as §7's ending.)*

## 7. Ending

«ENDING_SHAPE» — what is granted, what is lost, what the world looks like once the story stops, what closes the loop from §5's opening image. Two closing images if the arc runs multi-chapter; one if one-shot.

## 8. Novelty ledger (no row may repeat)

| Ch | creature form | orifice | partner config | setting | register | dissociation |
|---|---|---|---|---|---|---|
| «N» | «…» | «…» | «…» | «…» | «…» | «…» |

*(One row per chapter, filled in as each chapter is played — not authored ahead of time. Chapter 1's row starts empty: "(none yet — Chapter 1 not played)", matching `lore/novelty-ledger.tmpl`.)*

## 9. Prior-play exclusions

Configurations already used in earlier campaigns that this one must not repeat (pulled from `_scripts/ledger.json` at Phase 0 recall): «PRIOR_PLAY_EXCLUSIONS».
