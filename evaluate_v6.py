"""
Evaluate v6 fighter images with BLIP.
Compare against v3 (best performing iteration) to measure improvement.
"""
import json
import os
import sys
from PIL import Image
import statistics

# BLIP imports
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(CACHE_DIR, "generated_images")


def load_blip():
    print("Loading BLIP model...", end=" ", flush=True)
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("OK")
    return processor, model


def describe(image_path, processor, model):
    image = Image.open(image_path).convert("RGB")
    inputs = processor(image, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(**inputs, max_length=50)
    desc = processor.decode(out[0], skip_special_tokens=True)
    return desc


def pixel_metrics(image_path):
    img = Image.open(image_path).convert("RGB")
    pixels = list(img.getdata())
    r_vals = [p[0] for p in pixels]
    g_vals = [p[1] for p in pixels]
    b_vals = [p[2] for p in pixels]
    total = len(pixels)
    avg_r = statistics.mean(r_vals)
    avg_g = statistics.mean(g_vals)
    avg_b = statistics.mean(b_vals)
    brightness = (avg_r + avg_g + avg_b) / 3
    warmth = avg_r - avg_b
    red_ratio = avg_r / max(avg_r + avg_g + avg_b, 1)
    return {
        "brightness": round(brightness, 1),
        "warmth": round(warmth, 1),
        "red_ratio": round(red_ratio, 3),
        "avg_r": round(avg_r, 1),
        "avg_g": round(avg_g, 1),
        "avg_b": round(avg_b, 1),
    }


def extract_keywords(desc):
    dl = desc.lower()
    return {
        "sword": "sword" in dl or "blade" in dl,
        "axe_hammer": any(w in dl for w in ["axe", "hammer"]),
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "gatling"]),
        "armor": "armor" in dl or "armour" in dl,
        "helmet": "helmet" in dl,
        "human": any(w in dl for w in ["man", "woman", "human", "person", "character"]),
        "monster": any(w in dl for w in ["demon", "monster", "beast", "dragon", "fiend"]),
        "robot": any(w in dl for w in ["robot", "mech", "gundam", "android"]),
        "fire": any(w in dl for w in ["fire", "flame", "burn", "blaze", "molten", "lava", "ember"]),
        "dark": any(w in dl for w in ["dark", "black", "shadow", "obsidian"]),
        "red": "red" in dl or "orange" in dl,
        "blue": "blue" in dl,
        "metal": any(w in dl for w in ["metal", "iron", "steel", "forged"]),
        "wings": "wings" in dl or "winged" in dl,
        "shield": "shield" in dl,
        "cape": any(w in dl for w in ["cape", "cloak", "duster"]),
    }


def main():
    # v3 baseline results (best iteration)
    V3_RESULTS = {
        "forge_colossus": {
            "blip": "a robot standing in front of a fire",
            "warmth": 59.4,
        },
        "vatican_gun": {
            "blip": "a man in a gas mask holding a gun",
            "warmth": 8.8,
        },
    }

    processor, model = load_blip()

    # v6 fighters to evaluate
    FIGHTERS = [
        ("forge_colossus_portrait_v6.jpg", "forge_colossus", "Forge Colossus v6"),
        ("vatican_gun_portrait_v6.jpg", "vatican_gun", "Vatican Gun v6"),
        ("wrath_infernal_portrait_v6.jpg", "wrath_infernal", "Wrath Infernal v6"),
    ]

    results = {}

    print(f"\n{'='*70}")
    print(f"  v6 EVALUATION vs v3 BASELINE")
    print(f"{'='*70}")

    for fname, key, label in FIGHTERS:
        fpath = os.path.join(IMAGE_DIR, fname)
        if not os.path.exists(fpath):
            print(f"\n  [{label}] FILE NOT FOUND: {fname}")
            continue

        blip_desc = describe(fpath, processor, model)
        pixel = pixel_metrics(fpath)
        kws = extract_keywords(blip_desc)

        results[key] = {
            "file": fname,
            "blip": blip_desc,
            "pixel": pixel,
            "kws": kws,
        }

        # Active KW count
        active_kws = [kw for kw, present in kws.items() if present]
        nn_kws = ["monster", "fire", "red", "dark", "metal", "gun", "robot", "wings"]
        matched_nn = [kw for kw in nn_kws if kws.get(kw, False)]

        print(f"\n  [{label}]")
        print(f"  BLIP: \"{blip_desc}\"")
        print(f"  Warmth: {pixel['warmth']}  |  RedRatio: {pixel['red_ratio']}  |  Brightness: {pixel['brightness']}")
        print(f"  Keywords: {', '.join(sorted(active_kws)) or 'NONE'}")
        print(f"  NN keywords: {', '.join(matched_nn) or 'NONE'}")

        # Compare vs v3
        if key in V3_RESULTS:
            v3 = V3_RESULTS[key]
            warmth_change = pixel["warmth"] - v3["warmth"]
            direction = "IMPROVED" if warmth_change > 0 else "REGRESSED" if warmth_change < 0 else "SAME"
            print(f"  vs v3: \"{v3['blip']}\" (warmth={v3['warmth']})")
            print(f"  Warmth delta: {warmth_change:+0.1f}  [{direction}]")

        # Fighter-specific checks
        if key == "forge_colossus":
            has_robot = "robot" in blip_desc.lower()
            has_fire = any(w in blip_desc.lower() for w in ["fire", "flame"])
            has_human = any(w in blip_desc.lower() for w in ["man", "woman", "person"])
            verdict = "OK" if has_fire and not has_human else "HUMAN FORM DETECTED" if has_human else "MISSING FIRE"
            print(f"  VERDICT: {verdict} {'(non-human + fire = winning combo)' if verdict == 'OK' else ''}")

        elif key == "vatican_gun":
            has_gas_mask = "gas mask" in blip_desc.lower() or "mask" in blip_desc.lower()
            has_gun = any(w in blip_desc.lower() for w in ["gun", "rifle", "cannon"])
            verdict = "OK" if has_gas_mask and has_gun else "MISSING GAS MASK" if not has_gas_mask else "MISSING GUN" if not has_gun else "OK"
            print(f"  VERDICT: {verdict}")

        elif key == "wrath_infernal":
            has_fire = any(w in blip_desc.lower() for w in ["fire", "flame", "burn"])
            has_wings = "wings" in blip_desc.lower() or "winged" in blip_desc.lower()
            has_monster = any(w in blip_desc.lower() for w in ["demon", "monster", "beast", "dragon"])
            checks = []
            if has_fire: checks.append("fire")
            if has_wings: checks.append("wings")
            if has_monster: checks.append("monster")
            verdict = f"OK ({', '.join(checks)})" if len(checks) >= 2 else f"WEAK ({', '.join(checks) or 'NONE'})"
            print(f"  VERDICT: {verdict}")

    # Final confidence assessment
    print(f"\n{'='*70}")
    print(f"  CONFIDENCE ASSESSMENT")
    print(f"{'='*70}")

    for key, r in results.items():
        w = r["pixel"]["warmth"]
        blip = r["blip"]
        kws = r["kws"]

        # Compute confidence score
        score = 0.0
        reasons = []

        # Warmth score (0-40 points) — target > 40
        if w > 50:
            score += 40
            reasons.append(f"warmth={w} (EXCELLENT)")
        elif w > 30:
            score += 30
            reasons.append(f"warmth={w} (GOOD)")
        elif w > 15:
            score += 20
            reasons.append(f"warmth={w} (MODERATE)")
        else:
            score += 10
            reasons.append(f"warmth={w} (LOW — relies on outlier pattern)")

        # NN keyword score (0-30 points)
        nn_keywords = {"monster": 6, "fire": 6, "red": 5, "dark": 4, "metal": 3, "gun": 3, "robot": 3, "wings": 3}
        kw_score = sum(weight for kw, weight in nn_keywords.items() if kws.get(kw, False))
        score += kw_score
        matched_nn = [kw for kw in nn_keywords if kws.get(kw, False)]
        if matched_nn:
            reasons.append(f"NN keywords: {', '.join(matched_nn)}")

        # BLIP recognizability (0-30 points)
        if key == "forge_colossus":
            has_fire = any(w in blip.lower() for w in ["fire", "flame"])
            not_human = not any(w in blip.lower() for w in ["man", "woman", "person"])
            if has_fire and not_human:
                score += 30
                reasons.append("FLUX: non-human fire entity")
            elif not_human:
                score += 15
                reasons.append("FLUX: non-human (no fire detected)")
            else:
                reasons.append("FLUX: human form detected (RISK)")

        elif key == "vatican_gun":
            has_gas = "gas mask" in blip.lower()
            has_weapon = any(w in blip.lower() for w in ["gun", "rifle", "cannon"])
            if has_gas and has_weapon:
                score += 30
                reasons.append("FLUX: gas mask + weapon = distinctive")
            elif has_gas:
                score += 20
                reasons.append("FLUX: gas mask visible")
            elif has_weapon:
                score += 15
                reasons.append("FLUX: weapon visible (gas mask lost)")
            else:
                reasons.append("FLUX: key elements lost (RISK)")

        elif key == "wrath_infernal":
            has_fire = any(w in blip.lower() for w in ["fire", "flame", "burn"])
            has_wings = "wings" in blip.lower() or "winged" in blip.lower()
            has_demon = any(w in blip.lower() for w in ["demon", "monster", "beast"])
            combo = has_fire + has_wings + has_demon
            if combo >= 3:
                score += 30
                reasons.append("FLUX: demon + fire + wings (triple threat)")
            elif combo == 2:
                score += 20
                reasons.append(f"FLUX: {combo}/3 elements detected")
            else:
                reasons.append("FLUX: weak concept recognition")

        confidence = min(score, 100)
        bar = "#" * int(confidence / 5) + "-" * (20 - int(confidence / 5))
        print(f"\n  {key}:")
        print(f"    Confidence: {confidence:.0f}% |{bar}|")
        print(f"    BLIP: \"{blip}\"")
        for r in reasons:
            print(f"    -> {r}")

    # Save results
    out_path = os.path.join(CACHE_DIR, "evaluation_v6.json")
    with open(out_path, "w") as f:
        json.dump({
            "results": results,
            "v3_baseline": V3_RESULTS,
        }, f, indent=2)
    print(f"\nResults saved to evaluation_v6.json")


if __name__ == "__main__":
    main()
