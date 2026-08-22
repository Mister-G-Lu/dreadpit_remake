# Kiln on Oracle Cloud Always Free (ARM)

Deploy the real Kiln (Node 22 + Express + SQLite + Gemini, plus the Vite client)
onto an **Oracle Cloud Always Free** ARM VM. This is the only free host that gives
you both things this app needs:

- **persistent disk** for SQLite (`kiln/data/kiln.sqlite`) and portraits
  (`kiln/data/uploads`), and
- a **real always-on process** you can run the daily `tick()` round from.

`HOSTING_OPTIONS.md` (repo root) explains why free PaaS tiers don't fit this
codebase without a database/storage rewrite.

---

## 0. What you get in this folder

| File | Purpose |
|---|---|
| `setup.sh` | One-shot provisioning: Node 22 ARM, git, Caddy, systemd units, env, build. Run with `sudo`. |
| `kiln.service` | systemd unit that keeps the API + the 15s in-process round poller alive. |
| `kiln-round.service` / `.timer` | Optional belt-and-suspenders `npm run round` timer. **Only use with `KILN_POLL=0`.** |
| `caddy.service` | systemd unit for Caddy (installed as a plain binary by `setup.sh`). |
| `Caddyfile.template` | Caddy reverse proxy: `:80` HTTP by default, HTTPS block if you set a domain. |
| `kiln.env.example` | `/etc/kiln.env` template the app service reads. |
| `update.sh` | Pull latest repo, rebuild, restart the service. Run with `sudo`. |
| `README.md` | This file. |

A note on the fire trigger: `setup.sh` leaves the in-process poller **on**
(`KILN_POLL=1`) and does **not** enable the systemd round timer. That means the
single long-lived Node service is the one trigger, which is the safe default for
one VM. **Do not enable the round timer while `KILN_POLL=1`** — two processes can
then race on the same round (the code's `ticking` guard is per-process, not a DB
lock). If you want cron to own the fire, set `KILN_POLL=0` in `/etc/kiln.env` and
enable the timer.

---

## 1. Create the Oracle VM (in the OCI console)

1. Sign in at https://cloud.oracle.com → **Create a VM instance**.
2. **Image:** Ubuntu 22.04/24.04 or Oracle Linux 9 (the script supports both).
3. **Shape:** `VM.Standard.A1.Flex` (ARM). Put **2 OCPU / 12 GB** (or 4/24 if your
   region/console still offers it). This is the Always Free ARM allocation — do
   **not** pick a paid shape.
4. **Boot volume:** 50 GB is plenty (free block storage is 200 GB total).
5. Add your **SSH public key**. Record the public IP.
6. **Security list / NSG:** make sure ingress allows **TCP 22, 80, 443** from
   `0.0.0.0/0` (the OCI console "default" security list usually already has 22).

If the console says *out of capacity* for Ampere A1, try a different region or
retry later; that's a common Oracle quirk, not a config problem.

---

## 2. SSH in and scaffold

```bash
ssh ubuntu@YOUR_PUBLIC_IP     # Ubuntu image
# or ssh opc@YOUR_PUBLIC_IP    # Oracle Linux image
```

```bash
sudo bash -c 'curl -fsSL https://raw.githubusercontent.com/Mister-G-Lu/dreadpit_remake/main/deploy/oracle/setup.sh -o /tmp/kiln-setup.sh && bash /tmp/kiln-setup.sh'
```

Better, clone the repo on your **local** machine and scp the `deploy/oracle` folder up
so you don't depend on the repo being public:

```bash
scp -r deploy/oracle ubuntu@YOUR_PUBLIC_IP:/tmp/
ssh ubuntu@YOUR_PUBLIC_IP 'sudo bash /tmp/oracle/setup.sh'
```

`setup.sh` will:
- install Node 22 (arm64 tarball), git, curl, Caddy,
- create `kiln` and `caddy` system users,
- clone `https://github.com/Mister-G-Lu/dreadpit_remake.git` to `/opt/dreadpit_remake`
  (set `REPO_URL` / `REPO_BRANCH` first if your repo is private you need a deploy key
  or a different url),
- `npm ci` + `npm run build` in `kiln/`,
- write `/etc/kiln.env` from the template (ask you for `GEMINI_API_KEY` and `DOMAIN`),
- install `kiln.service` and `caddy.service`,
- print the firewall rule to add to your OCI security list.

If the repo is **private**, pre-stage it instead and run setup from the staged copy;
the script uses `git clone` unless `/opt/dreadpit_remake` already exists.

---

## 3. Put your secrets in `/etc/kiln.env`

`setup.sh` creates it from `kiln.env.example`. Edit it:

```bash
sudo nano /etc/kiln.env
```

At minimum:

```bash
NODE_ENV=production
PORT=3000
HOST=0.0.0.0
GEMINI_API_KEY=YOUR_GEMINI_KEY
GEMINI_MODEL=gemini-2.5-flash
FIRE_UTC_HOUR=12
KILN_POLL=1
BATCH_SIZE=10
BATCH_INTERVAL_MS=3600000
```

Start the app:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kiln
sudo systemctl status kiln
```

---

## 4. HTTPS (Caddy)

If you set a `DOMAIN` during setup, Caddy got the HTTP block. To get real HTTPS,
edit `/etc/caddy/Caddyfile` and use the `{$DOMAIN}` block (or our template's
HTTPS section), then:

```bash
# make sure the DNS A record for your domain points at the VM's public IP
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

If you have no domain yet, the `:80` HTTP block already reverse-proxies to
`127.0.0.1:3000`. You can still use the site over HTTP; for a public game you want
a domain + TLS.

Firewall (Oracle Linux / Ubuntu in the OS, in addition to the OCI security list):

```bash
# Ubuntu / Debian
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp

# Oracle Linux 8/9
sudo firewall-cmd --permanent --add-service=http --add-service=https --add-service=ssh
sudo firewall-cmd --reload
```

**Do not expose port 3000 publicly.** The app listens on `3000` only for Caddy
(`127.0.0.1:3000`). Your OCI security list / NSG should allow inbound `22`, `80`,
and `443` only — leave `3000` closed (and make sure `ufw`/`firewall-cmd` does too).

---

## 5. Optional: cron-only fire (only if you *don't* use the poller)

This is the DreadPit-style path. Only do this if you set `KILN_POLL=0` in
`/etc/kiln.env`:

```bash
sudo systemctl enable --now kiln-round.timer
```

If you leave `KILN_POLL=1` (recommended for this single-VM setup), leave the timer
**stopped/disabled**. See the note in the table above.

---

## 6. Deploy updates

From the VM (or after `git pull` locally / CI, then pull on the VM):

```bash
sudo bash /opt/dreadpit_remake/deploy/oracle/update.sh
```

That does `git pull --ff-only`, `npm ci`, `npm run build`, and `systemctl restart kiln`.

---

## 7. Verify

```bash
curl -s http://127.0.0.1:3000/api/health
# -> {"ok":true,"name":"kiln"}

curl -s http://YOUR_PUBLIC_IP/api/state | head -c 400
# live clock, roster, round status

sudo journalctl -u kiln -f
# should show "[kiln] listening" and, at the fire hour,
# "[kiln] round N opened" / "[kiln] firing batch ..."
```

The static Vite client is served by the Node process at `NODE_ENV=production`, so
you don't need a separate static host — `http://YOUR_PUBLIC_IP/` is the full app.

---

## 8. Staying under Oracle's Always-Free rules

- Keep the instance **running** and reasonably active (the Kiln service touches
  SQLite every 15s via `tick()`, which is enough activity).
- Don't stop the VM for long stretches — Oracle may repurpose idle Always-Free
  instances.
- Stay within the Always-Free ARM limits (2 OCPU / 12 GB as of mid-2026; some
  regions still show 4/24).
- Back up `kiln/data/` (SQLite + uploads) + `/etc/kiln.env` regularly — it's your
  entire state.

---

## References

- `HOSTING_OPTIONS.md` — why this hosting choice.
- `DREADPIT_SCHEDULING.md` — the daily-fire model the timer/poller implements.
- `kiln/README.md` — app config + the `KILN_POLL` / `FIRE_UTC_HOUR` knobs.
