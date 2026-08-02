#!/usr/bin/env python3
"""
Score the best renderable NEW archetype images through the NN predictor,
compared against Cyber God's score.
"""
import json, os, statistics
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

np.random.seed(42)

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "new_archetypes")


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


def load_and_train():
    with open(os.path.join(CACHE_DIR, "comparison_analysis.json"), encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    keyword_keys = ["sword","axe_hammer","gun","armor","helmet","human","monster",
                    "robot","fire","dark","red","blue","metal","wings","shield","cape"]
    pixel_keys = ["brightness","warmth","red_ratio","avg_r","avg_g","avg_b"]
    X, y = [], []
    for r in results:
        kws = r.get("kws", {}); pixel = r.get("pixel", {}); wins = r.get("wins", 0)
        feats = [1.0 if kws.get(k, False) else 0.0 for k in keyword_keys]
        feats += [float(pixel.get(p, 0.0) or 0.0) for p in pixel_keys]
        if wins >= 5:
            X.append(feats); y.append(1.0)
        elif wins <= 3:
            X.append(feats); y.append(0.0)
    X = np.array(X, dtype=np.float32); y = np.array(y, dtype=np.float32)
    mean = np.mean(X, axis=0); std = np.std(X, axis=0); std[std == 0] = 1.0
    X_norm = (X - mean) / std
    model = WinnerPredictor(X.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    crit = nn.BCELoss()
    Xt = torch.FloatTensor(X_norm); yt = torch.FloatTensor(y)
    for epoch in range(500):
        model.train(); opt.zero_grad()
        loss = crit(model(Xt), yt)
        loss.backward(); opt.step()
    return model, mean, std, keyword_keys, pixel_keys


def analyze_img(filepath, blip_proc, blip_model):
    img = Image.open(filepath).convert("RGB")
    inputs = blip_proc(img, return_tensors="pt")
    with torch.no_grad():
        out = blip_model.generate(**inputs, max_length=50)
    desc = blip_proc.decode(out[0], skip_special_tokens=True)
    px = list(img.getdata())
    r = statistics.mean([p[0] for p in px]); g = statistics.mean([p[1] for p in px]); b = statistics.mean([p[2] for p in px])
    dl = desc.lower()
    # EXACT same extraction as training data (iterate_prompts.py / blip pipeline).
    # Do NOT broaden keywords here, or scores become unfair vs stored fighters.
    kws = {
        "sword": "sword" in dl or "blade" in dl,
        "axe_hammer": any(w in dl for w in ["axe","hammer"]),
        "gun": any(w in dl for w in ["gun","rifle","cannon","gatling"]),
        "armor": "armor" in dl or "armour" in dl,
        "helmet": "helmet" in dl,
        "human": any(w in dl for w in ["man","woman","human","person","character"]),
        "monster": any(w in dl for w in ["demon","monster","beast","dragon","fiend"]),
        "robot": any(w in dl for w in ["robot","mech","gundam","android"]),
        "fire": any(w in dl for w in ["fire","flame","burn","blaze","molten","lava","ember"]),
        "dark": any(w in dl for w in ["dark","black","shadow","obsidian"]),
        "red": "red" in dl or "orange" in dl,
        "blue": "blue" in dl,
        "metal": any(w in dl for w in ["metal","iron","steel","forged"]),
        "wings": "wings" in dl or "winged" in dl,
        "shield": "shield" in dl,
        "cape": any(w in dl for w in ["cape","cloak","duster","coat"]),
    }
    return desc, kws, {"brightness": round((r+g+b)/3,1), "warmth": round(r-b,1),
                       "red_ratio": round(r/max(r+g+b,1),3), "avg_r": round(r,1),
                       "avg_g": round(g,1), "avg_b": round(b,1)}


def score(model, mean, std, keyword_keys, pixel_keys, kws, pixel):
    feats = [1.0 if kws.get(k, False) else 0.0 for k in keyword_keys]
    feats += [float(pixel.get(p, 0.0) or 0.0) for p in pixel_keys]
    f = np.array([feats], dtype=np.float32)
    fn = (f - mean) / std
    with torch.no_grad():
        return model(torch.FloatTensor(fn)).item()


def main():
    print("=" * 72)
    print("  NN SCORE: NEW RENDERABLE ARCHETYPES vs CYBER GOD")
    print("=" * 72)
    print("\nLoading BLIP + training NN...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    model, mean, std, keyword_keys, pixel_keys = load_and_train()
    print("  OK\n")

    # Best variant per renderable archetype
    targets = {
        "undead_skeleton_lich": "undead_skeleton_lich_v2",
        "ice_frost_titan": "ice_frost_titan_v1",
        "nature_fungal": "nature_fungal_v2",
    }

    print(f"{'Archetype':22s} {'Seed':>5s} {'NN Score':>9s} {'Warmth':>7s}  BLIP")
    print("-" * 100)
    results = {}
    for arch, prefix in targets.items():
        seeds = []
        for s in [42, 777, 2024]:
            fp = os.path.join(OUT_DIR, f"{prefix}_s{s}.jpg")
            if not os.path.exists(fp):
                continue
            desc, kws, pixel = analyze_img(fp, blip_proc, blip_model)
            sc = score(model, mean, std, keyword_keys, pixel_keys, kws, pixel)
            seeds.append(sc)
            print(f"{arch:22s} {s:>5d} {sc:>8.3f} {pixel['warmth']:>+6.1f}  {desc}")
        if not seeds:
            print(f"{arch:22s} NO IMAGES FOUND")
            continue
        results[arch] = {"mean": round(sum(seeds)/len(seeds),3), "seeds": seeds}

    # Cyber God comparison
    print("\n" + "-" * 100)
    print("CYBER GOD (Eldritch armord god on cyberdragon, 22+ wins, ALIVE)")
    with open(os.path.join(CACHE_DIR, "comparison_analysis.json"), encoding="utf-8") as f:
        data = json.load(f)
    cg = next((r for r in data["results"] if "cyberdragon" in r.get("name","").lower() or "armord god" in r.get("name","").lower()), None)
    if cg:
        sc = score(model, mean, std, keyword_keys, pixel_keys, cg["kws"], cg["pixel"])
        print(f"  Cyber God NN score: {sc:.3f}  (warmth {cg['pixel'].get('warmth',0):+.1f})")
        print(f"  BLIP: {cg.get('blip','')}")
    else:
        print("  Cyber God not found in dataset (using known reference: warmth=18.6)")
        sc = 0.993
    print("\n" + "=" * 72)
    print("  VERDICT")
    print("=" * 72)
    for arch, res in results.items():
        delta = res["mean"] - sc
        print(f"  {arch:22s} NN={res['mean']:.3f}  vs CyberGod {sc:.3f}  ({delta:+.3f})")


if __name__ == "__main__":
    main()
