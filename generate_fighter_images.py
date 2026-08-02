"""
DREADPIT FIGHTER IMAGE GENERATOR
Uses Pollinations.ai (free, no API key, FLUX model) to generate:
1. Portrait of each fighter
2. Each fighter vs Cyber God

Usage: python generate_fighter_images.py
"""

import requests
import json
import os
import time

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

FIGHTERS = {
    "forge_colossus": {
        "name": "Forge Colossus",
        "prompt": "Black iron furnace giant. Chest bars open to white-hot molten core. Each hand drags an anvil-headed hammer glowing orange. Shoulder coal cannon. Flat iron mask with orange eye slits. No skin. No dragon. No god. Just forge.",
        "battle_prompt": "Massive black iron furnace giant fighting a demonic armored god riding a cyber dragon. The forge giant's anvil hammer smashes into the dragon. Sparks and molten metal flying. Epic battle destruction fantasy art.",
    },
    "the_hook": {
        "name": "The Hook",
        "prompt": "Gaunt hunter draped in monster pelts. Hooked chain between both hands. Backpack holds severed dragon claws protruding over head. Scarred face with one glowing eye. Iron hook replaces one hand. No armor. Only trophies.",
        "battle_prompt": "Gaunt monster hunter with hooked chain fighting an armored god riding a cyber dragon. The hunter's hook grabs the dragon's neck, pulling the god off. Dragon claws on backpack. Epic battle fantasy art.",
    },
    "vatican_gun": {
        "name": "Vatican Gun",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel rotary cannon with holy water drums. Belt of exorcised silver bullets. Crucifix bolted to cannon stock. Gas mask with red lenses. No armor.",
        "battle_prompt": "Hooded executioner with massive rotary cannon firing holy water bullets at an armored god riding a cyber dragon. Crucifix on cannon. Smoke and light beams. Religious war in hell. Epic fantasy art.",
    },
}


def generate_image(prompt: str, filename: str) -> bool:
    """Generate an image using Pollinations.ai free API."""
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"  [SKIP] {filename} already exists")
        return True

    print(f"  Generating {filename}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"OK ({len(r.content)} bytes)")
            return True
        else:
            print(f"FAIL (status={r.status_code}, size={len(r.content)})")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = {"portraits": {}, "battles": {}}

    print("=" * 60)
    print("DREADPIT FIGHTER IMAGE GENERATOR")
    print("=" * 60)

    # Phase 1: Generate fighter portraits
    print("\n--- PHASE 1: Fighter Portraits ---")
    for key, fighter in FIGHTERS.items():
        print(f"\n[{fighter['name']}]")
        fname = f"{key}_portrait.jpg"
        ok = generate_image(fighter["prompt"], fname)
        results["portraits"][key] = {"prompt": fighter["prompt"], "file": fname, "success": ok}
        time.sleep(2)  # Rate limit

    # Phase 2: Generate battle scenes
    print("\n--- PHASE 2: Battle Scenes vs Cyber God ---")
    for key, fighter in FIGHTERS.items():
        print(f"\n[{fighter['name']} vs Cyber God]")
        fname = f"{key}_vs_cybergod.jpg"
        ok = generate_image(fighter["battle_prompt"], fname)
        results["battles"][key] = {"prompt": fighter["battle_prompt"], "file": fname, "success": ok}
        time.sleep(2)  # Rate limit

    # Save report
    report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    successes = sum(1 for v in results["portraits"].values() if v["success"])
    successes += sum(1 for v in results["battles"].values() if v["success"])
    total = len(results["portraits"]) + len(results["battles"])
    print(f"Generated {successes}/{total} images successfully")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
