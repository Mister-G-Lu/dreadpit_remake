#!/usr/bin/env python3
"""
Incremental BLIP analysis of all comparison fighters.
Saved results after every 25 images so progress isn't lost on timeout.
"""

import json
import os
import sys
import statistics
import time
from collections import Counter

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
RESULTS_PATH = os.path.join(CACHE_DIR, "comparison_analysis.json")

# BLIP globals
_proc = None
_model = None

def load_blip():
    global _proc, _model
    if _model is not None:
        return True
    from transformers import BlipProcessor, BlipForConditionalGeneration
    import torch
    print(" Loading BLIP...")
    _proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print(" BLIP ready.")
    return True


def describe(path):
    from PIL import Image
    import torch
    img = Image.open(path).convert("RGB")
    inputs = _proc(img, return_tensors="pt")
    with torch.no_grad():
        out = _model.generate(**inputs, max_length=80)
    return _proc.decode(out[0], skip_special_tokens=True).strip()


def extract(desc):
    dl = desc.lower() if desc else ""
    return {
        "sword": any(w in dl for w in ["sword", "blade", "katana", "saber", "longsword"]),
        "axe_hammer": any(w in dl for w in ["axe", "hammer", "mace", "maul"]),
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "shotgun", "bow", "crossbow", "spear"]),
        "armor": any(w in dl for w in ["armor", "plate", "chainmail", "breastplate", "pauldron", "gauntlet"]),
        "helmet": any(w in dl for w in ["helmet", "helm", "mask", "visor", "hood"]),
        "human": any(w in dl for w in ["man", "woman", "person", "warrior", "knight", "soldier", "human", "figure"]),
        "monster": any(w in dl for w in ["monster", "dragon", "demon", "beast", "creature"]),
        "robot": any(w in dl for w in ["robot", "mechanical", "machine", "cyborg", "mecha"]),
        "fire": any(w in dl for w in ["fire", "flame", "burning", "blazing", "molten"]),
        "dark": any(w in dl for w in ["dark", "shadow", "black", "sinister"]),
        "red": any(w in dl for w in ["red", "orange", "warm", "fiery"]),
        "blue": any(w in dl for w in ["blue", "cold", "ice", "icy", "frozen"]),
        "metal": any(w in dl for w in ["metal", "iron", "steel", "silver", "chrome"]),
        "wings": "wing" in dl,
        "shield": "shield" in dl,
        "cape": any(w in dl for w in ["cape", "cloak", "robe"]),
    }


def main():
    # Load manifest
    with open(os.path.join(CACHE_DIR, "comparison_manifest.json")) as f:
        manifest = json.load(f)
    print(f"Manifest: {len(manifest)} fighters ({len([m for m in manifest if m['group']=='high_winner'])} high, {len([m for m in manifest if m['group']=='low_winner'])} low)")

    # Load existing results if any
    results = []
    processed_names = set()
    if os.path.exists(RESULTS_PATH):
        try:
            with open(RESULTS_PATH) as f:
                existing = json.load(f)
            results = existing.get("results", [])
            processed_names = {r["name"] for r in results}
            print(f"Loaded {len(results)} existing results, skipping {len(processed_names)} already-processed fighters")
        except:
            pass

    # Load BLIP
    load_blip()

    # Process unprocessed fighters
    to_process = [m for m in manifest if m["name"] not in processed_names]
    if not to_process:
        print("All fighters already processed!")
    else:
        print(f"Processing {len(to_process)} new fighters...")
        batch_size = 25
        batch_start = len(results)

        for i, entry in enumerate(to_process):
            path = os.path.join(PORTRAIT_DIR, entry["file"])
            if not os.path.exists(path):
                continue

            try:
                desc = describe(path)
                kws = extract(desc)

                from PIL import Image
                img = Image.open(path).convert("RGB")
                px = list(img.getdata())
                r_vals = [p[0] for p in px]
                g_vals = [p[1] for p in px]
                b_vals = [p[2] for p in px]
                avg_r = statistics.mean(r_vals)
                avg_g = statistics.mean(g_vals)
                avg_b = statistics.mean(b_vals)
                brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
                warmth = avg_r - avg_b

                results.append({
                    "name": entry["name"],
                    "wins": entry["wins"],
                    "group": entry["group"],
                    "blip": desc,
                    "kws": kws,
                    "pixel": {
                        "brightness": round(brightness, 1),
                        "warmth": round(warmth, 1),
                        "avg_r": round(avg_r),
                        "avg_g": round(avg_g),
                        "avg_b": round(avg_b),
                        "red_ratio": round(avg_r / max(avg_r + avg_g + avg_b, 0.001), 3),
                    },
                })
            except Exception as e:
                print(f"  Error on {entry['name']}: {e}")

            # Save every batch_size
            if (i + 1) % batch_size == 0:
                partial_save(results)
                print(f"  Saved batch: {len(results)} total processed")

            # Print progress every 10
            if (i + 1) % 10 == 0:
                print(f"  [{batch_start + i + 1}/{batch_start + len(to_process)}] {entry['name'][:40]} ({entry['wins']}w)")

        # Final save
        partial_save(results)
        print(f"Saved final: {len(results)} results")

    # ===== ANALYSIS =====
    print("\n" + "=" * 72)
    print("  WINNER vs LOSER VISUAL COMPARISON")
    print("=" * 72)

    high = [r for r in results if r["group"] == "high_winner"]
    low = [r for r in results if r["group"] == "low_winner"]

    print(f"\n  High-winners (5+): {len(high)}")
    print(f"  Low-winners (<=3): {len(low)}")

    # Pixel comparison
    print(f"\n  -- PIXEL METRICS --")
    for key in ["brightness", "warmth", "red_ratio"]:
        h_v = [r["pixel"][key] for r in high if r.get("pixel")]
        l_v = [r["pixel"][key] for r in low if r.get("pixel")]
        if h_v and l_v:
            h_avg = statistics.mean(h_v)
            l_avg = statistics.mean(l_v)
            print(f"  {key:15s}: winners={h_avg:.3f}  losers={l_avg:.3f}  delta={h_avg-l_avg:+.3f}")

    # Keyword comparison
    print(f"\n  -- KEYWORD COMPARISON (BIGGEST DIFFERENCES) --")
    deltas = []
    for kw in extract("").keys():
        h_pct = sum(1 for r in high if r["kws"].get(kw, False)) / max(len(high), 1) * 100
        l_pct = sum(1 for r in low if r["kws"].get(kw, False)) / max(len(low), 1) * 100
        deltas.append((kw, h_pct - l_pct, h_pct, l_pct))

    deltas.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"  {'Feature':15s} {'Winners':>9s} {'Losers':>9s} {'Delta':>7s} {'Direction':>25s}")
    print(f"  {'-'*15} {'-'*9} {'-'*9} {'-'*7} {'-'*25}")
    for kw, d, h, l in deltas:
        if abs(d) > 5:
            arrow = "MORE in winners" if d > 0 else "MORE in losers"
            print(f"  {kw:15s} {h:8.1f}% {l:8.1f}% {d:+6.1f}%  {arrow:>25s}")

    # Top winner descriptions
    print(f"\n  -- INDIVIDUAL WINNER BLIP DESCRIPTIONS --")
    for r in sorted(results, key=lambda x: x["wins"], reverse=True):
        if r["group"] != "high_winner":
            continue
        p = r.get("pixel", {})
        pixel_str = f'R={p.get("avg_r")} G={p.get("avg_g")} B={p.get("avg_b")}' if p else ""
        print(f'\n  {r["name"]:45s} ({r["wins"]} wins)')
        print(f'    BLIP:  {r["blip"]}')
        print(f'    Pixel: {pixel_str}')

    print(f"\n  Done.")


def partial_save(results):
    """Save current results to disk."""
    with open(RESULTS_PATH, "w") as f:
        json.dump({"count": len(results), "results": results}, f, indent=1)


if __name__ == "__main__":
    main()
