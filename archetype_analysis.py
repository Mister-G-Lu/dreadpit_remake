#!/usr/bin/env python3
"""
Keyword Archetype Analysis for DreadPit Fighters.

Categorizes each fighter's BLIP-detected keywords into 5 combat archetypes:
  - ATTACK:  weapons, guns, blades
  - DEFENSE: armor, helmets, shields, metal plating
  - SPEED:   wings, capes (show of speed / mobility)
  - MAGIC:   fire, glowing/red elements, monster/dragon nature
  - ESOTERIC: unexplainable qualities — human in a monster world,
              dark/eldritch, robots, cold/alien blue, mysterious voids

Outputs per-fighter profiles and archetype popularity tables.
"""

import json
import os
import statistics
from collections import Counter

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================================================================
# Archetype keyword mapping
# =========================================================================

ARCHETYPES = {
    "ATTACK": {
        "label": "Attack",
        "icon": "[W]",
        "keywords": ["sword", "axe_hammer", "gun"],
        "description": "Weapons & ranged — how they HIT",
    },
    "DEFENSE": {
        "label": "Defense",
        "icon": "[A]",
        "keywords": ["armor", "helmet", "shield", "metal"],
        "description": "Armor, shields, plating — how they SURVIVE",
    },
    "SPEED": {
        "label": "Speed",
        "icon": "[>]",
        "keywords": ["wings", "cape"],
        "description": "Wings, flowing capes — show of MOBILITY",
    },
    "MAGIC": {
        "label": "Magic",
        "icon": "[~]",
        "keywords": ["fire", "red", "monster"],
        "description": "Fire, red glow, monster/dragon — SUPERNATURAL power",
    },
    "ESOTERIC": {
        "label": "Esoteric",
        "icon": "[?]",
        "keywords": ["human", "dark", "robot", "blue"],
        "description": "Human in monster world, darkness, robots, alien blue — UNEXPLAINABLE",
    },
}

# All 16 keywords, for the "uncategorized" check
ALL_KEYWORDS = [
    "sword", "axe_hammer", "gun", "armor", "helmet", "human",
    "monster", "robot", "fire", "dark", "red", "blue", "metal",
    "wings", "shield", "cape"
]


def score_archetypes(kws):
    """Score a fighter across all 5 archetypes based on their keyword vector."""
    scores = {}
    for ark, config in ARCHETYPES.items():
        count = sum(1 for kw in config["keywords"] if kws.get(kw, False))
        max_possible = len(config["keywords"])
        scores[ark] = {
            "count": count,
            "max": max_possible,
            "pct": round(count / max_possible * 100, 0) if max_possible > 0 else 0,
            "active_kws": [kw for kw in config["keywords"] if kws.get(kw, False)],
        }
    return scores


def total_keywords_triggered(kws):
    return sum(1 for kw in ALL_KEYWORDS if kws.get(kw, False))


def get_primary_archetype(scores):
    """Return the archetype with the highest % score (tie-breaking by count)."""
    best = None
    best_score = -1
    for ark, s in scores.items():
        val = s["pct"]
        if val > best_score or (val == best_score and s["count"] > (scores.get(best, {})).get("count", 0)):
            best_score = val
            best = ark
    return best, best_score


# =========================================================================
# Load data
# =========================================================================

def main():
    sep = "=" * 72
    print(sep)
    print("  DREADPIT KEYWORD ARCHETYPE ANALYSIS")
    print(sep)

    path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Cannot load data: {e}")
        return

    results = data.get("results", [])
    if not results:
        print("ERROR: No results found.")
        return

    print(f"  Loaded {len(results)} fighters\n")

    # =====================================================================
    # Score every fighter
    # =====================================================================
    print("[1/4] Scoring all fighters across archetypes...")
    fighters = []
    for r in results:
        kws = r.get("kws", {})
        pixel = r.get("pixel", {})
        name = r.get("name", "?")
        wins = r.get("wins", 0)
        group = r.get("group", "?")

        arch_scores = score_archetypes(kws)
        total_kws = total_keywords_triggered(kws)
        primary, primary_pct = get_primary_archetype(arch_scores)

        # Archetype vector for display
        arch_vec = []
        for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
            pct = arch_scores[ark]["pct"]
            arch_vec.append(f"{pct:.0f}%")

        fighters.append({
            "name": name,
            "wins": wins,
            "group": group,
            "total_kws": total_kws,
            "primary": primary,
            "primary_pct": primary_pct,
            "arch_scores": arch_scores,
            "arch_vec": arch_vec,
            "blip": r.get("blip", "")[:80],
            "warmth": pixel.get("warmth", 0),
            "brightness": pixel.get("brightness", 0),
            "kws_active": [kw for kw in ALL_KEYWORDS if kws.get(kw, False)],
        })

    print(f"  Scored {len(fighters)} fighters\n")

    # =====================================================================
    # Archetype Popularity (what wins?)
    # =====================================================================
    print(sep)
    print("  [2/4] ARCHETYPE POPULARITY AMONG HIGH-WINNERS (5+ wins)")
    print(sep)

    high = [f for f in fighters if f["wins"] >= 5]

    # Count primary archetypes
    primary_counts = Counter()
    for f in high:
        primary_counts[f["primary"]] += 1

    print(f"\n  Primary Archetype distribution among {len(high)} high-winners:")
    print(f"  {'Archetype':15s} {'Count':>7s} {'Percent':>9s}")
    print(f"  {'-'*15} {'-'*7} {'-'*9}")
    for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
        c = primary_counts.get(ark, 0)
        pct = c / len(high) * 100
        cfg = ARCHETYPES[ark]
        print(f"  {cfg['label']:15s} {c:>7d} {pct:>8.1f}%")

    # Also show average archetype score (not just primary)
    print(f"\n  Average archetype scores (out of 100%):")
    print(f"  {'Archetype':15s} {'Winners':>9s} {'Losers':>9s} {'Delta':>7s}")
    print(f"  {'-'*15} {'-'*9} {'-'*9} {'-'*7}")
    low = [f for f in fighters if f["wins"] <= 3]
    for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
        h_avg = statistics.mean([f["arch_scores"][ark]["pct"] for f in high])
        l_avg = statistics.mean([f["arch_scores"][ark]["pct"] for f in low]) if low else 0
        cfg = ARCHETYPES[ark]
        print(f"  {cfg['label']:15s} {h_avg:>8.1f}% {l_avg:>8.1f}% {h_avg-l_avg:>+6.1f}%")

    # =====================================================================
    # Top fighters per archetype
    # =====================================================================
    print(f"\n\n{sep}")
    print("  [3/4] TOP 10 FIGHTERS PER ARCHETYPE (highest % score)")
    print(sep)

    for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
        cfg = ARCHETYPES[ark]
        print(f"\n  {'='*60}")
        print(f"  {cfg['icon']} {cfg['label']:12s} | {cfg['description']}")
        print(f"  {'='*60}")

        # Sort high-winners by archetype score
        sorted_by_ark = sorted(
            [f for f in fighters if f["wins"] >= 5],
            key=lambda x: (-x["arch_scores"][ark]["pct"], -x["wins"])
        )

        print(f"  {'Name':35s} {'Wins':>4s} {'Score':>7s} {'Active Keywords':>30s}")
        print(f"  {'-'*35} {'-'*4} {'-'*7} {'-'*30}")
        for f in sorted_by_ark[:10]:
            s = f["arch_scores"][ark]
            kws_str = ", ".join(s["active_kws"][:4]) if s["active_kws"] else "(none)"
            marker = ""
            if "BIG" in f["name"].upper():
                marker = " << BIG"
            elif "SIMO" in f["name"].upper():
                marker = " << SIMO"
            elif "TOON" in f["name"].upper() or "JESTER" in f["name"].upper():
                marker = " << JESTER"
            print(f"  {f['name'][:35]:35s} {f['wins']:>4d} {s['pct']:>6.0f}% {kws_str:>30s}{marker}")

        # Show bottom 3 (lowest in that archetype)
        sorted_asc = sorted(
            sorted_by_ark,
            key=lambda x: (x["arch_scores"][ark]["pct"], -x["wins"])
        )
        print(f"  ...")
        for f in sorted_asc[:3]:
            s = f["arch_scores"][ark]
            kws_str = ", ".join(s["active_kws"][:3]) if s["active_kws"] else "(none)"
            print(f"  {f['name'][:35]:35s} {f['wins']:>4d} {s['pct']:>6.0f}% {kws_str:>30s}")

    # =====================================================================
    # Outlier deep-dive
    # =====================================================================
    print(f"\n\n{sep}")
    print("  [4/4] OUTLIER DEEP-DIVE — BIG, SIMO, TOON JESTER")
    print(sep)

    outlier_names = ["Big", "SIMO THE UNSEEN", "Irek'Ailth The Toon Jester"]
    for name_query in outlier_names:
        matches = [f for f in fighters if name_query.upper() in f["name"].upper()]
        if not matches:
            print(f"\n  (not found: {name_query})")
            continue
        f = matches[0]

        print(f"\n  {'='*60}")
        print(f"  --- {f['name']:40s} ({f['wins']} wins)")
        print(f"  {'='*60}")
        print(f"  BLIP:     {f['blip']}")
        print(f"  Warmth:   {f['warmth']:+.1f}  |  Bright: {f['brightness']:.1f}")
        print(f"  Keywords: {', '.join(f['kws_active']) if f['kws_active'] else '(none detected)'}")
        print(f"  Total keywords triggered: {f['total_kws']}")
        print()
        print(f"  {'Archetype':15s} {'Score':>8s} {'Active Keywords':>40s}")
        print(f"  {'-'*15} {'-'*8} {'-'*40}")
        for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
            cfg = ARCHETYPES[ark]
            s = f["arch_scores"][ark]
            kws_str = ", ".join(s["active_kws"]) if s["active_kws"] else "(none)"
            bar = "#" * int(s["pct"] / 5)
            print(f"  {cfg['icon']} {cfg['label']:12s} {s['pct']:>5.0f}% {bar:20s} {kws_str:>40s}")

        # Archetype interpretation
        primary, pct = f["primary"], f["primary_pct"]
        print(f"\n  >> Primary archetype: {ARCHETYPES[primary]['label']} ({pct:.0f}%)")
        print(f"  >> Archetype vector: {' | '.join(f['arch_vec'])}")

        # Compare to meta
        print(f"\n  -- How they compare to the meta --")
        for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"]:
            cfg = ARCHETYPES[ark]
            f_score = f["arch_scores"][ark]["pct"]
            h_avg = statistics.mean([x["arch_scores"][ark]["pct"] for x in high])
            delta = f_score - h_avg
            arrow = "+" if delta > 0 else ""
            print(f"  {cfg['icon']} {cfg['label']:12s} {f_score:>5.0f}%  vs winner avg {h_avg:>5.1f}%  ({arrow}{delta:+.0f}%)")

    # =====================================================================
    # Summary: the archetype landscape
    # =====================================================================
    print(f"\n\n{sep}")
    print("  ARCHETYPE LANDSCAPE — WHAT THE DATA SAYS")
    print(sep)

    print(f"""
  The 5 archetypes map to how Dreadpit fighters win:

  ATTACK [{sum(1 for f in high if f['primary']=='ATTACK')}/{len(high)} winners]:
    Having a weapon (sword, gun, axe) helps but is NOT required.
    Only {primary_counts.get('ATTACK', 0)}/{len(high)} high-winners primarily use weapons.
    Many top winners (Tigran, Black Entity, The Being) win WITHOUT visible weapons.

  DEFENSE [{sum(1 for f in high if f['primary']=='DEFENSE')}/{len(high)} winners]:
    Almost NO high-winners primarily show armor/shields.
    The Dreadpit AI judges don't care about defense — they care about PRESENCE.
    Armor may even make you look WEAK (boring knight archetype).

  SPEED [{sum(1 for f in high if f['primary']=='SPEED')}/{len(high)} winners]:
    Wings and capes are a consistent signal. ~{primary_counts.get('SPEED', 0)} high-winners
    primarily score on speed. Wings = mobility = threatening.

  MAGIC [{sum(1 for f in high if f['primary']=='MAGIC')}/{len(high)} winners]:
    The DOMINANT archetype. Fire + red glow + monster/dragon nature
    is the single strongest visual signal for winning.
    {primary_counts.get('MAGIC', 0)}/{len(high)} high-winners are primarily magical.

  ESOTERIC [{sum(1 for f in high if f['primary']=='ESOTERIC')}/{len(high)} winners]:
    The surprise archetype. Humans, robots, dark voids, alien blues
    win when they're UNEXPECTED. This is where BIG, SIMO, Jester live.
    {primary_counts.get('ESOTERIC', 0)}/{len(high)} high-winners are esoteric — they win
    by being WEIRD, not by fitting the fire+monster meta.
""")

    # The outliers
    print(sep)
    print("  WHY THE OUTLIERS WIN (archetype interpretation)")
    print(sep)

    for name_query in outlier_names:
        matches = [f for f in fighters if name_query.upper() in f["name"].upper()]
        if not matches:
            continue
        f = matches[0]
        print(f"\n  {f['name']:40s} ({f['wins']} wins)")
        print(f"  {'-'*60}")
        arch_vec_str = " | ".join(f"{ARCHETYPES[ark]['icon']} {f['arch_scores'][ark]['pct']:.0f}%" for ark in ["ATTACK", "DEFENSE", "SPEED", "MAGIC", "ESOTERIC"])
        print(f"  Profile: {arch_vec_str}")
        if f["name"].upper() == "BIG":
            print(f"  Reads: 'a man in a suit' — 0% on every combat archetype.")
            print(f"  Big wins by being COMPLETELY outside combat logic.")
            print(f"  The AI sees: 'eldritch horror in a business suit'")
        elif "SIMO" in f["name"].upper():
            print(f"  Reads: 'human with a rifle' — no armor, no magic, no speed.")
            print(f"  Simo wins by being a REALISTIC THREAT in a fantasy world.")
            print(f"  The AI sees: 'grizzled veteran who doesn't need magic'")
        elif "JESTER" in f["name"].upper():
            print(f"  Reads: 'toon character with a gun' — cartoon logic breaks rules.")
            print(f"  Jester wins by being UNPREDICTABLE and undismissable.")
            print(f"  The AI sees: 'funny clown that WON'T STAY DOWN'")

    # Single most important insight
    print(f"\n\n{sep}")
    print("  THE CORE INSIGHT")
    print(sep)
    print(f"""
  MAGIC is the dominant meta. {primary_counts.get('MAGIC', 0)}/{len(high)} winners.
  But the ESOTERIC path ({primary_counts.get('ESOTERIC', 0)} winners) is the
  highest-value niche — fewer fighters compete there.

  To beat Cyber God, the safest bet is MAGIC+ATTACK (fire + monster + weapon).
  The highest-upside bet is ESOTERIC (something the AI can't classify).
""")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
