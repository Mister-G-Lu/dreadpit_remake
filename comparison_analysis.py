#!/usr/bin/env python3
"""
Complete winner-vs-loser visual comparison using BLIP.

1. Downloads low-win fighters from graveyard (0-3 wins) for loser comparison group
2. Downloads ALL portraits to big_portraits/
3. Runs BLIP image captioning on every portrait
4. Cross-references visual features against win counts
5. Produces the most comprehensive visual analysis report
"""

import json
import os
import sys
import statistics
import time
from collections import Counter

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")

# =========================================================================
# BLIP model (reuse from earlier setup)
# =========================================================================

_blip_model = None
_blip_processor = None

def load_blip():
    global _blip_model, _blip_processor
    if _blip_model is not None:
        return True
    try:
        print("  Loading BLIP model...")
        from transformers import BlipProcessor, BlipForConditionalGeneration
        _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        print("  BLIP loaded.")
        return True
    except Exception as e:
        print(f"  ERROR loading BLIP: {e}")
        return False


def describe_image(image_path):
    """Generate a natural language description using BLIP."""
    if _blip_model is None:
        return ""
    try:
        from PIL import Image
        import torch
        raw_image = Image.open(image_path).convert("RGB")
        inputs = _blip_processor(raw_image, return_tensors="pt")
        with torch.no_grad():
            out = _blip_model.generate(**inputs, max_length=100, num_beams=3)
        caption = _blip_processor.decode(out[0], skip_special_tokens=True)
        return caption.strip()
    except Exception as e:
        return f"[error]"


def extract_keywords(description):
    """Extract visual features from a natural language description."""
    dl = description.lower() if description else ""
    
    return {
        # Weapons
        "sword_or_blade": any(w in dl for w in ["sword", "blade", "katana", "saber", "longsword", "cutlass"]),
        "axe_or_hammer": any(w in dl for w in ["axe", "hammer", "mace", "maul", "warhammer"]),
        "gun_or_ranged": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "bow", "crossbow", "spear", "javelin", "harpoon"]),
        "two_weapons": any(w in dl for w in ["two", "dual", "pair of"]),
        "big_weapon": any(w in dl for w in ["large", "massive", "giant", "oversized", "enormous"]),
        "unarmed": any(w in dl for w in ["unarmed", "no weapon", "bare hands", "with his hands"]),
        
        # Armor
        "helmet": any(w in dl for w in ["helmet", "helm", "faceplate", "visor", "mask", "hood"]),
        "body_armor": any(w in dl for w in ["armor", "plate", "pauldron", "gauntlet", "chainmail", "breastplate"]),
        "shield": "shield" in dl,
        "no_armor": any(w in dl for w in ["torn", "tattered", "robe", "cloth", "no armor"]),
        
        # Creature type
        "humanoid": any(w in dl for w in ["man", "woman", "person", "warrior", "knight", "soldier", "human", "humanoid", "figure"]),
        "monster_or_dragon": any(w in dl for w in ["monster", "dragon", "demon", "beast", "creature"]),
        "mechanical": any(w in dl for w in ["mechanical", "robot", "machine", "cyborg", "mecha", "android"]),
        "undead": any(w in dl for w in ["skeleton", "undead", "lich", "ghost", "skull"]),
        
        # Elements
        "wings": "wing" in dl,
        "cape_or_cloak": any(w in dl for w in ["cape", "cloak", "robe", "coat"]),
        "glowing": any(w in dl for w in ["glow", "glowing", "radiant", "energy", "bright"]),
        "fire": any(w in dl for w in ["fire", "flame", "burning", "blazing", "molten"]),
        
        # Tone
        "dark": any(w in dl for w in ["dark", "shadow", "black", "sinister"]),
        "bright": any(w in dl for w in ["bright", "vibrant", "colorful", "golden"]),
        "warm_red": any(w in dl for w in ["warm", "orange", "red", "fiery"]),
        "cold_blue": any(w in dl for w in ["cold", "ice", "icy", "frozen", "blue", "pale"]),
        
        # Materials
        "metal_armor": any(w in dl for w in ["metal", "iron", "steel", "silver", "chrome", "bronze"]),
        "organic": any(w in dl for w in ["flesh", "skin", "fur", "scale", "bone", "leather"]),
        "cloth_fabric": any(w in dl for w in ["cloth", "fabric", "silk", "wool", "garment"]),
        
        # Descriptors
        "veteran_or_aged": any(w in dl for w in ["veteran", "aged", "old", "scarred", "weathered", "grizzled"]),
        "powerful_imposing": any(w in dl for w in ["powerful", "imposing", "intimidating", "fearsome", "menacing"]),
        "mysterious": any(w in dl for w in ["mysterious", "enigmatic", "unknown"]),
    }


def fetch_json(url, timeout=15):
    try:
        import urllib.request
        r = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(r.read().decode())
    except Exception:
        return None


def download_portrait(fighter, wins, group):
    """Download a portrait, returns (filename, fighter_dict) or (None, dict)."""
    fid = fighter.get("id", "unknown")[:12]
    name = fighter.get("name", "?")
    url = fighter.get("imageUrl", "")
    if not url or not fid:
        return None, fighter
    
    safe_name = "".join(c for c in name[:30] if c.isalnum() or c in ' ._-').strip() or "unnamed"
    filename = f"{group}_{wins}w_{fid}_{safe_name}.png"
    path = os.path.join(PORTRAIT_DIR, filename)
    
    if os.path.exists(path):
        return filename, fighter
    
    try:
        import urllib.request
        r = urllib.request.urlopen(f"https://dreadpit.com{url}", timeout=15)
        with open(path, "wb") as f:
            f.write(r.read())
        return filename, fighter
    except Exception as e:
        return None, fighter


# =========================================================================
# Main
# =========================================================================

def main():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    
    print("=" * 72)
    print("  DREADPIT COMPLETE WINNER vs LOSER VISUAL ANALYSIS")
    print("=" * 72)
    
    # ----------------------------------------------------------------
    # STEP 1: Collect fighters
    # ----------------------------------------------------------------
    print("\n[1/5] Collecting fighters from graveyard...")
    
    api_base = "https://dreadpit.com/api"
    
    # High winners: paginate from start (highest wins descending)
    high_fighters = []
    for offset in range(0, 500, 100):
        data = fetch_json(f"{api_base}/graveyard?limit=100&offset={offset}&sort=wins")
        if not data or "items" not in data or not data["items"]:
            break
        items = data["items"]
        high = [f for f in items if f.get("wins", 0) >= 5]
        high_fighters.extend(high)
        if items and items[-1].get("wins", 0) < 5:
            break
        time.sleep(0.2)
    
    # Low winners: skip to high offset for <=3 win fighters
    low_fighters = []
    # Start from offset ~2000 where wins are likely 0-3
    for offset in range(2000, 5000, 100):
        data = fetch_json(f"{api_base}/graveyard?limit=100&offset={offset}")
        if not data or "items" not in data or not data["items"]:
            break
        items = data["items"]
        low = [f for f in items if f.get("wins", 0) <= 3]
        low_fighters.extend(low)
        # Sample up to 100 low-winners
        if len(low_fighters) >= 150:
            break
        time.sleep(0.2)
    
    # Also get from leaderboard (alive low-winners)
    lb = fetch_json(f"{api_base}/leaderboard")
    lb_low = []
    if lb:
        for e in lb:
            f = e["fighter"]
            if f.get("wins", 0) <= 3:
                lb_low.append(f)
    
    # Combine and dedup low-winners
    all_low = low_fighters + lb_low
    seen_ids = set()
    deduped_low = []
    for f in all_low:
        fid = f.get("id", "")
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            deduped_low.append(f)
    
    print(f"  High-winners (5+): {len(high_fighters)}")
    print(f"  Low-winners (<=3): {len(deduped_low)}")
    
    # Balance the groups: take up to 100 low-winners
    import random
    random.seed(42)
    low_sample = random.sample(deduped_low, min(100, len(deduped_low)))
    
    print(f"  Low-winner sample: {len(low_sample)}")
    
    # ----------------------------------------------------------------
    # STEP 2: Download all portraits
    # ----------------------------------------------------------------
    print("\n[2/5] Downloading portraits...")
    
    manifest = []
    
    for f in high_fighters:
        filename, _ = download_portrait(f, f.get("wins", 0), "high")
        if filename:
            manifest.append({
                "name": f.get("name", "?"),
                "wins": f.get("wins", 0),
                "file": filename,
                "group": "high_winner",
            })
    
    for f in low_sample:
        filename, _ = download_portrait(f, f.get("wins", 0), "low")
        if filename:
            manifest.append({
                "name": f.get("name", "?"),
                "wins": f.get("wins", 0),
                "file": filename,
                "group": "low_winner",
            })
    
    print(f"  Total portraits: {len(manifest)}")
    print(f"    High-winners: {len([m for m in manifest if m['group'] == 'high_winner'])}")
    print(f"    Low-winners:  {len([m for m in manifest if m['group'] == 'low_winner'])}")
    
    # Save manifest
    with open(os.path.join(CACHE_DIR, "comparison_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    
    # ----------------------------------------------------------------
    # STEP 3: Load BLIP
    # ----------------------------------------------------------------
    print("\n[3/5] Loading BLIP image captioning model...")
    if not load_blip():
        print("  Cannot continue without BLIP.")
        return
    
    # ----------------------------------------------------------------
    # STEP 4: Analyze all portraits with BLIP
    # ----------------------------------------------------------------
    print(f"\n[4/5] Analyzing {len(manifest)} portraits with BLIP...")
    
    results = []
    for i, entry in enumerate(manifest):
        path = os.path.join(PORTRAIT_DIR, entry["file"])
        if not os.path.exists(path):
            continue
        
        desc = describe_image(path)
        keywords = extract_keywords(desc)
        
        # Also compute pixel metrics
        from PIL import Image
        try:
            img = Image.open(path).convert("RGB")
            pixels = list(img.getdata())
            r_vals = [p[0] for p in pixels]
            g_vals = [p[1] for p in pixels]
            b_vals = [p[2] for p in pixels]
            avg_r = statistics.mean(r_vals)
            avg_g = statistics.mean(g_vals)
            avg_b = statistics.mean(b_vals)
            brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
            warmth = avg_r - avg_b
            pixel = {
                "brightness": round(brightness, 1),
                "warmth": round(warmth, 1),
                "avg_r": round(avg_r),
                "avg_g": round(avg_g),
                "avg_b": round(avg_b),
                "red_ratio": round(avg_r / max(avg_r + avg_g + avg_b, 0.001), 3),
            }
        except:
            pixel = {}
        
        results.append({
            "name": entry["name"],
            "wins": entry["wins"],
            "group": entry["group"],
            "blip_description": desc,
            "keywords": {k: bool(v) for k, v in keywords.items()},
            "pixel": pixel,
        })
        
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(manifest)}] ... ({len(results)} analyzed)")
    
    print(f"  Analyzed {len(results)} portraits")
    
    # ----------------------------------------------------------------
    # STEP 5: Cross-reference and save
    # ----------------------------------------------------------------
    print("\n[5/5] Cross-referencing visual features vs wins...")
    
    high = [r for r in results if r["group"] == "high_winner"]
    low = [r for r in results if r["group"] == "low_winner"]
    
    print(f"\n  Winner group (5+ wins): {len(high)} fighters")
    print(f"  Loser group  (<=3 wins): {len(low)} fighters")
    
    # --- Color/metric comparison ---
    print(f"\n  -- PIXEL METRICS COMPARISON --")
    print(f"  {'Metric':20s} {'Winners':>10s} {'Losers':>10s} {'Delta':>8s}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*8}")
    
    for key in ["brightness", "warmth", "red_ratio"]:
        h_vals = [r["pixel"].get(key, 0) for r in high if r["pixel"]]
        l_vals = [r["pixel"].get(key, 0) for r in low if r["pixel"]]
        if h_vals and l_vals:
            h_avg = statistics.mean(h_vals)
            l_avg = statistics.mean(l_vals)
            print(f"  {key:20s} {h_avg:>10.3f} {l_avg:>10.3f} {h_avg-l_avg:>+8.3f}")
    
    # --- Keyword feature comparison ---
    print(f"\n  -- BLIP KEYWORD COMPARISON (biggest differences) --")
    print(f"  {'Feature':25s} {'Winners%':>9s} {'Losers%':>9s} {'Delta':>7s} {'Direction':>25s}")
    print(f"  {'-'*25} {'-'*9} {'-'*9} {'-'*7} {'-'*25}")
    
    deltas = []
    for kw in extract_keywords("").keys():
        h_pct = sum(1 for r in high if r["keywords"].get(kw, False)) / max(len(high), 1) * 100
        l_pct = sum(1 for r in low if r["keywords"].get(kw, False)) / max(len(low), 1) * 100
        deltas.append((kw, h_pct - l_pct, h_pct, l_pct))
    
    deltas.sort(key=lambda x: abs(x[1]), reverse=True)
    for kw, delta, h, l in deltas:
        if abs(delta) > 5:
            arrow = "more common in winners" if delta > 0 else "more common in losers"
            print(f"  {kw:25s} {h:8.1f}% {l:8.1f}% {delta:+6.1f}%  {arrow:>25s}")
    
    # --- Individual winner profiles ---
    print(f"\n  -- ALL HIGH-WINNER BLIP DESCRIPTIONS --")
    for r in sorted(results, key=lambda x: x["wins"], reverse=True):
        if r["group"] != "high_winner":
            continue
        print(f'\n  {r["name"]:45s} ({r["wins"]} wins)')
        print(f'    BLIP: {r["blip_description"]}')
        p = r.get("pixel", {})
        if p:
            print(f'    Pixel: R={p.get("avg_r")} G={p.get("avg_g")} B={p.get("avg_b")}  bright={p.get("brightness"):.0f}  warm={p.get("warmth"):+.0f}')
    
    # Save final analysis
    out_path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    with open(out_path, "w") as f:
        json.dump({
            "high_count": len(high),
            "low_count": len(low),
            "results": results,
            "pixel_deltas": {
                k: {
                    "winner_avg": statistics.mean([r["pixel"].get(k, 0) for r in high if r["pixel"]]),
                    "loser_avg": statistics.mean([r["pixel"].get(k, 0) for r in low if r["pixel"]]),
                } for k in ["brightness", "warmth", "red_ratio"]
            },
            "keyword_deltas": [
                {"feature": f, "delta": d, "winner_pct": h, "loser_pct": l}
                for f, d, h, l in deltas if abs(d) > 3
            ],
        }, f, indent=1)
    
    print(f"\n  Saved to: comparison_analysis.json")
    print("  Done.")


if __name__ == "__main__":
    main()
