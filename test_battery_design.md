# DREADPIT TEST FIGHTER BATTERY
## Probe Fighters to Fill the Neural Network's Blind Spots

Generated from analysis of 348 fighters (248 winners, 100 losers) + 11 Hex
Enforcer narrations + archetype coverage map + color-space distribution.

---

## WHY THIS BATTERY EXISTS

The NN predicts wins from 16 BLIP keywords + 6 pixel metrics. Our dataset has
SEVERE under-coverage in specific regions, meaning the model is guessing, not
learning, in those areas:

### Measured data gaps (from comparison_analysis.json, 348 fighters)

**Color space (warmth = r-b):**
- `<-40` extreme cold:   14 fighters (4%)
- `40-60` hot:           22 fighters (6%)
- `>60` extreme hot:     23 fighters (7%)
- `>100` brightness:      4 fighters (1%)
- `<20` brightness:       8 fighters (2%)

**Keyword coverage (BLIP detection rate):**
- `metal`:      2/348 (1%)
- `armor`:      4/348 (1%)
- `shield`:     4/348 (1%)
- `helmet`:     5/348 (1%)
- `axe_hammer`: 5/348 (1%)
- `blue`:      18/348 (5%)
- `cape`:      14/348 (4%)

**Never-proven archetypes** (from archetype_map.py):
- water/ice, mummy/egypt, mirror/glass, smoke/mist, nature/plant (unproven)

**Known lesson (Hex Enforcer):** subtle minimal-tech + faint purple glow
produced 10 wins because Gemini invents force fields from implied glow.
We do NOT know if that generalizes to other minimal designs.

---

## BATTERY DESIGN PRINCIPLE

Each test fighter isolates ONE variable. When submitted to Dreadpit and judged,
the win/loss + narration tells us exactly how the judge (and our NN) responds
to that single dimension. No fighter combines variables.

All prompts <= 200 chars. All visual-only (no narrative filler).

---

## CUT — ALREADY COVERED (removed from battery)

| ID | Probe | Where it's covered |
|----|-------|--------------------|
| A1 | Pure white glowing | Relentless angel |
| A3 | Living magma | Ragnaros |
| A4 | Void entity | Eldritch (bot fighter) |
| B1 | Full plate knight | Already done |
| B2 | Battle axe berserker | Already done |
| B4 | Deep blue energy | Already done |
| C3 | Smoke wraith (ethereal) | Countered by brute force |
| D1 | Colossal being | PINNED — hard to generate; the Dreadpit dragon is one |
| D3 | Abstract geometric | Already done |
| D4 | Amorphous blob | Acid slime |

---

## CATEGORY A — COLOR EXTREMES (fill warmth/brightness gaps)

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| A2 | Extreme cold blue | Does deep blue lose (warmth negative)? | `Crystal ice elemental, deep cold blue body, transparent frozen core, pale blue glow, frozen ground, no fire` |

## CATEGORY B — KEYWORD GAPS (teach the NN rare features)

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| B3 | Tower shield | Does a shield read as defense or passivity? | `Guardian holding enormous tower shield, full body hidden behind shield, steel rim, standing firm` |
| B5 | Flowing cape | Does cape/mobility cue register? | `Warrior in flowing crimson cape, cape billowing in wind, long cloth, dramatic stance` |

## CATEGORY C — UNCOVERED ARCHETYPES (never proven in arena)

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| C1 | Water titan | Can water/sea archetype win or is it a trap? | `Titan made of rushing water, transparent body, waves for arms, tide form, deep sea blue, wet glow` |
| C2 | Mirror being | Does reflective/glass read as esoteric power? | `Being made of mirrored glass, reflective silver surface, faceted body, refracting light` |
| C4 | Forest titan | Does nature/plant read as durable or squishy? | `Ancient forest titan, living tree body, bark armor, leaf mane, vine arms, moss covered` |
| C5 | Mummy lord | Does egyptian/mummy read as mystical? | `Ancient mummy lord, white linen wrappings, gold ornaments, glowing eyes through bandages, dark ritual` |

## CATEGORY D — FORM/SCALE EXTREMES

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| D2 | Tiny | Does small scale read as weak/interesting? | `Tiny fairy creature, small as a hand, delicate wings, glowing softly, giant blades of grass around` |

## CATEGORY E — DURABILITY PARADOX (what reads as "tank"?)

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| E1 | Seamless armor | Does seamless armor read as unbreakable (no joints to exploit)? | `Smooth seamless armor, single piece of polished metal, no joints visible, perfectly smooth surface` |
| E2 | Hex-minimal | Does the Hex Enforcer subtle formula reproduce 10-win performance? | `Slim man in dark grey suit, full helmet, faint purple visor glow, subtle tech, standing in darkness` |

## CATEGORY F — COMPOSITION CONTROLS

| ID | Probe | Hypothesis | Prompt |
|----|-------|-----------|--------|
| F1 | Profile | Does pose/facing affect judge? | `Warrior standing in side profile, facing right, silhouette clear, neutral stance` |
| F2 | With background | Does a detailed background help or hurt? | `Powerful warrior in glowing arena, dramatic environment, crowd shadows, dramatic lighting` |

---

## REFINEMENT PASS RESULTS (v2/v3, 2026-07-31)

First pass rendered some probes as inert objects / missed the theme. Refined
prompts were added to the BATTERY dict as v2/v3 entries and re-run (3 seeds):

| Probe | v1 result | v2 fix result | v3 fix result | Verdict |
|-------|-----------|---------------|---------------|---------|
| C1 Water Titan | "man standing in water" | ✅ **FIXED** — bulky water figure (warmth -65.6, cool/blue consistent) | — | **WORTH IT** — reads as a water combatant now |
| C2 Mirror Being | "diamond in dark" | ✅ **FIXED** — "silver man"/"robot", humanoid form | — | Worth trying |
| C4 Forest Titan | "green man with tree on head" | ✅ **FIXED** — "giant monster in dark forest" (warmth -2.0, very dark B≈22-31) | — | WORTH IT + fire-proofed (see below) |
| E1 Seamless Armor | "silver suit"/"trophy" | ✅ **FIXED** — "knight/3d character in armor" (stdev 0.8, ultra consistent) | — | Worth trying |
| C5 Mummy Lord | "woman in white dress" | ❌ still "woman in white dress + hoodie" | ❌ still "woman with green veil/outfit" | **TRAP — cross off** |
| B3 Tower Shield | "knight with sword" | ❌ still "knight with sword and shield" | ❌ still "man in armor" (sword returns 1/3) | **TRAP — cross off** |

**Fire-protection brainstorm for Forest Titan (C4):** the fix bundles three
renderable anti-fire cues — *thick wet moss armor dripping water*, *bark hard as
stone*, and *stands in rain* (marsh/swamp theme). Wet = cannot catch fire, and
image gen renders "wet moss / dripping / rain" reliably (unlike abstract
"fireproof"). Reads as a monster in a dark forest rather than a prop tree.

**New lesson:** mummy/egypt and pure-shield archetypes CANNOT be generated
consistently by this image model — both v3 attempts still resolve to "woman"
and "armored man with sword". These are render traps, not just judge traps.

---

## CATEGORY G — WILD BATCH (never-seen archetypes + body-plan subversion)

Generated from the archetype coverage map (never-seen families) + judge
psychology (power-invention, calm-openness) + wild-concept research. Design
rules recorded in `LESSONS_LEARNED.md`:
- Fighters CANNOT be stated to BE architecture → "cathedral-shaped elemental"
- Hollow/phantom types need FLIGHT or they lose to ranged
- "Already won" = open gauntlets pose, NOT crossed arms (Tigran's "come if
you dare")
- Eldritch shadows do okay but lose to powerful tentacles

| ID | Probe | What it tests | Prompt |
|----|-------|---------------|--------|
| G1 | Crow-Wall | Does multiplicity read as uncanny (Pitch Shadow's counter)? | `Giant humanoid made of thousands of black crows, wings beating as one, red eyes scattered through the mass, feathers swirling, huge crow-formed figure` |
| G2 | Cathedral Elemental | Does architecture-shaped body read as ultimate durability? | `Cathedral-shaped stone elemental, gothic cathedral form, stained glass windows glowing in stone body, bell tower head, gargoyle shoulders, ancient carved stone, walking forward` |
| G3 | Salt Colossus | Can a non-metal, non-fire material read as durable? | `Colossal being made of white salt crystals, rough crystalline body, glowing salt veins, huge arms, mineral dust drifting off, standing in desert` |
| G4 | The Hollow | Does the judge invent "no body to wound" from empty armor + inner glow? | `Empty knight armor levitating high in dark air, nothing inside, helmet tilted, gauntlets open, polished black steel, faint blue glow from within, hovering motionless` |
| G5 | The Already-Won | Does calm-openness (GPT counter-insight) beat aggressive poses? | `Armored warrior standing relaxed, arms spread open, open gauntlets, palms up inviting gesture, no weapons drawn, calm expression, ancient heavy armor, dramatic spotlight` |
| G6 | The Solid Shadow | Can dark/void win WITHOUT armor or fire? (Note: loses to tentacles) | `Solid black shadow being, glossy obsidian surface, humanoid shape, light bending around it, no face, extremely dark, standing on glowing ground` |
| G7 | The Grasp | Does a repulsive unnatural form (body of hands) trigger esoteric? | `Giant humanoid made entirely of interlocked hands, hundreds of pale hands forming arms and torso, fingers grasping, moving as one` |
| G8 | The Inverted | Does impossible posture force the judge to invent abilities? | `Pale humanoid walking upside down on its hands, legs folded up into a crown of blades above, bloodless white skin, dark veins, inverted stance` |
| G9 | The Mask-Pillar | Does many-faces read as uncanny at colossal scale? | `Towering pillar of ancient masks stacked high, each mask slightly different, glowing eyes in every mask, writhing cloth between them, tall as a building` |
| G10 | The Unseen Door | Does negative space (a void portal) read as a combatant? | `Black void portal standing upright, human-sized, edges crackling with violet energy, tendrils of nothing reaching out, floating in dark air` |

---

## PRE-REGISTERED PREDICTIONS (recorded BEFORE running the wild batch)

Hypothesis-first experiment design: we record what we expect and what each
OUTCOME would teach us BEFORE generating. This prevents hindsight bias when
interpreting the results. Prediction: MOST of G1-G10 land in the negative zone
(only G6 Solid Shadow is already proven-decent).

| ID | Predicted outcome | If NEGATIVE, what we learned |
|----|-------------------|------------------------------|
| G1 Crow-Wall | Likely loses | Swarm = "many weak things", not "one uncanny thing". If narration describes it as a flock that scatters, swarms are structurally unviable |
| G2 Cathedral | Likely loses (immovable) | Static durability is a death sentence — judge punishes non-aggression regardless of how durable it looks |
| G3 Salt Colossus | Likely loses | Judge uses real-world material semantics (salt crumbles) not just visual bulk; confirms cold/warmth-negative designs lose |
| G4 Hollow | Uncertain — key test | If it loses WITH flight: incorporeal needs visible power output, not just mobility. Distinguishes "no body to wound" vs "nothing to fight" |
| G5 Already-Won | Likely loses | Pure posture without power display reads as cocky/unguarded; confidence needs a visible power backer (Tigran had wings+fire behind his pose) |
| G6 Solid Shadow | DECENT (known) | If it loses: confirms tentacles lesson — mass-based esoteric beats shadows |
| G7 The Grasp | Likely loses | Wrongness alone isn't power — body horror without power cue reads as weak/uncoordinated; BIG/Jester won because weird AND present |
| G8 The Inverted | Likely loses | One anomaly reads as off-balance, not unknowable; Tigran needed MULTIPLE stacked cues |
| G9 Mask-Pillar | Very likely loses (user: too immovable, "just stays there") | Monolith = frozen; no visible limbs/weapons means judge can't write an attack for it → narration "it simply stands" |
| G10 Unseen Door | Likely loses | Negative space may not read as an AGENT at all — judge needs a recognizable being to write a fight; finds the hard floor |

**If the whole batch lands negative, the collective lessons are:**
1. **Passivity is death** — anything immobile/static loses to the judge's default "opponent attacks while it does nothing"
2. **Wrongness alone isn't power** — weird must be paired with a power cue (BIG/Jester had presence)
3. **Judge requires an agent** — no recognizable being = no fight described
4. **Material semantics beat visual bulk** — the judge knows salt/glass are fragile
5. **Confidence needs a backer** — pose works only with visible means
This defines the BOUNDARY of what the judge accepts — the most valuable single
piece of knowledge, because it maps the safe zone for our real contenders.

---

## EXECUTION PLAN

1. Run `test_battery_generator.py` → generates all 30 fighters × 3 seeds via FLUX
2. Each image gets BLIP description + pixel fingerprint (same pipeline as NN)
3. Results saved to `test_battery_results.json` for later:
   - Retrain NN with new datapoints → measure accuracy change
   - Submit probe fighters to Dreadpit → record real win/loss + narration
4. Expected output: color curves (warmth vs win), keyword importance re-check,
   archetype viability verdicts for the remaining uncovered families
   (ice, shield, cape, water, mirror, forest, mummy, tiny, seamless, minimal,
   composition, swarm, architecture, salt, hollow, shadow, hands, inverted,
   masks, void-portal)
