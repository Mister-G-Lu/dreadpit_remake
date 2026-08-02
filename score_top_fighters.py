#!/usr/bin/env python3
"""
Score EVERY 5+ win fighter through the trained Neural Network predictor,
with special highlighting of outlier fighters: BIG, SIMO, Toon Jester.
"""

import json
import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))


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


def load_data():
    path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Cannot load data: {e}")
        return None, None, None, None, None, None

    results = data.get("results", [])
    if not results:
        print("ERROR: No results in comparison_analysis.json")
        return None, None, None, None, None, None

    keyword_keys = [
        "sword", "axe_hammer", "gun", "armor", "helmet", "human",
        "monster", "robot", "fire", "dark", "red", "blue", "metal",
        "wings", "shield", "cape"
    ]
    pixel_keys = ["brightness", "warmth", "red_ratio", "avg_r", "avg_g", "avg_b"]
    all_feature_names = keyword_keys + pixel_keys

    X = []
    y = []
    fighter_names = []
    wins_list = []

    for r in results:
        kws = r.get("kws", {})
        pixel = r.get("pixel", {})
        wins = r.get("wins", 0)
        name = r.get("name", "?")

        features = []
        for kw in keyword_keys:
            val = 1.0 if kws.get(kw, False) else 0.0
            features.append(val)
        for pk in pixel_keys:
            val = pixel.get(pk, 0.0)
            if val is None:
                val = 0.0
            features.append(float(val))

        if wins >= 5:
            y.append(1.0)
            X.append(features)
            fighter_names.append(name)
            wins_list.append(wins)
        elif wins <= 3:
            y.append(0.0)
            X.append(features)
            fighter_names.append(name)
            wins_list.append(wins)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    return X, y, all_feature_names, fighter_names, wins_list, results


def normalize(X, mean=None, std=None):
    if mean is None:
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        std[std == 0] = 1.0
    X_norm = (X - mean) / std
    return X_norm, mean, std


def main():
    sep = "=" * 72
    print(sep)
    print("  NN WINNER PREDICTOR - Full Fighter Scoring")
    print(sep)

    # 1. Load data
    print("\n[1/4] Loading data...")
    X, y, feature_names, names, wins, all_results = load_data()
    if X is None:
        return
    print(f"  Training set: {len(X)} fighters ({int(sum(y))} high-winners, {int(len(y)-sum(y))} low-winners)")

    # 2. Train on full dataset
    print("\n[2/4] Training NN on full training set...")
    X_norm, mean, std = normalize(X)

    X_t = torch.FloatTensor(X_norm)
    y_t = torch.FloatTensor(y)

    model = WinnerPredictor(X.shape[1])
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)

    for epoch in range(500):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_t)
        loss = criterion(outputs, y_t)
        loss.backward()
        optimizer.step()

        if epoch % 100 == 99:
            model.eval()
            with torch.no_grad():
                preds = (model(X_t) >= 0.5).float()
                acc = (preds == y_t).float().mean().item()
            if epoch % 200 == 199:
                print(f"    Epoch {epoch+1:3d} - train acc: {acc:.3f}")

    # 3. Score all fighters
    print("\n[3/4] Scoring ALL fighters from the dataset...")

    keyword_keys = [
        "sword", "axe_hammer", "gun", "armor", "helmet", "human",
        "monster", "robot", "fire", "dark", "red", "blue", "metal",
        "wings", "shield", "cape"
    ]
    pixel_keys = ["brightness", "warmth", "red_ratio", "avg_r", "avg_g", "avg_b"]

    scored = []
    model.eval()
    with torch.no_grad():
        for r in all_results:
            kws = r.get("kws", {})
            pixel = r.get("pixel", {})
            name = r.get("name", "?")
            wins_count = r.get("wins", 0)
            group = r.get("group", "?")

            features = []
            for kw in keyword_keys:
                features.append(1.0 if kws.get(kw, False) else 0.0)
            for pk in pixel_keys:
                val = pixel.get(pk, 0.0)
                if val is None:
                    val = 0.0
                features.append(float(val))

            feat = np.array([features], dtype=np.float32)
            feat_norm = (feat - mean) / std
            feat_t = torch.FloatTensor(feat_norm)
            score = model(feat_t).item()

            scored.append({
                "name": name,
                "wins": wins_count,
                "group": group,
                "nn_score": round(score, 4),
                "blip": r.get("blip", "")[:80],
                "warmth": pixel.get("warmth", 0),
                "brightness": pixel.get("brightness", 0),
                "red_ratio": pixel.get("red_ratio", 0),
            })

    # 4. Print results
    print("\n[4/4] Results\n")

    by_wins = sorted(scored, key=lambda x: (-x["wins"], -x["nn_score"]))

    print(sep)
    print("  ALL 5+ WIN FIGHTERS - Sorted by Wins")
    print(sep)
    header = f"  {'Rank':>4s} {'Name':35s} {'Wins':>4s} {'NN Score':>9s} {'Warmth':>7s} {'Bright':>7s} {'Red%':>5s} {'Group'}"
    print(header)
    print(f"  {'-'*4} {'-'*35} {'-'*4} {'-'*9} {'-'*7} {'-'*7} {'-'*5} {'-'*10}")

    top_fighters = [s for s in by_wins if s["wins"] >= 5]
    for i, s in enumerate(top_fighters):
        marker = ""
        name_upper = s["name"].upper()
        if "BIG" in name_upper:
            marker = " << BIG"
        elif "SIMO" in name_upper:
            marker = " << SIMO"
        elif "TOON" in name_upper or "JESTER" in name_upper:
            marker = " << JESTER"
        row = f"  {i+1:>4d} {s['name'][:35]:35s} {s['wins']:>4d} {s['nn_score']:>8.3f}  {s['warmth']:>+6.1f} {s['brightness']:>6.1f} {s['red_ratio']:>4.3f} {s['group'][:10]:10s}{marker}"
        print(row)

    # --- Outlier highlight ---
    print("\n" + sep)
    print("  *** OUTLIER FOCUS - BIG, SIMO, TOON JESTER ***")
    print(sep)

    outliers = [s for s in scored if
                "BIG" in s["name"].upper() or
                "SIMO" in s["name"].upper() or
                "TOON" in s["name"].upper() or "JESTER" in s["name"].upper()]

    for o in outliers:
        print(f"\n  {o['name']:40s} ({o['wins']} wins)")
        print(f"  {'':40s} NN Score: {o['nn_score']:.3f}")
        print(f"  {'':40s} Warmth: {o['warmth']:+.1f} | Bright: {o['brightness']:.1f} | Red: {o['red_ratio']:.3f}")
        print(f"  {'':40s} BLIP: {o.get('blip', '')}")

    # --- Top 10 by NN score ---
    print("\n" + sep)
    print("  TOP 10 CHAMPIONS (highest NN score)")
    print(sep)
    by_score = sorted([s for s in scored if s["wins"] >= 5], key=lambda x: -x["nn_score"])
    for i, s in enumerate(by_score[:10]):
        print(f"  {i+1:>2d}. {s['name'][:35]:35s} Win={s['wins']:>2d}  NN={s['nn_score']:.3f}  W={s['warmth']:+.0f}  B={s['brightness']:.0f}  R={s['red_ratio']:.3f}")

    # --- Bottom 10 by NN score (among 5+ winners) ---
    print("\n" + sep)
    print("  BOTTOM 10 HIGH-WINNERS (lowest NN score - the 'frauds')")
    print(sep)
    for i, s in enumerate(by_score[-10:]):
        print(f"  {i+1:>2d}. {s['name'][:35]:35s} Win={s['wins']:>2d}  NN={s['nn_score']:.3f}  W={s['warmth']:+.0f}  B={s['brightness']:.0f}  R={s['red_ratio']:.3f}")

    # --- THE VERDICT ---
    print("\n" + sep)
    print("  THE OUTLIER VERDICT")
    print(sep)

    for o in outliers:
        rank_wins = next((i+1 for i, s in enumerate(by_wins) if s["name"] == o["name"]), 999)
        rank_score = next((i+1 for i, s in enumerate(by_score) if s["name"] == o["name"]), 999)
        is_fraud = o["nn_score"] < 0.5
        verdict = "*** FRAUD - winning despite NN expectations! ***" if is_fraud else "NN expects this fighter to win"
        print(f"\n  {o['name']:40s}")
        print(f"    Wins rank:  #{rank_wins} / {len(top_fighters)}")
        print(f"    NN rank:    #{rank_score} / {len(top_fighters)}")
        print(f"    NN Score:   {o['nn_score']:.3f} (0=loser archetype, 1=winner archetype)")
        print(f"    Verdict:    {verdict}")
        print(f"    BLIP:       {o.get('blip', '')}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
