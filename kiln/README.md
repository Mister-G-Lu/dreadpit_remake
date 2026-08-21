# KILN — the night firing

Dark single-elimination portrait ladder. Users import a Pollinations account (BYOP), fire up to **10 Flux portraits per day**, and enter a **256-vessel stack**. Once per 24 hours the Eye judges the stack in **hourly batches of 10 matches** (Gemini Flash, with stutter on 429).

## Run

```bash
cd kiln
cp .env.example .env   # optional: add GEMINI_API_KEY
npm install
npm run dev            # http://0.0.0.0:3000
```

| Env | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | (none) | Google AI Studio key. Without it, a local "lesser eye" still closes matches so the pit works. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Primary judge. Falls back through Flash-Lite / 2.0 / 1.5 / 3.x names. |
| `BATCH_SIZE` | `10` | Matches per hour. |
| `BATCH_INTERVAL_MS` | `3600000` | Delay after a successful batch. First batch of a round fires immediately. |
| `MAX_ROSTER` | `256` | Living stack size **and** new vessels admitted per UTC day. |
| `SPARKS_PER_DAY` | `10` | Image generations per user per UTC day. |
| `VITE_POLLINATIONS_APP_KEY` | (none) | Optional `pk_…` so the BYOP consent screen names this app. |

## How a night works

1. User registers a kiln name (separate from Pollinations).
2. `/connect` — BYOP redirect to `enter.pollinations.ai/authorize`, or paste an `sk_` key. The key stays in the browser; it is only sent as `X-Pollinations-Key` when firing a spark.
3. `/forge` — up to 10 Flux sparks. Pick one, name it, enter the stack (or the mouth if 256 are already living).
4. Scheduler opens a round when ≥2 vessels live and 24h have passed since the last completed firing.
5. Matches 1–10 judge immediately. 11–20 wait an hour, and so on. A Gemini 429 parks the round for 10 minutes and retries (stutter). Losers go to ash; the mouth fills empty slots.

Sight-only judging: the 200-character prompt is **not** sent to Gemini.
