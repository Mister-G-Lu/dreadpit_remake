#!/usr/bin/env python3
"""
Identify GAP FIGHTERS for the NN: the two failure groups the user wants
Florence to help with:
  GAP A (false negatives): high-wins (5+) fighters the NN scores < 0.5
  GAP B (false positives): low-wins (<=3) fighters the NN scores >= 0.5

Trains the baseline WinnerPredictor on comparison_analysis.json, scores every
fighter, prints both gap groups with their BLIP keywords + pixel metrics.
"""
import json
import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))

KEYWORD_KEYS = [
    "sword", "axe_hammer", "gun", "armor", "helmet", "human",
    "monster", "robot", "fire", "dark", "red", "blue", "metal",
    "wings", "shield", "cape"
]
PIXEL_KEYS = ["brightness", "warmth", "red_ratio", "avg_r", "avg_g", "avg_b"]


class WinnerPredictor(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 16), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(16, 8), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(8, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze()


def build_feature(kws, pixel):
    feats = [1.0 if kws.get(k, False) else 0.0 for k in KEYWORD_KEYS]
    for pk in PIXEL_KEYS:
        v = pixel.get(pk, 0.0)
        feats.append(float(v if v is not None else 0.0))
    return feats


def main():
    with open(os.path.join(CACHE_DIR, "comparison_analysis.json"), encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])

    X, y, names, wins = [], [], [], []
    for r in results:
        w = r.get("wins", 0)
        if w >= 5 or w <= 3:
            X.append(build_feature(r.get("kws", {}), r.get("pixel", {})))
            y.append(1.0 if w >= 5 else 0.0)
            names.append(r.get("name", "?"))
            wins.append(w)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    mean, std = np.mean(X, axis=0), np.std(X, axis=0)
    std[std == 0] = 1.0
    X_norm = (X - mean) / std

    X_t = torch.FloatTensor(X_norm)
    y_t = torch.FloatTensor(y)
    model = WinnerPredictor(X.shape[1])
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    for epoch in range(500):
        model.train()
        optimizer.zero_grad()
        loss = criterion(model(X_t), y_t)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        scores = model(X_t).numpy()

    gap_a, gap_b = [], []
    for i, s in enumerate(scores):
        if wins[i] >= 5 and s < 0.5:
            gap_a.append((names[i], wins[i], float(s)))
        elif wins[i] <= 3 and s >= 0.5:
            gap_b.append((names[i], wins[i], float(s)))

    gap_a.sort(key=lambda x: x[2])
    gap_b.sort(key=lambda x: -x[2])

    # ---- Merge the 10 bot losers (GAP B from bot_loser_nn_scores.json) ----
    bot_path = os.path.join(CACHE_DIR, "bot_loser_nn_scores.json")
    merged_b = list(gap_b)
    if os.path.exists(bot_path):
        with open(bot_path, encoding="utf-8") as f:
            bots = json.load(f)
        for b in bots:
            sc = b.get("nn_score")
            if sc is not None and sc >= 0.5:
                rec = b.get("record", "?")
                try:
                    bw = int(rec.split("w")[0]) if "w" in rec else 0
                except (ValueError, IndexError):
                    bw = 0
                merged_b.append((b.get("name", "?"), bw, sc))
        merged_b.sort(key=lambda x: -x[2])
        print(f"  Merged {len(bots)} bot losers from bot_loser_nn_scores.json")

    print("=" * 90)
    print(f"  GAP A — HIGH-WINNERS (5+) the NN scores as LOSERS (< 0.5): {len(gap_a)}")
    print("=" * 90)
    name_to_res = {x.get("name"): x for x in results}
    for n, w, s in gap_a:
        r = name_to_res.get(n, {})
        kws = [k for k, v in r.get("kws", {}).items() if v]
        print(f"  {s:6.3f}  {w:>2d}w  {n[:38]:38s} kws=[{','.join(kws)[:50]}]")

    print()
    print("=" * 90)
    print(f"  GAP B — LOW-WINNERS the NN scores as WINNERS (>= 0.5): {len(merged_b)} "
          f"({len(gap_b)} humans + {len(merged_b)-len(gap_b)} bots)")
    print("=" * 90)
    for n, w, s in merged_b:
        r = name_to_res.get(n, {})
        kws = [k for k, v in r.get("kws", {}).items() if v]
        tag = "[BOT]" if n not in name_to_res else "     "
        print(f"  {s:6.3f}  {w:>2d}w  {n[:38]:38s} {tag} kws=[{','.join(kws)[:50]}]")

    print(f"\n  Baseline errors: {len(gap_a)} FN + {len(gap_b)} FP (humans) = {len(gap_a)+len(gap_b)} of {len(X)}")

    # ---- Persist for the Florence step ----
    out = {
        "gap_a": [{"name": n, "wins": w, "nn_score": s} for n, w, s in gap_a],
        "gap_b": [{"name": n, "wins": w, "nn_score": s} for n, w, s in merged_b],
    }
    with open(os.path.join(CACHE_DIR, "nn_gap_fighters.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  Saved: nn_gap_fighters.json ({len(gap_a)} gap A + {len(merged_b)} gap B)")


if __name__ == "__main__":
    main()
