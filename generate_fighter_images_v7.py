"""
DREADPIT FIGHTER IMAGE GENERATOR v7
Targeted final iteration. Keep what works, fix what doesn't.

Strategy:
  FORGE COLOSSUS: REVERT to v3 prompt (it produced non-human fire entity at warmth=59.4)
    The v6 attempt to add "flames from cracks" made it human again.
    v3's "No flesh. Just forge." was critical to the non-human form.

  VATICAN GUN: REVERT to v3 prompt (gas mask + gun confirmed working)
    v6's "barrels glowing" + "muzzle flash" lost the gas mask.
    Instead, try adding a warm BACKGROUND element:
    "Burning cathedral behind" adds fire pixels without changing the fighter.

  WRATH INFERNAL: REFINE v6 — add more explicit wing emphasis
    v6: "demonic dragon with fiery flames" (monster+fire, 54.5 warmth)
    Target monster+fire+wings = triple NN feature
    Add "Large leathery wings spread wide, burning" more prominently
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

FIGHTERS_V7 = {
    # REVERT to v3 — proven to produce non-human fire entity
    "forge_colossus": {
        "name": "Forge Colossus v7 (v3 revert)",
        "prompt": "Giant walking furnace made of black iron. White-hot molten core visible through chest bars. Massive anvil-headed hammer in each hand, glowing red. Flat iron mask with orange eye slits. Heat waves distort air around body. No flesh. Just forge.",
    },
    # REVERT to v3 gas mask + add warm background
    "vatican_gun": {
        "name": "Vatican Gun v7 (warm bg)",
        "prompt": "Hooded executioner in black leather duster. Carries a massive six-barrel gatling cannon, barrels clearly visible spinning. Holy water drums marked with crosses on each side. Gas mask with red glowing eyes. Burning cathedral behind. Silver bullets across chest. Crucifix on gun.",
    },
    # REFINE: emphasize wings more prominently
    "wrath_infernal": {
        "name": "Wrath Infernal v7 (wings+)",
        "prompt": "Demonic winged entity wreathed in flames. Large leathery burning wings spread wide behind. Obsidian skull face with burning orange eye sockets. Horns of twisted iron. Claws of molten rock. Body of ash and ember. Wrath made of fire.",
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
    print("DREADPIT FIGHTER IMAGE GENERATOR v7")
    print("(Targeted: revert best + refine Wrath Infernal for wings)")
    print("=" * 60)

    results = {}
    seed = 53

    print("\n--- PHASE: v7 Fighter Portraits ---")
    for key, fighter in FIGHTERS_V7.items():
        print(f"\n[{fighter['name']}]")
        print(f"  Prompt ({len(fighter['prompt'])} chars): {fighter['prompt'][:100]}...")
        fname = f"{key}_portrait_v7.jpg"
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

    report_path = os.path.join(OUTPUT_DIR, "generation_report_v7.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    successes = sum(1 for v in results.values() if v["success"])
    print(f"\nGenerated {successes}/{len(results)} images successfully")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
