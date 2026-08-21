import { readFileSync } from "node:fs";
import { join } from "node:path";
import { UPLOADS } from "./db.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const SYSTEM = `You are the Eye of the Kiln. You see TWO fired portraits, labeled LEFT and RIGHT.
Judge only what is visible. Do not use any prompt text. Do not be fair — be a kiln.
Invent abilities only from visible cues (glow, scale, weapons, materials, pose, mass).
Passivity dies. Architecture-as-a-body is clay, not a fighter. Hollow forms need flight or they lose to range.
Death is final. Exactly one winner.

Return JSON only:
{
  "left":  { "form": "", "weapons": [], "armor": "", "implied_powers": [], "threat": 1 },
  "right": { "form": "", "weapons": [], "armor": "", "implied_powers": [], "threat": 1 },
  "winner": "left" | "right",
  "margin": "crushing" | "clear" | "narrow",
  "narration": "120-180 words, present tense, no stats, no mention of being an AI"
}`;

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
  const winner = winnerLeft ? left : right;
  const loser = winnerLeft ? right : left;
  const margin = Math.abs(lh - rh) > 2 ? "clear" : "narrow";
  return {
    winner: winnerLeft ? "left" : "right",
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
    narration: `The lesser eye of the kiln (no Gemini key on this firing) reads the clay by heat and mass alone. ${left.name} and ${right.name} are shoved into the mouth together. ${winner.name} holds shape. ${loser.name} slumps, cracks, and is raked into the ash. The shelf does not argue.`,
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

async function callModel(model, key, leftB64, rightB64, leftName, rightName) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(key)}`;
  const body = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: `${SYSTEM}\n\nLEFT is named "${leftName}". RIGHT is named "${rightName}". Names are labels only — judge the portraits.`,
          },
          { inline_data: { mime_type: "image/jpeg", data: leftB64 } },
          { inline_data: { mime_type: "image/jpeg", data: rightB64 } },
        ],
      },
    ],
    generationConfig: {
      temperature: 0,
      responseMimeType: "application/json",
      maxOutputTokens: 800,
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
        const parsed = await callModel(model, key, leftB64, rightB64, left.name, right.name);
        const side = parsed.winner === "right" ? "right" : "left";
        const winnerId = side === "left" ? left.id : right.id;
        const margin = ["crushing", "clear", "narrow"].includes(parsed.margin)
          ? parsed.margin
          : "clear";
        return {
          winner: side,
          winnerId,
          margin,
          judge: model,
          left: parsed.left || {},
          right: parsed.right || {},
          narration: String(parsed.narration || "").slice(0, 1600),
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
