"""
Evaluate v4 images (comma-separated short prompts) with BLIP.
"""
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
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "shotgun", "crossbow", "bow"]),
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

# v3 results for comparison
V3_RESULTS = {
    "forge_colossus": ("a robot standing in front of a fire", 59.4, ["robot", "fire"]),
    "vatican_gun": ("a man in a gas mask holding a gun", 8.8, ["gun", "helmet", "human"]),
}

# We expect some regression on Forge Colossus since we removed "No flesh"
# We expect The Reclaimer to show crossbow instead of sword
# We expect Vatican Gun to maintain or improve

def main():
    load_blip()

    v4_files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith("_v4.jpg"))

    print("=" * 72)
    print("  v4 IMAGE EVALUATION — comma-separated short prompts")
    print("=" * 72)

    for fname in v4_files:
        path = os.path.join(IMAGE_DIR, fname)
        if not os.path.exists(path):
            continue

        desc = describe(path)
        kws = extract_keywords(desc)
        pix = pixel_metrics(path)
        kw_list = [k for k, v in kws.items() if v]

        # Identify which fighter
        if "forge" in fname:
            fighter = "forge_colossus"
            label = "Forge Colossus"
        elif "reclaimer" in fname:
            fighter = "the_reclaimer"
            label = "The Reclaimer (NEW)"
        elif "vatican" in fname:
            fighter = "vatican_gun"
            label = "Vatican Gun"
        else:
            fighter = "unknown"
            label = fname

        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        print(f"  BLIP:   \"{desc}\"")
        print(f"  Pixels: R={pix['avg_r']} G={pix['avg_g']} B={pix['avg_b']}  "
              f"Warmth={pix['warmth']}  Bright={pix['brightness']}")
        print(f"  KWs:    {', '.join(kw_list) if kw_list else 'NONE'}")

        # Compare with v3 if available
        has_man = "man" in desc.lower()
        if fighter in V3_RESULTS:
            v3_desc, v3_warmth, v3_kws = V3_RESULTS[fighter]
            warmth_change = pix["warmth"] - v3_warmth
            print(f"  v3 was: \"{v3_desc}\" (warmth={v3_warmth})")
            print(f"  Warmth change: {warmth_change:+.1f}")

        # Per-fighter checks
        if "forge" in fname:
            if has_man:
                print(f"  [REG] Still human-like (has 'man') — style change may have regressed")
            elif kws.get("robot") or kws.get("furnace"):
                print(f"  [OK] Non-human entity preserved despite style change!")
            elif kws.get("fire") or kws.get("metal"):
                print(f"  [OK] Has elemental presence")
            else:
                print(f"  [?] Unclear")
        elif "reclaimer" in fname:
            if kws.get("gun") or "crossbow" in desc.lower() or "bow" in desc.lower():
                print(f"  [OK] Crossbow weapon detected!")
            elif has_man and kws.get("monster"):
                print(f"  [OK] Human vs monster visible")
            elif has_man:
                print(f"  [!] Human visible, weapon unclear")
            else:
                print(f"  [?] Unclear")
        elif "vatican" in fname:
            if kws.get("gun") and kws.get("human"):
                print(f"  [OK] Man with gun")
            elif kws.get("gun"):
                print(f"  [OK] Gun visible")
            elif has_man:
                print(f"  [!] Human visible without gun")
            else:
                print(f"  [?] Unclear")
            if "gas mask" in desc.lower():
                print(f"  [OK] Gas mask visible!")
            else:
                print(f"  [GAS] Gas mask not in BLIP description")

    # All-versions comparison table
    print("\n" + "=" * 72)
    print("  ALL VERSIONS COMPARISON")
    print(f"{'='*72}")
    print(f"  {'Fighter':22s} {'v1':35s} {'v2':35s} {'v3':35s} {'v4':35s}")
    print(f"  {'-'*22} {'-'*35} {'-'*35} {'-'*35} {'-'*35}")

    fighters_data = {
        "forge_colossus": {
            "label": "Forge Colossus",
            "versions": {
                "v1": ("man in suit with fire", 35.2),
                "v2": ("robot with fire in mouth", 12.2),
                "v3": ("robot standing front of fire", 59.4),
            }
        },
        "vatican_gun": {
            "label": "Vatican Gun",
            "versions": {
                "v1": ("man cloak with gun", 12.1),
                "v2": ("man cloak with gun", 11.6),
                "v3": ("man gas mask holding gun", 8.8),
            }
        },
        "the_hook": {
            "label": "The Hook (→ Reclaimer)",
            "versions": {
                "v1": ("character with horns", 15.1),
                "v2": ("character large sword", 6.6),
                "v3": ("character sword demon", 8.8),
            }
        },
    }

    # Check v4 results
    v4_descs = {}
    for fname in v4_files:
        path = os.path.join(IMAGE_DIR, fname)
        if os.path.exists(path):
            desc = describe(path)
            v4_descs[fname] = desc

    for key, info in fighters_data.items():
        label = info["label"]
        v1_str = f"{info['versions']['v1'][0][:28]} ({info['versions']['v1'][1]:.0f}w)"
        v2_str = f"{info['versions']['v2'][0][:28]} ({info['versions']['v2'][1]:.0f}w)"
        v3_str = f"{info['versions']['v3'][0][:28]} ({info['versions']['v3'][1]:.0f}w)"
        
        # v4 — check if this fighter has a v4 file
        v4_fname = f"{key.replace('the_', '')}_portrait_v4.jpg"
        if key == "forge_colossus":
            v4_fname = "forge_colossus_portrait_v4.jpg"
        elif key == "vatican_gun":
            v4_fname = "vatican_gun_portrait_v4.jpg"
        
        v4_str = "N/A"
        if v4_fname in v4_descs:
            # Get warmth for v4
            path = os.path.join(IMAGE_DIR, v4_fname)
            pix = pixel_metrics(path)
            v4_str = f"{v4_descs[v4_fname][:28]} ({pix['warmth']:.0f}w)"
        
        print(f"  {label:22s} {v1_str:35s} {v2_str:35s} {v3_str:35s} {v4_str:35s}")

    # The Reclaimer gets its own line
    for fname in v4_files:
        if "reclaimer" in fname:
            path = os.path.join(IMAGE_DIR, fname)
            desc = v4_descs.get(fname, "N/A")
            pix = pixel_metrics(path)
            print(f"\n  {'The Reclaimer':22s} {'—':35s} {'—':35s} {'—':35s} {desc[:28]:35s} ({pix['warmth']:.0f}w)")
            print(f"  {'':22s} {'N/A (NEW)':35s} {'':35s} {'':35s} {'':35s}")

    print("\nDone.")


if __name__ == "__main__":
    main()
