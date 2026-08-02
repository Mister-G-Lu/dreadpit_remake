#!/usr/bin/env python3
"""
Florence Durability — Vision-Language Driven Armor & Protection Analysis.

Uses Florence-2 detailed captions as the PRIMARY signal for estimating
durability (0-10). A smart keyword classifier interprets what Florence-2
actually sees in each portrait and scores protection level.

Secondary: VQA "What armor?" prompt for concise archetype classification.

Reference anchors for calibration:
  Tigran 9.0, Black Entity 8.0, Eldritch Elemechtal 8.0,
  Bearer of cosmos 7.5, Dread 7.0, Dreadpit 7.0,
  Toon Jester 4.0, SIMO 2.0, Big 0.5
"""

import json
import os
import re
import statistics
import subprocess
import sys

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
VENV_PYTHON = os.path.join(CACHE_DIR, "..", "florence_setup", "venv", "Scripts", "python.exe")


# =========================================================================
# Reference anchor fighters for calibration
# =========================================================================
REFERENCE_ANCHORS = {
    "tigran":               {"durability": 9.0, "notes": "Immensely durable tight perfect armor"},
    "black entity":         {"durability": 8.0, "notes": "Sleek obsidian-like armor/carapace"},
    "eldritch elemechtal":  {"durability": 8.0, "notes": "Mecha/robot — full metal body"},
    "bearer of the cosmos": {"durability": 7.5, "notes": "Robot with sphere"},
    "the dreadpit itself":  {"durability": 7.0, "notes": "Dragon — scales, organic durability"},
    "dread, the unending":  {"durability": 7.0, "notes": "Demonic, likely durable"},
    "irek":                 {"durability": 4.0, "notes": "Toon — hard to assess cartoon durability"},
    "simo the unseen":      {"durability": 2.0, "notes": "Cloth uniform + helmet only"},
    "big":                  {"durability": 0.5, "notes": "Business suit, zero protection"},
}


def find_anchor(name_lower):
    """Find reference anchor for a fighter name. Returns (key, anchor) or (None, None)."""
    for ak, av in REFERENCE_ANCHORS.items():
        if ak in name_lower:
            return ak, av
    return None, None


# =========================================================================
# Smart Keyword Durability Classifier
# =========================================================================
# Each keyword family contributes a score. The combined score is mapped to 0-10.

# --- Direct armor evidence (HIGH confidence) ---
ARMOR_HIGH = {
    "armor": 3.5, "armoured": 3.5, "armored": 3.5,
    "plate": 3.0, "chainmail": 3.5, "mail": 2.5,
    "helmet": 2.0, "shield": 2.0, "gauntlet": 1.5,
    "suit of armor": 4.0, "full armor": 4.0,
    "metal": 3.0, "steel": 3.0, "iron": 3.0, "bronze": 2.5, "silver": 2.0,
}

# --- Robot/mecha body = inherently durable ---
ROBOT = {
    "robot": 2.5, "mecha": 3.0, "mechanical": 2.5,
    "cyborg": 2.0, "android": 2.5, "gundam": 3.0,
    "machine": 2.0, "automaton": 2.5,
}

# --- Warrior archetype (carries armor implicitly) ---
WARRIOR = {
    "knight": 3.0, "viking": 2.5, "paladin": 3.0,
    "warrior": 1.5, "soldier": 1.5, "gladiator": 2.0,
    "berserker": 1.5, "samurai": 2.5,
}

# --- Demon/monster (organic durability, tough) ---
CREATURE = {
    "dragon": 2.0, "demon": 1.5, "monster": 1.0,
    "creature": 0.5, "beast": 1.0, "giant": 1.5,
}

# --- Weapon evidence (implies combat readiness, but not directly armor) ---
WEAPON = {
    "sword": 1.0, "gun": 0.5, "rifle": 0.5, "axe": 1.0,
    "hammer": 1.0, "spear": 0.5, "blade": 1.0, "cannon": 1.0,
}

# --- Negative: cloth/fabric/unarmored ---
CLOTH = {
    "outfit": -2.0, "uniform": -2.0, "cloth": -2.5, "fabric": -2.0,
    "suit": -2.0, "robe": -2.0, "dress": -2.0, "rags": -2.5,
    "cloak": -1.5, "cape": -0.5,
}

# --- Negative: naked/exposed ---
NAKED = {
    "naked": -4.0, "bare": -3.0, "exposed": -2.5,
    "skin": -1.5, "flesh": -2.0, "fur": -1.5, "feather": -1.5,
}

# --- Negative: human/cartoon (squishy) ---
SQUISHY = {
    "man": -0.5, "woman": -0.5, "person": -0.5, "human": -0.5,
    "cartoon": -1.0, "jester": -1.0, "joker": -1.0,
}

# --- VQA answers (concise classification) ---
VQA_ARMOR_HIGH = {"knight", "paladin", "samurai", "viking", "gladiator",
                   "berserker", "heavy armor", "full plate"}
VQA_ARMOR_MED = {"warrior", "soldier", "demon", "monster", "robot"}
VQA_ARMOR_LOW = {"naked", "cloth", "robe", "suit", "civilian", "man"}


def score_caption(detailed_caption, vqa_answer=""):
    """Score a Florence-2 detailed caption for durability. Returns dict with score + hits."""
    if not detailed_caption:
        return {"raw_score": 5.0, "hits": {k: [] for k in ["armor","robot","warrior","creature","weapon","cloth","naked","squishy"]}, "vqa_used": False}

    dl = detailed_caption.lower()
    score = 5.0  # baseline (mid)

    hits = {"armor": [], "robot": [], "warrior": [], "creature": [],
            "weapon": [], "cloth": [], "naked": [], "squishy": []}

    # Accumulate keyword hits
    for kw, val in ARMOR_HIGH.items():
        if kw in dl:
            score += val
            hits["armor"].append(kw)
    for kw, val in ROBOT.items():
        if kw in dl:
            score += val
            hits["robot"].append(kw)
    for kw, val in WARRIOR.items():
        if kw in dl:
            score += val
            hits["warrior"].append(kw)
    for kw, val in CREATURE.items():
        if kw in dl:
            score += val * 0.5  # creature half-weight (organic ≠ armor)
            hits["creature"].append(kw)
    for kw, val in WEAPON.items():
        if kw in dl:
            score += val * 0.3  # weapon half-weight (weapon ≠ protection)
            hits["weapon"].append(kw)
    for kw, val in CLOTH.items():
        if kw in dl:
            score += val
            hits["cloth"].append(kw)
    for kw, val in NAKED.items():
        if kw in dl:
            score += val
            hits["naked"].append(kw)
    for kw, val in SQUISHY.items():
        if kw in dl:
            score += val * 0.5  # squishy half-weight
            hits["squishy"].append(kw)

    # VQA supplement
    if vqa_answer:
        vqa_lower = vqa_answer.lower().strip()
        if vqa_lower in VQA_ARMOR_HIGH:
            score += 2.0
            hits["armor"].append(f"vqa:{vqa_lower}")
        elif vqa_lower in VQA_ARMOR_MED:
            score += 1.0
            hits["warrior"].append(f"vqa:{vqa_lower}")
        elif vqa_lower in VQA_ARMOR_LOW:
            score -= 1.5
            hits["cloth"].append(f"vqa:{vqa_lower}")

    # Clamp raw score
    score = max(1.0, min(9.5, score))

    return {
        "raw_score": round(score, 2),
        "hits": hits,
        "vqa_used": bool(vqa_answer),
    }


def score_to_durability(raw_score):
    """Map raw score 1.0-9.5 to durability 0-10."""
    # Linear mapping: raw 1.0 → 0.0, raw 9.5 → 10.0
    dur = (raw_score - 1.0) / 8.5 * 10.0
    return round(max(0.0, min(10.0, dur)), 1)


# =========================================================================
# Load cached Florence-2 captions
# =========================================================================
def load_florence_cache():
    """Load cached Florence-2 detailed captions."""
    path = os.path.join(CACHE_DIR, "florence_analysis_results.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    results = {}
    for item in data:
        name = item.get("name", "")
        detail = item.get("detailed", "") or ""
        # Normalize name key
        key = name.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
        results[key] = {"name": name, "detailed": detail}
    return results


# =========================================================================
# Find portrait by name
# =========================================================================
def find_portrait(name_query):
    """Find a portrait file by name substring."""
    q = name_query.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
    best, best_len = None, 999
    for f in sorted(os.listdir(PORTRAIT_DIR)):
        if not f.endswith('.png'):
            continue
        fname_clean = re.sub(r'^[\w]+_\d+w_', '', f).replace('.png', '').replace('_', '').replace(' ', '').lower()
        if q in fname_clean:
            if best is None or abs(len(fname_clean) - len(q)) < best_len:
                best = f
                best_len = abs(len(fname_clean) - len(q))
    return os.path.join(PORTRAIT_DIR, best) if best else None


# =========================================================================
# Run Florence-2 VQA for specific armor question (batch)
# =========================================================================
FLORENCE_VQA_CACHE = {}

def run_florence_vqa_batch(fighters):
    """Run Florence-2 VQA 'What armor?' on all fighters in one subprocess."""
    global FLORENCE_VQA_CACHE

    if not os.path.exists(VENV_PYTHON):
        print("  WARNING: Florence-2 venv not found, skipping VQA")
        return

    missing = [(n, p) for n, p in fighters if n not in FLORENCE_VQA_CACHE]
    if not missing:
        return

    image_list_json = json.dumps(missing)
    inline = '''
import json, sys
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM

model_id = "microsoft/Florence-2-base-ft"
device = "cpu"
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, attn_implementation="eager")
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

targets = IMAGE_LIST_PLACEHOLDER
results = []
for name, path in targets:
    try:
        img = Image.open(path).convert("RGB")
        prompt = "<VQA>What armor is this character wearing?"
        inputs = processor(text=prompt, images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            ids = model.generate(**inputs, max_new_tokens=100, num_beams=3)
        ans = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        results.append({"name": name, "vqa": ans})
    except Exception as e:
        results.append({"name": name, "vqa": ""})

print("---VQA_RESULTS_START---")
print(json.dumps(results))
print("---VQA_RESULTS_END---")
'''.replace("IMAGE_LIST_PLACEHOLDER", image_list_json)

    proc = subprocess.run([VENV_PYTHON, "-c", inline], capture_output=True, text=True, timeout=300)
    start = proc.stdout.find("---VQA_RESULTS_START---")
    end = proc.stdout.find("---VQA_RESULTS_END---")
    if start != -1 and end != -1:
        json_str = proc.stdout[start + len("---VQA_RESULTS_START---"):end].strip()
        try:
            batch = json.loads(json_str)
            for item in batch:
                FLORENCE_VQA_CACHE[item["name"]] = item.get("vqa", "")
        except json.JSONDecodeError:
            pass


# =========================================================================
# MAIN
# =========================================================================
def main():
    sep = "=" * 72
    print(sep)
    print("  FLORENCE DURABILITY — Vision-Language Driven Armor Analysis")
    print(sep)

    # Load cached captions
    florence_cache = load_florence_cache()
    print(f"\n  Loaded {len(florence_cache)} cached Florence-2 captions")

    # Define fighters
    TARGETS = [
        "Tigran", "Black Entity", "Eldritch Elemechtal", "The Dreadpit itself",
        "Big", "SIMO THE UNSEEN", "Irek'Ailth The Toon Jester",
        "Bearer of the cosmos", "Abyss Regent",
        "Dread, the unending", "GL6",
        "Dominus Prime", "Dr. Manhattan",
        "GODBREAKER", "The Being From [Redacted]",
        "Void Monarch", "Tengen Toppa Gurren Laggan",
        "ArroganceFour", "Cosm",
        "BH Beater", "Forever",
        "Vaelstrix", "Universe breaker",
        "Scorch the nuclear snake", "Aurelion", "Nonamebot",
    ]

    # Find portraits and match captions
    print(f"\n[1/3] Finding portraits for {len(TARGETS)} fighters...")
    fighter_data = []
    for t in TARGETS:
        fpath = find_portrait(t)
        if not fpath:
            continue
        # Match to cached caption
        key = t.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
        cached = florence_cache.get(key, {})
        caption = cached.get("detailed", "")
        fighter_data.append({"name": t, "path": fpath, "caption": caption, "key": key})

    print(f"  Found {len(fighter_data)}/{len(TARGETS)} with images + captions")

    # Run VQA for armor question
    print(f"\n[2/3] Running Florence-2 VQA 'What armor?' on {len(fighter_data)} fighters...")
    run_florence_vqa_batch([(f["name"], f["path"]) for f in fighter_data])

    # Score each fighter
    print(f"\n[3/3] Scoring durability from Florence captions...")

    # Load comparison data (BLIP) once
    comp_path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    all_comp = {}
    if os.path.exists(comp_path):
        with open(comp_path) as cf:
            cd = json.load(cf)
            for r in cd.get("results", []):
                rk = r.get("name", "").lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
                all_comp[rk] = r

    results = []
    for f in fighter_data:
        vqa_ans = FLORENCE_VQA_CACHE.get(f["name"], "")
        scored = score_caption(f["caption"], vqa_ans)
        durability = score_to_durability(scored["raw_score"])
        comp_data = all_comp.get(f["key"], {})

        results.append({
            "name": f["name"],
            "durability": durability,
            "raw_score": scored["raw_score"],
            "wins": comp_data.get("wins", "?"),
            "florence_caption": f["caption"][:120],
            "vqa_answer": vqa_ans or "(none)",
            "kw_hits": scored["hits"],
            "blip": comp_data.get("blip", "")[:80],
        })

    # Sort by durability
    results.sort(key=lambda x: -x["durability"])

    # =================================================================
    # RESULTS TABLE
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  DURABILITY REPORT — Florence-2 Driven (0-10)")
    print(sep)
    header = (f"  {'Rank':>4s} {'Fighter':35s} {'Win':>3s}  {'Dur':>4s}  "
              f"{'Raw':>4s}  {'VQA':12s}  {'Key Signal':25s}")
    print(header)
    print(f"  {'-'*4} {'-'*35} {'-'*3}  {'-'*4}  {'-'*4}  {'-'*12}  {'-'*25}")

    for i, r in enumerate(results):
        # Determine the strongest signal
        all_hits = []
        for cat, kw_list in r["kw_hits"].items():
            for kw in kw_list:
                all_hits.append(kw)
        signal = all_hits[0][:25] if all_hits else "(none detected)"

        marker = ""
        nu = r["name"].upper()
        if "BIG" in nu: marker = " << OUT"
        elif "SIMO" in nu: marker = " << OUT"
        elif "JESTER" in nu: marker = " << OUT"

        print(f"  {i+1:>4d} {r['name'][:35]:35s} {str(r['wins']):>3s}  "
              f"{r['durability']:>4.1f}  {r['raw_score']:>4.1f}  "
              f"{r['vqa_answer'][:12]:12s}  {signal:25s}{marker}")

    # =================================================================
    # DEEP DIVES — Show full breakdown for key fighters
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  SIGNAL BREAKDOWN — Key Fighters")
    print(sep)

    deep_dives = ["Tigran", "Black Entity", "Big", "SIMO", "Irek",
                   "Eldritch Elemechtal", "Bearer of the cosmos",
                   "Dominus Prime", "Dr. Manhattan", "Universe breaker"]

    for q in deep_dives:
        matches = [r for r in results if q.upper() in r["name"].upper()]
        if not matches:
            continue
        r = matches[0]

        print(f"\n  {'='*60}")
        print(f"  {r['name'][:50]:50s} — Durability: {r['durability']}/10  ({r['wins']} wins)")
        print(f"  {'='*60}")

        print(f"  FLORENCE-2 CAPTION:")
        print(f"    {r['florence_caption'][:110]}")
        print(f"  VQA ANSWER:      {r['vqa_answer']}")
        print(f"  RAW SCORE:       {r['raw_score']}")

        print(f"  KEYWORD HITS:")
        for cat, kws in r["kw_hits"].items():
            if kws:
                print(f"    {cat+':':12s} {', '.join(str(k)[:20] for k in kws)}")

        # Anchor comparison
        nl = r["name"].lower()
        ak, ref = find_anchor(nl)
        if ref:
            delta = r["durability"] - ref["durability"]
            print(f"  CALIBRATION:     Expected={ref['durability']:.1f} "
                  f"Delta={delta:+.1f}  {ref['notes']}")

        if r["blip"]:
            print(f"  BLIP:            {r['blip']}")

    # =================================================================
    # CALIBRATION CHECK
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  CALIBRATION — Comparing vs Reference Fighters")
    print(sep)
    print(f"  {'Fighter':40s} {'Florence Dur':>12s} {'Expected':>9s} {'Delta':>8s}")
    print(f"  {'-'*40} {'-'*12} {'-'*9} {'-'*8}")

    cal_errors = []
    for r in results:
        nl = r["name"].lower()
        ak, ref = find_anchor(nl)
        if ref:
            delta = r["durability"] - ref["durability"]
            cal_errors.append(abs(delta))
            marker = ""
            if delta < -1.0: marker = " ** UNDER"
            elif delta > 1.0: marker = " ** OVER"
            print(f"  {r['name'][:40]:40s} {r['durability']:>10.1f}  "
                  f"{ref['durability']:>6.1f}   {delta:+>+6.1f}  {marker}")

    if cal_errors:
        mae = sum(cal_errors) / len(cal_errors)
        print(f"\n  Mean Absolute Calibration Error: {mae:.2f} points")
        prev_mae = 2.39  # from pixel-based estimator
        improvement = prev_mae - mae
        print(f"  vs previous pixel-based estimator: {prev_mae:.2f} "
              f"({'improved by ' + str(round(improvement, 2)) if improvement > 0 else 'worse by ' + str(round(abs(improvement), 2))})")

    # =================================================================
    # GROUP AVERAGES
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  GROUP AVERAGES")
    print(sep)

    high = [r for r in results if isinstance(r["wins"], int) and r["wins"] >= 7]
    mid = [r for r in results if isinstance(r["wins"], int) and 5 <= r["wins"] <= 6]

    if high:
        avg_h = statistics.mean([r["durability"] for r in high])
    else:
        avg_h = 0
    if mid:
        avg_m = statistics.mean([r["durability"] for r in mid])
    else:
        avg_m = 0

    print(f"\n  {'Group':25s} {'n':>4s} {'Avg Dur':>8s}")
    print(f"  {'-'*25} {'-'*4} {'-'*8}")
    print(f"  {'Top winners (7+ wins)':25s} {len(high):>4d} {avg_h:>7.1f}")
    print(f"  {'Mid winners (5-6 wins)':25s} {len(mid):>4d} {avg_m:>7.1f}")

    # =================================================================
    # FULL VERDICT TABLE — Florence Caption + Keywords + Durability
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  FULL VERDICT — Florence-2 Caption Analysis")
    print(sep)
    print(f"\n  {'Fighter':35s} {'Dur':>4s} {'Florence Caption Snippet':55s}")
    print(f"  {'-'*35} {'-'*4} {'-'*55}")
    for r in sorted(results, key=lambda x: -x["durability"]):
        cap = r["florence_caption"][:55]
        print(f"  {r['name'][:35]:35s} {r['durability']:>4.1f}  {cap}")

    print(f"\n  Done.")


if __name__ == "__main__":
    main()
