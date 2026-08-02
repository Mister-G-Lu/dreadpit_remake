"""
DREADPIT FIGHTER IMAGE GENERATOR v2
Iterated prompts based on BLIP evaluation feedback.

Key fixes:
- Forge Colossus: Was turning into a human in a suit. Now explicitly says "no skin no face no organs, walking furnace"
- The Hook: Was turning into a generic "horns" character. Now front-loads the weapon.
- Vatican Gun: Was decent but missed rotary cannon details. Now emphasizes "six barrels."
- All use ?model=flux for better quality
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

# v2 prompts — iterated based on what BLIP revealed
FIGHTERS_V2 = {
    "forge_colossus": {
        "name": "Forge Colossus v2",
        "prompt": "Walking furnace construct made of black iron. No skin no face no organs. Chest bars open to white-hot molten core. Each hand drags a giant anvil-headed hammer glowing red. Coal cannon on shoulder. Flat iron mask with orange slits.",
    },
    "the_hook": {
        "name": "The Hook v2",
        "prompt": "Monster hunter wielding a massive iron hook on a heavy chain. The hook weapon is barbed and oversized, clearly not a tool but a weapon. Gaunt face scarred, one glowing eye. Draped in grey monster pelts. Iron hook hand. No armor.",
    },
    "vatican_gun": {
        "name": "Vatican Gun v2",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel rotary cannon, each barrel visible. Holy water drums strapped to the cannon sides marked with crosses. Gas mask with glowing red lenses. Crucifix on gun stock. Silver bullet bandolier.",
    },
}

# Battle scenes — iterated
BATTLES_V2 = {
    "forge_colossus": {
        "name": "Forge Colossus vs Cyber God v2",
        "prompt": "A massive iron walking furnace giant swings an anvil hammer at an armored god riding a cyber dragon. The dragon breathes fire. Molten metal flying everywhere. Epic fantasy battle destruction. Dark sky with orange glow.",
    },
    "the_hook": {
        "name": "The Hook vs Cyber God v2",
        "prompt": "A scarred monster hunter throws a giant hooked chain at an armored god riding a cyber dragon. The hook wraps around the dragon's neck. Hunter pulls. Dragon claws protrude from hunter's backpack. Epic fantasy confrontation.",
    },
    "vatican_gun": {
        "name": "Vatican Gun vs Cyber God v2",
        "prompt": "A hooded executioner in black leather fires a massive six-barrel rotary cannon at an armored god on a cyber dragon. The cannon has a crucifix on it. Holy water and light beams pierce through dark clouds. Epic religious fantasy battle.",
    },
}


def generate_image(prompt: str, filename: str, seed: int = None) -> bool:
    """Generate an image using Pollinations.ai with FLUX model."""
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&width=1024&height=1024"
    if seed is not None:
        url += f"&seed={seed}"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"  [SKIP] {filename} already exists")
        return True

    print(f"  Generating {filename}...", end=" ", flush=True)
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(r.content)
                print(f"OK ({len(r.content)} bytes)")
                return True
            else:
                print(f"attempt {attempt+1} failed (status={r.status_code}, size={len(r.content)})", end=" ")
        except Exception as e:
            print(f"attempt {attempt+1} error: {e}", end=" ")
        time.sleep(3)
    print("FAILED")
    return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("DREADPIT FIGHTER IMAGE GENERATOR v2")
    print("(Iterated prompts based on BLIP evaluation)")
    print("=" * 60)

    results = {"portraits": {}, "battles": {}}

    # Phase 1: Generate iterated fighter portraits
    print("\n--- PHASE 1: Iterated Fighter Portraits ---")
    for key, fighter in FIGHTERS_V2.items():
        print(f"\n[{fighter['name']}]")
        fname = f"{key}_portrait_v2.jpg"
        ok = generate_image(fighter["prompt"], fname, seed=42)
        results["portraits"][key] = {
            "prompt": fighter["prompt"],
            "file": fname,
            "success": ok,
        }
        time.sleep(2)

    # Phase 2: Generate iterated battle scenes
    print("\n--- PHASE 2: Iterated Battle Scenes ---")
    for key, battle in BATTLES_V2.items():
        print(f"\n[{battle['name']}]")
        fname = f"{key}_vs_cybergod_v2.jpg"
        ok = generate_image(battle["prompt"], fname, seed=43)
        results["battles"][key] = {
            "prompt": battle["prompt"],
            "file": fname,
            "success": ok,
        }
        time.sleep(2)

    # Save report
    report_path = os.path.join(OUTPUT_DIR, "generation_report_v2.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("GENERATION SUMMARY v2")
    print("=" * 60)
    successes = sum(1 for v in results["portraits"].values() if v["success"])
    successes += sum(1 for v in results["battles"].values() if v["success"])
    total = len(results["portraits"]) + len(results["battles"])
    print(f"Generated {successes}/{total} images successfully")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
