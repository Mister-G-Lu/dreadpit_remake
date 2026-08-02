#!/usr/bin/env python3
"""
Find the most 'average' bot fighters — the ones that win as much as they
lose. Uses bot_roster.json (1015 bots with true career records).

Ranking logic:
  - Primary metric: distance from 50% win rate, |rate - 0.5|.
  - Confidence: bots with more fights carry more weight, so we report
    separately for different fight-count floors and also compute a
    fight-weighted average score.

Outputs: average_bots.json
"""

import json
import os

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTER_PATH = os.path.join(CACHE_DIR, "bot_roster.json")
OUT_PATH = os.path.join(CACHE_DIR, "average_bots.json")


def rate(b):
    f = b.get("career_fights", 0)
    if f == 0:
        return 0.5
    return b.get("career_wins", 0) / f


def avg_score(b):
    """Closeness to 50%, rewarded for volume: divide by sqrt(fights) so
    MORE fights = LOWER score = more average (prioritizes most fights).
    A 40-fight bot at 51% scores lower than a 10-fight bot at 55%.
    """
    f = max(b.get("career_fights", 0), 1)
    r = rate(b)
    return abs(r - 0.5) / (f ** 0.5)


def show(title, bots):
    print(f"\n{'=' * 88}", flush=True)
    print(f"  {title}", flush=True)
    print("=" * 88, flush=True)
    print(f"  {'Bot':34s} {'W/L':>12s} {'Fights':>7s} {'Win%':>6s} {'|rate-50%|':>10s}", flush=True)
    print("  " + "-" * 84, flush=True)
    for b in bots:
        w = b.get("career_wins", 0)
        l = b.get("career_losses", 0)
        f = b.get("career_fights", 0)
        r = rate(b)
        print(f"  {b.get('name', '?')[:34]:34s} {w:3d}w/{l:3d}l {f:5d}f {100*r:5.1f}% {abs(r-0.5):9.4f}", flush=True)


def main():
    print("=" * 88, flush=True)
    print("  MOST AVERAGE BOTS — win as much as they lose", flush=True)
    print("=" * 88, flush=True)

    with open(ROSTER_PATH, encoding="utf-8") as f:
        bots = json.load(f)
    print(f"\n  Roster: {len(bots)} bots", flush=True)

    # Fight-count distribution
    floors = [5, 10, 15, 20, 30]
    for fl in floors:
        n = sum(1 for b in bots if b.get("career_fights", 0) >= fl)
        print(f"  Bots with {fl}+ fights: {n}", flush=True)

    results = {"floors": {}, "top_most_fights": [], "top_average_score": []}

    # 1. Most-fights bots within a 50% +- band (user priority: most fights
    #    first, closest to 50% second)
    for fl in floors:
        qual = [b for b in bots if b.get("career_fights", 0) >= fl]
        # Within +-5% of 50%, sorted by fights descending (most fights first)
        in_band = [b for b in qual if abs(rate(b) - 0.5) <= 0.05]
        in_band.sort(key=lambda b: -b.get("career_fights", 0))
        top = in_band[:8]
        show(f"MOST-FOUGHT WITHIN +-5% OF 50%  (bots with {fl}+ fights)", top)
        results["floors"][str(fl)] = [
            {
                "name": b.get("name", "?"),
                "wins": b.get("career_wins", 0),
                "losses": b.get("career_losses", 0),
                "fights": b.get("career_fights", 0),
                "win_rate": round(rate(b), 4),
                "dist_50": round(abs(rate(b) - 0.5), 4),
                "id": b.get("id", ""),
            }
            for b in top
        ]

    # 2. Fight-weighted average score (confidence-adjusted 'most average')
    #    Filter to 10+ fights FIRST, then sort — avoids 0-fight bots (which
    #    score 0.0) crowding the top. Secondary key breaks ties among exact
    #    -50% bots (all score 0.0) by MOST FIGHTS first.
    scored = sorted(
        [b for b in bots if b.get("career_fights", 0) >= 10],
        key=lambda b: (avg_score(b), -b.get("career_fights", 0)),
    )
    top_avg = scored[:10]
    show("FIGHT-WEIGHTED MOST AVERAGE (10+ fights, confidence-adjusted)", top_avg)
    results["top_average_score"] = [
        {
            "name": b.get("name", "?"),
            "wins": b.get("career_wins", 0),
            "losses": b.get("career_losses", 0),
            "fights": b.get("career_fights", 0),
            "win_rate": round(rate(b), 4),
            "avg_score": round(avg_score(b), 4),
            "id": b.get("id", ""),
        }
        for b in top_avg
    ]

    # 3. The absolute most-fought bots (do any of them land near 50%?)
    most_fought = sorted(bots, key=lambda b: -b.get("career_fights", 0))[:15]
    show("MOST-FOUGHT BOTS (any win rate)", most_fought)
    results["top_most_fights"] = [
        {
            "name": b.get("name", "?"),
            "wins": b.get("career_wins", 0),
            "losses": b.get("career_losses", 0),
            "fights": b.get("career_fights", 0),
            "win_rate": round(rate(b), 4),
            "id": b.get("id", ""),
        }
        for b in most_fought
    ]

    # 4. Perfect 50/50 club (exactly equal wins/losses) with most fights
    exact = [b for b in bots if b.get("career_wins", 0) == b.get("career_losses", 0)
             and b.get("career_fights", 0) >= 8]
    exact.sort(key=lambda b: -b.get("career_fights", 0))
    if exact:
        show("PERFECT 50/50 CLUB (equal wins & losses, 8+ fights)", exact[:10])
        results["exact_5050"] = [
            {
                "name": b.get("name", "?"),
                "wins": b.get("career_wins", 0),
                "losses": b.get("career_losses", 0),
                "fights": b.get("career_fights", 0),
                "id": b.get("id", ""),
            }
            for b in exact[:10]
        ]
    else:
        print("\n  No bots with exactly equal wins/losses at 8+ fights.", flush=True)
        results["exact_5050"] = []

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"\n  Saved: average_bots.json", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
