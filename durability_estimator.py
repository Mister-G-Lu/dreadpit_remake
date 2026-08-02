#!/usr/bin/env python3
"""
Durability Estimator — Multi-Signal Armor & Protection Analysis.

Combines pixel-level surface analysis with Florence-2 vision captions
to estimate durability (0-10) consistently across all fighter portraits.

Key signals:
  - Edge density (sharp edges = plate armor)
  - Surface uniformity (smooth = polished armor, rough = organic)
  - Brightness variance (bimodal = shiny metal on dark surface)
  - Specular highlight density (metal reflections)
  - Low-saturation coverage (metallic surfaces even when colored)
  - Body-region coverage (what % of the character is protected)
  - Florence-2 keyword hits (armor, metal, plate, etc.)
  - Color-material patterns (gold, dark iron, obsidian indicators)

Calibrated against known reference fighters.
"""

import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "0"  # suppress warnings

import numpy as np
from PIL import Image

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(CACHE_DIR, "big_portraits")
VENV_PYTHON = os.path.join(CACHE_DIR, "..", "florence_setup", "venv", "Scripts", "python.exe")


# =========================================================================
# Reference fighter calibration anchors
# These are fighters whose durability we KNOW from the community/judges:
# =========================================================================
REFERENCE_ANCHORS = {
    "tigran":            {"durability": 9.0, "notes": "Immensely durable tight perfect armor"},
    "black entity":      {"durability": 8.0, "notes": "Sleek obsidian-like armor/carapace"},
    "eldritch elemechtal": {"durability": 8.0, "notes": "Mecha/robot — full metal body"},
    "the dreadpit itself": {"durability": 7.0, "notes": "Dragon — scales, organic durability"},
    "bearer of the cosmos": {"durability": 7.5, "notes": "Robot with sphere"},
    "big":               {"durability": 0.5, "notes": "Business suit, zero protection"},
    "simo the unseen":   {"durability": 2.0, "notes": "Cloth uniform + helmet only"},
    "irek":              {"durability": 4.0, "notes": "Toon — hard to assess cartoon durability"},
    "dread, the unending": {"durability": 7.0, "notes": "Demonic, likely durable"},
}


# Anchor lookup helper: use EXACT substring match in the correct direction
# (fighter name contains anchor key, not the other way around)
def find_anchor(name_lower):
    """Find reference anchor for a fighter name. Returns (key, anchor) or (None, None)."""
    for ak, av in REFERENCE_ANCHORS.items():
        if ak in name_lower:
            return ak, av
    return None, None


# =========================================================================
# Signal 1: Edge & Surface Analysis
# =========================================================================

def analyze_surface(img_array):
    """Analyze edge density, surface uniformity, and texture patterns (vectorized)."""
    from scipy.ndimage import sobel, uniform_filter

    gray = np.mean(img_array, axis=2).astype(np.float32)

    # Vectorized Sobel edge detection via scipy
    edges_x = sobel(gray, axis=1)  # horizontal gradient
    edges_y = sobel(gray, axis=0)  # vertical gradient
    edges = np.hypot(edges_x, edges_y)  # magnitude

    h, w = gray.shape

    # Crop to center 60% (body region)
    body_edges = edges[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]

    # Edge metrics — absolute threshold (fixed at 25 edge magnitude)
    # This prevents the "always 25%" artifact from percentile-based thresholds
    edge_threshold = 25.0  # absolute edge magnitude threshold
    edge_density = float(np.mean(body_edges > edge_threshold)) * 100
    edge_mean = float(np.mean(body_edges))
    # Also compute higher threshold for strong edges (deep creases in armor)
    strong_edge_density = float(np.mean(body_edges > 50.0)) * 100
    edge_std = float(np.std(body_edges))

    # High edge density suggests plate armor
    edge_score = min(edge_density / 40.0, 1.0)  # 40%+ density = max

    # Surface uniformity: low variance = smooth surface (armor-like)
    # Divide body into 16x16 blocks, measure variance within each
    block_vars = []
    bh, bw = body_edges.shape
    for y in range(0, bh - 16, 16):
        for x in range(0, bw - 16, 16):
            block = body_edges[y:y+16, x:x+16]
            block_vars.append(float(np.var(block)))

    if block_vars:
        texture_uniformity = float(np.mean(block_vars))
        # Low texture variance = smooth armor. Higher = rough/organic.
        # Use inverse ratio so score never clips to 0 for reasonable inputs.
        # texture_uniformity ~50-100 for smooth plate, ~500-2000 for organic.
        texture_score = max(0, min(1.0 - (texture_uniformity / (texture_uniformity + 200)), 1.0))
    else:
        texture_uniformity = 0
        texture_score = 0.5

    return {
        "edge_density": round(edge_density, 1),
        "strong_edge_density": round(strong_edge_density, 1),
        "edge_mean": round(edge_mean, 1),
        "edge_std": round(edge_std, 1),
        "edge_score": round(edge_score, 3),
        "texture_uniformity": round(texture_uniformity, 1),
        "texture_score": round(texture_score, 3),
    }


# =========================================================================
# Signal 2: Brightness & Reflection Analysis
# =========================================================================

def analyze_brightness(img_array):
    """Analyze brightness distribution for metal/armor indicators."""
    bright = np.mean(img_array, axis=2).astype(np.float32)
    h, w = bright.shape

    # Body region
    body = bright[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]

    b_mean = float(np.mean(body))
    b_std = float(np.std(body))
    b_median = float(np.median(body))

    # Specular highlights: pixels much brighter than mean
    highlight_threshold = b_mean + b_std * 1.8
    highlights = float(np.mean((body > highlight_threshold) & (body < 240)) * 100)

    # Bimodal distribution = metal surface (dark + bright highlights)
    low = float(np.mean(body < b_mean - b_std * 0.5) * 100)
    high = float(np.mean(body > b_mean + b_std * 0.5) * 100)
    # A good balance of dark and bright areas = metallic surface
    bimodal = min(low, high) / max(low, high, 0.01)
    bimodal_score = min(bimodal * 3, 1.0)  # Scale up

    # Contrast score: high std relative to mean = more reflective
    contrast_ratio = b_std / max(b_mean, 1.0)
    contrast_score = min(contrast_ratio * 3, 1.0)

    # Very dark regions (< 20 brightness) suggest obsidian/dark metal
    very_dark = float(np.mean(body < 20) * 100)
    dark_score = min(very_dark / 60.0, 1.0)

    return {
        "brightness_mean": round(b_mean, 1),
        "brightness_std": round(b_std, 1),
        "brightness_median": round(b_median, 1),
        "highlights_pct": round(highlights, 1),
        "low_pct": round(low, 1),
        "high_pct": round(high, 1),
        "bimodal_score": round(bimodal_score, 3),
        "contrast_score": round(contrast_score, 3),
        "dark_score": round(dark_score, 3),  # obsidian/dark metal indicator
    }


# =========================================================================
# Signal 3: Color-Material Analysis (catches colored armor)
# =========================================================================

def analyze_color_material(img_array):
    """Analyze color patterns to detect armor materials beyond gray metal."""
    h, w = img_array.shape[:2]
    body = img_array[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]
    r, g, b = body[:,:,0].astype(np.float32), body[:,:,1].astype(np.float32), body[:,:,2].astype(np.float32)
    bright = (r + g + b) / 3.0

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    denom = np.maximum(max_c, 1.0)
    sat = (max_c - min_c) / denom

    # --- Expanded metal/armor detection ---

    # 1. Standard gray metal: low sat, mid-high bright
    gray_metal = (sat < 0.25) & (bright > 30) & (bright < 200)

    # 2. Dark metal / obsidian: very dark but metallic (low sat)
    dark_metal = (bright > 10) & (bright <= 35) & (sat < 0.30)

    # 3. Gold/brass: warm tones, golden range
    gold = (sat >= 0.15) & (sat < 0.55) & (bright > 40) & (bright < 180) & \
           (r > g + 10) & (g > b + 5) & (r > b)

    # 4. Red/crimson metal: warm saturated with metallic look
    red_metal = (sat >= 0.3) & (sat < 0.65) & (r > g + 20) & (r > b + 20) & (bright > 30)

    # 5. Blue steel: cool saturated but metallic-looking
    blue_metal = (sat >= 0.2) & (sat < 0.55) & (b > r + 10) & (bright > 25) & (bright < 160)

    # 6. Bronze/copper: warm mid-saturation
    bronze = (sat >= 0.2) & (sat < 0.5) & (r > g) & (g > b) & (bright > 25) & (bright < 150)

    # 7. Tinted metal: broader range with metallic sheen pattern

    # 8. Warm dark metal — catches Tigran-style "dark but warm-toned armor"
    # Tigran has: bright 15-60, sat 0.25-0.60, r > g + 10, g > b
    # This is obsidian/volcanic/dark bronze plate with warm undertones
    # Note: texture check is done in estimate_durability() where colored_metal_texture is available
    warm_dark_metal = (bright > 15) & (bright <= 60) & (sat >= 0.25) & (sat < 0.60) & \
                      (r > g + 10) & (g > b)

    combined = gray_metal | dark_metal | gold | red_metal | blue_metal | bronze | warm_dark_metal

    # Coverage %
    total_pixels = body.shape[0] * body.shape[1]
    metal_coverage = float(np.sum(combined)) / total_pixels * 100

    # By type
    type_breakdown = {
        "gray_metal": float(np.sum(gray_metal)) / total_pixels * 100,
        "dark_metal": float(np.sum(dark_metal)) / total_pixels * 100,
        "gold_brass": float(np.sum(gold)) / total_pixels * 100,
        "red_metal": float(np.sum(red_metal)) / total_pixels * 100,
        "warm_dark": float(np.sum(warm_dark_metal)) / total_pixels * 100,
        "blue_steel": float(np.sum(blue_metal)) / total_pixels * 100,
        "bronze": float(np.sum(bronze)) / total_pixels * 100,
    }

    # Dominant material class
    dominant = max(type_breakdown, key=lambda k: type_breakdown[k])

    # Body coverage
    body_cov = metal_coverage  # % of the center frame that's "armor"

    # Also check how "organic-looking" the color is
    # Organic skin/flesh tends to have specific saturation ranges
    organic_colors = (sat > 0.3) & (sat < 0.8) & (bright > 40) & (bright < 180)
    organic_pct = float(np.sum(organic_colors & ~combined)) / total_pixels * 100

    return {
        "metal_coverage": round(metal_coverage, 1),
        "body_coverage": round(body_cov, 1),
        "dominant_metal": dominant,
        "metal_types": type_breakdown,
        "organic_pct": round(organic_pct, 1),
        "metal_score": round(min(metal_coverage / 40.0, 1.0), 3),
    }


# =========================================================================
# Signal 4: Florence-2 Caption Keyword Analysis
# =========================================================================

FLORENCE_CACHE = {}  # Cache Florence-2 results within session

def get_florence_caption(name, fpath):
    """Get Florence-2 detailed caption (cached)."""
    cache_key = (name, fpath)
    if cache_key in FLORENCE_CACHE:
        return FLORENCE_CACHE[cache_key]

    if not os.path.exists(VENV_PYTHON):
        return ""

    # Launch subprocess for this single image (may be slow but accurate)
    inline = f'''
import json, sys
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM

model_id = "microsoft/Florence-2-base-ft"
device = "cpu"
print("  Loading...", flush=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, attn_implementation="eager")
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

img = Image.open(r"{fpath}").convert("RGB")
task = "<MORE_DETAILED_CAPTION>"
inputs = processor(text=task, images=img, return_tensors="pt").to(device)
with torch.no_grad():
    ids = model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"], max_new_tokens=250, num_beams=3)
out = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
print("---FLORENCE_DETAILED_START---")
print(out[:600])
print("---FLORENCE_DETAILED_END---")
'''

    try:
        proc = subprocess.run(
            [VENV_PYTHON, "-c", inline],
            capture_output=True, text=True, timeout=120,
        )
        stdout = proc.stdout
        start = stdout.find("---FLORENCE_DETAILED_START---")
        end = stdout.find("---FLORENCE_DETAILED_END---")
        if start != -1 and end != -1:
            caption = stdout[start + len("---FLORENCE_DETAILED_START---"):end].strip()
            FLORENCE_CACHE[cache_key] = caption
            return caption
    except Exception:
        pass
    return ""


def analyze_florence_armor_kws(detailed_caption):
    """Score armor/durability keywords in Florence-2 caption."""
    if not detailed_caption:
        return {"armor_kw_score": 0.5, "armor_kws": [], "neg_kws": [], "structural_kws": []}

    dl = detailed_caption.lower()

    # Armor/material keywords (direct evidence)
    armor_kws = {
        "armor": 1.0, "plate": 0.9, "helmet": 0.9, "knight": 0.7,
        "metal": 1.0, "iron": 1.0, "steel": 1.0, "bronze": 0.8,
        "gold": 0.6, "silver": 0.8, "chainmail": 0.9, "shield": 0.8,
        "suit of armor": 1.0, "mecha": 0.7, "robot": 0.5,
        "mechanical": 0.6, "cyborg": 0.5, "armored": 1.0,
    }

    # Structural/organic keywords (negative evidence = no armor)
    negative_kws = {
        "cloth": -0.4, "robe": -0.5, "naked": -1.0,
        "bare": -0.8, "exposed": -0.6, "suit": -0.3,
        "outfit": -0.3, "uniform": -0.4, "skin": -0.6,
        "fur": -0.5, "feather": -0.4, "flesh": -0.8,
    }

    hits = []
    neg_hits = []
    score = 0.0
    for kw, val in armor_kws.items():
        if kw in dl:
            hits.append(kw)
            score = max(score, val)

    for kw, val in negative_kws.items():
        if kw in dl:
            neg_hits.append(kw)
            score += val  # negative adjustment

    # Also check for structural descriptors
    structural = {
        "wings": 0.3, "horn": 0.1, "tail": 0.1,
        "fire": 0.1, "flame": 0.1, "glowing": 0.2,
        "dark": 0.1, "black": 0.1,
    }
    struct_hits = [k for k in structural if k in dl]

    # Clamp
    score = max(-0.5, min(1.0, score))

    return {
        "armor_kw_score": round(score, 3),
        "armor_kws": hits,
        "neg_kws": neg_hits,
        "structural_kws": struct_hits,
    }


# =========================================================================
# Signal 5: BLIP + Existing Data Integration
# =========================================================================

def load_comparison_data():
    """Load existing BLIP and pixel data."""
    path = os.path.join(CACHE_DIR, "comparison_analysis.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    results = {}
    for r in data.get("results", []):
        name = r.get("name", "").lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
        results[name] = r
    return results


def analyze_blip_armor(blip_text):
    """Extract durability hints from BLIP description."""
    if not blip_text:
        return 0.5
    bt = blip_text.lower()

    # BLIP keywords that hint at armor
    blip_armor_kws = ["knight", "armor", "robot", "mecha", "gundam", "suit",
                       "warrior", "demon", "dragon", "monster"]
    hits = sum(1 for k in blip_armor_kws if k in bt)

    # BLIP negative indicators (squishy)
    blip_weak_kws = ["man", "woman", "person", "human", "cartoon"]
    weak_hits = sum(1 for k in blip_weak_kws if k in bt)

    if hits > 0 and weak_hits == 0:
        return 0.8
    elif hits > 0 and weak_hits > 0:
        return 0.6
    elif hits == 0 and weak_hits > 0:
        return 0.3
    return 0.5


# =========================================================================
# Signal 6: Coverage + Joint Gap Analysis
# =========================================================================

def analyze_coverage_patterns(img_array, metal_mask):
    """Analyze where armor is concentrated and find weak points."""
    h, w = img_array.shape[:2]

    # 4x4 grid of the body area (40%-80% of frame, centered)
    y_s, y_e = int(h * 0.3), int(h * 0.7)
    x_s, x_e = int(w * 0.25), int(w * 0.75)

    cell_h = max((y_e - y_s) // 4, 1)
    cell_w = max((x_e - x_s) // 4, 1)

    grid = []
    for gy in range(4):
        row = []
        for gx in range(4):
            cy1 = y_s + gy * cell_h
            cy2 = min(cy1 + cell_h, h)
            cx1 = x_s + gx * cell_w
            cx2 = min(cx1 + cell_w, w)
            cell = metal_mask[cy1:cy2, cx1:cx2]
            cov = float(np.mean(cell)) * 100
            row.append(round(cov, 0))
        grid.append(row)

    # Count gaps: low-coverage cells (<15%) adjacent to high-coverage (>35%)
    gaps = 0
    for r in range(4):
        for c in range(4):
            if grid[r][c] < 15:
                neighbors = []
                if r > 0: neighbors.append(grid[r-1][c])
                if r < 3: neighbors.append(grid[r+1][c])
                if c > 0: neighbors.append(grid[r][c-1])
                if c < 3: neighbors.append(grid[r][c+1])
                if any(n > 35 for n in neighbors):
                    gaps += 1

    # Evenness of armor distribution
    all_vals = [grid[r][c] for r in range(4) for c in range(4)]
    evenness = 1.0 - (np.std(all_vals) / max(np.mean(all_vals), 1)) if all_vals else 0
    evenness = max(0, min(1.0, evenness))

    return {
        "grid": grid,
        "gap_count": gaps,
        "evenness": round(evenness, 3),
    }


# =========================================================================
# DURABILITY ESTIMATOR — Combine All Signals
# =========================================================================

def estimate_durability(fighter_name, portrait_path,
                        florence_caption="", blip_text="",
                        comparison_data=None):
    """Estimate durability (0-10) by combining all analysis signals."""

    # Load image
    img = Image.open(portrait_path).convert("RGB")
    img_array = np.array(img).astype(np.float32)

    # --- Signal 1: Surface ---
    surface = analyze_surface(img_array)

    # --- Signal 2: Brightness/Reflection ---
    brightness = analyze_brightness(img_array)

    # --- Signal 3: Color-Material Detection ---
    material = analyze_color_material(img_array)

    # Metal mask from color-material for coverage analysis
    # ---- Texture-aware metal detection ----
    # First, compute edge density map from the full image analysis
    # Then ONLY classify a pixel as 'metal' if it's in a region with metallic properties
    r, g_b, b_b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
    bright = (r + g_b + b_b) / 3.0
    max_c = np.maximum(np.maximum(r, g_b), b_b)
    min_c = np.minimum(np.minimum(r, g_b), b_b)
    sat = (max_c - min_c) / np.maximum(max_c, 1.0)

    from scipy.ndimage import uniform_filter, binary_dilation
    h_img, w_img = img_array.shape[:2]

    # Vectorized local variance (5x5) via summed-area approach
    # E[x^2] - E[x]^2 gives variance in each 5x5 block
    bright_sq = bright ** 2
    mean_bright = uniform_filter(bright, size=5, mode='constant')
    mean_bright_sq = uniform_filter(bright_sq, size=5, mode='constant')
    local_var = mean_bright_sq - mean_bright ** 2
    # Metal surfaces have moderate local variance (not too high, not too low)
    metal_texture = (local_var > 100) & (local_var < 2000)  # raised min to 100 to reject snow/fabric

    # Create character region mask: inner 50% where the fighter actually is
    # This prevents backgrounds (sky, snow, fire) from being counted as armor
    cy_s, cy_e = int(h_img * 0.25), int(h_img * 0.75)
    cx_s, cx_e = int(w_img * 0.25), int(w_img * 0.75)
    char_mask = np.zeros((h_img, w_img), dtype=bool)
    char_mask[cy_s:cy_e, cx_s:cx_e] = True

    # Gray/silver metal: strict — requires metallic texture
    gray_metal = (sat < 0.25) & (bright > 30) & (bright < 200) & metal_texture

    # Dark metal / obsidian: needs local variance (surface reflectivity)
    # Expanded upper bound to 45 for Black Entity's obsidian armor (ambient-lit dark metal)
    dark_metal = (bright > 10) & (bright <= 45) & (sat < 0.30) & metal_texture

    # Colored metals: MUST also pass a 'specular neighbor' check
    # A colored pixel is 'metal-like' if adjacent pixels have metallic texture
    # This prevents fire/background from being counted as armor

    # Compute specular highlight mask (bright pixels that look like reflections)
    local_mean_bright = uniform_filter(bright, size=3, mode='constant')
    specular = (bright > local_mean_bright * 1.5) & (bright > 40) & (bright < 245)

    # Dilate specular mask so colored pixels near highlights get counted
    specular_region = binary_dilation(specular, structure=np.ones((3, 3)), iterations=1)

    # Colored metals: require EITHER metallic texture OR proximity to specular highlights
    colored_metal_texture = metal_texture | specular_region

    # Gold/brass: warm tones (cautious — only with texture evidence)
    gold = (sat >= 0.15) & (sat < 0.50) & (bright > 40) & (bright < 170) & \
           (r > g_b + 15) & (g_b > b_b + 5) & colored_metal_texture & char_mask

    # Red/crimson metal: very restrictive — unlikely to catch fire
    red_metal = (sat >= 0.35) & (sat < 0.65) & (r > g_b + 30) & (r > b_b + 30) & \
                (bright > 25) & (bright < 140) & colored_metal_texture & char_mask

    # Blue steel: cool metallic — REQUIRES character region + strong blue dominance
    # Stricter b > r threshold (30 instead of 15) to reject blue fabric (SIMO's uniform)
    blue_metal = (sat >= 0.20) & (sat < 0.50) & (b_b > r + 30) & (b_b > g_b + 5) & \
                 (bright > 25) & (bright < 150) & colored_metal_texture & char_mask

    # Bronze/copper: warm mid-range
    bronze = (sat >= 0.20) & (sat < 0.45) & (r > g_b + 10) & (g_b > b_b) & \
             (bright > 25) & (bright < 140) & colored_metal_texture & char_mask

    # Warm dark metal also restricted to character region
    # Use relaxed texture threshold (local_var > 30) because Tigran's polished armor
    # is very smooth and may not reach the default metal_texture threshold of 100
    warm_dark_texture = (local_var > 30) & (local_var < 2000) | specular_region
    warm_dark_metal_est = (bright > 15) & (bright <= 60) & (sat >= 0.25) & (sat < 0.60) & \
                          (r > g_b + 10) & (g_b > b_b) & warm_dark_texture & char_mask

    metal_mask = gray_metal | dark_metal | gold | red_metal | blue_metal | bronze | warm_dark_metal_est

    # --- Signal 4: Coverage ---
    coverage = analyze_coverage_patterns(img_array, metal_mask)

    # --- Signal 5: Florence-2 keywords ---
    florence_kws = analyze_florence_armor_kws(florence_caption)

    # --- Signal 6: BLIP ---
    blip_score = analyze_blip_armor(blip_text)

    # =====================================================================
    # COMPUTE WEIGHTED DURABILITY SCORE
    # =====================================================================

    # Factor 1: Metal body coverage (40% of body protected = 1.0)
    cov_ratio = min(material["metal_coverage"] / 40.0, 1.0)

    # Factor 2: Edge density — plate armor indicator
    edge_factor = surface["edge_score"]

    # Factor 3: Surface texture — smooth = polished armor
    texture_factor = surface["texture_score"]

    # Factor 4: Brightness contrast — reflective = metallic
    contrast_factor = brightness["contrast_score"]

    # Factor 5: Bimodal brightness — metallic reflections
    bimodal_factor = brightness["bimodal_score"]

    # Factor 6: Dark metal indicator (obsidian, dark iron)
    dark_factor = brightness["dark_score"]

    # Factor 7: Florence-2 keyword score
    florence_factor = florence_kws["armor_kw_score"]

    # Factor 8: Coverage evenness — uniform protection
    evenness_factor = coverage["evenness"]

    # Factor 9: Gap penalty — exposed joints reduce durability
    gap_penalty = min(coverage["gap_count"] * 0.08, 0.5)

    # Factor 10: BLIP indicator
    blip_factor = blip_score

    # ---- Weights ----
    # Coverage and edge density are strongest signals
    w_cov = 0.20
    w_edge = 0.15
    w_texture = 0.10
    w_contrast = 0.10
    w_bimodal = 0.05
    w_dark = 0.05
    w_florence = 0.15
    w_evenness = 0.05
    w_blip = 0.10

    raw_score = (
        w_cov * cov_ratio +
        w_edge * edge_factor +
        w_texture * texture_factor +
        w_contrast * contrast_factor +
        w_bimodal * bimodal_factor +
        w_dark * dark_factor +
        w_florence * florence_factor +
        w_evenness * evenness_factor -
        gap_penalty * 0.15 +  # gap penalty applies after max
        w_blip * blip_factor
    )

    # Clamp and scale to 0-10
    raw_score = max(0.0, min(1.0, raw_score))
    durability = round(raw_score * 10, 1)

    return {
        "durability": durability,
        "raw_score": round(raw_score, 3),
        "signals": {
            "coverage_pct": material["metal_coverage"],
            "body_coverage": material["body_coverage"],
            "dominant_metal": material["dominant_metal"],
            "edge_density": surface["edge_density"],
            "edge_score": edge_factor,
            "texture_score": texture_factor,
            "contrast_score": contrast_factor,
            "bimodal_score": bimodal_factor,
            "dark_metal_score": dark_factor,
            "florence_armor_kw_score": florence_factor,
            "florence_kws_hit": florence_kws["armor_kws"],
            "florence_neg_kws": florence_kws["neg_kws"],
            "blip_score": blip_factor,
            "coverage_evenness": evenness_factor,
            "gap_count": coverage["gap_count"],
            "coverage_grid": coverage["grid"],
        },
        "metal_types": material["metal_types"],
    }


# =========================================================================
# Find portrait by name
# =========================================================================

def find_portrait(name_query):
    """Find a portrait file by name substring."""
    q = name_query.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
    best, best_len = None, 999
    for f in sorted(os.listdir(PORTRAIT_DIR)):
        if not f.endswith('.png'):
            continue
        fname_clean = re.sub(r'^[\w]+_\d+w_', '', f).replace('.png', '').replace('_', '').replace(' ', '').lower()
        if q in fname_clean:
            if best is None or abs(len(fname_clean) - len(q)) < best_len:
                best = f
                best_len = abs(len(fname_clean) - len(q))
    return os.path.join(PORTRAIT_DIR, best) if best else None


# =========================================================================
# Calibrate against known reference fighters
# =========================================================================

def calibrate_against_anchors(results, comparison_data):
    """Compare computed durability against known anchors and report deviation."""
    print(f"\n{'='*72}")
    print(f"  CALIBRATION CHECK — Comparing vs Known Reference Fighters")
    print(f"{'='*72}")
    print(f"  {'Fighter':40s} {'Computed':>9s} {'Expected':>9s} {'Delta':>8s}")
    print(f"  {'-'*40} {'-'*9} {'-'*9} {'-'*8}")

    cal_errors = []
    for r in results:
        name_lower = r["name"].lower()
        ak, found_anchor = find_anchor(name_lower)
        if found_anchor:
            delta = r["durability"] - found_anchor["durability"]
            cal_errors.append(abs(delta))
            marker = ""
            if delta < -1.5: marker = " ** UNDER-estimated"
            elif delta > 1.5: marker = " ** OVER-estimated"
            print(f"  {r['name'][:40]:40s} {r['durability']:>8.1f}  {found_anchor['durability']:>6.1f}   {delta:+>+6.1f}  {marker}")
            print(f"  {'':40s} {found_anchor['notes']:50s}")

    if cal_errors:
        mae = sum(cal_errors) / len(cal_errors)
        print(f"\n  Mean Absolute Calibration Error: {mae:.2f} points")

    # Estimate bias correction
    if cal_errors:
        bias_list = []
        for r in results:
            ak, found = find_anchor(r["name"].lower())
            if found:
                bias_list.append(r["durability"] - found["durability"])
        if bias_list:
            bias = sum(bias_list)
            n_anchors = len(bias_list)
        if n_anchors > 0:
            avg_bias = bias / n_anchors
            print(f"  Estimated bias: {avg_bias:+.2f} (add to correction factor)")
            print(f"  NOTE: Computed scores are {'over' if avg_bias > 0 else 'under'}-estimating by {abs(avg_bias):.1f} points on average")
            return avg_bias
    return 0.0


# =========================================================================
# MAIN
# =========================================================================

def main():
    sep = "=" * 72
    print(sep)
    print("  DURABILITY ESTIMATOR — Multi-Signal Armor & Protection Analysis")
    print(sep)

    # Load comparison data
    comparison_data = load_comparison_data()

    # Define fighters to analyze
    TARGETS = [
        # Known anchors
        "Tigran", "Black Entity", "Eldritch Elemechtal", "The Dreadpit itself",
        "Big", "SIMO THE UNSEEN", "Irek'Ailth The Toon Jester",
        # Other key fighters
        "Bearer of the cosmos", "Calamity Breaker: Apex",
        "Mecha dragon - Hiryu", "Abyss Regent",
        "Dread, the unending", "GL6",
        "Straxar the destruction incarnate", "Ragnaros, the Firelord of Magma",
        "Dominus Prime", "Dr. Manhattan",
        "GODBREAKER", "The Being From [Redacted]",
        "Void Monarch", "Tengen Toppa Gurren Laggan",
        "ArroganceFour", "Cosm",
        "BH Beater", "Forever",
        # Outliers
        "Vaelstrix", "Mecha Dragon - Champion",
        "Universe breaker", "Scorch the nuclear snake",
        "Aurelion", "Nonamebot",
    ]

    print(f"\n[1/4] Finding portraits for {len(TARGETS)} fighters...")
    found_targets = []
    for t in TARGETS:
        fpath = find_portrait(t)
        if fpath:
            found_targets.append((t, fpath))
        else:
            print(f"  WARNING: No portrait for '{t}'")

    print(f"  Found {len(found_targets)}/{len(TARGETS)} portraits")

    # =================================================================
    # Run Florence-2 on ALL targets (batch)
    # =================================================================
    print(f"\n[2/4] Running Florence-2 batch analysis on {len(found_targets)} targets...")

    florence_results = {}

    # Check if we can use cached Florence results from armor_florence.py output
    cache_path = os.path.join(CACHE_DIR, "florence_analysis_results.json")
    use_cache = os.path.exists(cache_path)
    if use_cache:
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            if isinstance(cached, list) and len(cached) > 0:
                for item in cached:
                    name_key = item.get("name", "").lower().replace(" ", "")
                    florence_results[name_key] = item.get("detailed", "")
                print(f"  Loaded {len(cached)} cached Florence-2 results")
                use_cache = True
        except Exception:
            use_cache = False

    if not use_cache:
        # Batch through Florence-2 in a single subprocess
        image_list = [(name, path) for name, path in found_targets]
        image_list_json = json.dumps(image_list)

        inline_code = '''
import json, sys
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM

model_id = "microsoft/Florence-2-base-ft"
device = "cpu"
print("  Loading Florence-2...", flush=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, attn_implementation="eager")
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
print("  Loaded. Analyzing...", flush=True)

targets = IMAGE_LIST_PLACEHOLDER
results = []
for name, path in targets:
    try:
        img = Image.open(path).convert("RGB")
        task = "<MORE_DETAILED_CAPTION>"
        inputs = processor(text=task, images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            ids = model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"], max_new_tokens=250, num_beams=3)
        out = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        results.append({"name": name, "detailed": out[:600]})
        print(f"  {name[:35]:35s} DONE", flush=True)
    except Exception as e:
        results.append({"name": name, "detailed": ""})
        print(f"  {name[:35]:35s} ERROR: {e}", flush=True)

print("---FLORENCE_RESULTS_START---", flush=True)
print(json.dumps(results), flush=True)
print("---FLORENCE_RESULTS_END---", flush=True)
'''.replace("IMAGE_LIST_PLACEHOLDER", image_list_json)

        print("  (Florence-2 loading ~10s, then ~3s per fighter...)")
        proc = subprocess.run(
            [VENV_PYTHON, "-c", inline_code],
            capture_output=True, text=True, timeout=900,
        )

        if proc.returncode != 0:
            print(f"  ERROR: Florence-2 crashed: {proc.stderr[:300]}")
        else:
            start_m = "---FLORENCE_RESULTS_START---"
            end_m = "---FLORENCE_RESULTS_END---"
            s_idx = proc.stdout.find(start_m)
            e_idx = proc.stdout.find(end_m)
            if s_idx != -1 and e_idx != -1:
                json_str = proc.stdout[s_idx + len(start_m):e_idx].strip()
                try:
                    florence_batch = json.loads(json_str)
                    for item in florence_batch:
                        name_key = item.get("name", "").lower().replace(" ", "")
                        florence_results[name_key] = item.get("detailed", "")
                    print(f"  Got {len(florence_batch)} Florence-2 results")
                    # Cache
                    with open(cache_path, "w") as f:
                        json.dump(florence_batch, f, indent=1)
                except json.JSONDecodeError:
                    print(f"  ERROR: Could not parse Florence results")

    # =================================================================
    # Run durability estimation on each fighter
    # =================================================================
    print(f"\n[3/4] Estimating durability for {len(found_targets)} fighters...")

    results = []
    for i, (name, fpath) in enumerate(found_targets):
        name_key = name.lower().replace(" ", "").replace("'", "").replace(",", "").replace("-", "").replace("[", "").replace("]", "")
        florence_cap = florence_results.get(name_key, "")

        # Get BLIP from comparison data
        comp = comparison_data.get(name_key, {})
        blip_text = comp.get("blip", "")

        # Estimate durability
        result = estimate_durability(name, fpath, florence_cap, blip_text, comparison_data)
        result["name"] = name
        result["wins"] = comp.get("wins", "?")
        result["blip"] = blip_text[:80]

        results.append(result)

        if (i + 1) % 5 == 0:
            print(f"  [{i+1}/{len(found_targets)}] estimated...")

    # Sort by durability (descending)
    results.sort(key=lambda x: -x["durability"])

    # =================================================================
    # PRINT RESULTS TABLE
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  [4/4] DURABILITY REPORT — Sorted by Score")
    print(sep)

    header = (f"  {'Rank':>4s} {'Fighter':35s} {'Win':>3s} "
              f"{'Dur':>4s} {'Metal%':>7s} {'Edge':>5s} "
              f"{'CovSc':>5s} {'FlrSc':>5s} {'Type':14s}")
    print(header)
    print(f"  {'-'*4} {'-'*35} {'-'*3} {'-'*4} {'-'*7} {'-'*5} {'-'*5} {'-'*5} {'-'*14}")

    for i, r in enumerate(results):
        s = r["signals"]
        marker = ""
        nu = r["name"].upper()
        if "BIG" in nu: marker = " << BIG"
        elif "SIMO" in nu: marker = " << SIMO"
        elif "JESTER" in nu or "TOON" in nu: marker = " << JESTER"

        dom = r["metal_types"]
        if dom:
            dom_type = max(dom, key=lambda k: dom[k])
        else:
            dom_type = "?"
        if dom.get(dom_type, 0) < 3:
            dom_type = "minimal"

        print(f"  {i+1:>4d} {r['name'][:35]:35s} {str(r['wins']):>3s} "
              f"{r['durability']:>4.1f} "
              f"{s['coverage_pct']:>6.1f}% "
              f"{s['edge_density']:>4.1f} "
              f"{s['edge_score']:>4.2f} "
              f"{s['florence_armor_kw_score']:>4.2f} "
              f"{dom_type:14s}{marker}")

    # =================================================================
    # DEEP DIVES — Show signal breakdown for key fighters
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  SIGNAL BREAKDOWN — Key Fighters")
    print(sep)

    deep_dives = ["Tigran", "Black Entity", "Big", "SIMO", "Irek",
                   "Eldritch Elemechtal", "Bearer of the cosmos",
                   "Ragnaros", "Dominus Prime", "Dr. Manhattan"]

    for q in deep_dives:
        matches = [r for r in results if q.upper() in r["name"].upper()]
        if not matches:
            continue
        r = matches[0]
        s = r["signals"]
        fk = s["florence_kws_hit"]
        fn = s["florence_neg_kws"]

        print(f"\n  {'='*60}")
        print(f"  {r['name'][:50]:50s} — Durability: {r['durability']}/10  ({r['wins']} wins)")
        print(f"  {'='*60}")

        print(f"  COMPOSITE SIGNALS:")
        print(f"    Coverage:       {s['coverage_pct']:6.1f}% metal ({s['dominant_metal']})")
        print(f"    Edge density:   {s['edge_density']:6.1f}%  (score: {s['edge_score']:.2f})")
        print(f"    Texture score:  {s['texture_score']:6.2f}  (smooth=high)")
        print(f"    Contrast score: {s['contrast_score']:6.2f}  (reflective=high)")
        print(f"    Dark metal:     {s['dark_metal_score']:6.2f}")
        print(f"    Evenness:       {s['coverage_evenness']:6.2f}")
        print(f"    Gap exposure:   {s['gap_count']} vulnerable joints")

        print(f"  LANGUAGE SIGNALS:")
        print(f"    Florence KWs:   {fk[:5]}")
        if fn:
            print(f"    Negative KWs:   {fn[:5]}")
        print(f"    Florence score: {s['florence_armor_kw_score']:.2f}")
        print(f"    BLIP score:     {s['blip_score']:.2f}")
        print(f"    BLIP text:      {r['blip'][:70]}")

        # Coverage grid
        grid = s["coverage_grid"]
        if grid:
            print(f"  COVERAGE GRID (body center, 4x4):")
            for row in grid:
                print(f"    {' | '.join(f'{c:3.0f}' for c in row)}")
            print(f"    (0=exposed, 100=armored)")

        # Anchor comparison
        nl = r["name"].lower()
        ak, ref = find_anchor(nl)
        if ref:
            delta = r["durability"] - ref["durability"]
            print(f"  CALIBRATION: Expected={ref['durability']:.1f} "
                  f"Delta={delta:+.1f} {ref['notes']}")

    # =================================================================
    # CALIBRATION
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  CALIBRATION — Comparing Against Reference Fighters")
    print(sep)
    bias = calibrate_against_anchors(results, comparison_data)

    # Apply calibration bias to all scores (only if bias > 0.5 to avoid cosmetic changes)
    if abs(bias) > 0.5:
        print(f"\n  Applying bias correction: +{-bias:.1f} points to all scores")
        for r in results:
            r["calibrated_durability"] = round(max(0.0, min(10.0, r["durability"] - bias)), 1)
    else:
        print(f"\n  Bias too small ({bias:+.2f}) to apply — using raw scores")
        for r in results:
            r["calibrated_durability"] = r["durability"]

    # Print calibrated table
    print(f"\n\n{sep}")
    print(f"  CALIBRATED DURABILITY SCORES — Bias Corrected")
    print(sep)
    header = (f"  {'Rank':>4s} {'Fighter':35s} {'Win':>3s} "
              f"{'CalDur':>6s} {'RawDur':>6s} {'Metal%':>7s} {'Edge':>5s}")
    print(header)
    print(f"  {'-'*4} {'-'*35} {'-'*3} {'-'*6} {'-'*6} {'-'*7} {'-'*5}")

    # Re-sort by calibrated durability
    results.sort(key=lambda x: -x["calibrated_durability"])

    for i, r in enumerate(results):
        s = r["signals"]
        marker = ""
        nu = r["name"].upper()
        if "BIG" in nu: marker = " << OUTLIER"
        elif "SIMO" in nu: marker = " << OUTLIER"
        elif "JESTER" in nu or "TOON" in nu: marker = " << OUTLIER"
        print(f"  {i+1:>4d} {r['name'][:35]:35s} {str(r['wins']):>3s} "
              f"{r['calibrated_durability']:>5.1f}  {r['durability']:>4.1f}  "
              f"{s['coverage_pct']:>6.1f}%  {s['edge_density']:>4.1f}{marker}")

    # =================================================================
    # GROUP AVERAGES (using calibrated)
    # =================================================================
    print(f"\n\n{sep}")
    print(f"  GROUP AVERAGES (Calibrated)")
    print(sep)

    high = [r for r in results if isinstance(r["wins"], int) and r["wins"] >= 7]
    mid = [r for r in results if isinstance(r["wins"], int) and 5 <= r["wins"] <= 6]

    if high:
        avg_dur_h = statistics.mean([r["calibrated_durability"] for r in high])
        avg_cov_h = statistics.mean([r["signals"]["coverage_pct"] for r in high])
    else:
        avg_dur_h = avg_cov_h = 0

    if mid:
        avg_dur_m = statistics.mean([r["calibrated_durability"] for r in mid])
        avg_cov_m = statistics.mean([r["signals"]["coverage_pct"] for r in mid])
    else:
        avg_dur_m = avg_cov_m = 0

    print(f"\n  {'Group':25s} {'n':>4s} {'Avg CalDur':>10s} {'Avg RawDur':>10s}")
    print(f"  {'-'*25} {'-'*4} {'-'*10} {'-'*10}")
    print(f"  {'Top winners (7+ wins)':25s} {len(high):>4d} {avg_dur_h:>9.1f}  {statistics.mean([r['durability'] for r in high]):>7.1f}")
    print(f"  {'Mid winners (5-6 wins)':25s} {len(mid):>4d} {avg_dur_m:>9.1f}  {statistics.mean([r['durability'] for r in mid]):>7.1f}")

    print(f"\n  Done.")





if __name__ == "__main__":
    main()
