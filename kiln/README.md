# KILN — the night firing

Dark single-elimination portrait ladder. Users connect a Pollinations account, generate up to **10 Flux portraits per day**, and hold up to **15 vessel slots**. The kiln **fires once per UTC day at 00:00** (`FIRE_UTC_HOUR`); the **sealing hour** before it is when the gate line steps up and the founding dead fill the missing slots. The Eye judges in **hourly batches of 10 matches** (Gemini Flash, with stutter on 429).

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
| `MAX_ROSTER` | `64` | Living stack size **and** new fighters admitted per UTC day. Sized so one firing (≈32 matches) judges in ~3h even with 429 stutter. |
| `SPARKS_PER_DAY` | `10` | Image generations per user per UTC day. |
| `USER_SLOTS` | `15` | Vessels (living + waiting) a single player may hold. The dead hold no slot. |
| `FIRE_UTC_HOUR` | `0` | UTC hour the nightly firing opens. Never move it once players rely on it. |
| `SEAL_MINUTES` | `60` | Sealing window before the fire: entries and resurrections pause, gate + bots fill. |
| `KILN_BOTS` | `1` | Set `0` to disable the founding-dead bot pool. |
| `BOT_COOLDOWN_DAYS` | `1` | Days a dead bot rests in the pool before it may revive. |
| `VITE_POLLINATIONS_APP_KEY` | (none) | Optional `pk_…` so the BYOP consent screen names this app. |

## How a night works

1. User registers a Kiln account (separate from Pollinations).
2. `/connect` — Pollinations redirect to `enter.pollinations.ai/authorize`, or paste an `sk_` key. The key stays in the browser; it is only sent as `X-Pollinations-Key` when generating a portrait.
3. `/forge` — up to 10 Flux portraits. Pick one, name it, enter the stack or the gate line (slots permitting: 15 living/waiting vessels per player).
4. **23:00 UTC — the sealing.** Entries and resurrections pause for one hour. The gate line steps onto the stack; the founding dead fill whatever slots remain up to `MAX_ROSTER`. The stack is whole exactly when the Eye wakes.
5. **00:00 UTC — the firing.** Matches 1–10 judge immediately. 11–20 wait an hour, and so on. A Gemini 429 parks the round for 10 minutes and retries (stutter). Losers go to Ash; survivors rest until the next sealing.
6. A fresh install bootstraps: the first firing ever happens as soon as two vessels stand (bots included), then the nightly clock takes over.

Sight-only judging: the 200-character prompt is **not** sent to Gemini.

## Death, career, and resurrection

- `wins` is the **current life** — it sets ladder position. `careerWins` is carved forever.
- When a vessel dies it releases its slot. From `/profile` the owner may **raise it from ash**: it takes a slot, restarts at the **bottom of the ladder** (`wins = 0`), and keeps its career record on the vessel page.
- Nothing may enter or rise during the sealing hour (423 "the kiln is sealed").

## The founding dead (rotating bot pool)

308 real DreadPit portraits (catalogued in `../bot_images_manifest.json`, files in
`../big_portraits`, `../portraits`, `../bot_losers`) form a rotating bot pool:

- Bots **materialize only during the sealing hour** (and the one-time bootstrap
  firing): the gate line steps up first, then the pool deploys its longest-resting
  vessels until the stack reaches `MAX_ROSTER`. All day the stack reads human —
  the dead arrive with the night.
- A revived bot enters as a fresh fighter carrying its legend (`base_wins` from
  its scraped career).
- Bots die like anything else — Ash, sealed prompt, graveyard. On death their pool
  row rests for `BOT_COOLDOWN_DAYS`, then returns to `available` for a later
  revival. If even resting bots run short, the pit drafts the longest-resting
  anyway: **the stack never starves.**
- Gate users always get slots before bots. Bots never count against the daily
  admission cap.
- Portraits are served from the repo via `/bots/<folder>/<file>` (folder allowlist,
  `basename`-sanitized), and the Gemini judge reads them through the same
  `@bot/`-prefix path resolution as uploads.
- Set `KILN_BOTS=0` to run a humans-only pit.

## GitHub Pages

Static gallery (HashRouter + demo roster) builds into `/docs`.

```bash
cd kiln
npm run build:pages
```

Then: **Settings → Pages → Deploy from a branch → `main` / `docs`**.

Live URL: https://mister-g-lu.github.io/dreadpit_remake/

The Pages cut is the pit under glass (browse stack, firings, vessels). Throwing new clay still needs this Node flue (`npm run dev`).
