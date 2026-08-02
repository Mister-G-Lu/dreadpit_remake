#!/usr/bin/env python3
"""
Florence-2 Armor Analyzer — Batch mode.

Launches ONE Florence-2 subprocess that processes ALL targets,
minimizing model loading overhead.
"""

import json
import os
import subprocess
import re

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
# Windows .exe suffix
VENV_PYTHON = os.path.join(CACHE_DIR, "..", "florence_setup", "venv", "Scripts", "python.exe")


# The fighters we want armor analysis for
TARGETS = [
    "Black Entity",
    "Tigran",
    "Big",
    "SIMO THE UNSEEN",
    "Irek'Ailth The Toon Jester",
    "Eldritch Elemechtal",
    "Dread, the unending",
    "The Dreadpit itself",
    "Bearer of the cosmos",
    "Calamity Breaker: Apex",
    "Mecha dragon - Hiryu",
    "Abyss Regent",
    "GL6",
    "Straxar the destruction incarnate",
    "Ragnaros, the Firelord of Magma",
    "Dominus Prime",
    "Dr. Manhattan",
    "GODBREAKER",
    "The Being From [Redacted]",
    "Void Monarch",
    "Tengen Toppa Gurren Laggan",
    "ArroganceFour",
    "Cosm",
    "BH Beater",
]


def find_portrait(name_query):
    """Find a portrait file by name substring."""
    if not os.path.exists(PORTRAIT_DIR):
        return None
    # Normalize query
    q = name_query.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
    best = None
    for f in sorted(os.listdir(PORTRAIT_DIR)):
        if not f.endswith('.png'):
            continue
        fname_clean = re.sub(r'^[\w]+_\d+w_', '', f).replace('.png', '').replace('_', '').replace(' ', '').lower()
        if q in fname_clean:
            # Prefer longer match (more specific)
            if best is None or len(fname_clean) < len(q) * 2:
                best = f
    return os.path.join(PORTRAIT_DIR, best) if best else None


def main():
    sep = "=" * 72
    print(sep)
    print("  FLORENCE-2 ARMOR ANALYSIS")
    print(sep)

    # Verify venv
    if not os.path.exists(VENV_PYTHON):
        print(f"ERROR: Venice not found at {VENV_PYTHON}")
        return

    # Load comparison data for BLIP + wins
    comp_path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    comp_map = {}
    if os.path.exists(comp_path):
        with open(comp_path) as f:
            comp = json.load(f)
        for r in comp.get("results", []):
            key = r.get("name", "").lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
            comp_map[key] = r

    # Find all portraits first
    print("\n[1/4] Locating portraits...")
    target_images = []
    for t in TARGETS:
        fpath = find_portrait(t)
        if fpath:
            target_images.append((t, fpath))
        else:
            print(f"  WARNING: No portrait found for '{t}'")

    print(f"  Found {len(target_images)}/{len(TARGETS)} portraits")

    # =================================================================
    # Build and run the ONE Florence-2 subprocess
    # =================================================================
    print("\n[2/4] Launching Florence-2 batch analysis...")

    # Build the inline script
    image_list_json = json.dumps([(name, path) for name, path in target_images])

    inline_code = f'''
import json, sys
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM

model_id = "microsoft/Florence-2-base-ft"
device = "cpu"

print("  Loading Florence-2...", flush=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, attn_implementation="eager")
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
print("  Loaded. Analyzing portraits...", flush=True)

targets = {image_list_json}
results = []

for name, path in targets:
    try:
        image = Image.open(path).convert("RGB")

        # Detailed caption
        task = "<MORE_DETAILED_CAPTION>"
        inputs = processor(text=task, images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=250,
                num_beams=3,
            )
        detailed = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()

        # Standard caption
        task2 = "<CAPTION>"
        inputs2 = processor(text=task2, images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            ids2 = model.generate(
                input_ids=inputs2["input_ids"],
                pixel_values=inputs2["pixel_values"],
                max_new_tokens=100,
                num_beams=3,
            )
        caption = processor.batch_decode(ids2, skip_special_tokens=True)[0].strip()

        results.append({{
            "name": name,
            "detailed": detailed[:500],
            "caption": caption[:200],
        }})
        print(f"  {{name[:35]:35s}} DONE", flush=True)
    except Exception as e:
        results.append({{
            "name": name,
            "detailed": f"[ERROR: {{e}}]",
            "caption": "",
        }})
        print(f"  {{name[:35]:35s}} ERROR: {{e}}", flush=True)

print("---FLORENCE_RESULTS_START---", flush=True)
print(json.dumps(results), flush=True)
print("---FLORENCE_RESULTS_END---", flush=True)
'''

    print("  (Florence-2 is loading — this takes ~10 seconds...)")
    proc = subprocess.run(
        [VENV_PYTHON, "-c", inline_code],
        capture_output=True, text=True, timeout=600,
    )

    if proc.returncode != 0:
        print(f"  ERROR: Florence-2 process crashed: {proc.stderr[:300]}")
        return

    # Parse results from the output
    stdout = proc.stdout
    start_marker = "---FLORENCE_RESULTS_START---"
    end_marker = "---FLORENCE_RESULTS_END---"

    start_idx = stdout.find(start_marker)
    end_idx = stdout.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print(f"  ERROR: Could not parse Florence results from output")
        print(f"  Raw output: {stdout[:500]}")
        return

    json_str = stdout[start_idx + len(start_marker):end_idx].strip()
    try:
        florence_results = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse JSON: {e}")
        print(f"  Raw: {json_str[:300]}")
        return

    print(f"  Got results for {len(florence_results)} fighters\n")

    # =================================================================
    # Print results
    # =================================================================
    print(sep)
    print("  [3/4] FLORENCE-2 ARMOR DESCRIPTIONS")
    print(sep)

    for fr in florence_results:
        name = fr["name"]
        detailed = fr.get("detailed", "")
        caption = fr.get("caption", "")

        # Get comparison data
        name_key = name.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
        comp = comp_map.get(name_key, {})
        wins = comp.get("wins", "?")
        blip = comp.get("blip", "N/A")

        print(f"\n  {'='*60}")
        print(f"  {name[:45]:45s} ({wins} wins)")
        print(f"  {'='*60}")

        print(f"  BLIP:              {blip}")
        print(f"  Florence CAPTION:  {caption[:150]}")

        # Extract armor-relevant keywords from Florence output
        dl = detailed.lower()
        armor_hits = []
        for kw in ["armor", "plate", "helmet", "shield", "chainmail", "suit",
                    "knight", "metal", "iron", "steel", "bronze", "gold",
                    "silver", "cloth", "robe", "leather", "cape", "cloak",
                    "wings", "horn", "scale", "skin", "fur", "bone",
                    "black", "dark", "glowing", "fire", "flame",
                    "tight", "sleek", "heavy", "thick", "smooth",
                    "bare", "exposed", "naked", "unarmored"]:
            if kw in dl:
                armor_hits.append(kw)
        if armor_hits:
            print(f"  ARMOR KW:          {', '.join(armor_hits[:8])}")

        print(f"\n  FULL FLORENCE DESCRIPTION:")
        # Print wrapped
        words = detailed.split()
        line = ""
        for w in words:
            if len(line) + len(w) > 70:
                print(f"  {line}")
                line = w
            else:
                line = f"{line} {w}" if line else w
        if line:
            print(f"  {line}")

    # =================================================================
    # Armor classification for each fighter
    # =================================================================
    print(f"\n\n{sep}")
    print("  [4/4] ARMOR CLASSIFICATION SUMMARY")
    print(sep)

    print(f"""
  {'Fighter':30s} {'Armor':>25s} {'Cov':>5s} {'Type':>12s}
  {'-'*30} {'-'*25} {'-'*5} {'-'*12}""")

    for fr in florence_results:
        name = fr["name"]
        dl = fr.get("detailed", "").lower()

        # Classify armor level from keywords
        has_armor_kw = any(kw in dl for kw in ["armor", "plate", "chainmail", "knight", "helmet"])
        has_metal_kw = any(kw in dl for kw in ["metal", "iron", "steel", "bronze", "gold", "silver"])
        has_cloth_kw = any(kw in dl for kw in ["cloth", "robe", "leather", "suit"])
        has_exposed = any(kw in dl for kw in ["bare", "exposed", "unarmored", "naked", "skin"])

        if has_armor_kw and has_metal_kw:
            armor_level = "FULL ARMOR (metal)"
        elif has_armor_kw:
            armor_level = "ARMORED"
        elif has_metal_kw:
            armor_level = "PARTIAL/METAL"
        elif has_cloth_kw and not has_exposed:
            armor_level = "LIGHT/CLOTH"
        elif has_exposed:
            armor_level = "MINIMAL/EXPOSED"
        else:
            armor_level = "UNCLEAR"

        # Coverage estimate from keywords
        cov_hints = 0
        if "full" in dl: cov_hints += 2
        if "entire" in dl: cov_hints += 2
        if "body" in dl: cov_hints += 1
        if "covered" in dl: cov_hints += 1
        if "head" in dl: cov_hints += 1
        if "chest" in dl: cov_hints += 1
        if "torso" in dl: cov_hints += 1
        if "leg" in dl: cov_hints += 1
        if "arm" in dl: cov_hints += 1
        if "bare" in dl: cov_hints -= 1
        if "exposed" in dl: cov_hints -= 1

        if cov_hints >= 5: cov_str = "HIGH"
        elif cov_hints >= 3: cov_str = "MED"
        else: cov_str = "LOW"

        # Armor quality
        quality = "standard"
        if "smooth" in dl: quality = "smooth"
        if "thick" in dl or "heavy" in dl: quality = "heavy"
        if "spike" in dl or "sharp" in dl: quality = "spiked"
        if "glowing" in dl or "magical" in dl: quality = "magical"

        # Color
        color = ""
        for c in ["black", "gold", "silver", "bronze", "steel gray", "red", "blue", "white", "dark"]:
            if c in dl:
                color = c
                break

        marker = ""
        if "BIG" in name.upper(): marker = " << BIG"
        elif "SIMO" in name.upper(): marker = " << SIMO"
        elif "JESTER" in name.upper() or "TOON" in name.upper(): marker = " << JESTER"
        print(f"  {name[:30]:30s} {armor_level:>25s} {cov_str:>5s} {quality:>12s}{marker}")

    print(f"\n  Done.")


if __name__ == "__main__":
    main()
