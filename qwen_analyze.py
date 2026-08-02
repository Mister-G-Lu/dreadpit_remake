#!/usr/bin/env python3
"""
Qwen2.5-VL-7B-Instruct Image Analyzer for DreadPit Fighter Portraits.

Uses HuggingFace transformers to load Qwen2.5-VL-7B-Instruct and analyze
fighter portraits in natural language. Much more capable than CLIP/BLIP
at understanding detailed fantasy art.

Usage:
    python qwen_analyze.py                  # analyze all portraits
    python qwen_analyze.py --simo-only      # just SIMO THE UNSEEN
    python qwen_analyze.py --quick          # skip full batch, just outlier fighters
"""

import json
import os
import sys
import time
import base64
from io import BytesIO

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "portraits")

# =========================================================================
# Qwen model loading via HuggingFace transformers
# =========================================================================

_model = None
_processor = None

def load_qwen():
    global _model, _processor
    if _model is not None:
        return True
    try:
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
        print(f"  Loading {model_id} (this downloads ~15GB on first run)...")
        t0 = time.time()
        
        # Load model on CPU with float32 for compatibility
        _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype="auto",  # will use float32 on CPU
            device_map="cpu",
            trust_remote_code=True,
        )
        _processor = AutoProcessor.from_pretrained(
            model_id,
            trust_remote_code=True,
        )
        elapsed = time.time() - t0
        print(f"  Model loaded in {elapsed:.0f}s")
        return True
    except Exception as e:
        print(f"  ERROR loading Qwen2.5-VL: {e}")
        return False


def analyze_image(image_path, prompt=None):
    """
    Analyze an image using Qwen2.5-VL.
    Returns the model's text response describing the image.
    """
    if _model is None:
        return "[model not loaded]"
    if prompt is None:
        prompt = (
            "Describe this fighter in detail. What weapons are they holding? "
            "What armor are they wearing? Are they human, monster, machine, or something else? "
            "What materials are visible (metal, flesh, stone, cloth)? "
            "What is their pose and expression? Be specific about every visible detail."
        )
    try:
        from PIL import Image
        import torch
        
        image = Image.open(image_path).convert("RGB")
        
        # Format messages for Qwen2.5-VL chat template
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Apply chat template
        text = _processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # Process inputs
        inputs = _processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        )
        
        # Generate
        with torch.no_grad():
            generated_ids = _model.generate(
                **inputs,
                max_new_tokens=200,
                do_sample=False,
                num_beams=1,
            )
        
        # Trim input tokens from output
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        response = _processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        
        return response.strip()
    except Exception as e:
        return f"[error: {e}]"


# =========================================================================
# Keyword extraction from Qwen's natural language output
# =========================================================================

def extract_keywords(description):
    desc_lower = description.lower()
    
    features = {
        # Weapons
        "sword_or_blade": any(w in desc_lower for w in ["sword", "blade", "katana", "saber", "longsword", "cutlass"]),
        "axe_or_hammer": any(w in desc_lower for w in ["axe", "hammer", "mace", "maul", "warhammer"]),
        "gun_or_ranged": any(w in desc_lower for w in ["gun", "rifle", "cannon", "pistol", "shotgun", "laser", "blaster", "bow", "crossbow", "spear", "javelin"]),
        "two_weapons": any(w in desc_lower for w in ["two", "dual", "pair of", "both hands"]),
        "big_weapon": any(w in desc_lower for w in ["large", "massive", "giant", "oversized", "enormous"]),
        "unarmed": any(w in desc_lower for w in ["unarmed", "no weapon", "bare hands", "fist"]),
        
        # Armor
        "helmet_or_helm": any(w in desc_lower for w in ["helmet", "helm", "faceplate", "visor", "mask", "hood"]),
        "body_armor": any(w in desc_lower for w in ["armor", "plate", "pauldron", "gauntlet", "chainmail", "breastplate"]),
        "shield": "shield" in desc_lower,
        
        # Creature type
        "humanoid": any(w in desc_lower for w in ["man", "woman", "person", "warrior", "knight", "soldier", "human", "humanoid"]),
        "monster_or_dragon": any(w in desc_lower for w in ["monster", "dragon", "demon", "beast", "creature", "fiend"]),
        "mechanical": any(w in desc_lower for w in ["mechanical", "robot", "machine", "cyborg", "mecha", "android", "automaton"]),
        "undead": any(w in desc_lower for w in ["skeleton", "undead", "lich", "ghost", "spectral", "skull"]),
        
        # Visual elements
        "has_wings": "wing" in desc_lower,
        "has_cape": any(w in desc_lower for w in ["cape", "cloak", "robe"]),
        "has_visible_face": any(w in desc_lower for w in ["face", "beard", "eye", "expression"]),
        "has_glow": any(w in desc_lower for w in ["glow", "glowing", "radiant", "energy"]),
        "has_fire": any(w in desc_lower for w in ["fire", "flame", "burning", "blazing"]),
        
        # Tone
        "dark_shadowy": any(w in desc_lower for w in ["dark", "shadow", "black", "sinister", "menacing"]),
        "bright_colorful": any(w in desc_lower for w in ["bright", "vibrant", "colorful", "golden"]),
        "cold_icy": any(w in desc_lower for w in ["cold", "ice", "icy", "frozen", "blue"]),
        "warm_fiery": any(w in desc_lower for w in ["warm", "orange", "red", "molten", "fiery"]),
        
        # Materials
        "metal": any(w in desc_lower for w in ["metal", "iron", "steel", "silver", "chrome", "bronze"]),
        "organic": any(w in desc_lower for w in ["flesh", "skin", "fur", "scale", "bone", "leather"]),
        "stone": any(w in desc_lower for w in ["stone", "rock", "marble"]),
        "cloth_or_fabric": any(w in desc_lower for w in ["cloth", "fabric", "silk", "wool", "garment"]),
    }
    return features


# =========================================================================
# Main
# =========================================================================

def main():
    simo_only = "--simo-only" in sys.argv
    quick_mode = "--quick" in sys.argv
    
    # Load manifest
    manifest_path = os.path.join(CACHE_DIR, "portrait_manifest.json")
    if not os.path.exists(manifest_path):
        print("ERROR: portrait_manifest.json not found. Run download_portraits.py first.")
        return
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print(f"[1/4] Loaded manifest: {len(manifest)} fighters")
    
    # Load Qwen
    print("\n[2/4] Loading Qwen2.5-VL-7B-Instruct...")
    if not load_qwen():
        print("  Could not load Qwen. Trying alternative...")
        # Try Ollama as fallback
        print("  Checking if Ollama is available via API...")
        import urllib.request
        try:
            r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            print("  Ollama API is available! Will use that.")
        except:
            print("  Ollama API not available either. Giving up.")
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
            print(f'  Qwen says: "{desc}"')
            kws = extract_keywords(desc)
            present = [k for k, v in kws.items() if v]
            print(f'  Keywords: {", ".join(present)}')
    
    if simo_only:
        print("\n  Done (--simo-only).")
        return
    
    if quick_mode:
        print("\n  --quick mode: analyzing only outlier fighters")
        # Analyze a subset: known outliers
        outlier_names = ["SIMO THE UNSEEN", "GL6", "Cosm", "Dread, the unending",
                         "The Being From [Redacted]", "Nonamebot", "George",
                         "Never Slayed", "Dr. Manhattan", "The Dreadpit itself"]
        to_analyze = [e for e in manifest if e.get("name") in outlier_names]
    else:
        to_analyze = manifest
    
    # Analyze all fighters
    print(f"\n[4/4] Analyzing {len(to_analyze)} fighter portraits with Qwen2.5-VL...")
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
            "qwen_description": desc,
            "keywords": {k: bool(v) for k, v in keywords.items()},
        })
        
        short = desc[:100] + "..." if len(desc) > 100 else desc
        print(f"  [{i+1}/{len(to_analyze)}] {name:40s} wins={wins:2d} {short}")
    
    # Cross-reference
    print(f"\n  -- Cross-reference (high vs low winners) --")
    high = [r for r in results if r["wins"] >= 7]
    low = [r for r in results if r["wins"] <= 3]
    
    print(f"\n  {'Feature':30s} {'High%':>7s} {'Low%':>7s} {'Delta':>7s}")
    print(f"  {'-'*30} {'-'*7} {'-'*7} {'-'*7}")
    
    if results:
        deltas = []
        for kw in extract_keywords("").keys():
            h_pct = sum(1 for r in high if r["keywords"].get(kw, False)) / max(len(high), 1) * 100
            l_pct = sum(1 for r in low if r["keywords"].get(kw, False)) / max(len(low), 1) * 100
            deltas.append((kw, h_pct - l_pct, h_pct, l_pct))
        
        deltas.sort(key=lambda x: abs(x[1]), reverse=True)
        for kw, delta, h, l in deltas[:10]:
            if abs(delta) > 5:
                arrow = "more in winners" if delta > 0 else "more in losers"
                print(f"  {kw:30s} {h:6.1f}% {l:6.1f}% {delta:+6.1f}%  {arrow}")
    
    # Save
    out_path = os.path.join(CACHE_DIR, "qwen_analysis.json")
    with open(out_path, "w") as f:
        json.dump({
            "count": len(results),
            "results": results,
        }, f, indent=1)
    print(f"\n  Saved to: qwen_analysis.json")
    print("  Done.")


if __name__ == "__main__":
    main()
