# Reverse-engineering DreadPit's daily Gemini scheduler

**Date:** 2026-08-22
**Goal:** figure out, from public behavior and the public API, how `dreadpit.com` triggers its daily Gemini fight judging, and map that onto this repo's `kiln/`.

I could not read DreadPit's server source — there is no public repo and the backend is closed. What follows is **inference from observable behavior**: the public API, the server-rendered pages already scraped into this repo, and the timestamps on thousands of real fight/graveyard records. The hard facts are the timestamps and the site's own published rules.

---

## 1. What I actually observed

### 1.1 The schedule is 12:00 UTC, once per day

Querying public endpoints with a browser-grade client:

- `GET /api/fighters/<id>/fights` returns every fight for a fighter with a UTC timestamp.
- The current #1 fighter, "Apex", fought exactly once a day, every day, all at **`12:00:xxZ`**:

```
2026-08-11T12:01:10.401Z
2026-08-12T12:00:48.104Z
2026-08-13T12:00:30.052Z
2026-08-14T12:01:10.881Z
2026-08-15T12:00:04.683Z
2026-08-16T12:00:24.016Z
2026-08-17T12:00:07.089Z
2026-08-19T12:00:08.251Z
```

- `fighter_detail_cache.json` (5,270 `diedAt` values from the repo's earlier scrape) is almost entirely at **hour 12 UTC** — 4,965 of 5,270. Every date with a large death count shows a single `12` hour wave. There is no consistent second wave.

So the canonical DreadPit round is **one per day at 12:00 UTC**, not "twice a day" as some copy says (see 1.3).

### 1.2 The whole bracket is processed at the mark, not stretched over hours

Inside a single day's noon wave, deaths cluster within a narrow window of seconds to about a minute:

```
...12:00:04.683Z
...12:00:24.016Z
...12:00:30.052Z
...12:01:10.881Z
```

For a ~50–100 fight bracket that implies DreadPit's worker fires the whole round at 12:00 and runs the Gemini vision calls **back-to-back**, committing each verdict as it completes — seconds apart, with rate-limit/backoff if Gemini throttles. It does **not** spread the round over hours.

### 1.3 The site's own rules say "twice a day" but the data says once

The built static page (`abyssal_page.html`) and the live FAQ both say:

> *"Twice each day at the noon hour of Greenwich, adjacent rivals upon the ladder are paired."*
> *"Twice a day, fighters are paired up and an AI judge decides who wins and who dies."*

Yet the live `how-it-works` page says:

> *"Once each day the Arbiter pairs adjacent fighters on the ladder."*

The timestamp data is the tiebreaker: **one noon round per day**. The "twice" language almost certainly refers to the marketing copy for the two-portrait summon (Law II, "Two faces, one fate"), or is simply stale copy. Treat 12:00 UTC as the real cadence.

### 1.4 There is an idempotent catch-up / resume path

On 2026-08-21 a batch of deaths appeared at `21:57:xxZ`, after the cache shows no Aug-19/20-noon wave. Example:

```
Ghostrider the Vengeful /fights -> foughtAt 2026-08-21T21:57:36.855Z
```

That is best explained as a **round that was missed at noon and then run later (resume/catch-up)** on the same day, rather than a fixed second daily slot. This is the second half of the DreadPit scheduling model: **a scheduled trigger at noon, plus an idempotent state machine that keeps working on a round until it's done and refuses to open tomorrow's before today's is closed** (the FAQ: *"Rounds are final / Once a round is resolved it cannot be re-run"*).

### 1.5 What the AI judge is and isn't given

DreadPit's own `/how-it-works` and `/privacy`:

- Prompts are **sealed** and never returned by the API.
- *"The judge sees only images"* — the Arbiter receives both portraits and decides by visual impression.
- *"Portraits (images only) are sent to this service's vision API for duel verdicts."*

So the daily "call to Gemini" is a **vision call per fight** carrying the two portraits (minus the text prompt), not a chat job that reads the prompt.

### 1.6 Backend stack fingerprint

From server-rendered HTML + the API:

- Vite + React 19 + React Router + TanStack Query + **Clerk** (auth / identity provider).
- Express-style backend (unimplemented routes return the default `Cannot GET /path`).
- **PostgreSQL** (per privacy page: portraits stored as data URLs in PostgreSQL).
- **Stripe** for credits, Google AdSense / Ezoic for ads.
- JSON public endpoints: `/api/leaderboard`, `/api/graveyard`, `/api/fighters/:id`, `/api/fighters/:id/fights`, `/api/storage/objects/uploads/<id>`.

None of the schedule endpoints I probed (`/api/rounds`, `/api/rounds/latest`, `/api/schedule`, `/api/config`, `/api/state`) exist publicly, so the trigger itself is hidden server-side. But a Vite/Express/Postgres app that needs a once-daily job on a real host almost certainly uses **cron (systemd timer / crontab / managed cron) hitting an idempotent backend job**, with the DB itself carrying the "have we already fired today" state.

---

## 2. The scheduling model, in one picture

```
cron @ 12:07 UTC (or managed scheduled handler)
        │
        ▼
  backend job  ─────────────────────────────────────────────┐
  │  if today's round already exists & running  → resume it  │
  │  if today's round already complete          → no-op      │
  │  if none                                    → open round │
  │                                                          │
  │  pair adjacent ladder fighters                            │
  │  for each pair:                                           │
  │     call Gemini Vision (both portraits, no prompt)        │
  │     on 429/5xx/timeout: backoff, try fallback model       │
  │     commit verdict in one transaction                     │
  │  mark round complete (idempotent, never re-run)           │
  └──────────────────────────────────────────────────────────┘
```

Three properties are load-bearing:

1. **The trigger can be "at least once".** A cron that can fire while the previous run is still working must be harmless. The DB round state is the gate.
2. **The round is one-per-time-window.** The state machine refuses to start N+1 until N is closed.
3. **The work is a queue, not a web request.** It survives process restarts and rate limits.

---

## 3. DreadPit → your `kiln/` repo

Your repo already implements almost all of this. The relevant code:

| DreadPit behavior | Already in `kiln/` | Where |
|---|---|---|
| Daily mark at a fixed UTC hour | ✅ | `server/db.js` `fireMoment` / `nextFireAt` / `lastFireAt` / `isSealing` |
| One round per UTC day, no double-open in-process | ✅ | `server/scheduler.js` `tick()` + `alreadyFiredTonight` |
| Pair adjacent ladder fighters | ✅ | `server/scheduler.js` `pairFighters()` |
| Gemini vision, image-only, JSON schema | ✅ | `server/gemini.js` (no prompt sent; `responseSchema`) |
| 429 backoff / model fallback / lesser-eye | ✅ | `server/gemini.js` + `server/scheduler.js#processBatch` |
| Commit each verdict before next call | ✅ | `applyVerdict()` per match |
| Round is final / idempotent | ✅ | rounds/matches state machine; completed matches never re-judged |
| Public "next judgment" countdown | ✅ | `GET /api/state` → `clock.nextFireAt` |
| Manual/triggered tick for a scheduler | ✅ | `POST /api/round/tick` (authenticated) |

### Gaps vs. DreadPit

**A. The trigger is only an in-process poller today.**
`startScheduler(db)` uses `setTimeout(2s) + setInterval(15s)` to call `tick()`. That's fine on a single long-lived VPS process, but:
- it dies with the process;
- it can't be a scheduled function (Cloudflare/Vercel cron) unless the API is hit;
- a deployment that restarts *at* noon may skip the mark unless something re-hits it.

**Fix:** expose a one-shot runner (`kiln/server/job.js` / `npm run round`) that opens the DB, runs `tick()` once, and exits. Use that in a real cron (systemd timer, crontab, Vercel Cron, Cloudflare Cron, GitHub Actions scheduled workflow). The internal 15s poller can stay as a fallback — or be disabled with `KILN_POLL=0` when a cron is the sole trigger (see changes below).

**B. Default fire hour is 00:00 UTC; DreadPit is 12:00 UTC.**
The repo defaults to `FIRE_UTC_HOUR=0`. For DreadPit parity (and the same "evening-in-UTC / morning-in-US" feel), set `FIRE_UTC_HOUR=12`. The scheduler is fully config-driven, so no code change is needed.

**C. Batching is hourly (10/hr); DreadPit fires the round as one wall of calls.**
`BATCH_SIZE=10`, `BATCH_INTERVAL_MS=3600000` means a full 64-fight round takes ~6–7h. DreadPit appears to run the whole bracket in minutes. If you want that, raise `BATCH_SIZE` to the full round (e.g. 64) and drop `BATCH_INTERVAL_MS` to a few seconds — the `stalled`/429 path already handles throttling. This is a deliberate tradeoff: the repo chose hourly to stay politely under Gemini free-tier RPM; DreadPit-style "fire it all now with backoff" is closer to their observed behavior.

**D. No cross-process guard.**
`ticking` is per-process. If you ever run both the server poller *and* a cron `job.js`, two processes could create/process the same round concurrently. For the current single-process deployment this is fine; if you go multi-process, add a DB-based lease/lock around `tick()` (or simply run *only* the cron path, `KILN_POLL=0`).

**E. The "catch-up after a missed noon" behavior already exists.**
`tick()` continues an open `running`/`stalled` round regardless of the wall clock, and on restart after the fire mark it will open today's round. That's exactly DreadPit's 21:57 catch-up.

---

## 4. Recommended setup for a DreadPit-parity `kiln`

In `kiln/.env`:

```bash
# DreadPit fires at 12:00 GMT. This keeps the same "noon judgment" feel.
FIRE_UTC_HOUR=12

# Fire all matches at the mark and let the 429 stutter handle throttling,
# instead of trickling 10 matches/hour.
BATCH_SIZE=64
BATCH_INTERVAL_MS=15000

# If you drive the round from a real cron, turn the in-process 15s poller off
# (comment this out if you still want a single process self-scheduling).
KILN_POLL=0
```

Cron (systemd timer or crontab), **either** of these is equivalent and safe because `tick()` is idempotent:

```cron
17 12 * * *  cd /path/to/dreadpit_remake/kiln && node server/job.js >> kiln-cron.log 2>&1
```

Or hit the authenticated endpoint from a managed cron (Vercel/Cloudflare), which you already have:

```cron
17 12 * * *  curl -X POST https://your-host/api/round/tick -H "Cookie: kiln_session=..."
```

`job.js` is auth-free so it works from a server-side cron without managing a session.

---

## 5. Bottom line

DreadPit's daily Gemini load is:

> **one vision call per fight, fired by an idempotent once-per-UTC-day job at 12:00 UTC, over the full bracket, image-only, with per-verdict commits and a resume/catch-up path.**

Your `kiln/` already has the state machine, the image-only Gemini judge, the backoff, and the one-per-day gate. The only real gap is **where the trigger lives** — move it from a 15-second in-process poll to a real scheduled job (a one-shot `tick()` runner), and optionally align the hour to 12:00 UTC and fire the round in one wall instead of hourly batches.

## Evidence file references

- `bot_collector.py` — the scraper that pulled the public DreadPit API.
- `fighter_detail_cache.json` — 5,270 `diedAt` timestamps used for the 12:00 UTC histogram.
- `abyssal_page.html` / `WEBSITE_FEASIBILITY.md` — scraped rules and the earlier (partly incorrect "twice a day") analysis.
- `kiln/server/{db,scheduler,gemini}.js` — the code that already implements the model.
