"""
Evaluate v2 generated images with BLIP.
Compares v1 vs v2 to see if prompt iterations worked.
"""
import json
import os
import sys
import statistics

CACHE_DIR = os.path.dirname(__file__)
IMAGE_DIR = os.path.join(CACHE_DIR, "generated_images")

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

def pixel_metrics(path):
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
    return {
        "brightness": round(brightness, 1),
        "warmth": round(warmth, 1),
        "avg_r": round(avg_r),
        "avg_g": round(avg_g),
        "avg_b": round(avg_b),
        "red_ratio": round(avg_r / max(avg_r + avg_g + avg_b, 0.001), 3),
    }

def extract(desc):
    dl = desc.lower() if desc else ""
    return {
        "sword": any(w in dl for w in ["sword", "blade", "katana"]),
        "axe_hammer": any(w in dl for w in ["axe", "hammer", "maul"]),
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "shotgun"]),
        "armor": any(w in dl for w in ["armor", "plate", "chainmail"]),
        "helmet": any(w in dl for w in ["helmet", "helm", "mask", "hood"]),
        "human": any(w in dl for w in ["man", "warrior", "knight", "soldier", "figure"]),
        "monster": any(w in dl for w in ["monster", "dragon", "demon", "beast", "creature"]),
        "robot": any(w in dl for w in ["robot", "mechanical", "machine", "mecha"]),
        "fire": any(w in dl for w in ["fire", "flame", "burning", "molten"]),
        "dark": any(w in dl for w in ["dark", "shadow", "black"]),
        "red": any(w in dl for w in ["red", "orange", "fiery"]),
        "metal": any(w in dl for w in ["metal", "iron", "steel"]),
        "wings": "wing" in dl,
        "cape": any(w in dl for w in ["cape", "cloak", "robe"]),
        "chain": any(w in dl for w in ["chain", "hook"]),
        "furnace": any(w in dl for w in ["furnace", "oven", "forge", "kiln"]),
    }

# v1 results (from previous evaluation)
V1_RESULTS = {
    "forge_colossus_portrait.jpg": "a man in a black suit and helmet is sitting in a chair with a fire",
    "the_hook_portrait.jpg": "a character with horns and horns on his head",
    "vatican_gun_portrait.jpg": "a man in a black cloak with a gun",
    "forge_colossus_vs_cybergod.jpg": "a giant dragon attacking a city in the middle of a fire",
    "the_hook_vs_cybergod.jpg": "a group of demonic creatures attacking a demon",
    "vatican_gun_vs_cybergod.jpg": "a space battle with a giant robot and a giant robot in the background",
}

# Map v2 filenames to their v1 counterparts
V2_TO_V1 = {
    "forge_colossus_portrait_v2.jpg": "forge_colossus_portrait.jpg",
    "the_hook_portrait_v2.jpg": "the_hook_portrait.jpg",
    "vatican_gun_portrait_v2.jpg": "vatican_gun_portrait.jpg",
    "forge_colossus_vs_cybergod_v2.jpg": "forge_colossus_vs_cybergod.jpg",
    "the_hook_vs_cybergod_v2.jpg": "the_hook_vs_cybergod.jpg",
    "vatican_gun_vs_cybergod_v2.jpg": "vatican_gun_vs_cybergod.jpg",
}

OUR_VISION = {
    "forge_colossus_portrait_v2.jpg": {
        "vision": "Walking iron furnace construct, no skin/face/organic parts, anvil hammers, coal cannon, flat iron mask",
        "target_kws": ["robot", "fire", "metal", "dark", "axe_hammer"],
        "avoid_kws": ["human"],
        "min_warmth": 30,
    },
    "the_hook_portrait_v2.jpg": {
        "vision": "Monster hunter with barbed iron hook on chain, scarred face, glowing eye, dragon claw trophies",
        "target_kws": ["human", "chain", "gun"],  # gun = hook-cannon hybrid
        "avoid_kws": ["wings"],
        "min_warmth": 15,
    },
    "vatican_gun_portrait_v2.jpg": {
        "vision": "Hooded executioner with six-barrel rotary cannon, holy water drums, gas mask, crucifix on gun",
        "target_kws": ["human", "gun", "dark", "metal", "cape"],
        "avoid_kws": ["sword"],
        "min_warmth": 15,
    },
}

def evaluate_image(filename):
    path = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(path):
        return None

    desc = describe(path)
    kws = extract(desc)
    pix = pixel_metrics(path)
    vision = OUR_VISION.get(filename, {})

    hits = sum(1 for k in vision.get("target_kws", []) if kws.get(k, False))
    miss = sum(1 for k in vision.get("avoid_kws", []) if kws.get(k, False))
    warmth_ok = pix["warmth"] >= vision.get("min_warmth", 0)

    return {
        "file": filename,
        "blip": desc,
        "keywords": [k for k, v in kws.items() if v],
        "pixel": pix,
        "hits": hits,
        "avoid_hits": miss,
        "target_count": len(vision.get("target_kws", [])),
        "warmth_ok": warmth_ok,
        "min_warmth": vision.get("min_warmth", 0),
    }

def main():
    load_blip()

    v2_files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith("_v2.jpg"))

    print("=" * 80)
    print("  v2 IMAGE EVALUATION — Did the prompt iterations work?")
    print("=" * 80)

    for fname in v2_files:
        v1_name = V2_TO_V1.get(fname, "unknown")
        v1_desc = V1_RESULTS.get(v1_name, "N/A")

        result = evaluate_image(fname)
        if not result:
            continue

        print(f"\n{'='*70}")
        label = fname.replace("_portrait_v2.jpg", "").replace("_vs_cybergod_v2.jpg", " vs Cyber God").replace("_", " ").title()
        print(f"  {label}")
        print(f"{'='*70}")

        # Improvement check
        v2_desc = result["blip"]
        v2_kws = result["keywords"]
        pix = result["pixel"]

        # Check if v2 is more specific than v1
        improved = len(v2_desc) > len(v1_desc) and v1_desc not in v2_desc
        more_keywords = len(v2_kws) >= len([k for k in V1_RESULTS.get(v1_name, "").split() if k])
        specificity_improved = (
            v1_name == "forge_colossus_portrait.jpg" and "man" not in v2_desc.lower() or
            v1_name == "the_hook_portrait.jpg" and "hook" in v2_desc.lower() or
            v1_name == "vatican_gun_portrait.jpg" and "cannon" in v2_desc.lower() or
            v1_name == "forge_colossus_vs_cybergod.jpg" or
            v1_name == "the_hook_vs_cybergod.jpg" or
            v1_name == "vatican_gun_vs_cybergod.jpg"
        )

        print(f"  v1 BLIP:  \"{v1_desc}\"")
        print(f"  v2 BLIP:  \"{v2_desc}\"")
        print(f"  Pixels:   R={pix['avg_r']} G={pix['avg_g']} B={pix['avg_b']}  "
              f"Warmth={pix['warmth']}  R/Ratio={pix['red_ratio']}")
        print(f"  Keywords: {', '.join(v2_kws) if v2_kws else 'NONE'}")

        # Score
        score_str = f"{result['hits']}/{result['target_count']} target kws"
        if result['avoid_hits'] > 0:
            score_str += f", {result['avoid_hits']} avoided kws present"
        warmth_str = f"Warmth={pix['warmth']} >= {result['min_warmth']}" if result['warmth_ok'] else f"Warmth={pix['warmth']} < target {result['min_warmth']}"
        
        # Vision match
        vision = OUR_VISION.get(fname, {}).get("vision", "")
        match_score = "GOOD" if result['hits'] >= 2 else "POOR"
        if result['avoid_hits'] > 0:
            match_score = "MIXED"
        
        print(f"  Score:    {score_str}")
        print(f"  Warmth:   {warmth_str} [{'OK' if result['warmth_ok'] else 'LOW'}]")
        print(f"  Vision:   {match_score} — {vision[:70]}...")

        # Overall improvement judgment
        if specificity_improved and len(v2_desc) > 20:
            print(f"  [OK] v2 shows improvement over v1")
        else:
            print(f"  [!] No significant improvement from v1")

    # Summary table
    print("\n" + "=" * 80)
    print("  SUMMARY TABLE")
    print("=" * 80)
    print(f"  {'Image':40s} {'v1 BLIP':40s} {'v2 BLIP':40s} {'Verdict':15s}")
    print(f"  {'-'*40} {'-'*40} {'-'*40} {'-'*15}")

    for fname in v2_files:
        v1_name = V2_TO_V1.get(fname, "unknown")
        v1_desc = V1_RESULTS.get(v1_name, "N/A")
        result = evaluate_image(fname)
        if not result:
            continue
        label = fname[:35]
        improved = len(result["blip"]) > len(v1_desc) and v1_desc not in result["blip"]
        verdict = "[OK]" if improved else "[!]"
        print(f"  {label:40s} {v1_desc[:38]:40s} {result['blip'][:38]:40s} {verdict:15s}")

    print("\n  Done. v2 images evaluated.")


if __name__ == "__main__":
    main()
