#!/usr/bin/env python3
"""
ROYGBIV + White/Black Color Analysis for DreadPit fighters.

Bins each fighter portrait's pixels into hue buckets:
  Red, Orange, Yellow, Green, Blue, Indigo, Violet (chromatic, by HSV hue)
  plus White (high value / low saturation), Black (low value), and Gray
  (mid-value, low saturation) as an "other/neutral" bucket.

For each color we compare HIGH-winners (wins >= 5) against LOW-winners
(wins <= 3) from comparison_analysis.json and report:
  - mean pixel fraction for winners vs losers
  - point-biserial correlation with the winner/loser label
  - Pearson correlation with raw win count
  - win rate when that color is the DOMINANT hue of the portrait

Outputs: roygbiv_analysis.json (per-fighter + summary tables).
"""

import json
import os
import re
import statistics

import numpy as np

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
BOT_LOSER_DIR = os.path.join(CACHE_DIR, "bot_losers")
COMP_PATH = os.path.join(CACHE_DIR, "comparison_analysis.json")
OUT_PATH = os.path.join(CACHE_DIR, "roygbiv_analysis.json")

# ---------------------------------------------------------------------------
# Hue binning — HSV hue degrees (0-360)
# ---------------------------------------------------------------------------
# Chromatic bins (hue ranges, degrees)
HUE_BINS = {
    "Red": [(345, 360), (0, 15)],
    "Orange": [(15, 45)],
    "Yellow": [(45, 70)],
    "Green": [(70, 165)],
    "Blue": [(165, 250)],
    "Indigo": [(250, 280)],
    "Violet": [(280, 345)],
}
ORDER = ["Red", "Orange", "Yellow", "Green", "Blue", "Indigo", "Violet", "White", "Black", "Gray"]

WHITE_S = 0.15   # max saturation for white
WHITE_V = 0.80   # min value for white
BLACK_V = 0.20   # max value for black
GRAY_S = 0.15    # max saturation for neutral/gray


def norm(name):
    return (name.lower().replace(" ", "").replace("'", "").replace(",", "")
            .replace("-", "").replace("[", "").replace("]", ""))


def find_portrait(name):
    """Lenient substring match against cached portrait filenames."""
    q = norm(name)
    for directory in (PORTRAIT_DIR, BOT_LOSER_DIR):
        if not os.path.isdir(directory):
            continue
        for f in sorted(os.listdir(directory)):
            if not f.endswith(".png"):
                continue
            fname_clean = re.sub(r'^[\w]+_\d+w_', '', f).replace('.png', '').replace('_', '').replace(' ', '').replace('-', '').lower()
            if q in fname_clean:
                return os.path.join(directory, f)
    return None


def color_fractions_arr(arr, mask=None):
    """Compute color fractions from a normalized RGB float array (0..1).

    mask: optional boolean array (same 2D shape as the image). When given,
    fractions are computed only over masked (foreground) pixels.
    """
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    if r.size == 0:
        return {c: 0.0 for c in ORDER}
    if mask is None:
        sel = np.ones(r.shape, dtype=bool)
    else:
        sel = mask.astype(bool)
    if sel.sum() == 0:
        return {c: 0.0 for c in ORDER}

    mx = np.maximum(np.maximum(r, g), b)
    delta = mx - np.minimum(np.minimum(r, g), b)
    sat = np.zeros_like(mx)
    np.divide(delta, np.maximum(mx, 1e-9), out=sat, where=mx > 1e-9)
    val = mx

    # Hue in degrees (0 for achromatic)
    hue = np.zeros_like(mx)
    chrom_mask = delta > 1e-6
    with np.errstate(divide='ignore', invalid='ignore'):
        hr = ((g - b) / np.maximum(delta, 1e-9)) % 6.0
        hg = ((b - r) / np.maximum(delta, 1e-9)) + 2.0
        hb = ((r - g) / np.maximum(delta, 1e-9)) + 4.0
    hue = np.where(chrom_mask & (mx == r), hr, hue)
    hue = np.where(chrom_mask & (mx == g), hg, hue)
    hue = np.where(chrom_mask & (mx == b), hb, hue)
    hue = (hue * 60.0) % 360.0

    # Chromatic bins require minimum saturation so pale pixels fall to
    # white/gray instead of being double-counted as a hue AND white.
    sat_mask = sat >= 0.15
    fracs = {}
    chromatic = np.zeros_like(chrom_mask)
    for color, ranges in HUE_BINS.items():
        m = np.zeros_like(chrom_mask)
        for lo, hi in ranges:
            m |= (hue >= lo) & (hue < hi) & chrom_mask & sat_mask
        chromatic |= m
        fracs[color] = float(np.mean(m[sel]))

    white = (sat < WHITE_S) & (val >= WHITE_V)
    black = val < BLACK_V
    gray = (~chromatic) & (~white) & (~black)

    fracs["White"] = float(np.mean(white[sel]))
    fracs["Black"] = float(np.mean(black[sel]))
    fracs["Gray"] = float(np.mean(gray[sel]))
    # Note: Black is value-based while chromatic bins are saturation-based, so
    # a dark saturated pixel (e.g. RGB 30,5,5) counts as BOTH Red and Black.
    # We keep dark-red as Red (semantically correct); buckets may sum to >1.0.
    return fracs


def color_fractions(path):
    """Return dict of color -> fraction of pixels in that bucket (0..1)."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return color_fractions_arr(arr)


def point_biserial(values, labels):
    """Correlation between continuous values and binary labels (1 = winner)."""
    vals = np.array(values, dtype=np.float64)
    labs = np.array(labels, dtype=np.float64)
    if vals.std() == 0:
        return 0.0
    return float(np.corrcoef(vals, labs)[0, 1])


def pearson(xs, ys):
    xs = np.array(xs, dtype=np.float64)
    ys = np.array(ys, dtype=np.float64)
    if xs.std() == 0 or ys.std() == 0:
        return 0.0
    return float(np.corrcoef(xs, ys)[0, 1])


def main():
    print("=" * 78, flush=True)
    print("  ROYGBIV + WHITE/BLACK COLOR ANALYSIS", flush=True)
    print("=" * 78, flush=True)

    with open(COMP_PATH, encoding="utf-8") as f:
        results = json.load(f).get("results", [])
    print(f"\n  Dataset: {len(results)} fighters (wins 0-14)", flush=True)

    # Analyze each fighter that has a cached portrait
    rows = []
    missing = []
    for r in results:
        path = find_portrait(r.get("name", ""))
        if not path:
            missing.append(r["name"])
            continue
        try:
            fracs = color_fractions(path)
        except Exception as e:
            print(f"  ERROR analyzing {r['name']}: {e}", flush=True)
            continue
        wins = r.get("wins", 0)
        dominant = max(ORDER, key=lambda c: fracs[c])
        rows.append({
            "name": r["name"],
            "wins": wins,
            "label": 1 if wins >= 5 else 0,
            "dominant": dominant,
            "fracs": fracs,
        })
    print(f"  Analyzed: {len(rows)} fighters ({len(missing)} portraits missing)", flush=True)

    winners = [x for x in rows if x["label"] == 1]
    losers = [x for x in rows if x["label"] == 0]
    print(f"  High-winners (5+): {len(winners)}   Low-winners (<=3): {len(losers)}", flush=True)

    # ------------------------------------------------------------------
    # Table 1: per-color means + correlations
    # ------------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 1 - COLOR FRACTION: WINNERS vs LOSERS", flush=True)
    print("=" * 78, flush=True)
    header = f"  {'Color':9s} {'Winners':>9s} {'Losers':>9s} {'Delta':>8s} {'pt-biserial':>12s} {'Pearson':>8s}"
    print(header, flush=True)
    print("  " + "-" * 74, flush=True)

    summary = {}
    for color in ORDER:
        w_vals = [x["fracs"][color] for x in winners]
        l_vals = [x["fracs"][color] for x in losers]
        if not w_vals or not l_vals:
            continue  # defensive: one side empty would crash statistics.mean
        w_mean = statistics.mean(w_vals)
        l_mean = statistics.mean(l_vals)
        all_vals = [x["fracs"][color] for x in rows]
        all_labels = [x["label"] for x in rows]
        all_wins = [x["wins"] for x in rows]
        pb = point_biserial(all_vals, all_labels)
        pc = pearson(all_vals, all_wins)
        delta = w_mean - l_mean
        marker = " <<<" if abs(pb) > 0.10 else ""
        print(f"  {color:9s} {w_mean:8.3f} {l_mean:8.3f} {delta:+7.3f} {pb:+11.3f} {pc:+7.3f}{marker}", flush=True)
        summary[color] = {
            "winners_mean": round(w_mean, 4),
            "losers_mean": round(l_mean, 4),
            "delta": round(delta, 4),
            "point_biserial": round(pb, 4),
            "pearson": round(pc, 4),
        }

    # ------------------------------------------------------------------
    # Table 2: dominant color -> win rate
    # ------------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 2 - DOMINANT COLOR -> WIN RATE", flush=True)
    print("=" * 78, flush=True)
    dom_stats = {}
    for color in ORDER:
        group = [x for x in rows if x["dominant"] == color]
        if not group:
            continue
        n_win = sum(x["label"] for x in group)
        rate = n_win / len(group)
        avg_wins = statistics.mean(x["wins"] for x in group)
        dom_stats[color] = {
            "count": len(group),
            "win_rate": round(rate, 3),
            "avg_wins": round(avg_wins, 2),
        }
        bar = "#" * int(rate * 30)
        print(f"  {color:9s} n={len(group):3d}  win_rate={rate:5.1%}  avg_wins={avg_wins:4.1f}  {bar}", flush=True)

    # ------------------------------------------------------------------
    # Table 3: strongest examples per color (the fighters themselves)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 3 - MOST EXTREME EXAMPLES PER COLOR (highest fraction)", flush=True)
    print("=" * 78, flush=True)
    examples = {}
    for color in ORDER:
        top = sorted(rows, key=lambda x: -x["fracs"][color])[:3]
        examples[color] = [
            {"name": x["name"], "wins": x["wins"], "frac": round(x["fracs"][color], 3)}
            for x in top
        ]
        line = ", ".join(f"{x['name'][:28]} ({x['wins']}w, {x['frac']:.2f})" for x in examples[color])
        print(f"  {color:9s} {line}", flush=True)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    out = {
        "summary": summary,
        "dominant_color_stats": dom_stats,
        "top_examples": examples,
        "analyzed_count": len(rows),
        "missing_count": len(missing),
        "missing_names": missing,
        "per_fighter": [
            {
                "name": x["name"],
                "wins": x["wins"],
                "label": x["label"],
                "dominant": x["dominant"],
                **x["fracs"],
            }
            for x in rows
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n  Saved: roygbiv_analysis.json ({len(rows)} fighters)", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
