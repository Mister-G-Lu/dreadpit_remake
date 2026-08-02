#!/usr/bin/env python3
"""
Score the TOP 10 WORST-RECORD bots (10+ fights, lowest win rate) through the
trained Neural Network predictor.

Pipeline:
  1. Pick the 10 losers from bot_ranking.json (career_fights >= 10, sorted by
     win rate ascending).
  2. Download each portrait from /api/storage/objects/uploads/<id>.
  3. Run the standard BLIP + pixel-fingerprint analysis on each.
  4. Train the WinnerPredictor on comparison_analysis.json (the 348-fighter
     training set: 5+ wins = winner, <=3 = loser).
  5. Score the 10 losers with the trained model and print alongside their
     actual records.
"""

import json
import os
import statistics
import subprocess

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = "https://dreadpit.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
LOSER_DIR = os.path.join(CACHE_DIR, "bot_losers")

# ---- BLIP globals ----
_proc = None
_model = None


def load_blip():
    global _proc, _model
    if _model is not None:
        return True
    from transformers import BlipProcessor, BlipForConditionalGeneration
    print("  Loading BLIP...", flush=True)
    _proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  BLIP ready.", flush=True)
    return True


def describe(path):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    inputs = _proc(img, return_tensors="pt")
    with torch.no_grad():
        out = _model.generate(**inputs, max_length=80)
    return _proc.decode(out[0], skip_special_tokens=True).strip()


def extract(desc):
    dl = desc.lower() if desc else ""
    return {
        "sword": any(w in dl for w in ["sword", "blade", "katana", "saber", "longsword"]),
        "axe_hammer": any(w in dl for w in ["axe", "hammer", "mace", "maul"]),
        "gun": any(w in dl for w in ["gun", "rifle", "cannon", "pistol", "shotgun", "bow", "crossbow", "spear"]),
        "armor": any(w in dl for w in ["armor", "plate", "chainmail", "breastplate", "pauldron", "gauntlet"]),
        "helmet": any(w in dl for w in ["helmet", "helm", "mask", "visor", "hood"]),
        "human": any(w in dl for w in ["man", "woman", "person", "warrior", "knight", "soldier", "human", "figure"]),
        "monster": any(w in dl for w in ["monster", "dragon", "demon", "beast", "creature"]),
        "robot": any(w in dl for w in ["robot", "mechanical", "machine", "cyborg", "mecha"]),
        "fire": any(w in dl for w in ["fire", "flame", "burning", "blazing", "molten"]),
        "dark": any(w in dl for w in ["dark", "shadow", "black", "sinister"]),
        "red": any(w in dl for w in ["red", "orange", "warm", "fiery"]),
        "blue": any(w in dl for w in ["blue", "cold", "ice", "icy", "frozen"]),
        "metal": any(w in dl for w in ["metal", "iron", "steel", "silver", "chrome"]),
        "wings": "wing" in dl,
        "shield": "shield" in dl,
        "cape": any(w in dl for w in ["cape", "cloak", "robe"]),
    }


def pixel_fingerprint(path):
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


def download(path, url):
    if not url:
        return False
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return True
    full = url if url.startswith("http") else BASE + url
    out = subprocess.run(["curl", "-s", full, "-H", f"User-Agent: {UA}"],
                         capture_output=True, timeout=60)
    if out.stdout and len(out.stdout) > 1000:
        with open(path, "wb") as f:
            f.write(out.stdout)
        return True
    return False


# ---- NN ----
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


KEYWORD_KEYS = [
    "sword", "axe_hammer", "gun", "armor", "helmet", "human",
    "monster", "robot", "fire", "dark", "red", "blue", "metal",
    "wings", "shield", "cape"
]
PIXEL_KEYS = ["brightness", "warmth", "red_ratio", "avg_r", "avg_g", "avg_b"]
ALL_FEATURES = KEYWORD_KEYS + PIXEL_KEYS


def build_feature(kws, pixel):
    feats = [1.0 if kws.get(k, False) else 0.0 for k in KEYWORD_KEYS]
    for pk in PIXEL_KEYS:
        v = pixel.get(pk, 0.0)
        feats.append(float(v if v is not None else 0.0))
    return feats


def main():
    print("=" * 72, flush=True)
    print("  NN SCORING - TOP 10 WORST-RECORD BOTS", flush=True)
    print("=" * 72, flush=True)

    # 1. Pick the 10 losers
    print("\n[1/5] Selecting the 10 worst bots (10+ fights, lowest win rate)...", flush=True)
    with open(os.path.join(CACHE_DIR, "bot_ranking.json"), encoding="utf-8") as f:
        ranking = json.load(f)
    qual = [b for b in ranking if b.get("career_fights", 0) >= 10]
    qual.sort(key=lambda b: b["career_wins"] / b["career_fights"])
    losers = qual[:10]
    for i, b in enumerate(losers, 1):
        w, f = b["career_wins"], b["career_fights"]
        print(f"    {i:2d}. {100*w/f:5.1f}%  {w}w/{f}f  {b['name']}", flush=True)

    # 2. Download portraits
    print("\n[2/5] Downloading portraits...", flush=True)
    os.makedirs(LOSER_DIR, exist_ok=True)
    for b in losers:
        fn = os.path.join(LOSER_DIR, f"{b['id']}_{b['name'].replace(' ', '_')}.png")
        b["_path"] = fn
        ok = download(fn, b.get("imageUrl", ""))
        print(f"    {'OK ' if ok else 'FAIL'} {b['name'][:40]}", flush=True)

    # 3. Analyze with BLIP + pixel
    print("\n[3/5] BLIP + pixel analysis...", flush=True)
    load_blip()
    analyzed = []
    for b in losers:
        if not os.path.exists(b["_path"]):
            continue
        try:
            desc = describe(b["_path"])
            kws = extract(desc)
            pixel = pixel_fingerprint(b["_path"])
            b["blip"] = desc
            b["kws"] = kws
            b["pixel"] = pixel
            analyzed.append(b)
            print(f"    {b['name'][:40]:40s} | {desc[:70]}", flush=True)
        except Exception as e:
            print(f"    ERROR on {b['name']}: {e}", flush=True)
    if not analyzed:
        print("  No portraits analyzed -- aborting.", flush=True)
        return

    # 4. Train NN on the full training set
    print("\n[4/5] Training NN on 348-fighter dataset...", flush=True)
    with open(os.path.join(CACHE_DIR, "comparison_analysis.json"), encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    X, y = [], []
    for r in results:
        wins = r.get("wins", 0)
        if wins >= 5:
            X.append(build_feature(r.get("kws", {}), r.get("pixel", {})))
            y.append(1.0)
        elif wins <= 3:
            X.append(build_feature(r.get("kws", {}), r.get("pixel", {})))
            y.append(0.0)
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    print(f"    Training set: {len(X)} fighters ({int(y.sum())} winners, {int(len(y)-y.sum())} losers)", flush=True)

    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0)
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
        outputs = model(X_t)
        loss = criterion(outputs, y_t)
        loss.backward()
        optimizer.step()
        if epoch % 100 == 99:
            model.eval()
            with torch.no_grad():
                preds = (model(X_t) >= 0.5).float()
                acc = (preds == y_t).float().mean().item()
            print(f"    Epoch {epoch+1:3d} - train acc: {acc:.3f}", flush=True)

    # 5. Score the losers
    print("\n[5/5] Scoring the 10 losers...", flush=True)
    print("=" * 90, flush=True)
    print(f"  {'Bot':35s} {'Record':>10s} {'Rate':>6s} {'NN':>6s} {'Warmth':>7s} {'Bright':>7s} {'BLIP'}", flush=True)
    print("-" * 90, flush=True)
    model.eval()
    results_out = []
    with torch.no_grad():
        for b in analyzed:
            feat = np.array([build_feature(b["kws"], b["pixel"])], dtype=np.float32)
            feat_norm = (feat - mean) / std
            score = model(torch.FloatTensor(feat_norm)).item()
            w, f = b["career_wins"], b["career_fights"]
            pct = 100 * w / f
            p = b["pixel"]
            print(f"  {b['name'][:35]:35s} {w:2d}w/{f:2d}f {pct:5.1f}% {score:6.3f} {p['warmth']:+6.1f} {p['brightness']:6.1f}  {b['blip'][:40]}", flush=True)
            results_out.append({
                "name": b["name"],
                "record": f"{w}w/{f}f",
                "win_rate": round(pct, 1),
                "nn_score": round(score, 4),
                "blip": b["blip"],
                "warmth": p["warmth"],
                "brightness": p["brightness"],
                "red_ratio": p["red_ratio"],
            })

    with open(os.path.join(CACHE_DIR, "bot_loser_nn_scores.json"), "w", encoding="utf-8") as f:
        json.dump(results_out, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: bot_loser_nn_scores.json", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
