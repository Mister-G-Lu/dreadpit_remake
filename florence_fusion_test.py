#!/usr/bin/env python3
"""
NN + Florence FUSION TEST — does Florence close the NN's gap errors?

Loads florence_gap_results.json (39 gap fighters, each with BLIP caption,
Florence caption, NN score, wins, group A/B).

Tests three scorers against the TRUE label (gap A = should be WINNER,
gap B = should be LOSER):

  1. NN only          — baseline (the model that got these wrong by definition)
  2. Florence-keyword — a keyword classifier over the RICHER Florence captions
  3. FUSED            — NN score + Florence score combined

Measures "correction rate": the fraction of gap fighters each scorer would
classify correctly (gap A predicted as winner, gap B predicted as loser).
"""
import json
import os

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
GAP_PATH = os.path.join(CACHE_DIR, "florence_gap_results.json")

# Reuse BLIP's keyword extractor shape but tuned for Florence's richer
# vocabulary. Positive cues = winner-ish, negative cues = loser-ish.
WINNER_CUES = {
    "armor": 2.0, "armoured": 2.0, "armored": 2.0, "plate": 1.8, "chainmail": 2.0,
    "helmet": 1.2, "shield": 1.2, "gauntlet": 1.0, "metal": 1.8, "steel": 1.8,
    "iron": 1.6, "gold": 1.2, "robot": 2.2, "mecha": 2.5, "mechanical": 1.8,
    "machine": 1.2, "cyborg": 1.8, "dragon": 2.0, "demon": 1.5, "monster": 1.2,
    "creature": 0.6, "beast": 1.0, "wings": 1.0, "fire": 1.2, "flame": 1.2,
    "glowing": 1.0, "magical": 0.8, "giant": 0.8, "knight": 1.8, "paladin": 2.0,
    "samurai": 1.6, "viking": 1.4, "warrior": 0.8, "soldier": 0.6,
}
LOSER_CUES = {
    "skeleton": -2.5, "bone": -2.0, "skull": -1.8, "cartoon": -1.5,
    "jester": -1.5, "joker": -1.2, "statue": -1.0, "insect": -1.8,
    "grasshopper": -2.0, "mantis": -2.0, "human": -1.2, "man": -0.8,
    "woman": -0.8, "person": -0.8, "plain": -0.8, "normal": -0.8,
    "outfit": -1.2, "uniform": -1.2, "cloth": -1.4, "robe": -1.2,
    "suit": -1.0, "civilian": -1.5, "naked": -2.0, "bare": -1.5,
    "broken": -1.8, "cracked": -1.5, "hollow": -1.8, "dead": -2.0,
    "blind": -1.5, "bile": -2.0, "mountain": -0.5,
}


def florence_score(caption):
    """Score a Florence caption for winner-ness. Positive = winner, negative = loser.
    Returns (score, hits). Longer cues are matched first so a word like 'armored'
    doesn't also fire the contained 'armor' cue."""
    if not caption or caption.startswith("(no caption") or caption.startswith("[ERROR"):
        return 0.0, []
    dl = caption.lower()
    score = 0.0
    hits = []
    all_cues = list(WINNER_CUES.items()) + list(LOSER_CUES.items())
    all_cues.sort(key=lambda kv: -len(kv[0]))  # longest first to avoid double-count
    for kw, val in all_cues:
        if kw in dl:
            score += val
            hits.append(f"{kw}:{val:+}")
    return round(score, 2), hits


def main():
    print("=" * 90, flush=True)
    print("  NN + FLORENCE FUSION TEST — does Florence close the NN gap?", flush=True)
    print("=" * 90, flush=True)

    with open(GAP_PATH, encoding="utf-8") as f:
        fighters = json.load(f)

    # True label: gap A = winner, gap B = loser
    for r in fighters:
        r["true_winner"] = (r["group"] == "A")

    # Collect raw Florence scores first so we can normalize by observed range.
    raw_scores = []
    for r in fighters:
        fs, _ = florence_score(r.get("florence", ""))
        raw_scores.append(fs)
    lo, hi = min(raw_scores), max(raw_scores)
    span = hi - lo if hi > lo else 1.0

    results = []
    for r, fs in zip(fighters, raw_scores):
        hits = florence_score(r.get("florence", ""))[1]
        nn = r.get("nn_score", 0.5)
        # Map Florence score to 0-1 using the observed range (min-max normalize).
        fl_norm = (fs - lo) / span
        fl_norm = max(0.0, min(1.0, fl_norm))
        fused = 0.5 * nn + 0.5 * fl_norm
        results.append({
            "name": r["name"],
            "group": r["group"],
            "wins": r.get("wins", 0),
            "nn": nn,
            "florence_raw": fs,
            "florence_prob": round(fl_norm, 3),
            "fused": round(fused, 3),
            "true_winner": r["true_winner"],
            "florence": r.get("florence", ""),
            "blip": r.get("blip", ""),
            "hits": hits,
        })

    # ---- Accuracy per scorer ----
    def acc(key):
        correct = 0
        for r in results:
            pred_winner = r[key] >= 0.5
            if pred_winner == r["true_winner"]:
                correct += 1
        return correct / max(len(results), 1)

    nn_acc = acc("nn")
    fl_acc = acc("florence_prob")
    fu_acc = acc("fused")

    print(f"\n  Fighters: {len(results)} (gap A: {sum(1 for r in results if r['group']=='A')}, "
          f"gap B: {sum(1 for r in results if r['group']=='B')})", flush=True)
    print(f"\n  CORRECTION RATE (fraction of the NN's known gap errors each scorer fixes):")
    print(f"  {'Scorer':22s} {'Correct':>8s} {'Rate':>7s}")
    print(f"  {'-'*22} {'-'*8} {'-'*7}")
    print(f"  {'NN (predefined errors)':22s} {int(nn_acc*len(results)):>4d}/{len(results)} {nn_acc:>6.1%}")
    print(f"  {'Florence only':22s} {int(fl_acc*len(results)):>4d}/{len(results)} {fl_acc:>6.1%}")
    print(f"  {'FUSED (NN+Florence)':22s} {int(fu_acc*len(results)):>4d}/{len(results)} {fu_acc:>6.1%}")
    print(f"  (Florence raw-score range used for normalization: {lo:.2f} .. {hi:.2f})")

    # ---- Per-fighter table ----
    print(f"\n  {'Fighter':34s} {'G':>2s} {'W':>2s} {'NN':>5s} {'Flor':>5s} {'Fused':>5s}  Verdict", flush=True)
    print("-" * 95, flush=True)
    for r in sorted(results, key=lambda x: (x["group"], -x["fused"])):
        g = "A" if r["group"] == "A" else "B"
        correct_fused = (r["fused"] >= 0.5) == r["true_winner"]
        mark = "OK " if correct_fused else "MISS"
        print(f"  {r['name'][:34]:34s} {g:>2s} {r['wins']:>2d} {r['nn']:>5.2f} "
              f"{r['florence_prob']:>5.2f} {r['fused']:>5.2f}  {mark}", flush=True)

    # ---- What did Florence see that BLIP missed? (gap A deep dive) ----
    print(f"\n{'='*90}", flush=True)
    print("  GAP A DEEP DIVE — why these winners LOOKED like losers to the NN", flush=True)
    print("=" * 90, flush=True)
    for r in results:
        if r["group"] != "A":
            continue
        print(f"\n  {r['name']} ({r['wins']}w)  NN={r['nn']:.3f}", flush=True)
        print(f"    BLIP:     {r['blip'][:90]}", flush=True)
        print(f"    FLORENCE: {r['florence'][:120]}", flush=True)
        print(f"    Florence winner cues: {', '.join(r['hits'][:8]) if r['hits'] else '(none)'}", flush=True)

    # ---- Gap B examples where Florence caught the flaw ----
    print(f"\n{'='*90}", flush=True)
    print("  GAP B DEEP DIVE — losers the NN thought looked like winners", flush=True)
    print("=" * 90, flush=True)
    for r in results:
        if r["group"] != "B":
            continue
        print(f"\n  {r['name']} ({r['wins']}w)  NN={r['nn']:.3f}  Flor={r['florence_prob']:.3f}", flush=True)
        print(f"    FLORENCE: {r['florence'][:120]}", flush=True)

    with open(os.path.join(CACHE_DIR, "fused_gap_scores.json"), "w", encoding="utf-8") as f:
        json.dump({
            "fighters": results,
            "summary": {
                "n": len(results),
                "nn_acc": nn_acc,
                "florence_acc": fl_acc,
                "fused_acc": fu_acc,
                "florence_range": [lo, hi],
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: fused_gap_scores.json", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
