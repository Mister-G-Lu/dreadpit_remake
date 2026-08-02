"""
DREADPIT FIGHTER IMAGE GENERATOR v6
Data-driven prompt design based on NN feature importance + winner analysis.

v6 Changes from v3 (baseline best):
  FORGE COLOSSUS: Keep v3 sentence structure but add MORE fire intensity.
    "Flames erupt from cracks in iron body" + "glowing red hot" to push warmth >59.4
    Target: warmth 65+ (3.5x Cyber God's 18.6)

  VATICAN GUN: Add heat elements to fix low warmth (8.8 → target 30+).
    "barrels glowing from sustained fire" instead of "barrels visible spinning"
    "Muzzle flash illuminates the dark" for fire pixel presence
    Keep gas mask — that's the distinctive element

  THE RECLAIMER → REPLACED with "Wrath Infernal"
    The Hook/Reclaimer failed 5× across weapon types (hook, chain, harpoon, crossbow)
    New concept: demonic fire entity with wings (proven winner pattern)
    Black Entity (12w, warmth=45.5): "demonic demon with fiery flame"
    Tigran (9w, warmth=40.9): "demonic demon with wings and halo"
    Straxar (8w, warmth=54.9): "demonic demon with fiery wings"
    Wrath Infernal hits monster + fire + wings + dark + red = all top NN features
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

FIGHTERS_V6 = {
    "forge_colossus": {
        "name": "Forge Colossus v6",
        "prompt": "Giant walking furnace made of black iron. White-hot molten core visible through chest bars. Massive anvil-headed hammer in each hand, glowing red hot. Flat iron mask with orange eye slits. Flames erupt from cracks in iron body. Heat waves distort air around body. No flesh. Just forge.",
    },
    "vatican_gun": {
        "name": "Vatican Gun v6",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel gatling cannon, barrels glowing from sustained fire. Holy water drums marked with crosses on each side. Gas mask with red glowing eyes. Muzzle flash illuminates the dark. Silver bullets across chest. Crucifix on gun.",
    },
    "wrath_infernal": {
        "name": "Wrath Infernal v6",
        "prompt": "Demonic winged entity wreathed in black orange flames. Fiery wings spread wide burning bright. Obsidian skull face with burning orange eye sockets. Horns of twisted iron. Claws of molten rock. Body of ash and ember. Wrath made of fire.",
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
    print("DREADPIT FIGHTER IMAGE GENERATOR v6")
    print("(Data-driven: warmth-boosted + new demonic fire entity)")
    print("=" * 60)

    results = {}
    seed = 50

    print("\n--- PHASE: v6 Fighter Portraits ---")
    for key, fighter in FIGHTERS_V6.items():
        print(f"\n[{fighter['name']}]")
        print(f"  Prompt ({len(fighter['prompt'])} chars): {fighter['prompt'][:80]}...")
        fname = f"{key}_portrait_v6.jpg"
        ok = generate_image(fighter["prompt"], fname, seed=seed)
        results[key] = {
            "name": fighter["name"],
            "prompt": fighter["prompt"],
            "chars": len(fighter["prompt"]),
            "file": fname,
            "seed": seed,
            "success": ok,
        }
        seed += 1
        time.sleep(2)

    report_path = os.path.join(OUTPUT_DIR, "generation_report_v6.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    successes = sum(1 for v in results.values() if v["success"])
    print(f"\nGenerated {successes}/{len(results)} images successfully")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
