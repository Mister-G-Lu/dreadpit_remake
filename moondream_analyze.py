#!/usr/bin/env python3
"""
Moondream2 Vision-Language Model Analyzer for DreadPit Fighter Portraits.

Moondream2 is a small (1.8B params) but capable vision-language model
that runs on CPU with 8GB+ RAM. It generates natural language descriptions
of images — unlike CLIP which can only score against predefined prompts.

This is the most accurate model that can actually run on a Windows 10
CPU setup with 16GB RAM.

Usage:
    python moondream_analyze.py                 # analyze all portraits
    python moondream_analyze.py --simo-only     # just SIMO THE UNSEEN
    python moondream_analyze.py --quick         # just outliers
"""

import json
import os
import sys
import time
import urllib.request

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "portraits")

# =========================================================================
# Moondream2 model loading
# =========================================================================

_model = None
_tokenizer = None

def load_moondream():
    global _model, _tokenizer
    if _model is not None:
        return True
    try:
        model_id = "vikhyatk/moondream2"
        print(f"  Loading {model_id} (1.8B params, ~1GB download)...")
        t0 = time.time()
        
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        _model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="cpu",
        )
        _tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        elapsed = time.time() - t0
        print(f"  Loaded in {elapsed:.0f}s")
        return True
    except Exception as e:
        print(f"  ERROR loading moondream2: {e}")
        return False


def analyze_image(image_path, prompt=None):
    """Analyze an image with moondream2 and return a natural language description."""
    if _model is None:
        return "[model not loaded]"
    if prompt is None:
        prompt = (
            "Describe this fighter in detail. What weapons do you see? "
            "What armor are they wearing? Are they human, monster, or machine? "
            "What materials and colors are visible? What is their pose?"
        )
    try:
        from PIL import Image
        import torch
        
        image = Image.open(image_path).convert("RGB")
        
        # Encode image
        with torch.no_grad():
            image_embeds = _model.encode_image(image)
        
        # Ask question
        with torch.no_grad():
            answer = _model.answer_question(
                image_embeds=image_embeds,
                question=prompt,
                tokenizer=_tokenizer,
            )
        
        return answer.strip()
    except Exception as e:
        return f"[error: {e}]"


def extract_keywords(description):
    """Extract structured features from the natural language description."""
    desc_lower = description.lower()
    
    features = {
        # Weapons
        "sword_or_blade": any(w in desc_lower for w in ["sword", "blade", "katana", "saber", "longsword", "cutlass"]),
        "axe_or_hammer": any(w in desc_lower for w in ["axe", "hammer", "mace", "maul", "warhammer"]),
        "gun_or_ranged": any(w in desc_lower for w in ["gun", "rifle", "cannon", "pistol", "shotgun", "bow", "crossbow", "spear", "javelin", "harpoon"]),
        "two_weapons": any(w in desc_lower for w in ["two", "dual", "pair of", "both hands"]),
        "big_weapon": any(w in desc_lower for w in ["large", "massive", "giant", "oversized", "enormous"]),
        "unarmed": any(w in desc_lower for w in ["unarmed", "no weapon", "bare hands"]),
        
        # Armor
        "helmet": any(w in desc_lower for w in ["helmet", "helm", "faceplate", "visor", "mask", "hood"]),
        "body_armor": any(w in desc_lower for w in ["armor", "plate", "pauldron", "gauntlet", "chainmail", "breastplate"]),
        "shield": "shield" in desc_lower,
        "no_armor": any(w in desc_lower for w in ["torn", "tattered", "robe", "cloth", "bare chested", "no armor"]),
        
        # Creature type
        "humanoid": any(w in desc_lower for w in ["man", "woman", "person", "warrior", "knight", "soldier", "human", "humanoid", "figure"]),
        "monster": any(w in desc_lower for w in ["monster", "dragon", "demon", "beast", "creature", "fiend"]),
        "mechanical": any(w in desc_lower for w in ["mechanical", "robot", "machine", "cyborg", "mecha", "android", "automaton"]),
        "undead": any(w in desc_lower for w in ["skeleton", "undead", "lich", "ghost", "spectral", "skull"]),
        
        # Visual elements
        "wings": "wing" in desc_lower,
        "cape_or_cloak": any(w in desc_lower for w in ["cape", "cloak", "robe"]),
        "visible_face": any(w in desc_lower for w in ["face", "beard", "eye", "expression"]),
        "glowing": any(w in desc_lower for w in ["glow", "glowing", "radiant", "energy"]),
        "fire": any(w in desc_lower for w in ["fire", "flame", "burning", "blazing", "molten"]),
        
        # Tone
        "dark": any(w in desc_lower for w in ["dark", "shadow", "black", "sinister", "menacing"]),
        "bright": any(w in desc_lower for w in ["bright", "vibrant", "colorful", "golden"]),
        "cold_blue": any(w in desc_lower for w in ["cold", "ice", "icy", "frozen", "blue"]),
        "warm_red": any(w in desc_lower for w in ["warm", "orange", "red", "fiery"]),
        
        # Materials
        "metal": any(w in desc_lower for w in ["metal", "iron", "steel", "silver", "chrome", "bronze"]),
        "organic": any(w in desc_lower for w in ["flesh", "skin", "fur", "scale", "bone", "leather"]),
        "cloth": any(w in desc_lower for w in ["cloth", "fabric", "silk", "wool", "garment"]),
        
        # Context
        "veteran_or_aged": any(w in desc_lower for w in ["veteran", "aged", "old", "scarred", "weathered", "grizzled"]),
        "powerful": any(w in desc_lower for w in ["powerful", "imposing", "intimidating", "fearsome", "menacing"]),
        "mysterious": any(w in desc_lower for w in ["mysterious", "enigmatic", "unknown"]),
    }
    return features


# =========================================================================
# Helpers
# =========================================================================

def load_manifest():
    path = os.path.join(CACHE_DIR, "portrait_manifest.json")
    if not os.path.exists(path):
        print("ERROR: portrait_manifest.json not found. Run download_portraits.py first.")
        return []
    with open(path) as f:
        return json.load(f)


# =========================================================================
# Main
# =========================================================================

def main():
    simo_only = "--simo-only" in sys.argv
    quick_mode = "--quick" in sys.argv
    
    manifest = load_manifest()
    if not manifest:
        return
    print(f"[1/4] Loaded {len(manifest)} fighters from manifest")
    
    print("\n[2/4] Loading moondream2 vision model...")
    if not load_moondream():
        print("  Model failed to load.")
        return
    
    # Test on SIMO first
    print("\n[3/4] Testing on SIMO THE UNSEEN...")
    simo_entry = None
    for e in manifest:
        if "SIMO" in (e.get("name") or "").upper():
            simo_entry = e
            break
    
    if simo_entry and simo_entry.get("file"):
        simo_path = os.path.join(PORTRAIT_DIR, simo_entry["file"])
        if os.path.exists(simo_path):
            print(f'  Analyzing: "{simo_entry["name"]}" ({simo_entry["wins"]} wins)')
            desc = analyze_image(simo_path)
            print(f'  Moondream: "{desc}"')
            kws = extract_keywords(desc)
            present = [k for k, v in kws.items() if v]
            print(f'  Keywords: {", ".join(present)}')
    
    if simo_only:
        print("\n  Done (--simo-only).")
        return
    
    # Select fighters to analyze
    if quick_mode:
        outlier_names = ["SIMO THE UNSEEN", "GL6", "Cosm", "Dread, the unending",
                         "The Being From [Redacted]", "Nonamebot", "George",
                         "Never Slayed", "Dr. Manhattan", "The Dreadpit itself",
                         "Andy", "Theo", "Astrong"]
        to_analyze = [e for e in manifest if any(n in (e.get("name") or "") for n in outlier_names)]
    else:
        to_analyze = manifest
    
    print(f"\n[4/4] Analyzing {len(to_analyze)} portraits with moondream2...")
    results = []
    
    for i, entry in enumerate(to_analyze):
        name = entry.get("name", "?")
        wins = entry.get("wins", 0)
        filename = entry.get("file")
        if not filename:
            continue
        
        path = os.path.join(PORTRAIT_DIR, filename)
        if not os.path.exists(path):
            continue
        
        desc = analyze_image(path)
        keywords = extract_keywords(desc)
        
        results.append({
            "name": name,
            "wins": wins,
            "moondream_description": desc,
            "keywords": {k: bool(v) for k, v in keywords.items()},
        })
        
        short = desc[:100] + "..." if len(desc) > 100 else desc
        print(f"  [{i+1}/{len(to_analyze)}] {name:40s} wins={wins:2d} {short}")
    
    # Cross-reference
    print(f"\n  -- Cross-reference: high vs low winners --")
    high = [r for r in results if r["wins"] >= 7]
    low = [r for r in results if r["wins"] <= 3]
    
    if results:
        deltas = []
        for kw in extract_keywords("").keys():
            h_pct = sum(1 for r in high if r["keywords"].get(kw, False)) / max(len(high), 1) * 100
            l_pct = sum(1 for r in low if r["keywords"].get(kw, False)) / max(len(low), 1) * 100
            deltas.append((kw, h_pct - l_pct, h_pct, l_pct))
        
        deltas.sort(key=lambda x: abs(x[1]), reverse=True)
        print(f"\n  {'Feature':25s} {'High%':>7s} {'Low%':>7s} {'Delta':>7s} {'Direction':>25s}")
        print(f"  {'-'*25} {'-'*7} {'-'*7} {'-'*7} {'-'*25}")
        for kw, delta, h, l in deltas:
            if abs(delta) > 8:
                arrow = "more in winners" if delta > 0 else "more in losers"
                print(f"  {kw:25s} {h:6.1f}% {l:6.1f}% {delta:+6.1f}%  {arrow:>25s}")
    
    # Full descriptions for all high-winners
    if not quick_mode:
        print(f"\n  -- All high-winner descriptions --")
        for r in sorted(results, key=lambda x: x["wins"], reverse=True):
            if r["wins"] < 7:
                continue
            print(f'\n  {r["name"]:45s} ({r["wins"]} wins)')
            print(f'    {r["moondream_description"]}')
    
    # Save
    out_path = os.path.join(CACHE_DIR, "moondream_analysis.json")
    with open(out_path, "w") as f:
        json.dump({
            "count": len(results),
            "results": results,
        }, f, indent=1)
    print(f"\n  Saved to: moondream_analysis.json")
    print("  Done.")


if __name__ == "__main__":
    main()
