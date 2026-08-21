# Feasibility: Pollinations-Powered Daily Fight Ladder

**Date:** 2026-08-21
**Verdict:** **Yes — buildable as an MVP in 2–4 weeks.** The numbers close. The hard parts are not AI cost; they are auth, rate-limit stutter, judge consistency, and not cloning DreadPit.

**Shipped:** working app in [`kiln/`](kiln/README.md). `cd kiln && npm install && npm run dev` → port 3000. BYOP connect, 10 sparks/user/day, 256 roster + daily admit cap, nightly round in hourly batches of 10 with 429 stutter. Set `GEMINI_API_KEY` to use Flash; without it the lesser eye still closes matches.

This is a design-and-cost analysis, not a build. It is grounded in this repo’s existing pipeline (Pollinations FLUX portraits, visual feature extraction, ladder psychology) plus current Pollinations BYOP and Gemini Flash docs.

---

## 1. What you described, restated as a product

| Piece | Spec |
|---|---|
| Identity | User **imports a Pollinations account** (BYOP), not a custom billing system |
| Summoning | Up to **10 AI images / user / day**, paid from **that user’s Pollen** |
| Judging | Cheap vision model (Gemini 3 Flash family, preferably free) reads both portraits, extracts key details, picks a winner |
| Tone | Dark theme, **single-elimination ladder** feeling |
| Clock | **Once per 24 hours**, automatic. Calls may **stutter** on 429 |
| Cap | **Max 256 living fighters → 128 matches / day** |

That last line is internally consistent **only if “256 fighters” means the living roster, and “128 matches” means one round of pairing**, not a full tournament to a champion.

- Full single-elim of 256 = **255 matches** (256 − 1).
- First round of 256 = **128 matches**.
- Persistent DreadPit-style ladder (adjacent pairing, losers die, winners stay) = **up to 128 matches** when the pit is full.

**Recommendation:** persistent ladder, one round per 24h, cap 256 living. That is the product people already understand, and it matches the 128-match budget exactly.

DreadPit itself ([dreadpit.com](https://dreadpit.com)) already does a darker version of this: 200-character prompt, two portraits, pick one, adjacent ladder pairing **twice daily at 12:00 GMT**, death is final. This proposal is the same sport with three deliberate diffs: **user-paid image gen**, **once daily**, **hard 256 cap**.

Do **not** reuse DreadPit’s name, copy, fonts-as-brand, or assets. The *game idea* is not owned. The *site* is.

---

## 2. Verdict by subsystem

| Subsystem | Feasible? | Cost to operator | Risk |
|---|---|---|---|
| Pollinations account import (BYOP) | **Yes — official flow** | $0 | Key expiry (default 30d), never use `pk_` for gen |
| 10 images / user / day | **Yes** | $0 if users BYOP + Flux (Flux is 0 Pollen) | Anonymous ~1 req / 15s; `pk_` is 1 Pollen / IP / hour |
| Gemini vision judging, 128 matches | **Yes, on free tier** | **$0** free / **~$0.30–$2 / day** paid | Free RPM ~10; no SLA; quotas get cut without notice |
| Dark ladder UI | **Yes** | Hosting only | Easy to accidentally clone DreadPit |
| 24h cron + stutter | **Yes** | Worker + queue | Must persist the round if Gemini 429s mid-bracket |
| 256 cap / 128 matches | **Yes, by construction** | — | Need a waiting queue when the pit is full |

**Operator monthly burn at this scale, if you stay on free Gemini + user-paid Flux:** hosting + object storage, typically **$5–20/mo**.

**If you turn billing on for Gemini (recommended before public launch):** still **under ~$15/mo** at 128 matches/day. The sport is cheap. Reliability is the spend.

---

## 3. Pollinations account import — this is the right move

Pollinations has a first-class **Bring Your Own Pollen (BYOP)** OAuth-like flow. Third-party apps are *supposed* to do exactly this: the user authorizes your app, Pollinations mints a **scoped secret key** that spends *their* Pollen, you pay $0.

### How import actually works

1. You register an **App Key** (`pk_…`) at [enter.pollinations.ai](https://enter.pollinations.ai) with allowed `redirectUris`. This key is attribution only. It must never generate the 10 daily images.
2. User clicks **Connect Pollinations**. You redirect to:

```
https://enter.pollinations.ai/authorize
  ?redirect_url=https://yoursite.com/auth/pollinations/callback
  &app_key=pk_YOUR_APP
  &models=flux
  &budget=5
  &expiry=30
  &permissions=balance,usage,profile
```

3. Consent screen shows your app name. On approve, Pollinations creates a **user-scoped `sk_`** and returns it in the **URL fragment** (`#api_key=sk_…`). Fragments are not sent to servers — that is intentional.
4. Your **frontend** reads the fragment, then either:
   - **A (recommended):** keeps the key in the browser (memory / encrypted local store) and generates portraits client-side, uploading only the chosen image + prompt to you; or
   - **B:** POSTs the key to your backend, which encrypts it at rest (KMS / libsodium secretbox) and generates server-side.

### Why A is the correct default

BYOP was designed so the third-party **server never sees the key**. Path B is operationally nicer (retries, nologo, private, a real queue) and is what you will want if image gen is flaky — but it is a credential-custody product. If you do B:

- encrypt at rest, decrypt only in the worker
- show the user the budget cap you requested
- rotate / re-auth on 401
- never log the key
- default expiry is **30 days** — plan a “Reconnect Pollinations” banner

### What “uses Pollen to generate 10 images” actually costs the user

| Model | Pollen / image | 10 / day | Notes |
|---|---|---|---|
| **Flux** (what this repo already uses) | **0** | **0** | Free, unlimited in theory. Auth still helps rate limits and `nologo` / `private`. |
| Turbo | ~1/333 Pollen | ~0.03 | Cheap premium |
| Kontext (img2img) | ~1/200 | ~0.05 | Only if you iterate on a chosen portrait |
| GPT Image | ~1/77 | ~0.13 | Not needed for MVP |

Registered free tier is about **1.5 Pollen / week**. Flux does not spend it. So “import account + 10 images / day” works **even for broke users**, as long as you default to Flux and treat Pollen as headroom for premium / no-logo / less waiting.

Anonymous, no key: ~**1 request / 15 seconds**. Ten images = ~2.5 minutes plus generation time (this repo already uses 120s timeouts and 3 retries). That is fine for a summoning ritual. It is not fine if 50 users smash Generate at once on a shared operator key.

**Do not generate portraits with a site-wide `pk_`.** Publishable keys are rate-limited to **1 Pollen / IP / hour**. Ten Flux images would still be 0 Pollen, but the IP limiter and the “this is a public client key” model will bite you the moment you touch a paid model or a shared backend IP.

### 10 images / day — product meaning

DreadPit gives **two** portraits and you pick one. Ten is generous. Suggested rules:

- 10 **generations**, not 10 living fighters.
- User picks **one** portrait to enter the pit (or replace a dead one).
- Extra rolls are for seed-shopping. This repo’s own lesson: FLUX seed variance is huge; 10 rolls is a real advantage and should be a stated rule, not a hidden one.
- Hard cap in **your** DB (`generations_on_utc_date`), not in Pollinations. BYOP keys cannot enforce “10/day” for you.
- Prompt cap **200 characters**, visual-only. This repo’s `LESSONS_LEARNED.md` is load-bearing if you want the judge to behave.

---

## 4. Gemini as the Arbiter — 128 matches is a small job

### Model choice (Aug 2026)

Prefer the current Flash line over a frozen “Gemini 3 Flash” string:

| Model | Role | Free tier | Paid (promo through 2026-12-31) |
|---|---|---|---|
| **`gemini-3.7-flash`** | Best cheap judge | Free I/O, rate-limited | $0.75 / $3.75 per 1M |
| `gemini-3.6-flash` | Same price band | Free | $0.75 / $3.75 |
| `gemini-3-flash` / 3 Flash Preview | What you named | Free, ~10 RPM / ~1,500 RPD | $0.50 / $3.00 |
| `gemini-3.1-flash-lite` | Fallback if Flash 429s | Free, slightly cheaper | $0.25 / $1.50 |

**Primary:** `gemini-3.7-flash`. **Fallback on 429:** `gemini-3.1-flash-lite`. Both are vision-capable. Do **not** use Pro. Do **not** use image-*generation* models (`*-flash-image`) — those are paid and solve the wrong problem.

BLIP-base (this repo’s local captioner) is **not** a substitute for a fight judge. It emits one sentence. The DreadPit arbiter invents force fields from a purple visor glow. You need a real VLM.

Qwen2.5-VL-7B (also in this repo) would work self-hosted, but you need a GPU and you become an ML ops shop. Skip it for a website.

### Token math per match

Gemini tiles images: ≤384px → 258 tokens; larger → 768×768 tiles × 258 tokens.

A 1024×1024 portrait ≈ 2×2 tiles = **~1,032 image tokens**. Two fighters ≈ **2,064**. Add a 600-token system prompt ≈ **2,700 input tokens**.

Output: 250–500 tokens of JSON + narration. **If thinking is on, thinking tokens bill as output** and can 5–10× that. For a daily ladder, **turn thinking down or off** and use structured JSON. You want a referee, not a philosopher.

| Scale | Requests | Input tokens | Output tokens (no thinking) |
|---|---|---|---|
| 128 matches | 128 | ~0.35M | ~0.05M |
| 256 pre-extract + 128 fights | 384 | ~0.7M | ~0.15M |
| Full 256-man tournament (255 fights) | 255 | ~0.7M | ~0.1M |

Free Flash RPD is on the order of **1,000–1,500**. 128 is ~10% of quota. **RPM ~10** is the real limiter: 128 sequential calls at 10/min = **~13 minutes**. With 5–15s generation each, wall clock is **15–40 minutes**. That is the stutter window. Budget **90 minutes** before you declare the round stuck.

Paid cost if you leave the free tier (recommended for anything public — enabling billing **kills free quota on that project**, so keep a second no-billing project for experiments):

- 3.7 Flash promo: 0.35M × $0.75 + 0.05M × $3.75 ≈ **$0.45 / day ≈ $14 / month**
- 3 Flash at $0.50 / $3.00: ≈ **$0.30 / day**
- Lite fallback: ≈ **$0.12 / day**

Image tokens dominate. Downscale portraits to **768px on the long side** before the judge call (one tile, 258 tokens each) and you cut input ~4× with almost no loss for “who has a bigger sword.”

### Prompt shape (do not free-form)

Force JSON. Temperature 0. Pin a model version. Persist the raw response.

```text
You are the Arbiter. You see TWO portraits, labeled LEFT and RIGHT.
Judge by what is visible. Do not read the prompt text (we will not send it).
Invent abilities only from visible cues (glow, scale, weapons, materials, pose).
Death is final. Exactly one winner.

Return JSON:
{
  "left":  { "form": "", "weapons": [], "armor": "", "implied_powers": [], "threat": 1-10 },
  "right": { ... },
  "winner": "left" | "right",
  "margin": "crushing" | "clear" | "narrow",
  "narration": "120-180 words, present tense, no stats"
}
```

**Do not send the 200-character prompt to the judge.** DreadPit’s law III is “verdict by sight alone.” If you leak the prompt, players will write essays for the LLM instead of designing portraits. This repo spent months proving that surface pattern + pose is the actual meta.

Cache a **scouting card** per fighter on summon (one Gemini call, stored). Daily matches can then be: two scouting cards + two thumbnails, or two full images. Scouting cards make 429 recovery trivial (you already have structured traits) but they also freeze a fighter’s “read,” which is more sport-like.

### Stutter algorithm

```
for match in shuffled(today_bracket):
    for attempt in 1..8:
        try Gemini (primary)
        on 429 / 503 / timeout:
            sleep min(2^attempt + jitter, 60s)
            if attempt >= 4: try lite fallback
        on 200 + valid JSON: commit winner, loser → graveyard, break
    if still failing: mark match pending, continue
after loop: if any pending, cron every 5 min until round complete or T+6h
never start tomorrow’s round until today’s is closed or voided
```

Shuffle the call order so a mid-round outage does not always kill the same half of the ladder. Write each verdict in a transaction **before** the next call. The round is a queue, not a for-loop in a web request.

---

## 5. Ladder rules that make 256 / 128 feel like single-elim

DreadPit pairs **adjacent** ladder rivals, twice a day. Pure random 128-pair Swiss does not feel like a bracket. Use this:

1. Living roster, ordered by **wins desc, then id**. Cap 256.
2. Overflow sits in a **Gate queue** (unranked, not judged).
3. Each 24h tick: pair `(1v2, 3v4, …)` **or** pair adjacent with a 1-slot offset on odd days so #1 does not always eat #2. Offset is more sporting.
4. Loser dies (graveyard, prompt sealed). Winner stays, `wins += 1`.
5. After the round, dequeue from the Gate until 256.
6. Bye if odd count (lowest wins sits out — they already have the worst seat).

That is single-elimination **per fighter life**, not a 8-round daily tournament. A 23-win champion is someone who survived 23 daily cuts. That is the feeling.

If you instead want a **true daily 256-man bracket to one champion**, you need 255 judgements and ~30–60 minutes of Gemini, still free-tier-legal, but the 128-match budget is wrong and the UX becomes “watch a whole tournament” rather than “check the pit tomorrow.” Do not mix the two.

Clock: pick **one timezone and never move it**. DreadPit uses 12:00 GMT. Once daily, `00:00 UTC` or `12:00 UTC` is enough. Show a countdown. Run the worker 2 minutes after the mark.

---

## 6. Architecture (MVP)

```
[Browser]
  Connect Pollinations (BYOP fragment)
  Prompt → 10× Flux (user sk_) → pick 1
  Upload portrait + prompt to API
        │
        ▼
[API]  Next.js / Hono / FastAPI
  Clerk or Auth.js for site identity (separate from Pollinations)
  Postgres: users, fighters, matches, rounds, generation_ledger
  R2/S3: portraits
  Redis/BullMQ or Inngest: image-proxy (optional), daily_round
        │
        ▼
[Worker]  24h cron
  lock round
  build 128 pairs
  Gemini stutter loop
  commit verdicts one-by-one
  fill from Gate
```

**Hosting:** Cloudflare (Pages + Worker + D1/Postgres + R2 + Cron Triggers) is the cheapest shape and matches how Pollinations itself is built. A $5–10 VPS + Caddy + Postgres is simpler to reason about. Either works at 256 fighters.

**Storage:** 256 live portraits ≈ 100–400 MB. 128 deaths/day × 400 KB ≈ 50 MB/day ≈ **18 GB/year**. R2 is cents.

**Do not** run BLIP/Qwen/Florence in the web path. This repo’s local models are for analysis, not production judging.

### Minimal schema

```sql
users          (id, display, pollinations_key_enc, pollen_connected_at, tz)
generation_ledger (user_id, utc_date, count)  -- cap 10
fighters       (id, user_id, name, prompt, image_url, wins, status, ladder_pos, scout_json)
rounds         (id, starts_at, status)        -- pending|running|complete|stalled
matches        (id, round_id, left_id, right_id, winner_id, narration, raw_json, attempts)
graveyard      (fighter_id, died_at, killer_id, match_id)
gate_queue     (fighter_id, enqueued_at)
```

---

## 7. Dark-theme UX (enough to ship, not a DreadPit skin)

Keep the sport, change the coat of arms.

- Background `#070605`, bone text, one accent (copper or sickly green — not DreadPit blood `#b8181b` + gold).
- Ladder as a **vertical strip of 256**, current pair highlighted, losers greying into a graveyard drawer.
- During the 15–40 min judging window: a **live feed** of verdicts appearing, not a spinner. Stutter is a feature if you show “Arbiter delayed — retrying.”
- Summoning: prompt box (200 chars), “10 sparks remain today,” a 2×5 contact sheet, click to enter the Gate.
- Spectate: one match at a time, two portraits, then the narration typewriter.

This repo already has the visual language in `abyssal_page.html` / `quiet_vs_abyssal.html` as **reference for what players expect**, not as a template to copy.

---

## 8. Risks that actually kill this

1. **Free Gemini is not a contract.** Google cut Flash free quota ~50–80% in late 2025 and yanked Pro from free in April 2026. Design the stutter + Lite fallback on day one. Keep a **paid Gemini project** with a $10 hard cap for production, a **free project** for toys. Enabling billing on a project silently deletes its free tier.
2. **BYOP key in your database.** If you get phished or leaked, you spend other people’s Pollen. Prefer client-side gen for MVP.
3. **Judge inconsistency.** Same two images at temp 0 are *usually* stable; they are not a hash. Players will reroll screenshots. Cache the verdict forever; never rejudge a closed match.
4. **Prompt leakage / power-essay meta.** Sight-only judging. This repo’s whole point.
5. **FLUX render traps.** Mummy, pure shield, “fighter IS a building” — see `LESSONS_LEARNED.md`. Show those as summoning hints, or players will rage at the forge, not the pit.
6. **Safety filters.** Both Flux and Gemini will refuse gore / sexual / real-person looks. Have a “the forge rejected this” state, refund the generation slot, do not charge a death.
7. **Pollinations as SPOF.** No SLA. Cache every portrait the moment it lands. If gen.pollinations.ai dies at 11:59, today’s roster still fights.
8. **Legal / social.** A DreadPit clone with their voice will get you a C&D and a community that already has a pit. Ship a different myth. Cite Pollinations as required by their ecosystem norms; submit the app to their showcase if you want tier credit.
9. **`pk_` vs `sk_` footgun.** One wrong header and you are IP-throttled to nothing. Test this on day one.
10. **Content custody.** You store every prompt and portrait. ToS + privacy page before the first user. Graveyard “sealed forever” is a product promise — honor it, including against the summoner’s delete request *or* don’t make the promise.

---

## 9. What this repo already proves you can reuse

| Asset | Use on the website? |
|---|---|
| Pollinations FLUX URL + seed + 3× retry (`generate_fighter_images.py`, `battle_simulator.py`) | **Yes** — that’s the summoning backend |
| 200-char visual prompt discipline + `LESSONS_LEARNED.md` | **Yes** — show as forge hints |
| Gemini-as-arbiter psychology (glow → invented power, passivity dies, architecture-as-body fails) | **Yes** — write the system prompt from this, not from vibes |
| BLIP + NN win predictor | **No** for live matches. Optional “scout estimate” toy, clearly labeled as unofficial |
| DreadPit scraped HTML / portraits / fight narrations | **No** in the product. Analysis only |

---

## 10. Suggested build order

**Week 1 — Forge only (no fights)**
- Site auth
- BYOP connect / disconnect / expiry banner
- Flux contact sheet, 10/day ledger, pick-one, R2 upload
- Gate queue + 256 cap

**Week 2 — Pit**
- Gemini JSON judge on two stored portraits
- Stutter worker + round table
- Ladder + graveyard pages
- Countdown clock

**Week 3 — Sport**
- Adjacent pairing + odd-day offset
- Live verdict feed
- Reconnect-Pollen flow
- Lite fallback, 768px downscale, $10 Gemini cap

**Week 4 — Hardening**
- Don’t start round N+1 if N is stalled
- Safety-filter refund of a generation slot
- Basic ToS / privacy
- Load-test 128 sequential Gemini calls once, on the paid project

Skip: battle-scene image gen (doubles Pollen use, doubles failure modes, the sport is portraits), self-hosted VLMs, premium Pollinations models, twice-daily rounds.

---

## 11. Bottom line

The website is **possible, cheap, and well-matched to existing APIs**.

- **Users import Pollinations via official BYOP.** Default to Flux so 10 images/day cost them **0 Pollen**. Use their `sk_`, never your `pk_`.
- **You run Gemini Flash (3.7, Lite fallback) once per match.** 128 requests is well under free RPD; **RPM and 429s** are the design constraint. Stutter + persist. Optionally pay ~$10–15/mo for a real quota.
- **256 living / 128 matches / 24h** is a persistent single-life ladder, not a full bracket. Build that.
- **Operator cost can be ~$0 in AI** and should still be designed as if Gemini will 429 for an hour.
- The thing that is *not* free is taste: a dark pit that is not DreadPit, a judge that only looks at pictures, and a round that can pause without corrupting the ladder.

If the next step is a build, start with Week 1 (BYOP + 10 Flux rolls + Gate). The arbiter is the easy API call. The account import is the product.
)
