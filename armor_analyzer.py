#!/usr/bin/env python3
"""
Armor Analyzer — Pixel-Level Armor Detection from Fighter Portraits.

Uses pure numpy image processing (no ML, no scipy) to detect:
  - METAL COVERAGE: % of pixels that look like metal/armor
  - ARMOR TYPE: plate (sharp edges) vs chainmail (textured) vs smooth vs organic
  - COVERAGE GAPS: potential joint/exposure weak points
  - SURFACE QUALITY: polished vs battle-worn vs spiked
"""

import json
import os
import sys
import re
import statistics
from collections import Counter

import numpy as np
from PIL import Image

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")


# =========================================================================
# Vectorized metal detection (pure numpy — fast!)
# =========================================================================

def analyze_metal_vectorized(img_array):
    """Detect metal/armor pixels using vectorized numpy operations."""
    r = img_array[:, :, 0].astype(np.float32)
    g = img_array[:, :, 1].astype(np.float32)
    b = img_array[:, :, 2].astype(np.float32)

    brightness = (r + g + b) / 3.0
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    denom = np.maximum(max_c, 1.0)
    saturation = (max_c - min_c) / denom

    # Standard metal: low saturation, mid brightness
    metal = (saturation < 0.25) & (brightness > 30) & (brightness < 200)

    # Tinted metal: slightly higher saturation, some color
    tinted = (saturation < 0.35) & (brightness > 40) & (brightness < 180) & ~metal

    # Very dark metal (dark iron, obsidian)
    dark_metal = (brightness > 15) & (brightness <= 30) & (saturation < 0.30)

    metal_mask = metal | tinted | dark_metal
    total_pixels = img_array.shape[0] * img_array.shape[1]
    metal_coverage = np.mean(metal_mask) * 100

    # Classify metal types
    metal_pixels = metal_mask.sum()
    if metal_pixels == 0:
        dominant = "none"

    # Warm metal: R > G and R > B (gold, bronze, copper)
    warm = metal_mask & (r > g + 15) & (r > b + 10) & (brightness > 40)
    # Cool metal: B > R (silver, blue steel)
    cool = metal_mask & (b > r + 5) & (brightness > 40)
    # Dark metal: brightness < 50
    dark = metal_mask & (brightness < 50)
    # Standard gray metal: everything else
    gray = metal_mask & ~warm & ~cool & ~dark

    types = {
        "gold/brass": np.sum(warm),
        "silver/blue_steel": np.sum(cool),
        "dark_iron": np.sum(dark),
        "steel/gray": np.sum(gray),
    }
    dominant = max(types, key=lambda k: types[k])

    return {
        "mask": metal_mask,
        "coverage": round(metal_coverage, 1),
        "dominant": dominant,
        "types": {k: round(v / max(metal_pixels, 1) * 100, 1) for k, v in types.items()},
    }


# =========================================================================
# Edge detection (pure numpy Sobel — no scipy needed)
# =========================================================================

def sobel_edge_density(gray):
    """Manual Sobel edge detection using pure numpy."""
    # Sobel kernels
    Kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    Ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)

    # Convolve manually (simple but effective)
    from scipy.signal import convolve2d
    sx = convolve2d(gray, Kx, mode='same', boundary='symm')
    sy = convolve2d(gray, Ky, mode='same', boundary='symm')

    edges = np.hypot(sx, sy)
    edge_mean = float(np.mean(edges))
    edge_std = float(np.std(edges))

    # Edge density
    threshold = edge_mean + edge_std
    density = float(np.mean(edges > threshold)) * 100

    # High-percentile edge sharpness
    top10 = np.percentile(edges, 90)
    edge_sharp = float(np.mean(edges[edges > top10]))

    return {
        "edge_density": round(density, 1),
        "edge_mean": round(edge_mean, 1),
        "edge_sharpness": round(edge_sharp, 1),
    }


def laplacian_texture(gray):
    """Laplacian texture energy — high = rough/chainmail, low = smooth."""
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    from scipy.signal import convolve2d
    lap = convolve2d(gray, kernel, mode='same', boundary='symm')
    texture_energy = float(np.std(lap))

    # Block variance for texture uniformity
    h, w = gray.shape
    blocks = []
    for y in range(0, h - 8, 8):
        for x in range(0, w - 8, 8):
            block = gray[y:y+8, x:x+8]
            blocks.append(float(np.var(block)))

    uniformity = float(np.mean(blocks)) if blocks else 0
    return {
        "texture_energy": round(texture_energy, 1),
        "texture_uniformity": round(uniformity, 1),
    }


# =========================================================================
# Coverage analysis
# =========================================================================

def body_coverage(img_array, metal_mask):
    """Metal coverage in the center 70% of the frame (where the body is)."""
    h, w = img_array.shape[:2]
    y_s, y_e = int(h * 0.15), int(h * 0.85)
    x_s, x_e = int(w * 0.15), int(w * 0.85)

    center = metal_mask[y_s:y_e, x_s:x_e]
    return round(float(np.mean(center)) * 100, 1)


def grid_coverage(metal_mask):
    """4x4 grid of armor coverage for joint gap detection."""
    h, w = metal_mask.shape[:2]
    y_s, y_e = int(h * 0.2), int(h * 0.8)
    x_s, x_e = int(w * 0.2), int(w * 0.8)

    cell_h = max((y_e - y_s) // 4, 1)
    cell_w = max((x_e - x_s) // 4, 1)

    grid_vals = []
    for gy in range(4):
        for gx in range(4):
            cy1 = y_s + gy * cell_h
            cy2 = min(cy1 + cell_h, h)
            cx1 = x_s + gx * cell_w
            cx2 = min(cx1 + cell_w, w)
            cell = metal_mask[cy1:cy2, cx1:cx2]
            cov = float(np.mean(cell)) * 100
            grid_vals.append(round(cov, 0))

    # Joint gaps: low-coverage cells adjacent to high-coverage cells
    gap_count = 0
    for i in range(16):
        if grid_vals[i] < 20:
            row, col = i // 4, i % 4
            neighbors = []
            if row > 0: neighbors.append(grid_vals[(row-1)*4 + col])
            if row < 3: neighbors.append(grid_vals[(row+1)*4 + col])
            if col > 0: neighbors.append(grid_vals[row*4 + col - 1])
            if col < 3: neighbors.append(grid_vals[row*4 + col + 1])
            if any(n > 40 for n in neighbors):
                gap_count += 1

    return {"grid": grid_vals, "gap_count": gap_count}


# =========================================================================
# Armor type classification
# =========================================================================

def classify_armor(metal_cov, body_cov, edge_density, texture_energy):
    """Classify armor type from visual metrics."""
    scores = {
        "heavy_plate": {
            "score": 0,
            "desc": "Thick plate — high coverage, sharp edges, rigid",
        },
        "smooth_plate": {
            "score": 0,
            "desc": "Polished smooth armor — sleek, reflective",
        },
        "chainmail_scale": {
            "score": 0,
            "desc": "Chainmail or scale — flexible but textured",
        },
        "partial_light": {
            "score": 0,
            "desc": "Partial armor — some protection, some exposure",
        },
        "organic_none": {
            "score": 0,
            "desc": "No armor or organic carapace",
        },
    }

    if metal_cov > 30:
        scores["heavy_plate"]["score"] = edge_density * 2 + body_cov
        scores["smooth_plate"]["score"] = (30 - max(edge_density, 10)) + body_cov
        scores["chainmail_scale"]["score"] = texture_energy * 3 + metal_cov
    elif metal_cov > 10:
        scores["partial_light"]["score"] = metal_cov + body_cov
        scores["chainmail_scale"]["score"] = texture_energy * 2 + metal_cov / 2
    else:
        scores["organic_none"]["score"] = 30 - edge_density + (30 - metal_cov)

    best = max(scores, key=lambda k: scores[k]["score"])
    conf = min(scores[best]["score"] / 50 * 100, 100)

    # Modifiers for armor quality
    modifiers = []
    if edge_density > 30:
        modifiers.append("spiked/angular")
    if edge_density < 15 and metal_cov > 30:
        modifiers.append("polished")

    return best, scores[best]["desc"] + (f" ({', '.join(modifiers)})" if modifiers else ""), round(conf, 0)


# =========================================================================
# Weak point analysis
# =========================================================================

def analyze_weak_points(metal_cov, body_cov, edge_density, texture_energy, gap_count, armor_type):
    """Generate weak point analysis based on armor stats."""
    points = []

    if gap_count > 2:
        points.append(f"{gap_count} exposed joint areas — precision attacks exploit gaps")

    if body_cov < 15 and metal_cov > 5:
        points.append("Low body coverage — armor is sparse, wide target area")

    if metal_cov > 40 and edge_density > 30:
        points.append("Heavy rigid plate — crushing blows deform armor, joints restrict mobility")

    if metal_cov > 30 and edge_density < 15:
        points.append("Smooth polished armor — glancing blows slide off, but focused punctures may penetrate")

    if armor_type == "chainmail_scale":
        points.append("Flexible armor — resistant to slashing, vulnerable to blunt force and piercing")

    if armor_type == "organic_none":
        points.append("No armor — every hit is unmitigated, relies on endurance/regeneration")

    if metal_cov > 50 and body_cov > 60:
        points.append("Extremely heavy armor — slow movement, heat buildup, stamina drain")

    if edge_density > 25 and metal_cov < 20:
        points.append("Sharp/spiky silhouette but minimal armor — intimidation over protection")

    if not points:
        points.append("Balanced protection — no obvious weak points detected")

    return points


def extract_wins_from_filename(fname):
    """Extract win count from filename like '6w_Big.png' or 'high_6w_Big.png'."""
    m = re.search(r'(?:^|_)(\d+)w_', fname)
    if m:
        return int(m.group(1)), fname.split('_', 2)[-1].replace('.png', '')
    return None, fname.replace('.png', '')


def extract_name_from_filename(fname):
    """Clean up filename to get fighter name."""
    # Remove prefix like '6w_' or 'high_6w_' or 'low_0w_'
    name = re.sub(r'^[\w]+_\d+w_', '', fname)
    name = re.sub(r'^[\w]+_', '', name)
    name = name.replace('.png', '')
    # Restore special characters
    name = name.replace('_', ' ')
    name = name.strip()
    return name


# =========================================================================
# Main
# =========================================================================

def main():
    sep = "=" * 72
    print(sep)
    print("  ARMOR ANALYZER - Pixel-Level Protection Detection")
    print(sep)

    from scipy import signal as scipy_signal
    globals()['convolve2d'] = scipy_signal.convolve2d

    # Build file list
    if not os.path.exists(PORTRAIT_DIR):
        print(f"ERROR: No portrait directory at {PORTRAIT_DIR}")
        return

    all_files = sorted([f for f in os.listdir(PORTRAIT_DIR) if f.endswith('.png')])
    print(f"  Found {len(all_files)} portraits")

    # Load comparison data for names/BLIP
    comp_path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    comp_map = {}
    if os.path.exists(comp_path):
        with open(comp_path) as f:
            comp = json.load(f)
        for r in comp.get("results", []):
            comp_map[r.get("name", "").lower()] = r

    print("\n[1/4] Analyzing armor...")
    all_results = []
    for i, fname in enumerate(all_files):
        fpath = os.path.join(PORTRAIT_DIR, fname)
        try:
            img = Image.open(fpath).convert("RGB")
            img_array = np.array(img)
        except Exception as e:
            continue

        # Extract name and wins from filename
        wins, raw_name = extract_wins_from_filename(fname)
        if wins is None:
            continue
        name = extract_name_from_filename(fname)

        # Try to match to comparison data for canonical name + BLIP
        matched_name = name
        blip_text = ""
        for cname_lower, r in comp_map.items():
            cname_clean = cname_lower.replace(" ", "").replace("'", "").replace(",", "")
            name_clean = name.lower().replace(" ", "").replace("'", "").replace(",", "")
            if cname_clean == name_clean or cname_clean in name_clean or name_clean in cname_clean:
                matched_name = r.get("name", name)
                blip_text = r.get("blip", "")
                if r.get("wins", 0) != wins:
                    wins = r.get("wins", wins)
                break

        # --- Analysis ---
        gray = np.mean(img_array, axis=2).astype(np.float32)
        metal_result = analyze_metal_vectorized(img_array)
        metal_mask = metal_result["mask"]
        edges = sobel_edge_density(gray)
        texture = laplacian_texture(gray)
        body_cov = body_coverage(img_array, metal_mask)
        grid = grid_coverage(metal_mask)
        armor_type, armor_desc, armor_conf = classify_armor(
            metal_result["coverage"], body_cov,
            edges["edge_density"], texture["texture_energy"]
        )
        weak_points = analyze_weak_points(
            metal_result["coverage"], body_cov,
            edges["edge_density"], texture["texture_energy"],
            grid["gap_count"], armor_type
        )

        all_results.append({
            "name": matched_name,
            "wins": wins,
            "blip": blip_text[:80],
            "metal_coverage": metal_result["coverage"],
            "body_coverage": body_cov,
            "dominant_metal": metal_result["dominant"],
            "edge_density": edges["edge_density"],
            "texture_energy": texture["texture_energy"],
            "armor_type": armor_type,
            "armor_desc": armor_desc,
            "armor_conf": armor_conf,
            "gap_count": grid["gap_count"],
            "grid": grid["grid"],
            "weak_points": weak_points,
        })

        if (i + 1) % 60 == 0:
            print(f"  [{i+1}/{len(all_files)}] analyzed...")

    print(f"  Analyzed {len(all_results)} portraits")

    # =================================================================
    # Results table
    # =================================================================
    print(f"\n\n{sep}")
    print("  [2/4] TOP 60 FIGHTERS - Armor Report (sorted by wins)")
    print(sep)

    by_wins = sorted(all_results, key=lambda x: (-x["wins"], -x["metal_coverage"]))
    print(f"  {'Name':30s} {'W':>3s} {'Metal%':>7s} {'Body%':>7s} {'Edge':>5s} {'Tex':>5s} {'Armor Type':20s} {'Weakness':>30s}")
    print(f"  {'-'*30} {'-'*3} {'-'*7} {'-'*7} {'-'*5} {'-'*5} {'-'*20} {'-'*30}")

    for r in by_wins[:60]:
        wp = r["weak_points"][0][:28] if r["weak_points"] else ""
        marker = ""
        if "BIG" in r["name"].upper(): marker = " << BIG"
        elif "SIMO" in r["name"].upper(): marker = " << SIMO"
        elif "JESTER" in r["name"].upper() or "TOON" in r["name"].upper(): marker = " << JESTER"
        print(f"  {r['name'][:30]:30s} {r['wins']:>3d} {r['metal_coverage']:>6.1f}% {r['body_coverage']:>6.1f}% {r['edge_density']:>4.1f} {r['texture_energy']:>4.1f} {r['armor_type']:20s} {wp:30s}{marker}")

    # =================================================================
    # Deep dives
    # =================================================================
    print(f"\n\n{sep}")
    print("  [3/4] DEEP DIVES - Selected Fighters")
    print(sep)

    deep_dives = ["Big", "SIMO", "Irek", "Eldritch Elemechtal", "Black Entity", "Tigran"]
    for q in deep_dives:
        matches = [r for r in all_results if q.upper() in r["name"].upper()]
        if not matches:
            continue
        r = matches[0]
        print(f"\n  {'='*60}")
        print(f"  --- {r['name'][:45]:45s} ({r['wins']} wins)")
        print(f"  {'='*60}")
        print(f"  BLIP:      {r.get('blip', 'N/A')}")
        print(f"  Metal:     {r['metal_coverage']:.1f}% of image")
        print(f"  Body:      {r['body_coverage']:.1f}% of body area")
        print(f"  Metal:     {r['dominant_metal']}")
        print(f"  Edges:     {r['edge_density']:.1f} (sharpness)")
        print(f"  Texture:   {r['texture_energy']:.1f} (coarseness)")
        print(f"  Joints:    {r['gap_count']} exposed gaps")
        print(f"\n  ARMOR:     {r['armor_type']}")
        print(f"             {r['armor_desc']}")
        print(f"  Conf:      {r['armor_conf']:.0f}%")
        print(f"\n  WEAKNESSES:")
        for wp in r["weak_points"][:3]:
            print(f"    - {wp}")

        g = r.get("grid", [])
        if g:
            print(f"  Coverage grid (4x4, body center):")
            print(f"    {' | '.join(f'{g[i]:3.0f}' for i in range(4))}")
            print(f"    {' | '.join(f'{g[i]:3.0f}' for i in range(4,8))}")
            print(f"    {' | '.join(f'{g[i]:3.0f}' for i in range(8,12))}")
            print(f"    {' | '.join(f'{g[i]:3.0f}' for i in range(12,16))}")
            print(f"    (0=none, 100=full coverage)")

    # =================================================================
    # Meta stats
    # =================================================================
    print(f"\n\n{sep}")
    print("  [4/4] ARMOR META STATS")
    print(sep)

    high = [r for r in all_results if r["wins"] >= 5]
    low = [r for r in all_results if r["wins"] <= 3]

    h_metal = statistics.mean([r["metal_coverage"] for r in high])
    h_body = statistics.mean([r["body_coverage"] for r in high])
    h_edge = statistics.mean([r["edge_density"] for r in high])
    l_metal = statistics.mean([r["metal_coverage"] for r in low]) if low else 0
    l_body = statistics.mean([r["body_coverage"] for r in low]) if low else 0
    l_edge = statistics.mean([r["edge_density"] for r in low]) if low else 0

    print(f"\n  {'Metric':25s} {'Winners':>12s} {'Losers':>12s} {'Delta':>10s}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
    print(f"  {'Metal coverage %':25s} {h_metal:>11.1f}% {l_metal:>11.1f}% {h_metal-l_metal:>+9.1f}%")
    print(f"  {'Body coverage %':25s} {h_body:>11.1f}% {l_body:>11.1f}% {h_body-l_body:>+9.1f}%")
    print(f"  {'Edge sharpness':25s} {h_edge:>11.1f} {l_edge:>11.1f} {h_edge-l_edge:>+9.1f}")

    type_counts = Counter()
    for r in high:
        type_counts[r["armor_type"]] += 1
    print(f"\n  Armor type distribution ({len(high)} winners):")
    for t, c in type_counts.most_common():
        print(f"    {t:20s}: {c:3d} ({c/len(high)*100:5.1f}%)")

    # What the outliers show
    print(f"\n  OUTLIER ARMOR PROFILES:")
    for q in ["Big", "SIMO", "Irek"]:
        matches = [r for r in all_results if q.upper() in r["name"].upper()]
        if matches:
            r = matches[0]
            print(f"    {r['name'][:30]:30s} Type={r['armor_type']:18s} Metal={r['metal_coverage']:5.1f}% Body={r['body_coverage']:5.1f}% Joints={r['gap_count']}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
