"""
Evaluate v3 generated images with BLIP.
"""
import json
import os
import statistics

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(CACHE_DIR, "generated_images")

_proc = None
_model = None

def load_blip():
    global _proc, _model
    if _model is not None:
        return True
    from transformers import BlipProcessor, BlipForConditionalGeneration
    import torch
    print("Loading BLIP...")
    _proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("BLIP ready.")
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

def extract_keywords(desc):
    dl = desc.lower() if desc else ""
    return {
        "sword": any(w in dl for w in ["sword", "blade"]),
        "hammer": any(w in dl for w in ["axe", "hammer", "maul"]),
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "shotgun"]),
        "armor": any(w in dl for w in ["armor", "plate", "chainmail"]),
        "helmet": any(w in dl for w in ["helmet", "helm", "mask", "hood"]),
        "human": any(w in dl for w in ["man", "warrior", "knight", "soldier", "figure"]),
        "monster": any(w in dl for w in ["monster", "dragon", "demon", "beast", "creature"]),
        "robot": any(w in dl for w in ["robot", "mechanical", "machine", "mecha"]),
        "fire": any(w in dl for w in ["fire", "flame", "burning", "molten"]),
        "dark": any(w in dl for w in ["dark", "shadow", "black"]),
        "metal": any(w in dl for w in ["metal", "iron", "steel"]),
        "chain": any(w in dl for w in ["chain", "hook", "harpoon"]),
        "furnace": any(w in dl for w in ["furnace", "forge", "oven"]),
        "cloak": any(w in dl for w in ["cape", "cloak", "robe"]),
    }

def main():
    load_blip()

    v3_files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith("_v3.jpg"))

    print("=" * 72)
    print("  v3 IMAGE EVALUATION")
    print("=" * 72)

    results = []

    for fname in v3_files:
        path = os.path.join(IMAGE_DIR, fname)
        if not os.path.exists(path):
            continue

        desc = describe(path)
        kws = extract_keywords(desc)
        pix = pixel_metrics(path)
        kw_list = [k for k, v in kws.items() if v]

        label = fname.replace("_portrait_v3.jpg", "").replace("_vs_cybergod_v3.jpg", " vs Cyber God").replace("_", " ").title()

        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        print(f"  BLIP:   {desc}")
        print(f"  Pixels: R={pix['avg_r']} G={pix['avg_g']} B={pix['avg_b']}  "
              f"Warmth={pix['warmth']}  Bright={pix['brightness']}")
        print(f"  KWs:    {', '.join(kw_list) if kw_list else 'NONE'}")

        # Per-fighter judgment
        has_man = "man" in desc.lower()
        if "forge" in fname.lower():
            if has_man:
                print(f"  [FAIL] Still human-like (has 'man')")
            elif kws.get("robot") or kws.get("furnace"):
                print(f"  [OK] Non-human entity (robot/furnace)")
            elif kws.get("metal") or kws.get("fire"):
                print(f"  [OK] Has elemental presence (metal/fire)")
            else:
                print(f"  [?] Unclear what it looks like")
        elif "hook" in fname.lower():
            if kws.get("chain"):
                print(f"  [OK] Chain/hook/harpoon weapon visible!")
            elif has_man:
                print(f"  [!] Human visible, weapon unclear")
            else:
                print(f"  [?] Unclear")
        elif "vatican" in fname.lower():
            if kws.get("gun") and kws.get("human"):
                print(f"  [OK] Man with gun")
            elif kws.get("gun"):
                print(f"  [OK] Gun visible")
            else:
                print(f"  [?] Unclear")

        results.append({
            "file": fname,
            "label": label,
            "blip": desc,
            "keywords": kw_list,
            "pixel": pix,
        })

    # Summary
    print("\n" + "=" * 72)
    print("  v3 SUMMARY TABLE")
    print("=" * 72)
    warmths = [r["pixel"]["warmth"] for r in results]
    print(f"  Warmth range: {min(warmths):.1f} - {max(warmths):.1f}  (avg: {statistics.mean(warmths):.1f})")
    print()
    for r in results:
        print(f"  {r['file'][:40]:40s} warmth={r['pixel']['warmth']:6.1f}  KWs: {', '.join(r['keywords'][:4]) if r['keywords'] else 'NONE':30s}  BLIP: {r['blip'][:40]}")
    print("\nDone.")


if __name__ == "__main__":
    main()
