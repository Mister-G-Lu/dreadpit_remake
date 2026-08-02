#!/usr/bin/env python3
"""
Comprehensive DreadPit Dataset Builder.

Queries the API to collect:
1. ALL graveyard fighters with 5+ wins (paginated)
2. Recent round data to get winner/loser matchups
3. Downloads ALL portraits (winners AND losers)
4. Cross-references visual features from BLIP analysis against wins

Creates the most complete dataset possible for visual analysis.
"""

import json
import os
import sys
import time
import urllib.request
from collections import Counter, defaultdict

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
API_BASE = "https://dreadpit.com"


def fetch_json(url, timeout=15):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(r.read().decode())
    except Exception as e:
        return None


def download_portrait(fighter, prefix=""):
    """Download a fighter's portrait. Returns filename or None."""
    fid = fighter.get("id", "unknown")[:12]
    name = fighter.get("name", "?")[:30]
    url = fighter.get("imageUrl", "")
    if not url:
        return None
    
    # Clean name for filename
    safe_name = ""
    for c in name:
        if c.isalnum() or c in '._- ':
            safe_name += c
        else:
            safe_name += '_'
    safe_name = safe_name.strip().strip('_')
    
    filename = f"{prefix}{fid}_{safe_name}.png"
    path = os.path.join(PORTRAIT_DIR, filename)
    if os.path.exists(path):
        return filename
    
    try:
        r = urllib.request.urlopen(f"{API_BASE}{url}", timeout=15)
        with open(path, "wb") as f:
            f.write(r.read())
        return filename
    except Exception:
        return None


def main():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    
    print("=" * 72)
    print("  DREADPIT COMPREHENSIVE DATASET BUILDER")
    print("=" * 72)
    
    # ============================
    # STEP 1: Paginate graveyard for ALL 5+ win fighters
    # ============================
    print("\n[1/4] Paginating graveyard for ALL fighters with 5+ wins...")
    
    all_high_winners = []
    total_count = None
    
    for offset in range(0, 5000, 100):
        url = f"{API_BASE}/api/graveyard?limit=100&offset={offset}&sort=wins"
        data = fetch_json(url)
        if not data or "items" not in data:
            print(f"  Stopping at offset {offset}: no data")
            break
        
        items = data.get("items", [])
        if not items:
            print(f"  Stopping at offset {offset}: empty")
            break
        
        # Filter to 5+ wins
        high = [f for f in items if f.get("wins", 0) >= 5]
        all_high_winners.extend(high)
        
        # Check if there are any monsters? fighters with < 5 wins (meaning we've passed the threshold)
        if items and items[-1].get("wins", 0) < 5:
            print(f"  Stopping at offset {offset}: below 5-win threshold")
            break
        
        print(f"  offset={offset}: got {len(items)} fighters, {len(high)} with 5+ wins (total so far: {len(all_high_winners)})")
        
        # Rate limit
        time.sleep(0.3)
    
    print(f"\n  TOTAL: {len(all_high_winners)} fighters with 5+ wins")
    
    # Save metadata
    with open(os.path.join(CACHE_DIR, "all_high_winners.json"), "w") as f:
        json.dump(all_high_winners, f, indent=1)
    print(f"  Saved to: all_high_winners.json")
    
    # ============================
    # STEP 2: Fetch recent rounds for matchup data
    # ============================
    print("\n[2/4] Fetching recent round/fight data...")
    
    # Try the single round endpoint first, then look for more
    round_data = fetch_json(f"{API_BASE}/api/round")
    if round_data:
        round_id = round_data.get("round", {}).get("id", "?")
        print(f"  Current round: {round_id}")
        
        # Extract fighters from this round
        fighters_in_round = round_data.get("fighters", [])
        print(f"  Fighters in current round: {len(fighters_in_round)}")
        for f in fighters_in_round:
            name = f.get("name", "?")
            wins = f.get("wins", 0)
            print(f"    {name:45s} ({wins} wins)")
    
    # Try to find historical rounds
    # Check if there's a rounds list endpoint
    for endpoint in ["rounds", "rounds?limit=50", "round-history", "history", "fights"]:
        test_url = f"{API_BASE}/api/{endpoint}"
        test_data = fetch_json(test_url, timeout=10)
        if test_data:
            print(f"  Found endpoint: /{endpoint} -> {type(test_data).__name__}")
            if isinstance(test_data, list):
                print(f"    {len(test_data)} items")
            elif isinstance(test_data, dict):
                print(f"    keys: {list(test_data.keys())[:5]}")
            break
        else:
            print(f"  No endpoint: /{endpoint}")
    
    # ============================
    # STEP 3: Download ALL portraits (winners + round participants)
    # ============================
    print("\n[3/4] Downloading all portraits...")
    
    portrait_manifest = []
    
    # Download all 5+ win fighters
    for i, f in enumerate(all_high_winners):
        name = f.get("name", "?")
        wins = f.get("wins", 0)
        filename = download_portrait(f, f"{wins}w_")
        status = "OK" if filename else "FAIL"
        if filename:
            portrait_manifest.append({
                "name": name,
                "wins": wins,
                "file": filename,
                "group": "high_winner",
                "killed_by": f.get("killedByName"),
            })
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(all_high_winners)}] ... {status}: {name[:40]}")
        time.sleep(0.1)
    
    # Also download round participants (potential losers)
    round_fighters = []
    if round_data:
        for f in round_data.get("fighters", []):
            name = f.get("name", "?")
            wins = f.get("wins", 0)
            round_fighters.append(f)
            filename = download_portrait(f, f"r{wins}w_")
            status = "OK" if filename else "FAIL"
            if filename:
                # Check if already in manifest
                if not any(m["name"] == name for m in portrait_manifest):
                    portrait_manifest.append({
                        "name": name,
                        "wins": wins,
                        "file": filename,
                        "group": "current_round",
                    })
    
    print(f"\n  TOTAL PORTRAITS: {len(portrait_manifest)}")
    
    # Save manifest
    manifest_path = os.path.join(CACHE_DIR, "big_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(portrait_manifest, f, indent=1)
    print(f"  Manifest saved: big_manifest.json")
    
    # ============================
    # STEP 4: Summary / Next steps
    # ============================
    print("\n[4/4] Dataset summary:")
    
    # Win distribution
    win_counts = Counter()
    for m in portrait_manifest:
        w = m["wins"]
        if w >= 10:
            win_counts["10+ (champion)"] += 1
        elif w >= 7:
            win_counts["7-9 (high)"] += 1
        elif w >= 5:
            win_counts["5-6 (mid)"] += 1
        else:
            win_counts["<5 (current round)"] += 1
    
    for bucket, count in sorted(win_counts.items()):
        print(f"  {bucket:20s}: {count}")
    
    # Killed by stats
    killed_by = [m.get("killed_by") for m in portrait_manifest if m.get("killed_by")]
    if killed_by:
        top_killers = Counter(killed_by).most_common(10)
        print(f"\n  Top killers (from high-winners dataset):")
        for killer, count in top_killers:
            print(f"    {killer:45s}: {count} kills")
    
    print(f"\n  Next step: run BLIP analysis on the full dataset")
    print(f"    python big_blip_analysis.py")
    print(f"\n  Done.")


if __name__ == "__main__":
    main()
