#!/usr/bin/env python3
"""
DEDUCE HEX ENFORCER'S PROMPT

Reconstructs the prompt that likely produced Hex Enforcer's portrait
based on:
  - Original portrait analysis (dark bg, grey+green muted armor, subtle
    magenta-purple visor glow, lean build, helmet)
  - Judge narrations (purple palm energy, glowing visor, shoulder tech,
    arm-mounted weapon, 'blur of grey and green', sleek armor)

Then validates by generating through FLUX (3 seeds) and comparing the
render's pixel fingerprint + BLIP description to the ORIGINAL image.
"""
import json, os, time, urllib.parse, statistics, requests
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "hex_deduction")
os.makedirs(OUT_DIR, exist_ok=True)

ORIGINAL = os.path.join(CACHE_DIR, "..", "dreadpit_analysis", "real_hex_enforcer_portrait.png")

# Multiple deduced-prompt candidates (based on all evidence, <=200 chars each).
# The original BLIP says "a man in a suit and helmet" - keep it HUMAN + SUBTLE.
CANDIDATE_PROMPTS = {
    "v1_subtle_man": (
        "Man in dark grey tactical suit and full helmet, subtle green armor trim, "
        "faint purple visor glow, standing in darkness, moody"
    ),
    "v2_grey_green": (
        "Slim man in grey and green combat suit, full helmet, small glowing "
        "purple visor, subtle green plating, dim light, black background"
    ),
    "v3_original_guess": (
        "Dark cybernetic enforcer, sleek grey and green tech armor, full helmet "
        "with glowing purple visor, subtle purple energy glow from gauntlet, "
        "lean stance, standing in darkness"
    ),
}

SEEDS = [42, 777, 2024]


def generate(prompt, filename, seed, retries=3):
    fp = os.path.join(OUT_DIR, filename)
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        return True, "cached"
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(fp, "wb") as f:
                    f.write(r.content)
                return True, "OK"
            elif r.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                time.sleep(wait)
        except Exception:
            time.sleep(5)
    return False, "failed"


def fingerprint(filepath):
    """Extract the same metrics we used on the original portrait."""
    img = Image.open(filepath).convert("RGB")
    w, h = img.size
    px = list(img.getdata())
    n = len(px)
    r = sum(p[0] for p in px) / n
    g = sum(p[1] for p in px) / n
    b = sum(p[2] for p in px) / n

    dark = sum(1 for p in px if sum(p) / 3 < 40) / n * 100
    glow = sum(1 for p in px if max(p) > 150 and (max(p) - min(p)) > 60) / n * 100
    green = sum(1 for p in px if p[1] > p[0] * 1.3 and p[1] > p[2] * 1.1 and p[1] > 30) / n * 100
    purple = sum(1 for p in px if p[2] > p[1] * 1.15 and p[0] > p[1] * 1.15 and p[0] > 30 and p[2] > 30) / n * 100

    # Visor region glow (upper-center)
    vx0, vy0, vx1, vy1 = int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.35)
    vpts = [px[y * w + x] for y in range(vy0, vy1) for x in range(vx0, vx1)]
    visor_glow = sum(1 for p in vpts if max(p) > 120 and (max(p) - min(p)) > 40) / len(vpts) * 100

    return {
        "brightness": round((r + g + b) / 3, 1),
        "warmth": round(r - b, 1),
        "rgb": (round(r, 1), round(g, 1), round(b, 1)),
        "dark_pct": round(dark, 1),
        "glow_pct": round(glow, 1),
        "green_pct": round(green, 1),
        "purple_pct": round(purple, 1),
        "visor_glow_pct": round(visor_glow, 1),
        "size": img.size,
    }


def main():
    print("=" * 72)
    print("  DEDUCE HEX ENFORCER'S PROMPT")
    print("=" * 72)

    if not os.path.exists(ORIGINAL):
        print(f"ERROR: Original portrait not found at {ORIGINAL}")
        return

    print("Loading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    orig = fingerprint(ORIGINAL)
    print("=" * 72)
    print("  ORIGINAL HEX ENFORCER PORTRAIT FINGERPRINT")
    print("=" * 72)
    for k, v in orig.items():
        print(f"  {k:16s} {v}")

    # Test every candidate prompt
    all_results = {}
    keys = ["brightness", "warmth", "dark_pct", "glow_pct", "green_pct", "purple_pct", "visor_glow_pct"]

    for vname, prompt in CANDIDATE_PROMPTS.items():
        print("\n" + "=" * 72)
        print(f"  CANDIDATE: {vname} ({len(prompt)} chars)")
        print(f"  {prompt}")
        print("=" * 72)
        results = []
        for s in SEEDS:
            fname = f"{vname}_s{s}.jpg"
            ok, reason = generate(prompt, fname, s)
            if not ok:
                print(f"  seed {s}: FAILED ({reason})")
                continue
            fp = os.path.join(OUT_DIR, fname)
            fp_metrics = fingerprint(fp)
            img = Image.open(fp).convert("RGB")
            inputs = blip_proc(img, return_tensors="pt")
            with torch.no_grad():
                out = blip_model.generate(**inputs, max_length=50)
            desc = blip_proc.decode(out[0], skip_special_tokens=True)
            results.append({"seed": s, "metrics": fp_metrics, "blip": desc})
            desc_safe = desc.encode("ascii", "replace").decode()
            print(f"  seed {s}: BLIP=\"{desc_safe}\"")
            print(f"    bright={fp_metrics['brightness']} warmth={fp_metrics['warmth']} "
                  f"dark={fp_metrics['dark_pct']}% glow={fp_metrics['glow_pct']}% "
                  f"green={fp_metrics['green_pct']}% purple={fp_metrics['purple_pct']}% "
                  f"visor={fp_metrics['visor_glow_pct']}%")
        all_results[vname] = {"prompt": prompt, "renders": results}

    # Overall comparison - pick best candidate
    print("\n" + "=" * 72)
    print("  BEST MATCHING CANDIDATE (averaged error across key metrics)")
    print("=" * 72)
    best_name = None
    best_err = float("inf")
    for vname, data in all_results.items():
        renders = data["renders"]
        if not renders:
            continue
        # Per-metric diagnostic line
        avg_line = "  ".join(
            f"{k[:4]}={statistics.mean([r['metrics'][k] for r in renders]):.0f}"
            for k in keys)
        print(f"  {vname:22s} {avg_line}")
        # Error: weighted relative error on the most diagnostic metrics
        err = 0.0
        weights = {"dark_pct": 2.0, "brightness": 1.5, "glow_pct": 1.5,
                   "purple_pct": 1.0, "green_pct": 1.0, "warmth": 1.0, "visor_glow_pct": 0.5}
        for k in keys:
            avg = statistics.mean([r["metrics"][k] for r in renders])
            scale = max(abs(orig[k]), 1.0)
            err += weights[k] * abs(avg - orig[k]) / scale
        helms = sum(1 for r in renders if "helmet" in r["blip"].lower())
        err -= helms * 0.5  # small bonus for helmet keyword presence (capped influence)
        print(f"  {'':22s} error={err:.2f}  helmet={helms}/3")
        if err < best_err:
            best_err = err
            best_name = vname

    if best_name:
        print(f"\n  >>> BEST DEDUCTION: {best_name}")
        print(f"      {CANDIDATE_PROMPTS[best_name]}")

    out_path = os.path.join(CACHE_DIR, "hex_deduction_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"candidates": all_results, "original": orig, "best": best_name},
                  f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
