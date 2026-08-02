"""
Evaluate generated fighter images using BLIP.
Tells us if the image gen actually produced what we envisioned.
"""
import json
import os
import sys
import statistics

sys.path.insert(0, os.path.dirname(__file__))

CACHE_DIR = os.path.dirname(__file__)
IMAGE_DIR = os.path.join(CACHE_DIR, "generated_images")

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
    }

# Our expectations for each image
EXPECTATIONS = {
    "forge_colossus_portrait.jpg": {
        "expected_kws": ["fire", "metal", "robot", "dark", "axe_hammer"],
        "avoid_kws": ["human", "wings"],
        "min_warmth": 25,
        "notes": "Should be a massive iron furnace giant with anvil hammers, no skin, no organic parts"
    },
    "the_hook_portrait.jpg": {
        "expected_kws": ["human", "dark", "chain"],
        "avoid_kws": ["armor"],
        "min_warmth": 15,
        "notes": "Gaunt hunter with pelts, chain hook, dragon claw trophies. Should NOT have heavy armor"
    },
    "vatican_gun_portrait.jpg": {
        "expected_kws": ["human", "gun", "dark", "metal"],
        "avoid_kws": ["wings", "sword"],
        "min_warmth": 15,
        "notes": "Executioner with rotary cannon, holy water drums, gas mask, crucifix on gun"
    },
    "forge_colossus_vs_cybergod.jpg": {
        "expected_kws": ["fire", "monster", "metal", "dark"],
        "min_warmth": 20,
        "notes": "Forge Colossus fighting Cyber God's dragon. Epic battle scene"
    },
    "the_hook_vs_cybergod.jpg": {
        "expected_kws": ["human", "monster", "chain", "dark"],
        "notes": "Hook pulling god off dragon mount"
    },
    "vatican_gun_vs_cybergod.jpg": {
        "expected_kws": ["human", "gun", "monster", "fire", "dark"],
        "notes": "Executioner firing holy cannon at Cyber God on dragon"
    },
}

def evaluate_image(filename):
    path = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(path):
        return None

    desc = describe(path)
    kws = extract(desc)
    pix = pixel_metrics(path)
    exp = EXPECTATIONS.get(filename, {})

    # Score
    hits = sum(1 for k in exp.get("expected_kws", []) if kws.get(k, False))
    misses = sum(1 for k in exp.get("avoid_kws", []) if kws.get(k, False))
    expected_count = len(exp.get("expected_kws", []))
    kw_score = f"{hits}/{expected_count} expected keywords"
    if misses > 0:
        kw_score += f", {misses} unwanted keywords present"

    return {
        "file": filename,
        "blip": desc,
        "keywords": kws,
        "pixel": pix,
        "score": kw_score,
        "warmth_ok": pix["warmth"] >= exp.get("min_warmth", 0),
    }

def main():
    load_blip()

    files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg"))
    print("=" * 72)
    print("  GENERATED IMAGE EVALUATION — BLIP ANALYSIS")
    print("=" * 72)

    all_results = []
    for fname in files:
        print(f"\n{'='*60}")
        print(f"  [img] {fname}")
        print(f"{'='*60}")
        result = evaluate_image(fname)
        if not result:
            print("  ERROR: File not found")
            continue
        all_results.append(result)

        print(f"  BLIP says:  \"{result['blip']}\"")
        pix = result["pixel"]
        print(f"  Pixels:     R={pix['avg_r']} G={pix['avg_g']} B={pix['avg_b']}  "
              f"Warmth={pix['warmth']}  RedRatio={pix['red_ratio']}  "
              f"Brightness={pix['brightness']}")
        print(f"  Keywords:   {', '.join(k for k, v in result['keywords'].items() if v) or 'NONE'}")
        print(f"  Score:      {result['score']}")

        # Warmth check
        exp = EXPECTATIONS.get(fname, {})
        if "min_warmth" in exp:
            status = "[OK]" if result["warmth_ok"] else "[FAIL]"
            print(f"  Warmth:     {status} Target >= {exp['min_warmth']}, got {pix['warmth']}")

    # Summary
    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)

    warmths = [r["pixel"]["warmth"] for r in all_results]
    avg_warmth = statistics.mean(warmths)
    print(f"  Average warmth: {avg_warmth:.1f}")
    print(f"  Warmth range:   {min(warmths):.1f} - {max(warmths):.1f}")

    print(f"\n  -- VERDICT --")
    for r in all_results:
        desc = r["blip"]
        notes = EXPECTATIONS.get(r["file"], {}).get("notes", "")
        print(f"\n  [IMG] {r['file']}")
        print(f"     BLIP: \"{desc}\"")
        print(f"     Wanted: {notes[:80]}...")
        # Quick judgment
        has_expected = any(k in r['keywords'] for k in ['fire', 'gun', 'chain', 'metal', 'monster'])
        print(f"     {'[OK] Has relevant visual elements' if has_expected else '[WARN]  May not match intent'}")

    print("\n  Done. All images evaluated.")


if __name__ == "__main__":
    main()
