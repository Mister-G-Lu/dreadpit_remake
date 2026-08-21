import { writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { id, UPLOADS } from "./db.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function sparkUrl(prompt, seed, apiKey) {
  const params = new URLSearchParams({
    model: "flux",
    width: "768",
    height: "768",
    seed: String(seed),
    nologo: apiKey ? "true" : "false",
    private: "true",
  });
  if (apiKey) params.set("key", apiKey);
  return `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?${params}`;
}

export async function generateSpark(prompt, seed, apiKey) {
  const url = sparkUrl(prompt, seed, apiKey);
  let lastErr = "Image generation failed. Please try again.";
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 120000);
      const res = await fetch(url, {
        signal: ctrl.signal,
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
      });
      clearTimeout(t);
      if (res.status === 429) {
        lastErr = "Image generation is rate-limited. Please wait a minute and try again.";
        await sleep(8000 * attempt);
        continue;
      }
      if (!res.ok) {
        lastErr = `Image generation failed (${res.status}). Please try again.`;
        await sleep(3000 * attempt);
        continue;
      }
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length < 2000) {
        lastErr = "The image service returned an empty file. Please try again.";
        await sleep(2000);
        continue;
      }
      const sparkId = id();
      const filename = `${sparkId}.jpg`;
      writeFileSync(join(UPLOADS, filename), buf);
      return { id: sparkId, filename, seed, bytes: buf.length };
    } catch (err) {
      lastErr =
        err.name === "AbortError"
          ? "Image generation timed out. Please try again."
          : err.message || "Image generation failed. Please try again.";
      await sleep(1200 * attempt);
    }
  }
  if (/rate-limited/i.test(lastErr)) {
    const error = new Error(lastErr);
    error.status = 429;
    throw error;
  }
  console.warn("[kiln] pollinations unreachable, stamping local clay:", lastErr);
  return stampLocalClay(prompt, seed);
}

function stampLocalClay(prompt, seed) {
  const sparkId = id();
  const filename = `${sparkId}.svg`;
  const h = createHash("sha256").update(`${prompt}:${seed}`).digest();
  const hue = h[0] * 1.4;
  const hue2 = h[1] * 1.4;
  const cx = 280 + (h[2] % 200);
  const cy = 260 + (h[3] % 220);
  const r = 140 + (h[4] % 120);
  const caption = escapeXml(prompt.slice(0, 42));
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 768 768">
  <defs>
    <radialGradient id="g" cx="50%" cy="40%">
      <stop offset="0%" stop-color="hsl(${hue2},55%,28%)"/>
      <stop offset="100%" stop-color="#0a0908"/>
    </radialGradient>
  </defs>
  <rect width="768" height="768" fill="url(#g)"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="hsl(${hue},70%,48%)" stroke-width="18"/>
  <circle cx="${768 - cx}" cy="${768 - cy}" r="${Math.floor(r * 0.6)}" fill="hsl(${hue},80%,22%)" opacity="0.85"/>
  <rect x="48" y="48" width="672" height="672" fill="none" stroke="#d4894a" stroke-width="3" opacity="0.5"/>
  <text x="384" y="640" text-anchor="middle" fill="#d4c4b0" font-family="Georgia, serif" font-size="22" font-style="italic">${caption}</text>
  <text x="384" y="700" text-anchor="middle" fill="#8d8174" font-family="sans-serif" font-size="14" letter-spacing="4">LOCAL CLAY · SEED ${seed}</text>
</svg>`;
  writeFileSync(join(UPLOADS, filename), svg);
  return { id: sparkId, filename, seed, bytes: svg.length, local: true };
}

function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
