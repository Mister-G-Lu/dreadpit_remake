#!/usr/bin/env python3
"""
Foreground-only ROYGBIV color analysis.

Dreadpit portraits all sit on a near-black background (~50%+ of pixels),
which dilutes the fighter's real colors. This script strips the background
via adaptive border flood-fill:

  1. Sample the border ring (top/bottom/left/right edges) and take its
     median color as the estimated background color.
  2. Flood-fill from ALL border pixels through pixels whose color is close
     to the background color (Euclidean distance < tol) — this is the
     background mask (near-black field, gradients, vignettes).
  3. Everything NOT flooded = foreground = the fighter itself.

Then it recomputes the ROYGBIV + white/black/gray fractions using ONLY the
foreground pixels (via roygbiv_analysis.color_fractions_arr with a mask),
and reports the same winner-vs-loser tables as the full-image analysis.

It also reports FOREGROUND COVERAGE (fraction of the image the fighter
occupies) as its own signal — a fighter that fills the frame vs a small
figure in a void is visually meaningful.

Outputs: foreground_roygbiv.json
"""

import json
import os
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from scipy.ndimage import binary_propagation, generate_binary_structure

import roygbiv_analysis as ra  # reuses HUE_BINS, ORDER, find_portrait, stats

CACHE_DIR = ra.CACHE_DIR
OUT_PATH = os.path.join(CACHE_DIR, "foreground_roygbiv.json")

BG_TOL = 0.12  # normalized Euclidean distance to bg median for flood fill
MAX_WORKERS = min(os.cpu_count() or 4, 8)


MIN_COVERAGE = 0.05  # below this the flood likely ate the fighter -> use full image


def estimate_background_mask(arr, tol=BG_TOL):
    """Flood-fill background mask from borders (vectorized via scipy).

    arr: (H, W, 3) float array in 0..1.
    Returns (bg_mask, coverage) where bg_mask is True for background pixels
    and coverage = fraction of NON-background (foreground) pixels.
    """
    h, w, _ = arr.shape
    # Border ring pixels
    ring = np.concatenate([
        arr[0, :, :], arr[-1, :, :],
        arr[:, 0, :], arr[:, -1, :],
    ], axis=0)
    bg_med = np.median(ring, axis=0)  # (3,)

    # Candidate background pixels: close to bg color, OR very dark AND close
    # to bg (the dual condition stops a dark fighter body far from the bg
    # color from being eaten as background).
    dist = np.sqrt(((arr - bg_med) ** 2).sum(axis=-1))
    is_dark = arr.max(axis=-1) < 0.18
    cand = (dist < tol) | (is_dark & (dist < 0.35))

    # Seed = border pixels that are candidates; propagate through candidates
    # with 8-connectivity (exact same flood fill as BFS, but vectorized C).
    struct = generate_binary_structure(2, 2)
    seed = np.zeros((h, w), dtype=bool)
    seed[0, :] = cand[0, :]
    seed[-1, :] = cand[-1, :]
    seed[:, 0] = cand[:, 0]
    seed[:, -1] = cand[:, -1]
    bg_mask = binary_propagation(seed, structure=struct, mask=cand)
    coverage = float((~bg_mask).mean())
    return bg_mask, coverage


def foreground_stats(arr):
    """Return per-pixel mean stats of the foreground (fighter) region."""
    bg_mask, coverage = estimate_background_mask(arr)
    if coverage < MIN_COVERAGE:
        # Flood likely ate a dark-bodied fighter touching the border —
        # fall back to the full image rather than report garbage.
        fg = np.ones(arr.shape[:2], dtype=bool)
        coverage = 1.0
    else:
        fg = ~bg_mask
    px = arr[fg]  # (N,3)
    avg_r, avg_g, avg_b = px.mean(axis=0)
    brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
    warmth = avg_r - avg_b
    return {
        "coverage": round(coverage, 4),
        "brightness": round(float(brightness), 4),
        "warmth": round(float(warmth), 4),
        "avg_r": round(float(avg_r), 4),
        "avg_g": round(float(avg_g), 4),
        "avg_b": round(float(avg_b), 4),
    }, fg


def analyze_one(job):
    """Analyze a single fighter portrait. Top-level for ProcessPool pickling.

    job: (name, wins, portrait_path). Returns a row dict, or a dict with
    'error' if the portrait couldn't be analyzed.
    """
    name, wins, path = job
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        arr = np.asarray(img).astype(np.float32) / 255.0
        fstats, fg = foreground_stats(arr)
        fracs = ra.color_fractions_arr(arr, fg)
        full = ra.color_fractions_arr(arr, None)
    except Exception as e:
        return {"name": name, "error": str(e)}
    dominant = max(ra.ORDER, key=lambda c: fracs[c])
    return {
        "name": name,
        "wins": wins,
        "label": 1 if wins >= 5 else 0,
        "dominant_fg": dominant,
        "coverage": fstats["coverage"],
        "fg_fracs": fracs,
        "full_fracs": full,
        "fg_stats": fstats,
    }


def main():
    print("=" * 78, flush=True)
    print("  FOREGROUND-ONLY ROYGBIV (fighter extracted from black bg)", flush=True)
    print("=" * 78, flush=True)

    with open(ra.COMP_PATH, encoding="utf-8") as f:
        results = json.load(f).get("results", [])
    print(f"\n  Dataset: {len(results)} fighters", flush=True)
    print(f"  Workers: {MAX_WORKERS}  (Ctrl+C to abort, progress printed below)", flush=True)

    # Collect jobs (name, wins, portrait_path)
    jobs = []
    missing = []
    for r in results:
        path = ra.find_portrait(r.get("name", ""))
        if not path:
            missing.append(r["name"])
            continue
        jobs.append((r["name"], r.get("wins", 0), path))

    # Parallel analysis across CPU cores
    rows = []
    errors = []
    done = 0
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(analyze_one, j): j for j in jobs}
        for fut in as_completed(futs):
            done += 1
            res = fut.result()
            if "error" in res:
                errors.append((res["name"], res["error"]))
            else:
                rows.append(res)
            if done % 25 == 0 or done == len(jobs):
                print(f"  Progress: {done}/{len(jobs)} analyzed", flush=True)

    for name, err in errors:
        print(f"  ERROR analyzing {name[:40]}: {err}", flush=True)
    print(f"  Analyzed: {len(rows)} fighters ({len(missing)} portraits missing, "
          f"{len(errors)} failed)", flush=True)

    winners = [x for x in rows if x["label"] == 1]
    losers = [x for x in rows if x["label"] == 0]
    print(f"  High-winners (5+): {len(winners)}   Low-winners (<=3): {len(losers)}", flush=True)

    # ----------------------------------------------------------------
    # Table 1: foreground-only color fractions, winners vs losers
    # ----------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 1 - FOREGROUND-ONLY COLOR FRACTIONS", flush=True)
    print("  (background stripped — fighter alone)", flush=True)
    print("=" * 78, flush=True)
    header = f"  {'Color':9s} {'Winners':>9s} {'Losers':>9s} {'Delta':>8s} {'pt-biserial':>12s} {'Pearson':>8s}"
    print(header, flush=True)
    print("  " + "-" * 74, flush=True)

    summary = {}
    for color in ra.ORDER:
        w_vals = [x["fg_fracs"][color] for x in winners]
        l_vals = [x["fg_fracs"][color] for x in losers]
        if not w_vals or not l_vals:
            continue
        w_mean = statistics.mean(w_vals)
        l_mean = statistics.mean(l_vals)
        all_vals = [x["fg_fracs"][color] for x in rows]
        all_labels = [x["label"] for x in rows]
        all_wins = [x["wins"] for x in rows]
        pb = ra.point_biserial(all_vals, all_labels)
        pc = ra.pearson(all_vals, all_wins)
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

    # ----------------------------------------------------------------
    # Table 2: foreground dominant color -> win rate
    # ----------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 2 - DOMINANT COLOR (FG) -> WIN RATE", flush=True)
    print("=" * 78, flush=True)
    dom_stats = {}
    for color in ra.ORDER:
        group = [x for x in rows if x["dominant_fg"] == color]
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

    # ----------------------------------------------------------------
    # Table 3: full-image vs foreground comparison (signal shift)
    # ----------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 3 - FULL-IMAGE vs FOREGROUND (signal change)", flush=True)
    print("=" * 78, flush=True)
    print(f"  {'Color':9s} {'Full pb':>9s} {'FG pb':>9s} {'Full mean':>10s} {'FG mean':>10s}", flush=True)
    print("  " + "-" * 60, flush=True)
    for color in ra.ORDER:
        f_all = [x["full_fracs"][color] for x in rows]
        g_all = [x["fg_fracs"][color] for x in rows]
        f_pb = ra.point_biserial(f_all, [x["label"] for x in rows])
        g_pb = ra.point_biserial(g_all, [x["label"] for x in rows])
        f_mean = statistics.mean(f_all)
        g_mean = statistics.mean(g_all)
        shift = " <<<" if abs(g_pb) > abs(f_pb) + 0.02 else ""
        print(f"  {color:9s} {f_pb:+9.3f} {g_pb:+9.3f} {f_mean:9.3f} {g_mean:10.3f}{shift}", flush=True)

    # ----------------------------------------------------------------
    # Table 4: foreground coverage vs wins
    # ----------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 4 - FOREGROUND COVERAGE (fighter size in frame)", flush=True)
    print("=" * 78, flush=True)
    cov_vals = [x["coverage"] for x in rows]
    cov_pb = ra.point_biserial(cov_vals, [x["label"] for x in rows])
    cov_pc = ra.pearson(cov_vals, [x["wins"] for x in rows])
    print(f"  Coverage pt-biserial: {cov_pb:+.3f}   Pearson: {cov_pc:+.3f}", flush=True)
    print(f"  Winners mean coverage: {statistics.mean([x['coverage'] for x in winners]):.3f}   "
          f"Losers: {statistics.mean([x['coverage'] for x in losers]):.3f}", flush=True)
    print("\n  Coverage quartiles -> win rate:", flush=True)
    covs = sorted(rows, key=lambda x: x["coverage"])
    n_q = len(covs) // 4
    for i in range(4):
        q = covs[i * n_q:(i + 1) * n_q] if i < 3 else covs[i * n_q:]
        if not q:
            continue
        rate = sum(x["label"] for x in q) / len(q)
        lo, hi = q[0]["coverage"], q[-1]["coverage"]
        print(f"    Q{i+1}: coverage {lo:.2f}-{hi:.2f}  n={len(q):3d}  win_rate={rate:5.1%}", flush=True)

    # ----------------------------------------------------------------
    # Table 5: examples — biggest fighters, smallest fighters
    # ----------------------------------------------------------------
    print("\n" + "=" * 78, flush=True)
    print("  TABLE 5 - EXTREMES: biggest & smallest fighters in frame", flush=True)
    print("=" * 78, flush=True)
    biggest = sorted(rows, key=lambda x: -x["coverage"])[:6]
    smallest = sorted(rows, key=lambda x: x["coverage"])[:6]
    print("  Largest (fills frame):", flush=True)
    for x in biggest:
        print(f"    {x['name'][:44]:44s} {x['coverage']:.2f} cov  {x['wins']}w  dom={x['dominant_fg']}", flush=True)
    print("  Smallest (tiny figure):", flush=True)
    for x in smallest:
        print(f"    {x['name'][:44]:44s} {x['coverage']:.2f} cov  {x['wins']}w  dom={x['dominant_fg']}", flush=True)

    # ----------------------------------------------------------------
    # Save
    # ----------------------------------------------------------------
    out = {
        "summary": summary,
        "dominant_color_stats": dom_stats,
        "coverage": {
            "point_biserial": round(cov_pb, 4),
            "pearson": round(cov_pc, 4),
            "winners_mean": round(statistics.mean([x['coverage'] for x in winners]), 4),
            "losers_mean": round(statistics.mean([x['coverage'] for x in losers]), 4),
        },
        "analyzed_count": len(rows),
        "missing_count": len(missing),
        "missing_names": missing,
        "per_fighter": [
            {
                "name": x["name"],
                "wins": x["wins"],
                "label": x["label"],
                "dominant_fg": x["dominant_fg"],
                "coverage": x["coverage"],
                "fg_brightness": x["fg_stats"]["brightness"],
                "fg_warmth": x["fg_stats"]["warmth"],
                **{f"fg_{k}": v for k, v in x["fg_fracs"].items()},
                **{f"full_{k}": v for k, v in x["full_fracs"].items()},
            }
            for x in rows
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n  Saved: foreground_roygbiv.json ({len(rows)} fighters)", flush=True)
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
