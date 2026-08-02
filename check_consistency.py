"""
DREADPIT CONSISTENCY CHECKER
Generates each fighter at 3 seeds, analyzes with BLIP,
reports per-fighter consistency metrics.
"""
import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "consistency_check")
os.makedirs(OUT_DIR, exist_ok=True)

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

def generate(prompt, filename, seed):
    fp = os.path.join(OUT_DIR, filename)
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(fp, "wb") as f:
                    f.write(r.content)
                return True, "OK"
            elif r.status_code == 429:
                return False, f"429 (rate limited, attempt {attempt+1})"
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
    return False, "Failed after 3 attempts"

KEYWORD_KEYS = ["sword","axe_hammer","gun","armor","helmet","human",
                "monster","robot","fire","dark","red","blue","metal",
                "wings","shield","cape"]

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
    pixel = {
        "brightness": round((r+g+b)/3, 1),
        "warmth": round(r-b, 1),
        "red_ratio": round(r/max(r+g+b, 1), 3),
        "avg_r": round(r, 1), "avg_g": round(g, 1), "avg_b": round(b, 1),
    }
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
    active_kws = [kw for kw, v in kws.items() if v]
    return desc, pixel, kws, active_kws


def main():
    print("=" * 72)
    print("  CONSISTENCY CHECK: 3 seeds per fighter")
    print("=" * 72)

    print("\nLoading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    SEEDS = [42, 777, 2024]
    results = {}

    for fkey, finfo in FIGHTERS.items():
        print(f"--- {finfo['name']} ---")
        print(f'Prompt: {finfo["prompt"][:80]}...')
        print(f'Length: {len(finfo["prompt"])} chars')

        seed_data = []
        for s in SEEDS:
            fname = f"{fkey}_seed{s}.jpg"
            ok, reason = generate(finfo["prompt"], fname, s)
            if not ok:
                print(f"  seed {s}: FAILED - {reason}")
                continue
            fpath = os.path.join(OUT_DIR, fname)
            desc, pixel, kws, active_kws = analyze(fpath, blip_proc, blip_model)
            seed_data.append({
                "seed": s, "blip": desc, "pixel": pixel,
                "active_kws": active_kws,
            })
            print(f"  seed {s}: BLIP=\"{desc}\"  warmth={pixel['warmth']}  kws={active_kws}")

        results[fkey] = seed_data

        if len(seed_data) >= 2:
            # Consistency metrics
            descs = [d["blip"] for d in seed_data]
            warmths = [d["pixel"]["warmth"] for d in seed_data]
            kw_sets = [set(d["active_kws"]) for d in seed_data]
            shared_kws = set.intersection(*kw_sets) if kw_sets else set()
            all_kws = set.union(*kw_sets) if kw_sets else set()
            warmth_var = statistics.stdev(warmths) if len(warmths) > 1 else 0

            print(f"\n  CONSISTENCY:")
            print(f"    Descriptions: {' | '.join(descs)}")
            print(f"    Warmth range: {min(warmths)} - {max(warmths)} (stdev={warmth_var:.1f})")
            print(f"    Shared keywords ({len(shared_kws)}/{len(all_kws)}): {sorted(shared_kws) if shared_kws else '(none)'}")
            rating = "HIGH" if (warmth_var < 10 and len(shared_kws) >= len(all_kws) * 0.5) else \
                     "MEDIUM" if warmth_var < 20 else "LOW"
            print(f"    Consistency: {rating} (target: HIGH)\n")
        else:
            print(f"  Only {len(seed_data)} seed(s) generated - not enough for variance check\n")

        time.sleep(2)

    # Summary table
    print("\n" + "=" * 72)
    print("  CONSISTENCY RESULTS SUMMARY")
    print("=" * 72)
    print(f"\n  {'Fighter':<20} {'Seeds':<6} {'Prompt Chars':<14} {'Warmth Range':<14} {'Consistency'}")
    print(f"  {'-'*20} {'-'*6} {'-'*14} {'-'*14} {'-'*12}")

    for fkey, finfo in FIGHTERS.items():
        sd = results.get(fkey, [])
        n = len(sd)
        if n > 0:
            w = [d["pixel"]["warmth"] for d in sd]
            wr = f"{min(w)}-{max(w)}"
            warmths = [d["pixel"]["warmth"] for d in sd]
            warmth_var = statistics.stdev(warmths) if len(warmths) > 1 else 0
            kw_sets = [set(d["active_kws"]) for d in sd]
            shared_kws = set.intersection(*kw_sets) if kw_sets else set()
            all_kws = set.union(*kw_sets) if kw_sets else set()
            pct = len(shared_kws) / max(len(all_kws), 1) * 100
            rating = "HIGH" if (warmth_var < 10 and pct >= 50) else \
                     "MEDIUM" if warmth_var < 20 else "LOW"
        else:
            wr, rating = "N/A", "FAILED"
        print(f"  {finfo['name']:<20} {n}/{len(SEEDS):<6} {len(finfo['prompt']):<14} {wr:<14} {rating}")

    # Save
    out_path = os.path.join(CACHE_DIR, "consistency_report.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to: consistency_report.json")


if __name__ == "__main__":
    main()
