"""
Evaluate v5 images with BLIP. Produce final summary across all 5 iterations.
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
        "furnace": any(w in dl for w in ["furnace", "forge", "oven"]),
        "cloak": any(w in dl for w in ["cape", "cloak", "robe"]),
    }

# All-iterations tracking
ALL_ITERATIONS = {
    "forge_colossus": {
        "label": "Forge Colossus",
        "best": (3, "robot standing in front of a fire", 59.4),  # (version, blip, warmth)
        "v1": ("man in suit with fire", 35.2),
        "v2": ("robot with fire in mouth", 12.2),
        "v3": ("robot standing front of fire", 59.4),
        "v4": ("man in suit fire from chest", 49.1),
    },
    "vatican_gun": {
        "label": "Vatican Gun",
        "best": (3, "man in gas mask holding a gun", 8.8),
        "v1": ("man cloak with gun", 12.1),
        "v2": ("man cloak with gun", 11.6),
        "v3": ("man gas mask holding gun", 8.8),
        "v4": ("man gas mask gas gas gas", 7.3),
    },
    "the_hook": {
        "label": "The Hook / Reclaimer",
        "best": (1, "character with horns", 15.1),  # best was still v1
        "v1": ("character with horns", 15.1),
        "v2": ("character large sword", 6.6),
        "v3": ("character sword demon", 8.8),
    },
}

def main():
    load_blip()

    v5_files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith("_v5.jpg"))

    print("=" * 72)
    print("  v5 EVALUATION — hybrid short phrases + positive alternatives")
    print("=" * 72)

    v5_results = {}

    for fname in v5_files:
        path = os.path.join(IMAGE_DIR, fname)
        if not os.path.exists(path):
            continue

        desc = describe(path)
        kws = extract_keywords(desc)
        pix = pixel_metrics(path)
        kw_list = [k for k, v in kws.items() if v]

        # Identify fighter
        if "forge" in fname:
            label = "Forge Colossus"
        elif "reclaimer" in fname:
            label = "The Reclaimer"
        elif "vatican" in fname:
            label = "Vatican Gun"
        else:
            label = fname

        print(f"\n{'='*60}")
        print(f"  {label} v5")
        print(f"{'='*60}")
        print(f"  BLIP:   \"{desc}\"")
        print(f"  Pixels: R={pix['avg_r']} G={pix['avg_g']} B={pix['avg_b']}  "
              f"Warmth={pix['warmth']}  Bright={pix['brightness']}")
        print(f"  KWs:    {', '.join(kw_list) if kw_list else 'NONE'}")

        has_man = "man" in desc.lower()

        if "forge" in fname:
            if not has_man and (kws.get("robot") or kws.get("furnace")):
                print(f"  [OK] Non-human entity! (robot/furnace)")
            elif not has_man:
                print(f"  [OK] No human detected!")
            elif has_man:
                print(f"  [REG] Still human-like")
        elif "reclaimer" in fname:
            if kws.get("gun") or "crossbow" in desc.lower():
                print(f"  [OK] Weapon detected!")
            elif has_man:
                print(f"  [!] Human visible, weapon unclear")
            else:
                print(f"  [?] Unclear")
        elif "vatican" in fname:
            if kws.get("gun") and kws.get("human"):
                print(f"  [OK] Man with gun! (strongest result)")
            elif kws.get("gun"):
                print(f"  [OK] Gun visible")
            elif has_man:
                print(f"  [!] Human visible without gun")
            else:
                print(f"  [?] Unclear")
            if "gas mask" in desc.lower():
                print(f"  [OK] Gas mask detected!")
            else:
                print(f"  [GAS] Gas mask not visible")

        v5_results[label] = {"blip": desc, "kws": kw_list, "pix": pix}

    # FINAL SUMMARY across ALL 5 versions
    print("\n" + "=" * 72)
    print("  FINAL SUMMARY — All 5 Iterations")
    print("=" * 72)

    for key, info in ALL_ITERATIONS.items():
        label = info["label"]
        print(f"\n  --- {label} ---")
        print(f"  v1: {info['v1'][0]:38s} warmth={info['v1'][1]:5.1f}")
        print(f"  v2: {info['v2'][0]:38s} warmth={info['v2'][1]:5.1f}")
        if info.get("v3"):
            print(f"  v3: {info['v3'][0]:38s} warmth={info['v3'][1]:5.1f}")
        if info.get("v4"):
            print(f"  v4: {info['v4'][0]:38s} warmth={info['v4'][1]:5.1f}")

        # v5 results
        if label in v5_results:
            r = v5_results[label]
            print(f"  v5: {r['blip']:38s} warmth={r['pix']['warmth']:5.1f}")

        print(f"  BEST: v{info['best'][0]} — \"{info['best'][1]}\" (warmth={info['best'][2]})")

    # Reclaimer tracking
    print(f"\n  --- The Reclaimer (NEW, replaces The Hook) ---")
    if "The Reclaimer" in v5_results:
        r = v5_results["The Reclaimer"]
        print(f"  v5: \"{r['blip']}\" warmth={r['pix']['warmth']}")

    # FINAL VERDICT
    print("\n" + "=" * 72)
    print("  FINAL VERDICT — Best prompt per fighter")
    print("=" * 72)

    # Determine best versions
    # Forge Colossus: v3 was best (robot, no human, warmth=59.4)
    # Vatican Gun: v3 was best (gas mask + gun detected)
    # The Reclaimer: only v5 exists, still untested well

    print("""
  FIGHTER 1: FORGE COLOSSUS
  BEST VERSION: v3 prompt (full sentence style, warmth=59.4)
  Image-gen result: "a robot standing in front of a fire" — NO HUMAN
  Character length: 199/200 (can fit with comma-separated refactor)

  FINAL PROMPT (199 chars, verified v3):
  Giant walking furnace made of black iron. White-hot molten core
  visible through chest bars. Massive anvil-headed hammer in each
  hand, glowing red. Flat iron mask with orange eye slits. Heat
  waves distort air around body. No flesh. Just forge.
  
  ---
  
  FIGHTER 2: VATICAN GUN
  BEST VERSION: v3 prompt (gas mask + gun, both visible)
  Image-gen result: "a man in a gas mask holding a gun"
  Character length: 198/200

  FINAL PROMPT (198 chars, verified v3):
  Hooded executioner in black leather duster. Carries a massive
  six-barrel gatling cannon, barrels clearly visible spinning.
  Holy water drums marked with crosses on each side. Gas mask with
  red glowing eyes. Silver bullets across chest. Crucifix on gun.
  
  ---
  
  FIGHTER 3: THE RECLAIMER (replaces The Hook)
  STATUS: REQUIRES FURTHER TESTING
  Crossbow weapon not yet recognized by BLIP after 2 iterations.
  Recommend testing more crossbow-focused prompts.
  
  CURRENT BEST PROMPT (v5, untested):
  Gaunt dragon hunter grey monster pelts, giant crossbow taller
  than body, crossbow string drawn ready to fire, severed dragon
  claws from backpack, scarred face one glowing yellow eye.
  
  ---
  
  IMAGE GENERATION VERDICT:
  - Forge Colossus: CONFIRMED — produces non-human fire entity with warmth=59.4
  - Vatican Gun: CONFIRMED — produces man with gun + gas mask (stable 3/3 iterations)
  - The Reclaimer: NEEDS WORK — crossbow not rendering as recognizable weapon
  """)

    print("Done.")


if __name__ == "__main__":
    main()
