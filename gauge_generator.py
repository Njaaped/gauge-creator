# gauge_generator.py
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
import json
from datetime import datetime

# --- Absolute Path Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# Helper functions (Unchanged)
# ==============================================================================
def pil_to_cv2(pil_image):
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)

def overlay_image_alpha(background, overlay, x, y):
    x, y = int(x), int(y)
    h_overlay, w_overlay, _ = overlay.shape
    y1, y2 = max(0, y), min(background.shape[0], y + h_overlay)
    x1, x2 = max(0, x), min(background.shape[1], x + w_overlay)
    overlay_y1, overlay_x1 = max(0, -y), max(0, -x)
    overlay_y2, overlay_x2 = overlay_y1 + (y2 - y1), overlay_x1 + (x2 - x1)
    if y2 <= y1 or x2 <= x1: return
    alpha = overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2, 3] / 255.0
    beta = 1.0 - alpha
    for c in range(3):
        background[y1:y2, x1:x2, c] = (alpha * overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2, c] +
                                       beta * background[y1:y2, x1:x2, c])

def draw_text_with_outline_pil(text, font, fill_color, outline_color, stroke_width):
    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    try:
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
    except AttributeError:
        w, h = dummy_draw.textsize(text, font=font); bbox = (0, 0, w, h)
    text_w = bbox[2] - bbox[0] + (stroke_width * 2)
    text_h = bbox[3] - bbox[1] + (stroke_width * 2)
    img = Image.new('RGBA', (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x, y = stroke_width - bbox[0], stroke_width - bbox[1]
    for i in range(-stroke_width, stroke_width + 1):
        for j in range(-stroke_width, stroke_width + 1):
            if i*i + j*j >= stroke_width*stroke_width: continue
            draw.text((x + i, y + j), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill_color)
    return img

# ==============================================================================
# Main video creation function for the web app
# ==============================================================================
def create_gauge_video(json_path, output_path, progress_callback=None):
    """
    Reads sliced data and generates video using a caching strategy for high performance.
    """
    # --- 1. MASTER CONFIGURATION ---
    VIDEO_FPS = 30
    FRAME_WIDTH = 1280
    FRAME_HEIGHT = 720
    BODY_WEIGHT_KG = 65.0
    BG_COLOR_CV = (255, 0, 0)
    TEXT_FILL_COLOR_PIL = (255, 255, 255, 255)
    TEXT_OUTLINE_COLOR_PIL = (0, 0, 0, 255)
    TEXT_OUTLINE_WIDTH = 5
    FONT_PATH = os.path.join(SCRIPT_DIR, "assets/CartoonVibes-Regular.otf")
    LIGHTNING_ICON_PATH = os.path.join(SCRIPT_DIR, "assets/lightning.png")
    HEART_ICON_PATH = os.path.join(SCRIPT_DIR, "assets/heart.png")
    LAYOUT_START_X = 100
    LAYOUT_START_Y = 100
    LINE_SPACING = 30
    ICON_SPACING = 20
    ICON_TARGET_HEIGHT = 90
    LINE_HEIGHT_XL = 130
    LINE_HEIGHT_L = 100
    HEART_ANIMATION_STRENGTH = 0.15

    # --- 2. FONT & ICON LOADING ---
    try:
        FONT_XL = ImageFont.truetype(FONT_PATH, 120)
        FONT_L = ImageFont.truetype(FONT_PATH, 90)
        lightning_icon_orig = Image.open(LIGHTNING_ICON_PATH).convert("RGBA")
        heart_icon_orig = Image.open(HEART_ICON_PATH).convert("RGBA")
        def resize_icon(icon, new_height):
            aspect_ratio = icon.width / icon.height
            new_width = int(new_height * aspect_ratio)
            return icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
        LIGHTNING_ICON = resize_icon(lightning_icon_orig, ICON_TARGET_HEIGHT)
        HEART_ICON = resize_icon(heart_icon_orig, ICON_TARGET_HEIGHT)
    except FileNotFoundError as e:
        raise RuntimeError(f"Asset file not found: {e.filename}.") from e

    # --- 3. DATA LOADING & INTERPOLATION (Unchanged) ---
    with open(json_path, 'r') as f:
        trackpoints = json.load(f)
    if not trackpoints:
        raise ValueError("Input JSON file is empty.")
    power = [tp.get('power', 0) for tp in trackpoints]
    hr = [tp.get('hr', 0) for tp in trackpoints]
    num_points = len(trackpoints)
    start_dt, end_dt = datetime.fromisoformat(trackpoints[0]['time']), datetime.fromisoformat(trackpoints[-1]['time'])
    duration_seconds = (end_dt - start_dt).total_seconds()
    num_interpolated = int(duration_seconds * VIDEO_FPS) if duration_seconds > 0 else 1
    interpolated_data = {}
    orig_x, interp_x = np.linspace(0, num_points - 1, num_points), np.linspace(0, num_points - 1, num_interpolated)
    interpolated_data['power'] = np.interp(interp_x, orig_x, power)
    interpolated_data['hr'] = np.interp(interp_x, orig_x, hr)
    interpolated_data['w_per_kg'] = [(p / BODY_WEIGHT_KG) if BODY_WEIGHT_KG > 0 else 0 for p in interpolated_data['power']]

    # --- 4. FRAME COMPOSITION & VIDEO CREATION (WITH CACHING) ---
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, VIDEO_FPS, (FRAME_WIDTH, FRAME_HEIGHT))
    if not out.isOpened():
        raise IOError("Could not open video writer.")

    total_frames = len(interpolated_data['power'])
    
    #_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    #  OPTIMIZATION: Initialize caches
    text_cache = {}
    base_frame_cache = {}
    #_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    for i in range(total_frames):
        power_val = int(interpolated_data['power'][i])
        hr_val = int(interpolated_data['hr'][i])
        w_per_kg_val = interpolated_data['w_per_kg'][i]

        #_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
        #  OPTIMIZATION: Check cache for a pre-rendered base frame
        cache_key = f"{power_val}-{hr_val}"
        if cache_key in base_frame_cache:
            frame_cv = base_frame_cache[cache_key].copy()
            # Retrieve pre-calculated text image for heart icon placement
            hr_text_pil = text_cache[f"{hr_val} bpm"]
        else:
            # Not in cache, so we render it once
            frame_cv = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), BG_COLOR_CV, dtype=np.uint8)
            current_y = LAYOUT_START_Y

            # --- Power Text ---
            power_text_str = f"{power_val}W"
            if power_text_str not in text_cache:
                text_cache[power_text_str] = draw_text_with_outline_pil(power_text_str, FONT_XL, TEXT_FILL_COLOR_PIL, TEXT_OUTLINE_COLOR_PIL, TEXT_OUTLINE_WIDTH)
            power_text_pil = text_cache[power_text_str]
            text_y = current_y + (LINE_HEIGHT_XL - power_text_pil.height) // 2
            overlay_image_alpha(frame_cv, pil_to_cv2(power_text_pil), LAYOUT_START_X, text_y)
            icon_x = LAYOUT_START_X + power_text_pil.width + ICON_SPACING
            icon_y = current_y + (LINE_HEIGHT_XL - LIGHTNING_ICON.height) // 2
            overlay_image_alpha(frame_cv, pil_to_cv2(LIGHTNING_ICON), icon_x, icon_y)
            current_y += LINE_HEIGHT_XL + LINE_SPACING

            # --- W/kg Text ---
            wkg_text_str = f"{w_per_kg_val:.1f} W/kg"
            if wkg_text_str not in text_cache:
                text_cache[wkg_text_str] = draw_text_with_outline_pil(wkg_text_str, FONT_L, TEXT_FILL_COLOR_PIL, TEXT_OUTLINE_COLOR_PIL, TEXT_OUTLINE_WIDTH)
            wkg_text_pil = text_cache[wkg_text_str]
            text_y = current_y + (LINE_HEIGHT_L - wkg_text_pil.height) // 2
            overlay_image_alpha(frame_cv, pil_to_cv2(wkg_text_pil), LAYOUT_START_X, text_y)
            current_y += LINE_HEIGHT_L + LINE_SPACING

            # --- Heart Rate Text (static part) ---
            hr_text_str = f"{hr_val} bpm"
            if hr_text_str not in text_cache:
                text_cache[hr_text_str] = draw_text_with_outline_pil(hr_text_str, FONT_L, TEXT_FILL_COLOR_PIL, TEXT_OUTLINE_COLOR_PIL, TEXT_OUTLINE_WIDTH)
            hr_text_pil = text_cache[hr_text_str]
            text_y = current_y + (LINE_HEIGHT_L - hr_text_pil.height) // 2
            overlay_image_alpha(frame_cv, pil_to_cv2(hr_text_pil), LAYOUT_START_X, text_y)
            
            # Save the fully rendered static frame to the cache
            base_frame_cache[cache_key] = frame_cv.copy()
        #_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

        # --- Heart Animation (This must be done for every frame as it always changes) ---
        time_s = i / VIDEO_FPS
        beat_freq_hz = hr_val / 60.0
        scale_factor = 1.0 + HEART_ANIMATION_STRENGTH * (np.sin(2 * np.pi * beat_freq_hz * time_s) * 0.5 + 0.5)
        w, h = HEART_ICON.size
        beating_heart_pil = HEART_ICON.resize((int(w * scale_factor), int(h * scale_factor)), Image.Resampling.LANCZOS)
        
        icon_x = LAYOUT_START_X + hr_text_pil.width + ICON_SPACING
        icon_y = (LAYOUT_START_Y + LINE_HEIGHT_XL + LINE_SPACING + LINE_HEIGHT_L + LINE_SPACING) + (LINE_HEIGHT_L - beating_heart_pil.height) // 2
        overlay_image_alpha(frame_cv, pil_to_cv2(beating_heart_pil), icon_x, icon_y)

        out.write(frame_cv)

        if progress_callback and (i + 1) % (VIDEO_FPS * 2) == 0: # Update every 2 seconds
            percentage = int(((i + 1) / total_frames) * 100)
            progress_callback(percentage, f"Rendering frame {i + 1}/{total_frames}")

    out.release()