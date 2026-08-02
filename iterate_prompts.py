"""
DREADPIT PROMPT ITERATOR
Tests prompt variants until all 3 fighters achieve:
  - HIGH consistency (warmth stdev < 10, keyword overlap >= 50%)
  - ≤200 characters
Saves the best variant for each fighter.
"""
import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "iterations")
os.makedirs(OUT_DIR, exist_ok=True)

# Prompt variants to test per fighter (short, visual, comma-separated, ≤200 chars)
PROMPT_VARIANTS = {
    "forge_colossus": [
        {
            "name": "forge_colossus_v1_short",
            "prompt": "Giant walking furnace black iron, white-hot molten core through open chest bars, anvil hammer each hand orange-glowing, flat iron mask orange eye slits, heat waves, no flesh pure forge",
        },
        {
            "name": "forge_colossus_v2_bright",
            "prompt": "Giant furnace walking black iron, white-hot core glowing through chest bars, massive anvil hammers both hands orange, flat iron mask orange eye slits, heat shimmer, pure forge zero flesh",
        },
    ],
    "wrath_infernal": [
        {
            "name": "wrath_infernal_v1_short",
            "prompt": "Demonic winged entity wreathed black orange flames, fiery wings spread wide, obsidian skull burning eyes, horns twisted iron, claws molten rock, body ash ember, wrath made fire",
        },
        {
            "name": "wrath_infernal_v2_concrete",
            "prompt": "Black dragon demon large leathery fiery wings spread wide, skull head orange burning eyes, twisted iron horns, molten rock claws, body ash ember, wreathed orange flames, no text",
        },
    ],
    "vatican_gun": [
        {
            "name": "vatican_gun_v1_short",
            "prompt": "Hooded executioner black leather duster, six-barrel gatling spinning, holy water drums crosses each side, gas mask red eyes, silver bullets bandolier chest, crucifix on gun",
        },
        {
            "name": "vatican_gun_v2_tight",
            "prompt": "Hooded executioner black leather long coat, six-barrel gatling cannon rotating barrels, holy water tanks crosses both sides, gas mask red glowing eyes, silver bullets across chest, crucifix mounted on gun stock",
        },
    ],
}

KEYWORD_KEYS = ["sword","axe_hammer","gun","armor","helmet","human",
                "monster","robot","fire","dark","red","blue","metal",
                "wings","shield","cape"]


def generate(prompt, filename, seed, retries=3):
    fp = os.path.join(OUT_DIR, filename)
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        return True, "cached"
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(fp, "wb") as f:
                    f.write(r.content)
                return True, "OK"
            elif r.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                print(f"      429'd, waiting {wait}s...")
                time.sleep(wait)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5)
    return False, "failed"


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


def test_variant(variant, fkey, blip_proc, blip_model, seeds, verbose=True):
    name = variant["name"]
    prompt = variant["prompt"]
    nchars = len(prompt)
    if verbose:
        print(f"\n  Variant: {name}")
        print(f"  Prompt: {prompt[:100]}...")
        print(f"  Chars: {nchars}")

    seed_data = []
    for s in seeds:
        fname = f"{name}_s{s}.jpg"
        ok, reason = generate(prompt, fname, s)
        if not ok:
            if verbose:
                print(f"    seed {s}: FAILED ({reason})")
            continue
        fpath = os.path.join(OUT_DIR, fname)
        desc, pixel, active_kws = analyze(fpath, blip_proc, blip_model)
        seed_data.append({
            "seed": s, "blip": desc, "pixel": pixel, "active_kws": active_kws,
        })
        if verbose:
            print(f"    seed {s}: BLIP=\"{desc}\"  warmth={pixel['warmth']}  kws={active_kws}")

    if len(seed_data) < 2:
        if verbose:
            print(f"    INSUFFICIENT DATA ({len(seed_data)} seeds)")
        return {"pass": False, "reason": "insufficient_data", "nchars": nchars,
                "seeds": len(seed_data)}

    descs = [d["blip"] for d in seed_data]
    warmths = [d["pixel"]["warmth"] for d in seed_data]
    kw_sets = [set(d["active_kws"]) for d in seed_data]
    shared_kws = set.intersection(*kw_sets) if kw_sets else set()
    all_kws = set.union(*kw_sets) if kw_sets else set()
    warmth_var = statistics.stdev(warmths) if len(warmths) > 1 else 0
    kw_pct = len(shared_kws) / max(len(all_kws), 1) * 100

    passes_length = nchars <= 200
    passes_kw = kw_pct >= 50
    passes_warmth = warmth_var < 10

    result = {
        "pass": passes_length and passes_kw and passes_warmth,
        "nchars": nchars,
        "passes_length": passes_length,
        "passes_kw": passes_kw,
        "passes_warmth": passes_warmth,
        "warmth_mean": round(statistics.mean(warmths), 1),
        "warmth_stdev": round(warmth_var, 1),
        "warmth_range": f"{min(warmths)}-{max(warmths)}",
        "shared_kws": sorted(shared_kws),
        "all_kws": sorted(all_kws),
        "kw_overlap_pct": round(kw_pct, 0),
        "descriptions": descs,
        "seeds": len(seed_data),
    }

    if verbose:
        print(f"    Chars: {nchars}/200 {'PASS' if passes_length else 'FAIL'}")
        print(f"    Warmth stdev: {warmth_var:.1f} {'PASS' if passes_warmth else 'FAIL'} (need <10)")
        print(f"    Kw overlap: {kw_pct:.0f}% {'PASS' if passes_kw else 'FAIL'} (need >=50%)")
        print(f"    RESULT: {'PASS' if result['pass'] else 'FAIL'}")

    return result


def main():
    SEEDS = [42, 777, 2024]
    MAX_ITERATIONS = 5

    print("=" * 72)
    print("  DREADPIT PROMPT ITERATOR")
    print(f"  Target: HIGH consistency + <=200 chars for all 3 fighters")
    print(f"  Max iterations: {MAX_ITERATIONS}")
    print("=" * 72)

    print("\nLoading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    all_passing = {fkey: [] for fkey in PROMPT_VARIANTS}
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"\n{'#' * 72}")
        print(f"#  ITERATION {iteration}")
        print(f"{'#' * 72}")

        remaining = [fkey for fkey in PROMPT_VARIANTS if not all_passing[fkey]]
        if not remaining:
            print("\nAll fighters have passing variants! Done.")
            break

        for fkey in remaining:
            print(f"\n{'=' * 60}")
            print(f"  FIGHTER: {fkey}")
            print(f"{'=' * 60}")

            variants = PROMPT_VARIANTS[fkey]
            best_result = None
            best_idx = -1

            for i, v in enumerate(variants):
                # Skip if this variant already has a short name match in passing
                result = test_variant(v, fkey, blip_proc, blip_model, SEEDS, verbose=True)
                result["prompt"] = v["prompt"]
                result["variant_name"] = v["name"]

                if result["pass"]:
                    best_result = result
                    best_idx = i
                    print(f"\n  >>> {v['name']} PASSED all checks! Saving.")
                    break
                elif best_result is None or (
                    # Track best non-passing as fallback
                    result["warmth_stdev"] < (best_result.get("warmth_stdev", 999) if best_result else 999)
                ):
                    best_result = result
                    best_idx = i

                time.sleep(1)

            if best_result and best_result["pass"]:
                all_passing[fkey] = [{
                    "variant": variants[best_idx],
                    "result": best_result,
                }]
            else:
                print(f"\n  No passing variant found for {fkey}.")
                if best_result:
                    print(f"  Best: {variants[best_idx]['name']} (warmth_stdev={best_result['warmth_stdev']}, kw={best_result['kw_overlap_pct']}%)")
                # Try again with same variants next iteration (Pollinations randomness may help)

    # Final results
    print("\n\n" + "=" * 72)
    print("  FINAL RESULTS")
    print("=" * 72)

    ok = True
    for fkey in PROMPT_VARIANTS:
        passing = all_passing.get(fkey, [])
        if passing:
            v = passing[0]["variant"]
            r = passing[0]["result"]
            print(f"\n  {fkey}: PASS ✅")
            print(f"    Prompt ({r['nchars']} chars): {v['prompt']}")
            print(f"    Warmth stdev: {r['warmth_stdev']}  |  Kw overlap: {r['kw_overlap_pct']}%")
            print(f"    Descriptions: {' | '.join(r['descriptions'])}")
        else:
            ok = False
            print(f"\n  {fkey}: FAIL ❌ - no passing variant")

    if ok:
        print("\n\n  ALL FIGHTERS PASSED! ✅")
    else:
        print("\n\n  SOME FIGHTERS STILL FAILING - more iterations needed")

    # Save
    out_path = os.path.join(CACHE_DIR, "best_prompts.json")
    summary = {}
    for fkey in PROMPT_VARIANTS:
        passing = all_passing.get(fkey, [])
        if passing:
            v = passing[0]["variant"]
            r = passing[0]["result"]
            summary[fkey] = {
                "prompt": v["prompt"],
                "chars": r["nchars"],
                "warmth_stdev": r["warmth_stdev"],
                "kw_overlap_pct": r["kw_overlap_pct"],
                "pass": r["pass"],
            }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nBest prompts saved to: best_prompts.json")


if __name__ == "__main__":
    main()
