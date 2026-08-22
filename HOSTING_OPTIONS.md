# Cheapest / free hosting for the Kiln

**Date:** 2026-08-22
**Workload:** Node 22 + Express API, `node:sqlite` (persistent disk), local uploads for
portraits under `kiln/data/uploads`, a Vite/React client (buildable to static),
outbound Gemini vision calls (cheap/free), and a daily scheduled round.

---

## 1. The one thing that decides everything: persistent disk + a real scheduler

This app is **not** a good fit for generic serverless/PaaS free tiers, and it's not
because of performance. It's because of two hard requirements:

1. **Persistent local disk.** The DB is SQLite (`kiln/data/kiln.sqlite`) and portraits
   live on disk (`kiln/data/uploads`). On most free PaaS (Render, Fly, Railway,
   Koyeb, Northflank services) the container filesystem is **ephemeral** — it is
   wiped on deploy/restart. You'd hit one of these:
   - lose the roster and every portrait,
   - or have to move to a managed database (Postgres/Redis) + object storage (R2/S3),
     which means a rewrite of `db.js`, `app.js`, and the upload path.
   
   A real **VPS with a block/boot volume** avoids all of this: SQLite + files just work.

2. **A reliable daily trigger.** `tick()` is idempotent, so it can be driven by either
   the in-process poller (`KILN_POLL=1`, a long-lived process) or by a cron running
   `npm run round` (`KILN_POLL=0`). Purely serverless free tiers that can't keep a
   process alive (or that cap CPU at ~10 ms) make this awkward.

So the cheapest *actually works* answer is a small **always-on VM you run yourself**,
not a PaaS free tier.

---

## 2. Comparison (2026 free tiers)

| Host | Cost | Always-on? | Persistent disk | Cron built in | Card to start | Fits "just deploy" | Fit for Kiln |
|---|---|---|---|---|---|---|---|
| **Oracle Cloud Always Free (Ampere A1)** | **$0** | Yes | **Yes (200 GB block)** | Yes (systemd/cron) | Yes (identity) | Needs a few hours setup | **Best fit** |
| **Northflank Sandbox** | **$0** | Yes | Service FS is ephemeral (has a managed DB add-on) | Yes (2 crons) | Yes | Easy | Good, but needs Postgres/R2 rewrite for persistence |
| **Render Free** | **$0** | No — sleeps after 15 min | No | Cron requires paid tier | No | Easiest | Demo only; loses data, and no free cron |
| **Koyeb Free** | **$0** | No — scale to zero after ~1 h | No | Limited | Yes | Easy | Demo only; loses data |
| **Railway** | $5 trial / ~$1 credit | Yes (while credit) | No | Yes | No | Smooth | Trial only |
| **Cloudflare Workers + D1** | **$0** | Yes (edge) | D1 yes, images need R2 | Yes (Cron, 5 triggers) | No | Needs full rewrite | Heavy rewrite; free CPU limit is very tight for the judge loop |
| **GitHub Pages** | **$0** | Static only | n/a | Via Actions (delayed, UTC) | No | Trivial | Static/demo only — gives you the browser-local fallback, not real shared fires |

Details behind the table:

- **Oracle Cloud Always Free** currently offers up to **2 OCPU / 12 GB** of ARM
  (Ampere A1) compute "always free" on the docs, with **200 GB block storage** and
  ~10 TB/mo egress. Some accounts still see 4 OCPU / 24 GB; the stable, documented
  number is 2/12. It does not expire. Downsides: it's a full VM (you install Node,
  Caddy/Nginx, systemd), ARM (all fine for Node 22), capacity can be out in some
  regions, and Oracle warns about reclaiming idle Always-Free VMs — so keep real
  traffic/activity (a continuous server + a weekly touch does this).
- **Northflank Sandbox** is the strongest *always-on PaaS* free tier: 2 always-on
  services, 1 managed database, 2 cron jobs, no sleeping. But the service filesystem
  is ephemeral, so to keep it production-correct you'd point the app at their
  managed Postgres for `db.js` and object storage for uploads — a real port.
- **Render free** is the easiest to try: no credit card, 512 MB, 750 hr/mo, but it
  **sleeps after 15 min**, cold starts are 30–60 s, **cron jobs are on paid plans**,
  and the filesystem is ephemeral. Fine for a demo; not for a live daily ladder.
- **Cloudflare Workers** is genuinely $0 and never sleeps, but the free tier caps CPU
  at ~10 ms and the free *Bundled* model isn't meant for a 15–40 min loop of
  sequential Gemini calls. You'd also rewrite Express + SQLite into Worker + D1 + R2.
- **GitHub Pages** is already in this repo (`/docs`, free, static). It's the right
  place for the **browser-local demo** (which the code already supports), but it does
  **not** run the shared SQLite/Gemini scheduler.

---

## 3. Recommendation

### Best "free server that can host this" → Oracle Cloud Always Free VM

- One `VM.Standard.A1.Flex` (e.g. 2 OCPU / 12 GB, ARM).
- Install Node 22 (or use a Node Docker image), clone this repo, `npm ci`.
- `npm run dev` (or a systemd service) keeps the server up. Leave `KILN_POLL=1` as the
  default so the 15 s in-process poller is the trigger — no cron needed for the daily
  round, and a continuously-running process also keeps the Oracle idle-reclaimer away.
- **Optionally** add a systemd timer for a belt-and-suspenders `npm run round` at the
  fire hour (set `KILN_POLL=0` *only* if you want cron to be the sole trigger).
- For HTTPS + a real domain: a single Caddyfile reverse-proxies `:80/:443` → `:3000`.
  Caddy and Let's Encrypt are free.

Cost after Gemini/Pollinations (which are themselves free/BYOP): **$0/mo.**

### Easiest zero-ops path that's genuinely always-on → Northflank Sandbox (with a small port)

- Deploy the Node container, add their managed Postgres, and change `db.js` to Postgres
  (or, simpler, keep SQLite but wire a persistent volume — Northflank's free service
  tier may not include a volume, so this is the "about $0 but some work" option).
- Their 2 free cron jobs fit the daily `npm run round` trigger nicely.

### Try-it-now/demo path → GitHub Pages (static) + Render free (API)

- Keep the `/docs` GitHub Pages gallery for the static/browser-local experience.
- Put the real API on Render free only if you only need a toy; you'd need to add
  `KILN_POLL=1` plus an external keep-alive/cron-workaround because Render sleeps and
  its cron is paid. Not recommended as the production home.

---

## 4. What NOT to do (for this codebase)

- **Don't assume a free PaaS "just works" with SQLite/uploaded images.** Most free
  tiers give you an ephemeral filesystem. You'll silently lose the roster.
- **Don't switch to Render/Koyeb and expect the nightly fire to happen on free plans.**
  They sleep when idle, and their free tiers don't reliably host your daily job. That
  is precisely the "won't fire in time" failure mode.
- **Don't go Cloudflare Workers free expecting to run the existing Express app.** It's
  a different runtime; the free CPU cap makes the sequential judge loop impractical
  without a paid plan and a rewrite.

---

## 5. The smallest paid fallback (if you later want zero maintenance)

| Option | ~$/mo | Why |
|---|---|---|
| DigitalOcean / Vultr $4–6 droplet | ~$4–6 | Real disk, any stack, easy `npm` + `pm2` + Caddy |
| Hostinger VPS (long term) | ~$4–6 | Similar, cheap |
| Render Starter / Northflank PAYG | ~$5–7 | Always-on, but still ephemeral disk → DB rewrite |

For a persistent, free, always-on host that runs this code **without a rewrite**, the
Oracle Cloud Always Free ARM VM is the clear choice.
