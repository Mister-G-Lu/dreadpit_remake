"""
DREADPIT BATTLE GENERATOR
Generates fighter images at multiple FLUX seeds, extracts visual features
via BLIP + pixel analysis, scores each with the NN predictor, and outputs
raw data. The narration and iteration decisions are made by the human/AI
reviewing this data, not by hardcoded logic.
"""
import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
import torch, torch.nn as nn, numpy as np
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(CACHE_DIR, "battle_sims")

# ============================================================
# CONFIGURATION
# ============================================================
KEYWORD_KEYS = ["sword","axe_hammer","gun","armor","helmet","human",
                "monster","robot","fire","dark","red","blue","metal",
                "wings","shield","cape"]
PIXEL_KEYS = ["brightness","warmth","red_ratio","avg_r","avg_g","avg_b"]
ALL_FEATURES = KEYWORD_KEYS + PIXEL_KEYS

CYBER_GOD_STATS = {
    "blip": "a demonic dragon with a sword and a fire",
    "warmth": 18.6, "red_ratio": 0.407, "brightness": 65.0,
    "kws": {"sword":True, "monster":True, "fire":True}
}

FIGHTERS = {
    "forge_colossus": {
        "name": "Forge Colossus",
        "prompt": "Giant walking furnace made of black iron. White-hot molten core visible through chest bars. Massive anvil-headed hammer in each hand, glowing red. Flat iron mask with orange eye slits. Heat waves distort air around body. No flesh. Just forge.",
    },
    "wrath_infernal": {
        "name": "Wrath Infernal",
        "prompt": "Demonic winged entity wreathed in black orange flames, fiery wings spread wide, obsidian skull burning orange eyes, horns twisted iron, claws molten rock, body ash ember, wrath made fire",
    },
    "vatican_gun": {
        "name": "Vatican Gun",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel gatling cannon, barrels clearly visible spinning. Holy water drums marked with crosses on each side. Gas mask with red glowing eyes. Silver bullets across chest. Crucifix on gun.",
    },
}

# ============================================================
# NN PREDICTOR (matches nn_predictor.py)
# ============================================================
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

def load_data():
    path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", [])
    X, y = [], []
    for r in results:
        kws = r.get("kws", {})
        pixel = r.get("pixel", {})
        wins = r.get("wins", 0)
        features = []
        for kw in KEYWORD_KEYS:
            features.append(1.0 if kws.get(kw, False) else 0.0)
        for pk in PIXEL_KEYS:
            val = pixel.get(pk, 0.0) or 0.0
            features.append(float(val))
        if wins >= 5:
            y.append(1.0); X.append(features)
        elif wins <= 3:
            y.append(0.0); X.append(features)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

def train_nn(X, y):
    mean, std = np.mean(X, axis=0), np.std(X, axis=0)
    std[std == 0] = 1.0
    Xn = (X - mean) / std
    model = WinnerPredictor(X.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    crit = nn.BCELoss()
    Xt, yt = torch.FloatTensor(Xn), torch.FloatTensor(y)
    best_loss, best_state, patience = float('inf'), None, 0
    for epoch in range(1000):
        model.train(); opt.zero_grad()
        loss = crit(model(Xt), yt)
        loss.backward(); opt.step()
        if loss.item() < best_loss:
            best_loss = loss.item(); best_state = model.state_dict().copy(); patience = 0
        else:
            patience += 1
        if patience >= 100: break
    model.load_state_dict(best_state)
    return model, mean, std

def build_features(pixel, kws):
    f = []
    for kw in KEYWORD_KEYS:
        f.append(1.0 if kws.get(kw, False) else 0.0)
    for pk in PIXEL_KEYS:
        f.append(float(pixel.get(pk, 0.0) or 0.0))
    return f

def predict(model, features, mean, std):
    f = (np.array(features, dtype=np.float32) - mean) / std
    model.eval()
    with torch.no_grad():
        return model(torch.FloatTensor(f).unsqueeze(0)).item()

# ============================================================
# IMAGE GENERATION + ANALYSIS
# ============================================================
def generate(prompt, filename, seed):
    os.makedirs(IMAGE_DIR, exist_ok=True)
    fp = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        return True
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(fp, "wb") as f: f.write(r.content)
                return True
        except: pass
        time.sleep(3)
    return False

def analyze(filepath, blip_proc, blip_model):
    img = Image.open(filepath).convert("RGB")
    inputs = blip_proc(img, return_tensors="pt")
    with torch.no_grad():
        out = blip_model.generate(**inputs, max_length=50)
    desc = blip_proc.decode(out[0], skip_special_tokens=True)
    px = list(img.getdata())
    r = statistics.mean([p[0] for p in px])
    g = statistics.mean([p[1] for p in px])
    b = statistics.mean([p[2] for p in px])
    pixel = {"brightness": round((r+g+b)/3,1), "warmth": round(r-b,1),
             "red_ratio": round(r/max(r+g+b,1),3), "avg_r": round(r,1),
             "avg_g": round(g,1), "avg_b": round(b,1)}
    dl = desc.lower()
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
    return desc, pixel, kws

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 72)
    print("  DREADPIT BATTLE GENERATOR")
    print("  Generates fighters at multiple seeds, analyzes, scores")
    print("  Review output data manually for narration + iteration")
    print("=" * 72)

    # Train NN
    print("\n[1/4] Training NN predictor...")
    X, y = load_data()
    if len(X) == 0:
        print("ERROR: No data"); return
    print(f"  {len(X)} fighters ({int(sum(y))} winners, {int(len(y)-sum(y))} losers)")
    model, mean, std = train_nn(X, y)

    # Cyber God score
    cg_feats = build_features(
        {"warmth":18.6,"red_ratio":0.407,"brightness":65.0,"avg_r":61,"avg_g":49,"avg_b":43},
        {"sword":True,"monster":True,"fire":True}
    )
    cg_score = predict(model, cg_feats, mean, std)
    print(f"\n[2/4] Cyber God NN score: {cg_score:.4f}")

    # Load BLIP
    print(f"\n[3/4] Loading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK")

    # Generate + analyze
    SEEDS = 10
    all_data = {"cyber_god": {"nn_score": cg_score, "stats": CYBER_GOD_STATS}, "fighters": {}}

    for fkey, finfo in FIGHTERS.items():
        print(f"\n  --- {finfo['name']} ---")
        results = []
        for s in range(SEEDS):
            seed = 1000 + (hash(fkey + str(s)) % 9000)
            fname = f"{fkey}_s{seed}.jpg"
            ok = generate(finfo["prompt"], fname, seed)
            if not ok:
                print(f"    [{s+1}/{SEEDS}] seed {seed}: FAILED to generate")
                continue
            fpath = os.path.join(IMAGE_DIR, fname)
            desc, pixel, kws = analyze(fpath, blip_proc, blip_model)
            feats = build_features(pixel, kws)
            score = predict(model, feats, mean, std)
            wins = score > cg_score
            results.append({
                "seed": seed, "blip": desc, "pixel": pixel, "kws": kws,
                "nn_score": score, "margin": score - cg_score,
                "winner": finfo["name"] if wins else "Cyber God",
            })
            wins_so_far = sum(1 for r in results if r["winner"] == finfo["name"])
            # Find top keywords
            active_kws = [kw for kw in KEYWORD_KEYS if kws.get(kw)]
            print(f"    [{s+1}/{SEEDS}] seed={seed} | BLIP: \"{desc[:60]}...\" | warmth={pixel['warmth']} | score={score:.3f} | {'WIN' if wins else 'LOSS'} (margin={score-cg_score:+.3f})")
            if active_kws:
                print(f"           keywords: {', '.join(active_kws[:5])} | {'WIN' if wins else 'LOSS'} vs Cyber God (score={cg_score:.3f})")

        wins = sum(1 for r in results if r["winner"] == finfo["name"])
        total = len(results)
        wr = wins / max(total, 1) * 100
        avg_score = statistics.mean([r["nn_score"] for r in results]) if results else 0
        avg_margin = statistics.mean([r["margin"] for r in results]) if results else 0
        all_data["fighters"][fkey] = {
            "name": finfo["name"], "prompt": finfo["prompt"],
            "total_battles": total, "wins": wins, "losses": total - wins,
            "win_rate_pct": round(wr, 1),
            "avg_nn_score": round(avg_score, 4),
            "avg_margin": round(avg_margin, 4),
            "results": sorted(results, key=lambda r: abs(r["margin"]), reverse=True)
        }
        print(f"\n  >> {finfo['name']}: {wins}W/{total-wins}L = {wr:.0f}% win rate (avg NN score: {avg_score:.4f})")

    # Save
    out_path = os.path.join(CACHE_DIR, "battle_results_raw.json")
    with open(out_path, "w") as f:
        json.dump(all_data, f, indent=2)
    print(f"\n  Raw results saved to: battle_results_raw.json")
    print("  Ready for narration + iteration review.")


if __name__ == "__main__":
    main()
