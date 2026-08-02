"""
Analyze cached iteration images — BLIP analysis only, no generation needed.
Reports per-variant consistency and finds the best prompt for each fighter.
"""
import json, os, statistics
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
ITER_DIR = os.path.join(CACHE_DIR, "iterations")

KEYWORD_KEYS = ["sword","axe_hammer","gun","armor","helmet","human",
                "monster","robot","fire","dark","red","blue","metal",
                "wings","shield","cape"]

FIGHTER_VARIANTS = {
    "forge_colossus": {
        "v1_short": "Giant walking furnace black iron, white-hot molten core through open chest bars, anvil hammer each hand orange-glowing, flat iron mask orange eye slits, heat waves, no flesh pure forge",
        "v2_bright": "Giant furnace walking black iron, white-hot core glowing through chest bars, massive anvil hammers both hands orange, flat iron mask orange eye slits, heat shimmer, pure forge zero flesh",
    },
    "wrath_infernal": {
        "v1_short": "Demonic winged entity wreathed black orange flames, fiery wings spread wide, obsidian skull burning eyes, horns twisted iron, claws molten rock, body ash ember, wrath made fire",
        "v2_concrete": "Black dragon demon large leathery fiery wings spread wide, skull head orange burning eyes, twisted iron horns, molten rock claws, body ash ember, wreathed orange flames, no text",
    },
    "vatican_gun": {
        "v1_short": "Hooded executioner black leather duster, six-barrel gatling spinning, holy water drums crosses each side, gas mask red eyes, silver bullets bandolier chest, crucifix on gun",
        "v2_tight": "Hooded executioner black leather long coat, six-barrel gatling cannon rotating barrels, holy water tanks crosses both sides, gas mask red glowing eyes, silver bullets across chest, crucifix mounted on gun stock",
    },
}

SEEDS = [42, 777, 2024]


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
    return desc, pixel, active_kws


def score_variant(seed_data):
    """Score a variant's consistency. Returns (passes_bool, metrics_dict)."""
    if len(seed_data) < 2:
        return False, {"reason": f"only {len(seed_data)} seeds"}

    descs = [d["blip"] for d in seed_data]
    warmths = [d["pixel"]["warmth"] for d in seed_data]
    kw_sets = [set(d["active_kws"]) for d in seed_data]
    shared_kws = set.intersection(*kw_sets) if kw_sets else set()
    all_kws = set.union(*kw_sets) if kw_sets else set()
    warmth_var = statistics.stdev(warmths) if len(warmths) > 1 else 0
    kw_pct = len(shared_kws) / max(len(all_kws), 1) * 100

    passes = warmth_var < 10 and kw_pct >= 50
    return passes, {
        "descriptions": descs,
        "warmth_mean": round(statistics.mean(warmths), 1),
        "warmth_stdev": round(warmth_var, 1),
        "warmth_range": f"{min(warmths)}-{max(warmths)}",
        "shared_kws": sorted(shared_kws),
        "all_kws": sorted(all_kws),
        "kw_overlap_pct": round(kw_pct, 0),
        "passes_warmth": warmth_var < 10,
        "passes_kw": kw_pct >= 50,
        "n_seeds": len(seed_data),
    }


def main():
    print("=" * 72)
    print("  ANALYZING CACHED ITERATION IMAGES")
    print("=" * 72)

    print("\nLoading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    results = {}

    for fkey, variants in FIGHTER_VARIANTS.items():
        print(f"\n{'=' * 60}")
        print(f"  {fkey.upper()}")
        print(f"{'=' * 60}")

        best_variant = None
        best_score = None
        best_metrics = None

        for vname, prompt in variants.items():
            nchars = len(prompt)
            print(f"\n  --- {vname} ({nchars} chars) ---")
            print(f"  Prompt: {prompt[:100]}...")

            seed_data = []
            for s in SEEDS:
                fname = f"{fkey}_{vname}_s{s}.jpg"
                fpath = os.path.join(ITER_DIR, fname)
                if not os.path.exists(fpath):
                    print(f"    seed {s}: FILE NOT FOUND")
                    continue
                desc, pixel, active_kws = analyze(fpath, blip_proc, blip_model)
                seed_data.append({
                    "seed": s, "blip": desc, "pixel": pixel, "active_kws": active_kws,
                })
                print(f"    seed {s}: BLIP=\"{desc}\"  warmth={pixel['warmth']}  kws={active_kws}")

            passes_length = nchars <= 200
            passes, metrics = score_variant(seed_data)

            overall = passes and passes_length
            metrics["nchars"] = nchars
            metrics["passes_length"] = passes_length
            metrics["overall_pass"] = overall

            print(f"    Chars: {nchars}/200 {'PASS' if passes_length else 'FAIL'}")
            if passes:
                print(f"    Warmth stdev: {metrics['warmth_stdev']} PASS | Kw overlap: {metrics['kw_overlap_pct']}% PASS")
                print(f"    >>> OVERALL: PASS ✅")
            else:
                fails = []
                if not metrics.get("passes_warmth", False):
                    fails.append(f"warmth_stdev={metrics.get('warmth_stdev', 'N/A')} (need <10)")
                if not metrics.get("passes_kw", False):
                    fails.append(f"kw_overlap={metrics.get('kw_overlap_pct', 'N/A')}% (need >=50%)")
                if not passes_length:
                    fails.append(f"chars={nchars} (need <=200)")
                print(f"    FAILS: {'; '.join(fails)}")
                print(f"    >>> OVERALL: FAIL ❌")

            if overall and (best_score is None or metrics["warmth_stdev"] < best_score):
                best_variant = vname
                best_score = metrics["warmth_stdev"]
                best_metrics = metrics

        results[fkey] = {
            "best_variant": best_variant,
            "best_prompt": variants.get(best_variant, ""),
            "best_metrics": best_metrics,
        }

        if best_variant:
            print(f"\n  >>> BEST: {best_variant} (stdev={best_metrics['warmth_stdev']}, chars={best_metrics['nchars']})")
        else:
            print(f"\n  >>> NO PASSING VARIANT")

    # Final summary
    print("\n\n" + "=" * 72)
    print("  FINAL VERDICT")
    print("=" * 72)

    all_pass = True
    for fkey, r in results.items():
        if r["best_variant"]:
            m = r["best_metrics"]
            print(f"\n  {fkey}: PASS ✅")
            print(f"    Prompt ({m['nchars']} chars): {r['best_prompt'][:120]}...")
            print(f"    Warmth stdev: {m['warmth_stdev']} | Kw overlap: {m['kw_overlap_pct']}%")
            print(f"    Descriptions: {' | '.join(m['descriptions'])}")
        else:
            print(f"\n  {fkey}: FAIL ❌")
            all_pass = False

    if all_pass:
        print("\n  ALL THREE PASS! ✅")
    else:
        print("\n  SOME FAILURES — need another iteration")

    # Save results
    out_path = os.path.join(CACHE_DIR, "iteration_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: iteration_results.json")


if __name__ == "__main__":
    main()
