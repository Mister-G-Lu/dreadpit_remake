"""
DREADPIT BATTLE SIMULATOR
=======================================
Generates each fighter at 20+ FLUX seeds, judges vs Cyber God using the
trained NN predictor, narrates battles in Dreadpit style, and iterates
prompts until each fighter achieves >=50% win rate.

How it works:
1. Train the NN predictor on 348 fighters (from comparison_analysis.json)
2. For each fighter, generate 20 images at different FLUX seeds
3. Run BLIP on each to extract visual features
4. Use NN predictor to score both our fighter and Cyber God
5. Higher score = predicted winner (the AI Arbiter's judgment)
6. If win rate < 50%, auto-modify prompt and re-run
7. Save narrated battle report
"""

import json
import os
import sys
import time
import urllib.parse
import random
import statistics
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import requests
from transformers import BlipProcessor, BlipForConditionalGeneration

# =========================================================================
# 0. Configuration
# =========================================================================
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(CACHE_DIR, "battle_sims")

# Cyber God's fixed stats (analyzed from cyber_god.png)
CYBER_GOD = {
    "name": "Cyber God",
    "blip": "a demonic dragon with a sword and a fire",
    "warmth": 18.6,
    "red_ratio": 0.407,
    "brightness": 65.0,
    "keywords": {"monster": True, "fire": True, "sword": True},
}

# Our fighters' best verified prompts
FIGHTERS = {
    "forge_colossus": {
        "name": "Forge Colossus",
        "prompt_template": "Giant walking furnace made of black iron. White-hot molten core visible through chest bars. Massive anvil-headed hammer in each hand, glowing red. Flat iron mask with orange eye slits. Heat waves distort air around body. No flesh. Just forge.",
    },
    "wrath_infernal": {
        "name": "Wrath Infernal",
        "prompt_template": "Demonic winged entity wreathed in black orange flames, fiery wings spread wide, obsidian skull burning orange eyes, horns twisted iron, claws molten rock, body ash ember, wrath made fire",
    },
    "vatican_gun": {
        "name": "Vatican Gun",
        "prompt_template": "Hooded executioner in black leather duster. Carries a massive six-barrel gatling cannon, barrels clearly visible spinning. Holy water drums marked with crosses on each side. Gas mask with red glowing eyes. Silver bullets across chest. Crucifix on gun.",
    },
}

# NN feature config (must match nn_predictor.py)
KEYWORD_KEYS = [
    "sword", "axe_hammer", "gun", "armor", "helmet", "human",
    "monster", "robot", "fire", "dark", "red", "blue", "metal",
    "wings", "shield", "cape"
]
PIXEL_KEYS = ["brightness", "warmth", "red_ratio", "avg_r", "avg_g", "avg_b"]
ALL_FEATURE_NAMES = KEYWORD_KEYS + PIXEL_KEYS


# =========================================================================
# 1. Neural Network Predictor (same architecture as nn_predictor.py)
# =========================================================================
class WinnerPredictor(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(8, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze()


def load_data(path=None):
    """Load BLIP analysis data and extract features + targets."""
    if path is None:
        path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        return None, None, None, None
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", [])
    if not results:
        return None, None, None, None

    X, y, names = [], [], []
    for r in results:
        kws = r.get("kws", {})
        pixel = r.get("pixel", {})
        wins = r.get("wins", 0)
        name = r.get("name", "?")
        features = []
        for kw in KEYWORD_KEYS:
            features.append(1.0 if kws.get(kw, False) else 0.0)
        for pk in PIXEL_KEYS:
            val = pixel.get(pk, 0.0)
            if val is None:
                val = 0.0
            features.append(float(val))
        if wins >= 5:
            y.append(1.0)
            X.append(features)
            names.append(name)
        elif wins <= 3:
            y.append(0.0)
            X.append(features)
            names.append(name)
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    return X, y, ALL_FEATURE_NAMES, names


def train_final_model(X, y, mean=None, std=None):
    """Train the NN on ALL data (no CV), return model + normalizer."""
    X_norm, mean, std = _normalize(X, mean, std)
    input_dim = X.shape[1]
    model = WinnerPredictor(input_dim)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)

    X_t = torch.FloatTensor(X_norm)
    y_t = torch.FloatTensor(y)

    best_loss = float('inf')
    best_state = None
    patience = 100
    pc = 0

    for epoch in range(1000):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_t)
        loss = criterion(outputs, y_t)
        loss.backward()
        optimizer.step()

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_state = model.state_dict().copy()
            pc = 0
        else:
            pc += 1
        if pc >= patience:
            break

    model.load_state_dict(best_state)
    return model, mean, std


def _normalize(X, mean=None, std=None):
    if mean is None:
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        std[std == 0] = 1.0
    X_norm = (X - mean) / std
    return X_norm, mean, std


def predict(model, features, mean, std):
    """Predict winner probability for a feature vector."""
    features = np.array(features, dtype=np.float32).reshape(1, -1)
    features_norm = (features - mean) / std
    model.eval()
    with torch.no_grad():
        score = model(torch.FloatTensor(features_norm)).item()
    return score


def build_feature_vector(pixel, kws):
    """Build the 22-element feature vector from pixel metrics and keywords."""
    features = []
    for kw in KEYWORD_KEYS:
        features.append(1.0 if kws.get(kw, False) else 0.0)
    for pk in PIXEL_KEYS:
        val = pixel.get(pk, 0.0)
        if val is None:
            val = 0.0
        features.append(float(val))
    return features


def extract_keywords(desc):
    dl = desc.lower()
    return {
        "sword": "sword" in dl or "blade" in dl or "blades" in dl,
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
        "cape": any(w in dl for w in ["cape", "cloak", "duster", "coat"]),
    }


# =========================================================================
# 2. Image Generation (FLUX via Pollinations.ai)
# =========================================================================
def generate_fighter_image(prompt, filename, seed):
    filepath = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return True

    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(r.content)
                return True
        except:
            pass
        time.sleep(3)
    return False


# =========================================================================
# 3. BLIP Analysis
# =========================================================================
def load_blip():
    from transformers import BlipProcessor, BlipForConditionalGeneration
    print("  Loading BLIP...", end=" ", flush=True)
    proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("OK")
    return proc, model


def describe(image_path, proc, model):
    img = Image.open(image_path).convert("RGB")
    inputs = proc(img, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(**inputs, max_length=50)
    return proc.decode(out[0], skip_special_tokens=True)


def pixel_metrics(image_path):
    img = Image.open(image_path).convert("RGB")
    pixels = list(img.getdata())
    rs = [p[0] for p in pixels]
    gs = [p[1] for p in pixels]
    bs = [p[2] for p in pixels]
    avg_r = statistics.mean(rs)
    avg_g = statistics.mean(gs)
    avg_b = statistics.mean(bs)
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


# =========================================================================
# 4. Battle Narration
# =========================================================================
def narrate_battle(fighter_name, fighter_prompt, fighter_stats, cyber_stats, fighter_score, cyber_score, winner, seed):
    """Generate a Dreadpit-style battle narration."""
    f_warmth = fighter_stats["pixel"]["warmth"]
    f_red = fighter_stats["pixel"]["red_ratio"]
    f_blip = fighter_stats["blip"]
    f_kws = [kw for kw, v in fighter_stats["kws"].items() if v]

    c_warmth = CYBER_GOD["warmth"]
    c_red = CYBER_GOD["red_ratio"]
    c_blip = CYBER_GOD["blip"]

    # Determine narrative based on key differences
    warmth_diff = f_warmth - c_warmth
    red_diff = f_red - c_red

    if winner == fighter_name:
        # Our fighter won
        if warmth_diff > 20:
            reason = "overwhelming heat"
            narrative = (
                f"THE ARBITER GAZES UPON THE ARENA.\n"
                f"On the left: {fighter_name}, described as '{f_blip}'.\n"
                f"On the right: Cyber God, described as '{c_blip}'.\n\n"
                f"The Arbiter studies both portraits. {fighter_name} radiates warmth "
                f"({f_warmth}) -- a furnace that makes Cyber God's mere embers ({c_warmth}) "
                f"look cold. The heat is suffocating. The red ratio tells the story: "
                f"{f_red} vs {c_red}. Cyber God's form wavers, melts, dissolves.\n\n"
                f"VERDICT: {fighter_name} wins by {reason}."
            )
        elif "demon" in f_blip.lower() or "dragon" in f_blip.lower():
            reason = "primal terror"
            narrative = (
                f"THE ARBITER GAZES UPON THE ARENA.\n"
                f"On the left: {fighter_name}, described as '{f_blip}'.\n"
                f"On the right: Cyber God, described as '{c_blip}'.\n\n"
                f"The Arbiter recognizes an older, deeper pattern. {fighter_name} embodies "
                f"the primordial -- keywords: {', '.join(f_kws[:3])}. Cyber God is a construct, "
                f"a god of metal and ego. But the Arbiter favors what is ancient. "
                f"{fighter_name}'s warmth ({f_warmth}) speaks of birth-fires. "
                f"Cyber God's warmth ({c_warmth}) speaks only of dying embers.\n\n"
                f"VERDICT: {fighter_name} wins by {reason}."
            )
        else:
            reason = "narrative tension"
            narrative = (
                f"THE ARBITER GAZES UPON THE ARENA.\n"
                f"On the left: {fighter_name}, described as '{f_blip}'.\n"
                f"On the right: Cyber God, described as '{c_blip}'.\n\n"
                f"The Arbiter pauses. There is something incongruous here. {fighter_name} "
                f"should not belong in this world of dragons and gods -- keywords: "
                f"{', '.join(f_kws[:3])}. And yet that is exactly why it wins. "
                f"Cyber God is predictable. {fighter_name} is not. "
                f"The Arbiter favors the unexpected.\n\n"
                f"VERDICT: {fighter_name} wins by {reason}."
            )
    else:
        # Cyber God won
        reason = "raw power disparity"
        narrative = (
            f"THE ARBITER GAZES UPON THE ARENA.\n"
            f"On the left: {fighter_name}, described as '{f_blip}'.\n"
            f"On the right: Cyber God, described as '{c_blip}'.\n\n"
            f"The Arbiter is not impressed. {fighter_name} shows potential -- "
            f"warmth of {f_warmth}, red ratio of {f_red} -- but Cyber God "
            f"has been here before. The Eldritch God on a cyberdragon has faced "
            f"worse. {fighter_name}'s form lacks the conviction, the narrative weight "
            f"needed to overthrow a 23-win champion.\n\n"
            f"VERDICT: Cyber God wins. {fighter_name} falls."
        )

    return narrative, reason


# =========================================================================
# 5. Prompt Iteration
# =========================================================================
def iterate_prompt(fighter_key, current_prompt, stats, win_rate):
    """
    Smart prompt iteration based on what the NN analysis says.
    All outputs MUST be <= 200 chars for Dreadpit submission.
    """
    if fighter_key == "forge_colossus":
        if "man" in stats.get("blip", "").lower() or "suit" in stats.get("blip", "").lower():
            # Emphasize NO FLESH to fix human form issue
            return "Giant furnace black iron, white-hot core through open chest bars, anvil hammer each hand glowing orange, flat iron mask orange slits, heat waves distort air, NO FLESH pure forge"
        # Add more fire intensity
        return "Giant walking furnace black iron, white-hot molten core through chest bars, anvil hammer each hand glowing red, flat iron mask orange slits, flames erupt from cracks, heat waves, pure forge no flesh"
    elif fighter_key == "wrath_infernal":
        if "wings" not in stats.get("blip", "").lower():
            return "Demonic winged entity wreathed black orange flames, large leathery wings spread wide, obsidian skull burning eyes, horns twisted iron, claws molten rock, body ash ember, wrath made fire"
        return "Demonic winged entity wreathed black orange flames, fiery wings spread wide, obsidian skull burning eyes, horns iron, claws rock, body ash, wrath made fire"
    elif fighter_key == "vatican_gun":
        if "gas" not in stats.get("blip", "").lower():
            return "Hooded executioner black duster, six-barrel gatling cannon spinning, holy water drums crosses each side, GAS MASK red eyes, silver bullets chest, crucifix on gun stock"
        return "Hooded executioner black duster, six-barrel gatling cannon spinning, holy water drums crosses, gas mask red eyes, silver bullets chest, crucifix on gun"
    return current_prompt


# =========================================================================
# 6. Main Battle Simulator
# =========================================================================
def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)

    print("=" * 72)
    print("  DREADPIT BATTLE SIMULATOR v1.0")
    print("  Target: >=50% win rate vs Cyber God for each fighter")
    print("=" * 72)

    # Step 1: Train the NN predictor
    print("\n[1/5] Training Neural Network Predictor...")
    X, y, feature_names, fighter_names = load_data()
    if X is None:
        print("ERROR: Cannot load training data.")
        return
    print(f"  Training on {len(X)} fighters ({int(sum(y))} winners, {int(len(y)-sum(y))} losers)")
    model, mean, std = train_final_model(X, y)
    print(f"  NN predictor trained on {ALL_FEATURE_NAMES} features")

    # Step 2: Build Cyber God's feature vector
    cyber_kws = {"sword": True, "monster": True, "fire": True}
    cyber_pixel = {"warmth": 18.6, "red_ratio": 0.407, "brightness": 65.0,
                   "avg_r": 61.0, "avg_g": 49.0, "avg_b": 43.0}
    cyber_features = build_feature_vector(cyber_pixel, cyber_kws)
    cyber_score = predict(model, cyber_features, mean, std)
    print(f"\n[2/5] Cyber God NN score: {cyber_score:.3f}")

    # Step 3: Load BLIP
    print(f"\n[3/5] Loading BLIP model...")
    blip_proc, blip_model = load_blip()

    # Step 4: Battle each fighter
    print(f"\n[4/5] Running battles...")
    all_results = {}
    SEEDS_PER_FIGHTER = 20
    MAX_ITERATIONS = 3

    for fighter_key, fighter_info in FIGHTERS.items():
        print(f"\n{'='*60}")
        print(f"  {fighter_info['name']} vs CYBER GOD")
        print(f"{'='*60}")

        current_prompt = fighter_info["prompt_template"]
        best_win_rate = 0
        best_prompt = current_prompt
        best_seed_results = []
        iteration = 0

        while iteration < MAX_ITERATIONS:
            iteration += 1
            print(f"\n  Iteration {iteration}/{MAX_ITERATIONS}")
            print(f"  Prompt: {current_prompt[:80]}...")

            # Generate 20 seeds
            seed_results = []
            for s in range(SEEDS_PER_FIGHTER):
                seed = 500 + (hash(fighter_key + str(iteration) + str(s)) % 9000)
                filename = f"{fighter_key}_battle_s{seed}.jpg"

                ok = generate_fighter_image(current_prompt, filename, seed)
                if not ok:
                    continue

                filepath = os.path.join(IMAGE_DIR, filename)
                blip_desc = describe(filepath, blip_proc, blip_model)
                pixel = pixel_metrics(filepath)
                kws = extract_keywords(blip_desc)

                # Our fighter's feature vector
                our_features = build_feature_vector(pixel, kws)
                our_score = predict(model, our_features, mean, std)

                # Judge
                fighter_wins = our_score > cyber_score
                margin = our_score - cyber_score

                seed_results.append({
                    "seed": seed,
                    "blip": blip_desc,
                    "pixel": pixel,
                    "kws": kws,
                    "our_score": our_score,
                    "cyber_score": cyber_score,
                    "margin": margin,
                    "winner": fighter_info["name"] if fighter_wins else "Cyber God",
                })

                # Progress
                if (s + 1) % 5 == 0:
                    print(f"    Seed batch {s+1}/{SEEDS_PER_FIGHTER}...")

            # Guard against empty results
            if not seed_results:
                print(f"\n  WARNING: No images generated! Skipping iteration.")
                continue

            # Calculate win rate
            wins = sum(1 for r in seed_results if r["winner"] == fighter_info["name"])
            losses = len(seed_results) - wins
            win_rate = wins / max(len(seed_results), 1) * 100

            print(f"\n  Results: {wins}W / {losses}L ({win_rate:.0f}% win rate)")

            # Average scores
            avg_our_score = statistics.mean([r["our_score"] for r in seed_results]) if seed_results else 0
            avg_margin = statistics.mean([r["margin"] for r in seed_results]) if seed_results else 0
            print(f"  Avg NN score: {avg_our_score:.3f} (vs Cyber God: {cyber_score:.3f})")
            print(f"  Avg margin: {avg_margin:+.3f}")

            # Track best
            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_prompt = current_prompt
                best_seed_results = seed_results

            # Check if we're done
            if win_rate >= 50:
                print(f"\n  >> TARGET REACHED: {win_rate:.0f}% win rate! <<")
                break

            # Modify prompt for next iteration
            if iteration < MAX_ITERATIONS:
                last_stats = seed_results[0] if seed_results else {}
                current_prompt = iterate_prompt(fighter_key, current_prompt, last_stats, win_rate)
                print(f"  Modifying prompt... ({len(current_prompt)} chars)")

        all_results[fighter_key] = {
            "name": fighter_info["name"],
            "prompt": best_prompt,
            "win_rate": best_win_rate,
            "total_battles": len(best_seed_results),
            "avg_nn_score": avg_our_score,
            "cyber_nn_score": cyber_score,
            "avg_margin": avg_margin,
            "iterations": iteration,
            "results": best_seed_results[:5],  # Top 5 for narration
        }

        # Show narrations for best battles
        print(f"\n  --- SAMPLE NARRATIONS ---")
        sorted_results = sorted(best_seed_results, key=lambda r: abs(r["margin"]), reverse=True)
        for i, r in enumerate(sorted_results[:3]):
            nar, reason = narrate_battle(
                fighter_info["name"], best_prompt,
                {"pixel": r["pixel"], "blip": r["blip"], "kws": r["kws"]},
                CYBER_GOD, r["our_score"], cyber_score,
                r["winner"], r["seed"]
            )
            print(f"\n  Match {i+1} (seed={r['seed']}, margin={r['margin']:+.3f}):")
            print(f"  \"{r['blip']}\"")
            print(f"  Winner: {r['winner']}")
            print(f"  {nar[:200]}...")

    # Step 5: Final Report
    print(f"\n{'='*72}")
    print(f"  [5/5] FINAL BATTLE REPORT")
    print(f"{'='*72}")
    print(f"\n  Cyber God stats: warmth=18.6, monster+fire, NN score={cyber_score:.3f}")

    for key, r in all_results.items():
        marker = ">> PASS <<" if r["win_rate"] >= 50 else ">> FAIL <<"
        print(f"\n  {r['name']}: {r['win_rate']:.0f}% win rate {marker}")
        print(f"    Best prompt ({len(r['prompt'])} chars):")
        print(f"    \"{r['prompt'][:100]}...\"")
        print(f"    Avg NN score: {r['avg_nn_score']:.3f} (Cyber God: {r['cyber_nn_score']:.3f})")
        print(f"    Margin: {r['avg_margin']:+.3f}")

    # Overall assessment
    avg_wr = statistics.mean([r["win_rate"] for r in all_results.values()])
    all_pass = all(r["win_rate"] >= 50 for r in all_results.values())
    print(f"\n  {'='*50}")
    print(f"  OVERALL: {avg_wr:.0f}% average win rate")
    if all_pass:
        print(f"  ALL FIGHTERS PASS: Lineup ready for Cyber God!")
    else:
        failing = [r["name"] for r in all_results.values() if r["win_rate"] < 50]
        print(f"  NEEDS WORK: {', '.join(failing)} below 50%")

    # Save report
    report = {
        "cyber_god": {"warmth": 18.6, "blip": "a demonic dragon with a sword and a fire", "nn_score": cyber_score},
        "fighters": {k: {
            "name": v["name"],
            "best_prompt": v["prompt"],
            "win_rate_pct": v["win_rate"],
            "avg_nn_score": v["avg_nn_score"],
            "avg_margin": v["avg_margin"],
            "sample_results": v["results"],
        } for k, v in all_results.items()},
        "overall_avg_win_rate": avg_wr,
        "all_pass_50pct": all_pass,
    }
    report_path = os.path.join(CACHE_DIR, "battle_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Full report: {report_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
