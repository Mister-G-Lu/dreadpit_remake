#!/usr/bin/env python3
"""
Florence Gap Analysis — does Florence-2 catch what BLIP/NN missed?

Runs Florence-2 detailed captions on the GAP fighters identified by
find_nn_gaps.py (nn_gap_fighters.json):
  GAP A: high-wins (5+) fighters the NN scores < 0.5  (false negatives)
  GAP B: low-wins fighters the NN scores >= 0.5       (false positives)

For each gap fighter we print the Florence caption side by side with the BLIP
caption + NN score, so we can see whether Florence's richer description would
have flipped the NN's call.
"""
import json
import os
import re
import subprocess

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
BOT_LOSER_DIR = os.path.join(CACHE_DIR, "bot_losers")
VENV_PYTHON = os.path.join(CACHE_DIR, "..", "florence_setup", "venv", "Scripts", "python.exe")
GAP_PATH = os.path.join(CACHE_DIR, "nn_gap_fighters.json")
OUT_PATH = os.path.join(CACHE_DIR, "florence_gap_results.json")


def norm(name):
    return name.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")


def find_portrait(name):
    q = norm(name)
    for directory in (PORTRAIT_DIR, BOT_LOSER_DIR):
        if not os.path.isdir(directory):
            continue
        for f in sorted(os.listdir(directory)):
            if not f.endswith(".png"):
                continue
            fname_clean = re.sub(r'^[\w]+_\d+w_', '', f).replace('.png', '').replace('_', '').replace(' ', '').replace('-', '').lower()
            if q in fname_clean:
                return os.path.join(directory, f)
    return None


def main():
    print("=" * 72, flush=True)
    print("  FLORENCE GAP ANALYSIS", flush=True)
    print("=" * 72, flush=True)

    if not os.path.exists(GAP_PATH):
        print(f"ERROR: {GAP_PATH} not found. Run find_nn_gaps.py first.")
        return
    with open(GAP_PATH, encoding="utf-8") as f:
        gaps = json.load(f)

    targets = []
    for g in gaps.get("gap_a", []):
        targets.append((g["name"], "A", g["wins"], g["nn_score"]))
    for g in gaps.get("gap_b", []):
        targets.append((g["name"], "B", g["wins"], g["nn_score"]))

    print(f"\n[1/3] Gap fighters: {len(targets)} ({len(gaps.get('gap_a', []))} A + {len(gaps.get('gap_b', []))} B)", flush=True)

    # Find portraits
    image_list = []
    for name, group, wins, score in targets:
        path = find_portrait(name)
        if path:
            image_list.append((name, path))
        else:
            print(f"  WARNING: no portrait for '{name}'", flush=True)
    print(f"  Found {len(image_list)}/{len(targets)} portraits", flush=True)

    if not os.path.exists(VENV_PYTHON):
        print(f"ERROR: Florence venv missing at {VENV_PYTHON}")
        return

    # Load BLIP comparison data for side-by-side
    comp_map = {}
    with open(os.path.join(CACHE_DIR, "comparison_analysis.json"), encoding="utf-8") as f:
        for r in json.load(f).get("results", []):
            comp_map[norm(r.get("name", ""))] = r

    # =================================================================
    # Launch ONE Florence subprocess for all images (batch)
    # =================================================================
    print(f"\n[2/3] Launching Florence-2 batch ({len(image_list)} images)...", flush=True)
    image_list_json = json.dumps(image_list)
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
print("  Loaded. Analyzing...", flush=True)

targets = {image_list_json}
results = []
for name, path in targets:
    try:
        image = Image.open(path).convert("RGB")
        task = "<MORE_DETAILED_CAPTION>"
        inputs = processor(text=task, images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=200,
                num_beams=3,
            )
        detailed = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        results.append({{"name": name, "florence": detailed[:400]}})
        print(f"  {{name[:35]:35s}} DONE", flush=True)
    except Exception as e:
        results.append({{"name": name, "florence": f"[ERROR: {{e}}]"}})
        print(f"  {{name[:35]:35s}} ERROR", flush=True)

print("---FLORENCE_GAP_RESULTS_START---", flush=True)
print(json.dumps(results), flush=True)
print("---FLORENCE_GAP_RESULTS_END---", flush=True)
'''
    proc = subprocess.run([VENV_PYTHON, "-c", inline_code], capture_output=True, text=True, timeout=1200)
    if proc.returncode != 0:
        print(f"  ERROR: Florence crashed: {proc.stderr[:300]}")
        return

    stdout = proc.stdout
    s_mark, e_mark = "---FLORENCE_GAP_RESULTS_START---", "---FLORENCE_GAP_RESULTS_END---"
    s_i, e_i = stdout.find(s_mark), stdout.find(e_mark)
    if s_i == -1 or e_i == -1:
        print(f"  ERROR: could not parse Florence output: {stdout[:500]}")
        return
    florence_map = {}
    try:
        for item in json.loads(stdout[s_i + len(s_mark):e_i].strip()):
            florence_map[item["name"]] = item["florence"]
    except json.JSONDecodeError as e:
        print(f"  ERROR: JSON parse: {e}")
        return

    # =================================================================
    # Print side-by-side comparison
    # =================================================================
    print(f"\n[3/3] GAP COMPARISON — Florence vs BLIP vs NN", flush=True)
    print("=" * 100, flush=True)

    results_out = []
    for name, group, wins, score in targets:
        fl = florence_map.get(name, "(no caption)")
        comp = comp_map.get(norm(name), {})
        blip = comp.get("blip", "(no BLIP)")
        results_out.append({
            "name": name,
            "group": "A" if group == "A" else "B",
            "wins": wins,
            "nn_score": score,
            "florence": fl,
            "blip": blip,
        })

    for r in sorted(results_out, key=lambda x: (x["group"], -x["nn_score"])):
        g = "GAP A (high-win, low-NN)" if r["group"] == "A" else "GAP B (low-win, high-NN)"
        print(f"\n  {'='*70}", flush=True)
        print(f"  [{g}]  {r['name'][:40]:40s}  {r['wins']}w  NN={r['nn_score']:.3f}", flush=True)
        print(f"  {'='*70}", flush=True)
        print(f"  BLIP:     {r['blip'][:110]}", flush=True)
        fl = r["florence"]
        for i in range(0, len(fl), 100):
            print(f"  FLORENCE: {fl[i:i+100]}", flush=True)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results_out, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: florence_gap_results.json ({len(results_out)} fighters)", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
