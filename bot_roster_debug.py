#!/usr/bin/env python3
"""
Diagnostic: why are known bots (Abyssal Fiend, Hex Enforcer, Quiet Fighter)
missing from bot_roster.json?

Hypotheses to test:
  H1: bots are present in the graveyard list but with isBot=false there
      (list endpoint and detail endpoint disagree).
  H2: bots are NOT present in the graveyard/leaderboard lists at all.
  H3: they are present and flagged, but the collector's merge dropped them.
"""
import json
import subprocess
import time

BASE = "https://dreadpit.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGE = 100
KNOWN = {
    "9e1fdb2d-12c6-4996-bdae-29d647fb3c43": "Abyssal Fiend",
    "02cd2dc6-c796-4f3e-87ba-3a125d9cfa5d": "Hex Enforcer",
    "b43563ba-047c-4162-840d-8be1c9c6b68a": "Quiet Fighter",
    "84805b89-6867-4890-9203-4181fc2c3768": "Thorn Spirit",
    "2f77dea2-363b-44a5-b9e3-3e54191e442b": "Echo Psion",
    "131c2500-62c3-4ee8-ba83-a71e5d44c647": "Quantum Dreadnought",
}


def get_json(url):
    raw = subprocess.run(["curl", "-s", url, "-H", f"User-Agent: {UA}"],
                         capture_output=True, timeout=60).stdout
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def main():
    # 1) Detail endpoint truth
    print("[1] DETAIL endpoint isBot truth:", flush=True)
    for fid, label in KNOWN.items():
        d = get_json(f"{BASE}/api/fighters/{fid}")
        print(f"  {label:20s} isBot={d.get('isBot') if d else 'ERR'} wins={d.get('wins') if d else '?'}", flush=True)

    # 2) Scan graveyard pages for these ids, record their isBot in the list
    print("\n[2] Scanning full graveyard for known ids...", flush=True)
    found = {}
    bot_flagged = 0
    total = 0
    for page in range(80):
        url = f"{BASE}/api/graveyard?limit={PAGE}&offset={page*PAGE}"
        data = get_json(url)
        if not data or "items" not in data:
            print(f"  stopped page {page}", flush=True)
            break
        batch = data["items"]
        total += len(batch)
        for it in batch:
            if it.get("isBot"):
                bot_flagged += 1
            if it["id"] in KNOWN:
                found[it["id"]] = (it.get("isBot"), it.get("name"))
        if len(batch) < PAGE:
            print(f"  complete at page {page} ({total} total, {bot_flagged} isBot=True)", flush=True)
            break
        time.sleep(0.25)

    print("\n[3] Known ids found in graveyard list:", flush=True)
    for fid, label in KNOWN.items():
        if fid in found:
            print(f"  {label:20s} present, isBot in list = {found[fid][0]}", flush=True)
        else:
            print(f"  {label:20s} NOT present in graveyard list at all", flush=True)

    # 3) Also scan leaderboard
    print("\n[4] Scanning leaderboard for known ids...", flush=True)
    for page in range(5):
        url = f"{BASE}/api/leaderboard?limit={PAGE}&offset={page*PAGE}"
        data = get_json(url)
        if not data or not isinstance(data, list):
            break
        for it in data:
            f = it.get("fighter", {})
            if f.get("id") in KNOWN:
                print(f"  {KNOWN[f['id']]:20s} in leaderboard, isBot={f.get('isBot')}", flush=True)
        if len(data) < PAGE:
            break
        time.sleep(0.25)

    print("\nDONE. Total graveyard entries seen:", total, flush=True)


if __name__ == "__main__":
    main()
