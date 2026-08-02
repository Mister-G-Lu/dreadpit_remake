#!/usr/bin/env python3
"""
DREADPIT BOT COLLECTOR  (v3 - cross-reference harvest, cache-safe)

Problem: the graveyard + leaderboard LIST endpoints EXCLUDE bots (a full scan
of 7,655 graveyard entries found 0 isBot=True; the only bots visible are alive
ones on the leaderboard). Dead bots (Abyssal Fiend, Hex Enforcer, Quiet
Fighter...) are invisible to list-based collection.

Fix: harvest bot IDs from cross-references:
  1. Every graveyard entry carries killedById (the fighter that killed it) --
     so EVERY bot that ever won a fight appears as someone's killer.
  2. Every fight record carries opponentId -- so BFS through a bot's opponents
     finds bots that lost (to other bots) but never killed anyone.
  3. Leaderboard fighters are fetched directly (alive bots).

Known limitation: a bot that never won a fight AND only ever fought humans
(never another bot) cannot be discovered this way. For a wins ranking that is
acceptable -- any bot with >=1 career win is reachable via killedById.

Then pulls true career wins from /fights (the API 'wins' field is unreliable).

Outputs:
  bot_roster.json   -- every bot found, with API wins + career record
  bot_ranking.json  -- bots sorted by true career wins
  fighter_detail_cache.json -- disk cache of all fetched fighter details
"""
import json
import os
import subprocess
import time

BASE = "https://dreadpit.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGE = 100
MAX_PAGES = 80
RETRIES = 3
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fighter_detail_cache.json")
CACHE_TMP = CACHE + ".tmp"
SAVE_EVERY = 25  # persist cache every N new fetches


def get_bytes(url):
    out = subprocess.run(["curl", "-s", url, "-H", f"User-Agent: {UA}"],
                         capture_output=True, timeout=60)
    return out.stdout


def get_json(url):
    for attempt in range(RETRIES):
        try:
            raw = get_bytes(url)
            if not raw:
                time.sleep(2 * (attempt + 1))
                continue
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"    retry {attempt+1}/{RETRIES} after parse fail: {e}", flush=True)
            time.sleep(2 * (attempt + 1))
    return None


def load_cache():
    """Load the detail cache, salvaging a corrupt file if needed."""
    if not os.path.exists(CACHE):
        return {}
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt (e.g. killed mid-write). Try to salvage the last valid entry.
        print("  cache corrupt -- attempting salvage", flush=True)
        try:
            raw = open(CACHE, encoding="utf-8").read()
            cut = raw.rfind("},\n", 0, len(raw))
            if cut == -1:
                cut = raw.rfind("}\n", 0, len(raw))
            if cut != -1:
                return json.loads(raw[:cut] + "}")
        except Exception:
            pass
        return {}


def save_cache(cache):
    """Persist cache. Prefer atomic tmp+rename; fall back to direct write on
    Windows PermissionError (destination momentarily held) so a rare lock
    can't kill a long run. On any failure, skip -- the cache is only for
    resumability.

    career_* fields are per-run analysis data (see harvest_bots) and must NOT
    be persisted: a stale career_* in the cache could mask a later /fights
    failure and produce a wrong ranking."""
    sanitized = {
        k: {kk: vv for kk, vv in v.items() if not kk.startswith("career_")}
        for k, v in cache.items()
    }
    tmp = CACHE_TMP
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, ensure_ascii=False)
        try:
            os.replace(tmp, CACHE)
        except OSError:
            # Destination locked (Windows). Try direct write to CACHE.
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(sanitized, f, ensure_ascii=False)
    except Exception as e:
        print(f"  !! cache save skipped: {e}", flush=True)


def collect(endpoint, label, shape):
    """Page through a list endpoint. Returns raw items (graveyard) or fighters (leaderboard)."""
    items = []
    hit_cap = False
    for page in range(MAX_PAGES):
        offset = page * PAGE
        url = f"{BASE}{endpoint}?limit={PAGE}&offset={offset}"
        data = get_json(url)
        if data is None:
            print(f"  {label}: parse failure at page {page} -- retries exhausted", flush=True)
            break
        if shape == "items":
            if "items" not in data:
                break
            batch = data["items"]
        else:
            if not isinstance(data, list):
                break
            batch = [it["fighter"] for it in data if isinstance(it, dict) and "fighter" in it]
        items.extend(batch)
        if len(batch) < PAGE:
            print(f"  {label}: complete at page {page} ({len(items)} total)", flush=True)
            break
        if page == MAX_PAGES - 1:
            hit_cap = True
        time.sleep(0.3)
    if hit_cap:
        print(f"  !! {label}: hit MAX_PAGES cap -- may be truncated!", flush=True)
    return items


def get_fighter(fid, cache):
    """Fetch fighter detail, using+updating the in-memory cache.
    Returns (detail_or_None, was_cached: bool)."""
    if fid in cache:
        return cache[fid], True
    d = get_json(f"{BASE}/api/fighters/{fid}")
    if d:
        cache[fid] = d
    return d, False


def fetch_career(fid):
    """Return (fights, wins, losses) via /fights, or (None, 0, 0) on failure."""
    fights = get_json(f"{BASE}/api/fighters/{fid}/fights")
    if fights is None:
        return None, 0, 0
    w = sum(1 for f in fights if f.get("won"))
    return fights, w, len(fights) - w


def harvest_bots(graveyard, leaderboard, cache):
    """
    Find every bot via cross-references (see module docstring).
    Returns (bots dict id->detail, fetches_count).
    """
    bots = {}
    fresh_career = set()   # bot ids whose /fights were fetched THIS run
    for it in graveyard + leaderboard:
        if it.get("isBot"):
            bots[it["id"]] = it

    candidates = set()
    for it in graveyard:
        kid = it.get("killedById")
        if kid:
            candidates.add(kid)

    checked = set()
    expanded = set()   # bots whose /fights we've already attempted this run
    queue = list(candidates)
    fetches = 0
    print(f"  harvest candidates (killer refs): {len(candidates)}", flush=True)
    while queue:
        fid = queue.pop()
        if fid in checked:
            continue
        checked.add(fid)
        d, was_cached = get_fighter(fid, cache)
        if not was_cached:
            fetches += 1
        if d and d.get("isBot"):
            bots[fid] = d
        # Expand fights for any bot (seeded or discovered) so bot-vs-bot chains
        # rooted anywhere get explored. Store career data here so main() does
        # not re-fetch /fights a second time.
        if d and d.get("isBot") and fid not in expanded:
            expanded.add(fid)
            fights, w, losses = fetch_career(fid)
            if fights is not None:
                fresh_career.add(fid)
                d["career_fights"] = len(fights)
                d["career_wins"] = w
                d["career_losses"] = losses
                for f in fights:
                    oid = f.get("opponentId")
                    if oid and oid not in checked:
                        queue.append(oid)
            else:
                # Transient /fights failure: clear any stale career_* (e.g.
                # from an old un-sanitized cache) so main() retries instead of
                # silently ranking off last run's numbers.
                for k in ("career_fights", "career_wins", "career_losses"):
                    d.pop(k, None)
            time.sleep(0.2)
        if fetches % SAVE_EVERY == 0 and fetches > 0:
            save_cache(cache)
        if not was_cached:
            time.sleep(0.1)
        if len(bots) % 25 == 0 and len(bots) > 0:
            print(f"  ...{len(bots)} bots found (checked {len(checked)})", flush=True)
    return bots, fetches, fresh_career


def main():
    print("=" * 70, flush=True)
    print("  DREADPIT BOT COLLECTOR v3 (cross-reference harvest)", flush=True)
    print("=" * 70, flush=True)

    cache = load_cache()
    print(f"  loaded cache: {len(cache)} fighters", flush=True)

    print("\n[1] Scraping graveyard...", flush=True)
    graveyard = collect("/api/graveyard", "graveyard", shape="items")
    print("[2] Scraping alive leaderboard...", flush=True)
    leaderboard = collect("/api/leaderboard", "leaderboard", shape="list")
    print(f"  graveyard={len(graveyard)} leaderboard={len(leaderboard)}", flush=True)

    print("\n[3] Harvesting bots via cross-references...", flush=True)
    bots, fetches, fresh_career = harvest_bots(graveyard, leaderboard, cache)
    print(f"  Bots found: {len(bots)} (fetched {fetches} details this run)", flush=True)
    save_cache(cache)

    print("[4] Pulling career records via /fights (only where missing)...", flush=True)
    bot_list = list(bots.values())
    for i, b in enumerate(bot_list):
        if b.get("career_fights") is not None and b["id"] in fresh_career:
            continue  # captured fresh during this run's harvest expansion
        fid = b["id"]
        fights, w, losses = fetch_career(fid)
        if fights is None:
            b["career_fights"] = 0
            b["career_wins"] = 0
            b["career_losses"] = 0
        else:
            b["career_fights"] = len(fights)
            b["career_wins"] = w
            b["career_losses"] = losses
        if (i + 1) % 10 == 0 or i == len(bot_list) - 1:
            print(f"    {i+1}/{len(bot_list)} bots done", flush=True)
        time.sleep(0.2)

    with open("bot_roster.json", "w", encoding="utf-8") as f:
        json.dump(bot_list, f, indent=2, ensure_ascii=False)

    ranking = sorted(bot_list, key=lambda b: -b.get("career_wins", 0))
    with open("bot_ranking.json", "w", encoding="utf-8") as f:
        json.dump(ranking, f, indent=2, ensure_ascii=False)

    print("\n[5] TOP 25 BOTS BY TRUE CAREER WINS", flush=True)
    print("-" * 70, flush=True)
    for i, b in enumerate(ranking[:25], 1):
        print(
            f"  {i:2d}. {b.get('career_wins',0):3d}w/{b.get('career_fights',0):3d}f "
            f"(api {b.get('wins',0):3d})  {b.get('name','?')[:45]}",
            flush=True,
        )
    print("\nSaved: bot_roster.json + bot_ranking.json", flush=True)


if __name__ == "__main__":
    main()
