#!/usr/bin/env python3
"""
NEW ARCHETYPE CONSISTENCY TEST

Tests 5 uncovered archetype prompts (undead/skeleton, ice/frost, egyptian/anubis,
mirror/glass, nature/fungal) through Pollinations FLUX with 3 seeds each,
evaluating BLIP description consistency + warmth + keyword retention.

Goal: which uncovered archetypes can FLUX render CONSISTENTLY?
"""
import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "new_archetypes")
os.makedirs(OUT_DIR, exist_ok=True)

# Candidate archetypes: each with 2 prompt variants (short, visual, <=200 chars)
# target_kws = BLIP words proving the archetype RENDERED (not just color consistency)
CANDIDATES = {
    "undead_skeleton_lich": {
        "icon": "[B]",
        "why": "Never truly seen: 'Undead archmage' is a cartoon dino rider; no real skeleton/lich in arena. Gemini knows lich = necromancy, can't-die, soul magic.",
        "target_kws": ["skeleton", "bone", "skull", "undead", "lich", "death", "corpse"],
        "variants": [
            "Ancient lich king, white bone skeleton body, tattered royal purple robe, golden crown, green soul flames in eye sockets, bone staff with skull, green necrotic aura",
            "Skeleton death god, polished white bone armor, glowing green eye sockets, black royal crown, bone scythe, tattered dark cloak, green soul fire around body",
        ],
    },
    "ice_frost_titan": {
        "icon": "[~]",
        "why": "No true ice/frost fighter with 5+ wins. Frost Void Wraith (5w) renders as a hooded knife-man, not ice. Polar opposite of the fire meta.",
        "target_kws": ["ice", "frost", "glacier", "snow", "frozen", "cold"],
        "variants": [
            "Frost titan of living glacier ice, cracked frozen blue armor, ice crystal shards floating, pale blue glow, frozen crown, glacier greatsword of solid ice",
            "Ice golem colossus, translucent blue frozen body, frost spikes on shoulders, cold mist aura, glowing pale blue core chest, jagged ice sword hand",
        ],
    },
    "egyptian_anubis": {
        "icon": "[J]",
        "why": "ZERO egyptian/anubis/mummy fighters in 348. Dense archetype (like Tigran) - Gemini fills in death magic, judgment, soul-weighing.",
        "target_kws": ["dog", "jackal", "anubis", "egypt", "pharaoh", "head"],
        "variants": [
            "Black jackal-headed god, golden armor, pharaoh collar, long staff with ankh tip, burning scale hanging from belt, one pan blue flame, wraith cloak",
            "Anubis death god, jackal head, black and gold armor, was-scepter staff, glowing blue scale of judgment in left hand, dark sand aura, standing calm",
        ],
    },
    "mirror_glass_entity": {
        "icon": "[M]",
        "why": "No mirror/glass fighter. Dirumath 'Mirrored Anguish' is actually a blue dragon. Abstract but high curiosity value.",
        "target_kws": ["mirror", "glass", "reflect", "shard", "prism"],
        "variants": [
            "Entity of living mirror glass, body of reflective silver shards, fractured mirror face, light refracting rainbow, floating glass shards orbit, silver white",
            "Glass golem, body made of cracked mirrors, reflections on every surface, jagged glass claw hands, prismatic light shards floating around, pale silver",
        ],
    },
    "nature_fungal": {
        "icon": "[F]",
        "why": "Nature/plant/fungus never proven. 'Rotting Carrier' (3w) is closest. Fungal horror is esoteric + distinct from fire meta.",
        "target_kws": ["mushroom", "fungus", "moss", "plant", "tree", "rot"],
        "variants": [
            "Fungal plague titan, giant mushroom crown, orange spotted cap, spore cloud aura, moss covered body, glowing green spores, vine wrapped arms, rotting wood",
            "Forest rot god, ancient tree body, giant glowing mushroom cap head, glowing green spores drifting, roots for legs, moss and fungus covering, dark wood",
        ],
    },
}


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
    return desc, pixel


def main():
    SEEDS = [42, 777, 2024]
    print("=" * 72)
    print("  NEW ARCHETYPE CONSISTENCY TEST (5 uncovered archetypes)")
    print("=" * 72)

    print("\nLoading BLIP...")
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    # Allow running only specific archetypes: python test_new_archetypes.py undead_skeleton_lich ice_frost_titan
    only = sys.argv[1:] if len(sys.argv) > 1 else None

    results = {}
    for key, cand in CANDIDATES.items():
        if only and key not in only:
            continue
        print("=" * 72)
        print(f"  {cand['icon']} ARCHETYPE: {key}")
        print(f"  WHY: {cand['why']}")
        print("=" * 72)

        arch_results = []
        for vi, prompt in enumerate(cand["variants"], 1):
            print(f"\n  Variant {vi} ({len(prompt)} chars): {prompt[:90]}...")
            seed_data = []
            for s in SEEDS:
                fname = f"{key}_v{vi}_s{s}.jpg"
                ok, reason = generate(prompt, fname, s)
                if not ok:
                    print(f"    seed {s}: FAILED ({reason})")
                    continue
                fpath = os.path.join(OUT_DIR, fname)
                desc, pixel = analyze(fpath, blip_proc, blip_model)
                seed_data.append({"seed": s, "blip": desc, "pixel": pixel})
                print(f"    seed {s}: \"{desc}\"  warmth={pixel['warmth']}")

            if len(seed_data) >= 2:
                descs = [d["blip"] for d in seed_data]
                warmths = [d["pixel"]["warmth"] for d in seed_data]
                warmth_stdev = statistics.stdev(warmths) if len(warmths) > 1 else 0
                # ARCHETYPE VERIFICATION: did the intended concept actually render?
                tk = cand["target_kws"]
                hit_seeds = [d for d in seed_data if any(w in d["blip"].lower() for w in tk)]
                arch_pct = round(len(hit_seeds) / len(seed_data) * 100)
                arch_results.append({
                    "variant": vi,
                    "prompt": prompt,
                    "chars": len(prompt),
                    "descriptions": descs,
                    "warmth_mean": round(statistics.mean(warmths), 1),
                    "warmth_stdev": round(warmth_stdev, 1),
                    "warmth_range": f"{min(warmths)}-{max(warmths)}",
                    "target_kws": tk,
                    "arch_render_pct": arch_pct,
                    "arch_rendered": arch_pct >= 67,  # >=2 of 3 seeds
                })
                print(f"    -> warmth mean={statistics.mean(warmths):.1f} stdev={warmth_stdev:.1f}  "
                      f"ARCHETYPE rendered in {len(hit_seeds)}/{len(seed_data)} seeds "
                      f"({'PASS' if arch_pct >= 67 else 'FAIL'})")
            else:
                print(f"    INSUFFICIENT seeds for variant {vi}")
            time.sleep(1)

        results[key] = {
            "why": cand["why"],
            "variants": arch_results,
            # Prefer a variant that RENDERED the archetype; only fall back to
            # lowest color-stdev when none rendered.
            "best": (min([v for v in arch_results if v["arch_rendered"]],
                          key=lambda v: v["warmth_stdev"])
                     if any(v["arch_rendered"] for v in arch_results)
                     else (min(arch_results, key=lambda v: v["warmth_stdev"])
                           if arch_results else None)),
        }
        print()

    # Summary
    print("\n\n" + "=" * 72)
    print("  CONSISTENCY SUMMARY (lowest warmth_stdev variant per archetype)")
    print("=" * 72)
    for key, res in results.items():
        best = res["best"]
        if not best:
            print(f"\n  {CANDIDATES[key]['icon']} {key}: NO DATA")
            continue
        verdict = "RENDERABLE" if best["arch_rendered"] else "NOT CONSISTENT"
        print(f"\n  {CANDIDATES[key]['icon']} {key}  [{verdict}]")
        print(f"    Best variant: {best['variant']} ({best['chars']} chars)")
        print(f"    Warmth: {best['warmth_mean']} (stdev {best['warmth_stdev']})  "
              f"Archetype in {best['arch_render_pct']}% of seeds")
        for d in best["descriptions"]:
            print(f"      - \"{d}\"")

    out_path = os.path.join(CACHE_DIR, "new_archetype_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
