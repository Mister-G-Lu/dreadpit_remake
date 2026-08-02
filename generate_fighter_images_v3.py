"""
DREADPIT FIGHTER IMAGE GENERATOR v3

Key fixes from v2 evaluation:
- The Hook: FLUX cannot render "hook on chain" as a weapon. Pivot to "giant
  harpoon weapon" (more recognizable) or completely different weapon concept.
  Also trying a version with just "massive meat hook on chain" to see if that
  works better.
- Forge Colossus: "robot with fire" improved concept but lost warmth (35->12).
  Restore fire/heat language while keeping "no organic parts."
- Vatican Gun: stable at "man with cloak gun." Adding "six rotating barrels"
  and "gatling" for better cannon recognition.
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

# v3 prompts — completely restructured based on v2 BLIP failures
FIGHTERS_V3 = {
    "forge_colossus": {
        "name": "Forge Colossus v3",
        "prompt": "Giant walking furnace made of black iron. White-hot molten core visible through chest bars. Massive anvil-headed hammer in each hand, glowing red. Flat iron mask with orange eye slits. Heat waves distort air around body. No flesh. Just forge.",
    },
    "the_hook": {
        "name": "The Hook v3",
        "prompt": "Monster hunter wielding a giant steel harpoon on a thick chain. The harpoon tip is barbed and huge, clearly designed to pierce dragons. Worn grey pelts draped over body. Scarred face, one glowing yellow eye. Iron claw replaces hand.",
    },
    "vatican_gun": {
        "name": "Vatican Gun v3",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel gatling cannon, barrels clearly visible spinning. Holy water drums marked with crosses on each side. Gas mask with red glowing eyes. Silver bullets across chest. Crucifix on gun.",
    },
}

BATTLES_V3 = {
    "forge_colossus": {
        "name": "Forge Colossus vs Cyber God v3",
        "prompt": "A colossal walking furnace of black iron swings a glowing anvil hammer at an armored god riding a cyber dragon. Molten metal sprays from the impact. The furnace giant's chest glows white-hot. Epic destruction battle. Dark sky orange flames.",
    },
    "the_hook": {
        "name": "The Hook vs Cyber God v3",
        "prompt": "A scarred monster hunter hurls a giant barbed harpoon on a chain at an armored god on a cyber dragon. The harpoon pierces the dragon's wing. Hunter pulls the chain. Dragon claws on his back. Epic monster hunter fight.",
    },
    "vatican_gun": {
        "name": "Vatican Gun vs Cyber God v3",
        "prompt": "A hooded executioner fires a six-barrel gatling cannon at an armored god riding a cyber dragon. Crosses on the cannon. Holy water blasts through the air. Dark clouds and light beams. Religious war. Epic dark fantasy.",
    },
}


def generate_image(prompt: str, filename: str, seed: int = None) -> bool:
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
                print(f"attempt {attempt+1} failed (s={r.status_code}, sz={len(r.content)})", end=" ")
        except Exception as e:
            print(f"attempt {attempt+1} error: {e}", end=" ")
        time.sleep(3)
    print("FAILED")
    return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("DREADPIT FIGHTER IMAGE GENERATOR v3")
    print("(Restructured prompts based on v2 failures)")
    print("=" * 60)

    results = {"portraits": {}, "battles": {}}

    print("\n--- PHASE 1: v3 Fighter Portraits ---")
    for key, fighter in FIGHTERS_V3.items():
        print(f"\n[{fighter['name']}]")
        fname = f"{key}_portrait_v3.jpg"
        ok = generate_image(fighter["prompt"], fname, seed=44)
        results["portraits"][key] = {"prompt": fighter["prompt"], "file": fname, "success": ok}
        time.sleep(2)

    print("\n--- PHASE 2: v3 Battle Scenes ---")
    for key, battle in BATTLES_V3.items():
        print(f"\n[{battle['name']}]")
        fname = f"{key}_vs_cybergod_v3.jpg"
        ok = generate_image(battle["prompt"], fname, seed=45)
        results["battles"][key] = {"prompt": battle["prompt"], "file": fname, "success": ok}
        time.sleep(2)

    report_path = os.path.join(OUTPUT_DIR, "generation_report_v3.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    successes = sum(1 for v in results["portraits"].values() if v["success"])
    successes += sum(1 for v in results["battles"].values() if v["success"])
    total = len(results["portraits"]) + len(results["battles"])
    print(f"\nGenerated {successes}/{total} images successfully")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
