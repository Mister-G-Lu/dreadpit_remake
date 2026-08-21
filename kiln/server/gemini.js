import { readFileSync } from "node:fs";
import { join } from "node:path";
import { UPLOADS } from "./db.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Secret backend labels. Names are stored on our end only — Gemini is shown
// "FIGHTER1 vs FIGHTER2" and must answer in those labels; the server swaps
// them for real names after judging. Fixed labels are safe here because the
// model never sees fighter names (so its prose cannot legitimately contain
// them) and substitution is single-pass (so a fighter whose NAME contains a
// label can never trigger a second replacement).
const F1 = "FIGHTER1";
const F2 = "FIGHTER2";

const SYSTEM = `You are the Eye of the Kiln. You see TWO fired portraits: ${F1} (the first image) and ${F2} (the second image).
Judge only what is visible. Do not use any prompt text.
Invent abilities only from visible cues (glow, scale, weapons, materials, pose, mass, focus).

THE PIT FLATTENS ALL PRETENDERS TO ONE TIER. Calibrate before you judge:

SCALE IS STYLE, NOT SUBSTANCE. Suns, moons, black holes, galaxies, gods: read them
as arena-scale beings that wield that theme — a "black hole" fighter is a
fighter-sized gravity-wielder, a "sun" is a huge flaming sphere with heat and
mass, not literal astrophysics. Cosmic imagery is a coat of paint, never an
auto-win. Backdrop spectacle is decoration; judge the body in the ring.

COUNT IS NOT POWER. Six arms, fifty guns, walls of blades: these display
firepower capacity, not multiplied damage. Guns already prove lethal force —
one calm marksman's aimed shot outweighs a dozen barrels sprayed blind. Judge
weapon DISCIPLINE (grip, stance, sightline, poise, a drawn bead) over weapon
COUNT. Extra limbs are extra targets and split attention unless the pose shows
true mastery of all of them.

ARMOR HAS SEAMS. Heavy plate is real protection, but every suit has joints,
eye slits, vents, straps. An unarmored fighter showing precision cues — a
duelist's stance, a killer's calm, predator focus, perfect balance — can find
those gaps. Speed, stealth, reach, and skill are armor of their own. Bare skin
is not an automatic wound; a slow bunker is not an automatic win.

EVERY COHERENT FIGHTER HAS A PATH. Assassin, duelist, monk, sniper, caster,
beast, brute, tank — all can take this pit. Before you choose, state how EACH
side wins this specific fight, then crown the more convincing path. Never
decide on mass, size, limb count, or spectacle alone.

BUT THE KILN IS HONEST. Some clay cannot fight: passivity dies. Architecture-
as-a-body is clay, not a fighter. Hollow forms need flight or they lose to
range. A form with no credible offense or defense loses — do not invent
viability that is not on the surface.

Death is final. Exactly one winner.

Return JSON only:
{
  "fighter1": { "form": "", "weapons": [], "armor": "", "implied_powers": [], "path_to_victory": "", "threat": 1 },
  "fighter2": { "form": "", "weapons": [], "armor": "", "implied_powers": [], "path_to_victory": "", "threat": 1 },
  "winner": "${F1}" | "${F2}",
  "margin": "crushing" | "clear" | "narrow",
  "narration": "100-160 words, present tense, no stats, no mention of being an AI. Refer to the fighters ONLY as ${F1} and ${F2} — you are not told their names; never invent names or paraphrase the labels. Narrate the exchange only; do NOT declare the final outcome in prose. The kiln itself states the verdict after your last sentence."
}`;

// Display names for prose. If both fighters share a name, disambiguate by
// side so the narration can never be read both ways.
export function displayNames(left, right) {
  const same =
    String(left.name || "").trim().toLowerCase() ===
    String(right.name || "").trim().toLowerCase();
  return {
    left: same ? `${left.name} (left)` : left.name,
    right: same ? `${right.name} (right)` : right.name,
  };
}

// The canonical closing line. Composed by the server from the structured
// winner side — never trusted to model prose.
export function verdictLine(side, left, right) {
  const names = displayNames(left, right);
  const winner = side === "left" ? names.left : names.right;
  const loser = side === "left" ? names.right : names.left;
  return `The kiln rules: ${winner} holds shape. ${loser} slumps, cracks, and is raked into the ash.`;
}

// Substitute the FIGHTER1/FIGHTER2 labels with (disambiguated) display names
// in ONE regex pass — substituted text is never rescanned, so a fighter whose
// NAME contains a label can never trigger a second replacement — then append
// the canonical verdict. Done server-side at judge time so the stored
// narration is final: every consumer (match page, home teaser, history, any
// future feed) reads real names with zero client logic. The placeholder
// original survives in raw_json.
export function renderNarration(rawNarration, side, left, right) {
  const names = displayNames(left, right);
  // tolerate FIGHTER1 / Fighter 1 / fighter_1 style slips from the model
  const pattern = /fighter[\s_-]?([12])/gi;
  const prose = String(rawNarration || "")
    .replace(pattern, (_, n) => (n === "1" ? names.left : names.right))
    .trim();
  return `${prose}${prose ? " " : ""}${verdictLine(side, left, right)}`.slice(0, 1600);
}

function models() {
  const primary = process.env.GEMINI_MODEL || "gemini-2.5-flash";
  const list = [
    primary,
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-3.7-flash",
    "gemini-3-flash-preview",
  ];
  return [...new Set(list)];
}

function heatScore(fighter) {
  const t = `${fighter.name} ${fighter.prompt}`.toLowerCase();
  const keys = [
    "fire",
    "molten",
    "forge",
    "ember",
    "glow",
    "iron",
    "armor",
    "wing",
    "shadow",
    "cannon",
    "hook",
    "skull",
    "furnace",
  ];
  return keys.reduce((n, k) => n + (t.includes(k) ? 1 : 0), 0) + fighter.wins * 0.25;
}

export function localJudge(left, right) {
  const lh = heatScore(left);
  const rh = heatScore(right);
  const winnerLeft = lh === rh ? left.id < right.id : lh > rh;
  const side = winnerLeft ? "left" : "right";
  const winner = winnerLeft ? left : right;
  const names = displayNames(left, right);
  const margin = Math.abs(lh - rh) > 2 ? "clear" : "narrow";
  return {
    winner: side,
    winnerId: winner.id,
    margin,
    judge: "lesser-eye",
    left: {
      form: left.name,
      weapons: [],
      armor: "",
      implied_powers: [],
      threat: Math.min(10, Math.round(lh + 3)),
    },
    right: {
      form: right.name,
      weapons: [],
      armor: "",
      implied_powers: [],
      threat: Math.min(10, Math.round(rh + 3)),
    },
    narration: `The lesser eye of the kiln (no Gemini key on this firing) reads the clay by heat and mass alone. ${names.left} and ${names.right} are shoved into the mouth together. ${verdictLine(side, left, right)} The shelf does not argue.`,
    raw: null,
  };
}

function parseJson(text) {
  if (!text) throw new Error("empty gemini");
  const trimmed = text.trim();
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start < 0 || end < 0) throw new Error("no json");
  return JSON.parse(trimmed.slice(start, end + 1));
}

// Constrained decoding: with responseMimeType alone, JSON validity is only a
// "strong hint"; adding responseSchema masks illegal tokens at generation
// time, so `winner` can only ever be "left" or "right".
const SCOUT_SCHEMA = {
  type: "OBJECT",
  properties: {
    form: { type: "STRING" },
    weapons: { type: "ARRAY", items: { type: "STRING" } },
    armor: { type: "STRING" },
    implied_powers: { type: "ARRAY", items: { type: "STRING" } },
    path_to_victory: { type: "STRING" },
    threat: { type: "INTEGER" },
  },
  required: ["form", "path_to_victory", "threat"],
};

const RESPONSE_SCHEMA = {
  type: "OBJECT",
  properties: {
    fighter1: SCOUT_SCHEMA,
    fighter2: SCOUT_SCHEMA,
    winner: { type: "STRING", enum: [F1, F2] },
    margin: { type: "STRING", enum: ["crushing", "clear", "narrow"] },
    narration: { type: "STRING" },
  },
  required: ["fighter1", "fighter2", "winner", "margin", "narration"],
  propertyOrdering: ["fighter1", "fighter2", "winner", "margin", "narration"],
};

async function callModel(model, key, leftB64, rightB64) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(key)}`;
  const body = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: `${SYSTEM}\n\nThe first image is ${F1}. The second image is ${F2}. ${F1} vs ${F2} — judge the portraits.`,
          },
          { inline_data: { mime_type: "image/jpeg", data: leftB64 } },
          { inline_data: { mime_type: "image/jpeg", data: rightB64 } },
        ],
      },
    ],
    generationConfig: {
      temperature: 0,
      responseMimeType: "application/json",
      responseSchema: RESPONSE_SCHEMA,
      maxOutputTokens: 1100,
    },
  };
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 45000);
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  });
  clearTimeout(t);
  if (res.status === 429) {
    const err = new Error("rate limited");
    err.code = "RATE_LIMIT";
    throw err;
  }
  if (!res.ok) {
    const err = new Error(`gemini ${res.status}`);
    err.status = res.status;
    err.body = await res.text().catch(() => "");
    throw err;
  }
  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
  return parseJson(text);
}

export async function judgeMatch(left, right) {
  const key = process.env.GEMINI_API_KEY;
  const raster = (name) => /\.(jpe?g|png|webp|gif)$/i.test(name || "");
  if (!key || !raster(left.filename) || !raster(right.filename)) {
    return localJudge(left, right);
  }

  const leftB64 = readFileSync(join(UPLOADS, left.filename)).toString("base64");
  const rightB64 = readFileSync(join(UPLOADS, right.filename)).toString("base64");

  let last;
  for (const model of models()) {
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const parsed = await callModel(model, key, leftB64, rightB64);
        // FIGHTER1 = first image = left slot; FIGHTER2 = second = right slot.
        const side = parsed.winner === F2 ? "right" : "left";
        const winnerId = side === "left" ? left.id : right.id;
        const margin = ["crushing", "clear", "narrow"].includes(parsed.margin)
          ? parsed.margin
          : "clear";
        return {
          winner: side,
          winnerId,
          margin,
          judge: model,
          left: parsed.fighter1 || {},
          right: parsed.fighter2 || {},
          narration: renderNarration(parsed.narration, side, left, right),
          raw: parsed,
        };
      } catch (err) {
        last = err;
        if (err.code === "RATE_LIMIT") {
          await sleep(4000 * attempt);
          if (attempt === 3) throw err;
          continue;
        }
        if (err.status === 404 || err.status === 400) break;
        await sleep(2000 * attempt);
      }
    }
  }
  if (last?.code === "RATE_LIMIT") throw last;
  console.warn("Gemini failed, lesser eye:", last?.message || last);
  return localJudge(left, right);
}
