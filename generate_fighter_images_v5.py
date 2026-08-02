"""
DREADPIT FIGHTER IMAGE GENERATOR v5
Hybrid prompt style: short positive phrases, no wasted words.

Key rules applied:
- Short comma-separated fragments with punchy phrases
- Negatives replaced with positive alternatives ("pure iron" not "no flesh")
- Simple words preferred
- Each element gets balanced emphasis — no single element dominates
- ~15-20 words per prompt (concise but complete)
"""
import requests
import json
import os
import time
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_images")

# v5 prompts — hybrid style
FIGHTERS_V5 = {
    "forge_colossus": {
        "name": "Forge Colossus v5",
        "prompt": "Giant walking furnace black iron, white-hot core through chest bars open, anvil hammer each hand glowing orange, flat iron mask orange eye slits, pure metal construct zero organic parts",
    },
    "the_reclaimer": {
        "name": "The Reclaimer v5",
        "prompt": "Gaunt dragon hunter grey monster pelts, giant crossbow weapon taller than body, crossbow string drawn ready to fire, severed dragon claws from backpack, scarred face one glowing yellow eye",
    },
    "vatican_gun": {
        "name": "Vatican Gun v5",
        "prompt": "Hooded executioner black leather duster, six-barrel gatling cannon spinning barrels, holy water drums crosses on each side, gas mask red eyes, silver bullets bandolier across chest, crucifix bolted to gun stock",
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
    print("DREADPIT FIGHTER IMAGE GENERATOR v5")
    print("(Hybrid: short phrases + positive alternatives)")
    print("=" * 60)

    results = {}

    print("\n--- PHASE: v5 Fighter Portraits ---")
    for key, fighter in FIGHTERS_V5.items():
        print(f"\n[{fighter['name']}]")
        fname = f"{key}_portrait_v5.jpg"
        ok = generate_image(fighter["prompt"], fname, seed=47)
        results[key] = {"name": fighter["name"], "prompt": fighter["prompt"], "file": fname, "success": ok}
        time.sleep(2)

    report_path = os.path.join(OUTPUT_DIR, "generation_report_v5.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    successes = sum(1 for v in results.values() if v["success"])
    print(f"\nGenerated {successes}/{len(results)} images successfully")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
