#!/usr/bin/env python3
"""
DREADPIT TEST FIGHTER BATTERY GENERATOR

Generates all probe fighters from test_battery_design.md through FLUX
(3 seeds each), evaluates each render with BLIP + pixel fingerprint
(same pipeline as the NN training data), and saves everything to
test_battery_results.json.

Usage:
  python test_battery_generator.py            # all 30 fighters (12 probes + 8 refinements + 10 wild)
  python test_battery_generator.py A B        # only categories A and B
  python test_battery_generator.py A2 G5      # specific fighters
"""
import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CACHE_DIR, "test_battery")
os.makedirs(OUT_DIR, exist_ok=True)

# Fighter definitions: id -> (name, prompt). Source: test_battery_design.md
# NOTE: 10 probes were cut because their archetypes are ALREADY COVERED:
#   A1 white glowing -> Relentless angel | A3 magma -> Ragnaros
#   A4 void -> Eldritch (bot) | B1 full plate -> done | B2 berserker -> done
#   B4 blue energy -> done | C3 ethereal -> countered by brute force
#   D1 colossal -> PINNED (hard to gen; Dreadpit dragon is one) | D3 abstract -> done
#   D4 blob -> acid slime
BATTERY = {
    # A - Color extremes
    "A2": ("Crystal Ice Elemental", "Crystal ice elemental, deep cold blue body, transparent frozen core, pale blue glow, frozen ground, no fire"),
    # B - Keyword gaps
    "B3": ("Tower Shield Guardian", "Guardian holding enormous tower shield, full body hidden behind shield, steel rim, standing firm"),
    "B5": ("Flowing Crimson Cape", "Warrior in flowing crimson cape, cape billowing in wind, long cloth, dramatic stance"),
    # C - Uncovered archetypes
    "C1": ("Water Titan", "Titan made of rushing water, transparent body, waves for arms, tide form, deep sea blue, wet glow"),
    "C2": ("Mirror Being", "Being made of mirrored glass, reflective silver surface, faceted body, refracting light"),
    "C4": ("Forest Titan", "Ancient forest titan, living tree body, bark armor, leaf mane, vine arms, moss covered"),
    "C5": ("Mummy Lord", "Ancient mummy lord, white linen wrappings, gold ornaments, glowing eyes through bandages, dark ritual"),
    # D - Form/scale extremes
    "D2": ("Tiny Fairy", "Tiny fairy creature, small as a hand, delicate wings, glowing softly, giant blades of grass around"),
    # E - Durability paradox
    "E1": ("Seamless Armor", "Smooth seamless armor, single piece of polished metal, no joints visible, perfectly smooth surface"),
    "E2": ("Hex-Minimal Operative", "Slim man in dark grey suit, full helmet, faint purple visor glow, subtle tech, standing in darkness"),
    # F - Composition controls
    "F1": ("Profile Warrior", "Warrior standing in side profile, facing right, silhouette clear, neutral stance"),
    "F2": ("Arena Background Warrior", "Powerful warrior in glowing arena, dramatic environment, crowd shadows, dramatic lighting"),
    # v2 - REFINED probes (first pass rendered as inert objects / missed theme)
    "C1v2": ("Water Giant v2", "Colossal humanoid water giant, body made of rushing translucent water, muscular water arms and torso, waves for shoulders, deep sea blue, standing upright, looming pose"),
    "C4v2": ("Marsh Forest Titan v2", "Ancient forest titan, living tree body, bark hard as stone, thick wet moss armor dripping water, leaf mane, vine arms, fireproof, stands in rain"),
    "C2v2": ("Mirror Golem v2", "Humanoid being made of mirrored glass, man-shaped body, faceted silver mirror surface, arms and legs, reflecting light, standing pose"),
    "C5v2": ("Mummy Warrior v2", "Mummy warrior wrapped head to toe in tan linen bandages, arms crossed, glowing eyes, gold amulet, dark tomb background"),
    "E1v2": ("Seamless Knight v2", "Knight in single seamless suit of polished silver armor, no joints, no seams, mirror smooth surface, faceless helmet, standing tall"),
    "B3v2": ("Pure Shield Guardian v2", "Guardian holding enormous steel tower shield, full body hidden behind shield taller than him, steel rim, standing firm"),
    # v3 - SECOND refinement pass (v2 still failed: mummy read as white dress, shield summoned sword)
    "C5v3": ("Undead Mummy v3", "Undead mummy warrior, shriveled grey corpse skin, bandaged arms and legs, glowing green eyes, gold amulet on chest, ancient tomb"),
    "B3v3": ("Living Shield Being v3", "Giant living tower shield, single massive steel shield as whole body, small glowing eyes on shield face, steel rim, standing upright, battle-scarred"),
    # G - WILD BATCH (never-seen archetypes + body-plan subversion + judge psychology)
    # Design rules (see LESSONS_LEARNED.md): cannot BE architecture (must be
    # 'X-shaped elemental'); hollow/phantom needs flight for ranged; open pose
    # not crossed arms; shadows lose to tentacles.
    "G1": ("The Crow-Wall", "Giant humanoid made of thousands of black crows, wings beating as one, red eyes scattered through the mass, feathers swirling, huge crow-formed figure"),
    "G2": ("The Cathedral Elemental", "Cathedral-shaped stone elemental, gothic cathedral form, stained glass windows glowing in stone body, bell tower head, gargoyle shoulders, ancient carved stone, walking forward"),
    "G3": ("The Salt Colossus", "Colossal being made of white salt crystals, rough crystalline body, glowing salt veins, huge arms, mineral dust drifting off, standing in desert"),
    "G4": ("The Hollow", "Empty knight armor levitating high in dark air, nothing inside, helmet tilted, gauntlets open, polished black steel, faint blue glow from within, hovering motionless"),
    "G5": ("The Already-Won", "Armored warrior standing relaxed, arms spread open, open gauntlets, palms up inviting gesture, no weapons drawn, calm expression, ancient heavy armor, dramatic spotlight"),
    "G6": ("The Solid Shadow", "Solid black shadow being, glossy obsidian surface, humanoid shape, light bending around it, no face, extremely dark, standing on glowing ground"),
    "G7": ("The Grasp", "Giant humanoid made entirely of interlocked hands, hundreds of pale hands forming arms and torso, fingers grasping, moving as one"),
    "G8": ("The Inverted", "Pale humanoid walking upside down on its hands, legs folded up into a crown of blades above, bloodless white skin, dark veins, inverted stance"),
    "G9": ("The Mask-Pillar", "Towering pillar of ancient masks stacked high, each mask slightly different, glowing eyes in every mask, writhing cloth between them, tall as a building"),
    "G10": ("The Unseen Door", "Black void portal standing upright, human-sized, edges crackling with violet energy, tendrils of nothing reaching out, floating in dark air"),
}

SEEDS = [42, 777, 2024]
FORCE = "--force" in sys.argv
if FORCE:
    sys.argv.remove("--force")
KEYWORD_KEYS = ["sword","axe_hammer","gun","armor","helmet","human","monster",
                "robot","fire","dark","red","blue","metal","wings","shield","cape"]


def generate(prompt, filename, seed, retries=3):
    fp = os.path.join(OUT_DIR, filename)
    if not FORCE and os.path.exists(fp) and os.path.getsize(fp) > 1000:
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
    n = len(px)
    r = sum(p[0] for p in px) / n
    g = sum(p[1] for p in px) / n
    b = sum(p[2] for p in px) / n
    pixel = {
        "brightness": round((r + g + b) / 3, 1),
        "warmth": round(r - b, 1),
        "red_ratio": round(r / max(r + g + b, 1), 3),
        "avg_r": round(r, 1), "avg_g": round(g, 1), "avg_b": round(b, 1),
    }
    dl = desc.lower()
    kws = {
        "sword": "sword" in dl or "blade" in dl,
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
    active = [k for k, v in kws.items() if v]
    return desc, pixel, active


def main():
    # Select fighters from CLI args (category or id)
    args = sys.argv[1:]
    if args:
        wanted = set()
        for a in args:
            if len(a) == 1:
                wanted.update(k for k in BATTERY if k.startswith(a))
            elif a in BATTERY:
                wanted.add(a)
        selected = {k: v for k, v in BATTERY.items() if k in wanted}
    else:
        selected = BATTERY

    if not selected:
        print("ERROR: No fighters matched your arguments.")
        print(f"Valid categories: {sorted(set(k[0] for k in BATTERY))}")
        print(f"Valid IDs: {sorted(BATTERY)}")
        sys.exit(1)

    print("=" * 72, flush=True)
    print("  DREADPIT TEST FIGHTER BATTERY GENERATOR", flush=True)
    print(f"  {len(selected)} fighters x {len(SEEDS)} seeds", flush=True)
    print("=" * 72, flush=True)

    print("\nLoading BLIP...", flush=True)
    blip_proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    print("  OK\n")

    results = {}
    for i, (fid, (name, prompt)) in enumerate(sorted(selected.items()), 1):
        print("\n" + "=" * 60, flush=True)
        print(f"  [{i}/{len(selected)}] GENERATING {fid}: {name} ({len(prompt)} chars)", flush=True)
        print(f"  Prompt: {prompt}", flush=True)
        print("=" * 60, flush=True)
        seeds_out = []
        for s in SEEDS:
            fname = f"{fid}_s{s}.jpg"
            ok, reason = generate(prompt, fname, s)
            if not ok:
                print(f"    seed {s}: FAILED ({reason})", flush=True)
                continue
            fp = os.path.join(OUT_DIR, fname)
            desc, pixel, active = analyze(fp, blip_proc, blip_model)
            seeds_out.append({"seed": s, "blip": desc, "pixel": pixel, "kws": active})
            desc_safe = desc.encode("ascii", "replace").decode()
            print(f"    seed {s}: \"{desc_safe}\"  W={pixel['warmth']:+6.1f} B={pixel['brightness']:5.1f} {active}", flush=True)
            time.sleep(0.5)
        print(f"  DONE {fid}: {len(seeds_out)}/{len(SEEDS)} seeds rendered", flush=True)

        # Aggregate
        if len(seeds_out) >= 2:
            descs = [d["blip"] for d in seeds_out]
            warmths = [d["pixel"]["warmth"] for d in seeds_out]
            brights = [d["pixel"]["brightness"] for d in seeds_out]
            kw_sets = [set(d["kws"]) for d in seeds_out]
            shared = set.intersection(*kw_sets) if kw_sets else set()
            all_kws = set.union(*kw_sets) if kw_sets else set()
            results[fid] = {
                "name": name,
                "prompt": prompt,
                "chars": len(prompt),
                "category": fid[0],
                "seeds": seeds_out,
                "summary": {
                    "warmth_mean": round(statistics.mean(warmths), 1),
                    "warmth_stdev": round(statistics.stdev(warmths), 1) if len(warmths) > 1 else 0,
                    "brightness_mean": round(statistics.mean(brights), 1),
                    "shared_kws": sorted(shared),
                    "kw_overlap_pct": round(len(shared) / max(len(all_kws), 1) * 100),
                    "descriptions": descs,
                },
            }
            print(f"\n    -> warmth={results[fid]['summary']['warmth_mean']} "
                  f"stdev={results[fid]['summary']['warmth_stdev']} "
                  f"kw_shared={sorted(shared)}", flush=True)
        else:
            results[fid] = {"name": name, "prompt": prompt, "seeds": seeds_out, "summary": None}
        print()

    out_path = os.path.join(CACHE_DIR, "test_battery_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}", flush=True)
    print(f"Completed: {len(results)}/{len(selected)} fighters with data", flush=True)


if __name__ == "__main__":
    main()
