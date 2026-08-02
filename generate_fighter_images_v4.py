"""
DREADPIT FIGHTER IMAGE GENERATOR v4
Prompt style: comma-separated short visual fragments, no negatives, simple words.

User's rules:
- NO negation: "no shadow" is useless, image gens ignore it
- Simple words: "mech" over "machinations of machinery"
- Comma separated: "white beard man strong, left hand sword" instead of full sentences
- Visual-only: describe what it looks like, nothing abstract
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

# v4 prompts — comma-separated short fragments, no negation
FIGHTERS_V4 = {
    "forge_colossus": {
        "name": "Forge Colossus v4",
        "prompt": "Giant walking furnace black iron, white-hot core visible through chest bars, massive anvil hammer each hand glowing orange, flat iron mask orange eye slits, heat waves distort air around body",
    },
    "the_reclaimer": {
        "name": "The Reclaimer (replaces The Hook)",
        "prompt": "Gaunt dragon hunter grey monster pelts, massive steel crossbow taller than body, severed dragon claws protruding from backpack, scarred face one glowing yellow eye, iron claw hand",
    },
    "vatican_gun": {
        "name": "Vatican Gun v4",
        "prompt": "Hooded executioner black leather duster, massive six-barrel gatling cannon barrels spinning visible, holy water drums crosses each side, gas mask red glowing eyes, silver bullets across chest, crucifix bolted to gun stock",
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
    print("DREADPIT FIGHTER IMAGE GENERATOR v4")
    print("(Comma-separated short prompts, no negatives)")
    print("=" * 60)

    results = {}

    print("\n--- PHASE: v4 Fighter Portraits ---")
    for key, fighter in FIGHTERS_V4.items():
        print(f"\n[{fighter['name']}]")
        fname = f"{key}_portrait_v4.jpg"
        ok = generate_image(fighter["prompt"], fname, seed=46)
        results[key] = {"name": fighter["name"], "prompt": fighter["prompt"], "file": fname, "success": ok}
        time.sleep(2)

    report_path = os.path.join(OUTPUT_DIR, "generation_report_v4.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    successes = sum(1 for v in results.values() if v["success"])
    print(f"\nGenerated {successes}/{len(results)} images successfully")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
