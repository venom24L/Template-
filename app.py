"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          AAA GAME LOADING SCREEN GENERATOR  —  v2.0                        ║
║          Cinematic quality · Dark Fantasy · Streamlit Cloud Ready           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Architecture:
  • Font Engine   — requests-based Cinzel TTF download from Google Fonts CDN
  • Image Path    — Pillow-only: resize → darken → vignette → UI overlay → PNG
  • Video Path    — FFmpeg grade + resize → Pillow UI PNG → FFmpeg overlay → MP4
  • Output        — forced 1280×720 (16:9) for all media
"""

from __future__ import annotations

import io
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

TARGET_W, TARGET_H = 1280, 720   # forced output resolution (16:9)

FONT_DIR         = Path("fonts")
CINZEL_REG_PATH  = FONT_DIR / "Cinzel-Regular.ttf"
CINZEL_BOLD_PATH = FONT_DIR / "Cinzel-Bold.ttf"

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FONT_DIR.mkdir(parents=True, exist_ok=True)

# Google Fonts static CDN — stable TTF direct links
CINZEL_REG_URL  = "https://fonts.gstatic.com/s/cinzel/v23/8vIU7ww63mVu7gt7xTs.ttf"
CINZEL_BOLD_URL = "https://fonts.gstatic.com/s/cinzel/v23/8vIJ7ww63mVu7gt79GT7KHBdRpqR.ttf"

# Fallback: parse CSS API for dynamic URLs
GOOGLE_FONTS_CSS = (
    "https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&display=swap"
)
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Colour palette (RGBA)
GOLD   = (212, 182, 100, 255)
GOLD_D = (180, 148,  72, 200)
WHITE  = (238, 232, 215, 255)
DIM    = (155, 142, 118, 195)


# ══════════════════════════════════════════════════════════════════════════════
# FONT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _fetch(url: str, timeout: int = 15) -> bytes:
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    r.raise_for_status()
    return r.content


def _css_ttf_urls(css: str) -> list[str]:
    return re.findall(r"url\((https://[^)]+\.ttf)\)", css)


def download_cinzel() -> bool:
    """
    Download Cinzel Regular + Bold TTF files from Google Fonts.
    Strategy:
      1. Try known static CDN URLs.
      2. Parse CSS API for fresh URLs.
      3. Copy one weight to serve as the other if only one succeeded.
    Returns True when Regular is available.
    """
    if CINZEL_REG_PATH.exists() and CINZEL_BOLD_PATH.exists():
        return True

    for path, url in [(CINZEL_REG_PATH, CINZEL_REG_URL),
                      (CINZEL_BOLD_PATH, CINZEL_BOLD_URL)]:
        if not path.exists():
            try:
                path.write_bytes(_fetch(url))
            except Exception:
                pass

    if not CINZEL_REG_PATH.exists() or not CINZEL_BOLD_PATH.exists():
        try:
            css  = _fetch(GOOGLE_FONTS_CSS, timeout=10).decode()
            urls = _css_ttf_urls(css)
            for i, p in enumerate([CINZEL_REG_PATH, CINZEL_BOLD_PATH]):
                if not p.exists() and i < len(urls):
                    try:
                        p.write_bytes(_fetch(urls[i]))
                    except Exception:
                        pass
        except Exception:
            pass

    if CINZEL_REG_PATH.exists() and not CINZEL_BOLD_PATH.exists():
        shutil.copy(CINZEL_REG_PATH, CINZEL_BOLD_PATH)
    elif CINZEL_BOLD_PATH.exists() and not CINZEL_REG_PATH.exists():
        shutil.copy(CINZEL_BOLD_PATH, CINZEL_REG_PATH)

    return CINZEL_REG_PATH.exists()


@st.cache_resource(show_spinner=False)
def _load_font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    path = CINZEL_BOLD_PATH if bold else CINZEL_REG_PATH
    try:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    except Exception:
        pass
    return ImageFont.load_default()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return _load_font(size, bold)


# ══════════════════════════════════════════════════════════════════════════════
# NUMPY DRAWING HELPERS  (vectorised — no pixel loops)
# ══════════════════════════════════════════════════════════════════════════════

def make_vignette(w: int, h: int, strength: float = 0.88) -> Image.Image:
    """Radial vignette: dark corners → transparent centre."""
    xs = np.linspace(-1, 1, w, dtype=np.float32)
    ys = np.linspace(-1, 1, h, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)
    dist  = np.sqrt(xg ** 2 + yg ** 2) / math.sqrt(2)
    alpha = np.clip(strength * dist ** 2.0, 0, 1)
    arr   = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def make_left_gradient(w: int, h: int, reach: float = 0.54) -> Image.Image:
    """
    Cosine-eased gradient: solid black (80 % opacity) at x=0
    → fully transparent at x = reach*w.
    """
    gw  = int(w * reach)
    t   = np.linspace(0.0, 1.0, gw, dtype=np.float32)
    a   = (0.80 * 255 * 0.5 * (1.0 + np.cos(math.pi * t))).astype(np.uint8)
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :gw, 3] = a[np.newaxis, :]
    return Image.fromarray(arr, "RGBA")


# ══════════════════════════════════════════════════════════════════════════════
# PILLOW TEXT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def kern(text: str, gap: int = 3) -> str:
    """Simulate CSS letter-spacing by inserting spaces between characters."""
    return (" " * gap).join(text)


def text_size(text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = probe.textbbox((0, 0), text, font=fnt)
    return bb[2] - bb[0], bb[3] - bb[1]


def draw_glow_text(
    canvas:        Image.Image,
    text:          str,
    pos:           tuple[int, int],
    fnt:           ImageFont.FreeTypeFont,
    color:         tuple = WHITE,
    glow_color:    tuple = (255, 220, 130, 110),
    glow_radius:   int   = 22,
    shadow_offset: tuple = (5, 7),
    shadow_alpha:  int   = 170,
) -> None:
    """
    Three-pass compositing:
      Pass 1 — Gaussian-blurred drop shadow
      Pass 2 — Gaussian-blurred outer glow (warm amber)
      Pass 3 — Crisp main text on top
    """
    w, h = canvas.size

    # Shadow
    shd = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shd).text(
        (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1]),
        text, font=fnt, fill=(0, 0, 0, shadow_alpha),
    )
    canvas.alpha_composite(shd.filter(ImageFilter.GaussianBlur(7)))

    # Glow
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).text(pos, text, font=fnt, fill=glow_color)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(glow_radius)))

    # Crisp text
    ImageDraw.Draw(canvas).text(pos, text, font=fnt, fill=color)


# ══════════════════════════════════════════════════════════════════════════════
# UI OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

def build_ui_overlay(
    w:            int,
    h:            int,
    title:        str,
    subtitle:     str,
    menu_items:   list[str],
    selected_idx: int,
    tip_text:     str,
) -> Image.Image:
    """
    Compose the complete AAA loading-screen UI on a transparent RGBA canvas.

    Layers (bottom → top):
      1.  Heavy radial vignette
      2.  Left-side cosine-gradient panel
      3.  Decorative rule + diamond ornament above title
      4.  Title  — kerned · glowing · gold
      5.  Subtitle — spaced · dimmed
      6.  Thin separator rule
      7.  Menu items with animated › selector + subtle highlight bar
      8.  Bottom ornament rule
      9.  Loading tip  (TIP label + body text)
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # ── Atmosphere ────────────────────────────────────────────────────────────
    canvas.alpha_composite(make_vignette(w, h, strength=0.88))
    canvas.alpha_composite(make_left_gradient(w, h, reach=0.54))

    # ── Type scale (relative to 720 p baseline) ───────────────────────────────
    sc = h / 720
    T_TITLE = max(58, int(68 * sc))
    T_SUB   = max(19, int(22 * sc))
    T_MENU  = max(22, int(26 * sc))
    T_IND   = max(20, int(24 * sc))
    T_TIP   = max(14, int(16 * sc))

    f_title = font(T_TITLE, bold=True)
    f_sub   = font(T_SUB)
    f_menu  = font(T_MENU)
    f_ind   = font(T_IND,   bold=True)
    f_tip   = font(T_TIP)

    draw   = ImageDraw.Draw(canvas)
    LM     = int(w * 0.060)
    RULE_W = int(w * 0.230)

    # ── 3. Rule + diamond above title ─────────────────────────────────────────
    title_y = int(h * 0.270)
    rule_y  = title_y - int(28 * sc)
    draw.line([(LM, rule_y), (LM + RULE_W, rule_y)], fill=GOLD_D,
              width=max(1, int(2 * sc)))
    d = max(3, int(5 * sc))
    draw.polygon(
        [(LM - d, rule_y), (LM, rule_y - d),
         (LM + d, rule_y), (LM, rule_y + d)],
        fill=GOLD,
    )

    # ── 4. Title ──────────────────────────────────────────────────────────────
    title_spaced = kern(title.upper(), gap=3)
    draw_glow_text(
        canvas, title_spaced, (LM, title_y),
        fnt=f_title, color=GOLD,
        glow_color=(255, 215, 100, 100), glow_radius=28,
        shadow_offset=(6, 8),
    )
    _, t_h = text_size(title_spaced, f_title)

    # ── 5. Subtitle ───────────────────────────────────────────────────────────
    sub_y      = title_y + t_h + int(12 * sc)
    sub_spaced = kern(subtitle.upper(), gap=2)
    draw_glow_text(
        canvas, sub_spaced, (LM + 2, sub_y),
        fnt=f_sub, color=DIM,
        glow_color=(200, 180, 100, 40), glow_radius=8,
        shadow_offset=(3, 4), shadow_alpha=100,
    )
    _, s_h = text_size(sub_spaced, f_sub)

    # ── 6. Separator ──────────────────────────────────────────────────────────
    sep_y = sub_y + s_h + int(24 * sc)
    draw.line([(LM, sep_y), (LM + int(RULE_W * 0.75), sep_y)],
              fill=GOLD_D, width=1)

    # ── 7. Menu items ─────────────────────────────────────────────────────────
    menu_y   = sep_y + int(38 * sc)
    line_gap = int(T_MENU * 2.15)
    ind_w, _ = text_size("›  ", f_ind)

    for i, item in enumerate(menu_items):
        y      = menu_y + i * line_gap
        is_sel = (i == selected_idx)

        if is_sel:
            # Highlight bar
            bar_h = line_gap - int(4 * sc)
            bar_w = int(w * 0.260)
            bar   = Image.new("RGBA", (bar_w, bar_h), (210, 175, 90, 28))
            canvas.alpha_composite(bar, dest=(LM - 4, y - 2))
            # Glowing arrow
            draw_glow_text(
                canvas, "›", (LM, y + int(1 * sc)),
                fnt=f_ind, color=GOLD,
                glow_color=(255, 210, 80, 80), glow_radius=12,
                shadow_offset=(2, 3), shadow_alpha=80,
            )
            # Glowing item text
            draw_glow_text(
                canvas, item, (LM + ind_w, y),
                fnt=f_menu, color=GOLD,
                glow_color=(255, 215, 100, 55), glow_radius=10,
                shadow_offset=(3, 4),
            )
        else:
            draw = ImageDraw.Draw(canvas)
            draw.text((LM + ind_w, y), item, font=f_menu, fill=DIM)

    # ── 8. Bottom ornament ────────────────────────────────────────────────────
    bot_y = h - int(h * 0.095)
    draw  = ImageDraw.Draw(canvas)
    draw.line([(LM, bot_y), (LM + RULE_W, bot_y)], fill=GOLD_D, width=1)

    # ── 9. Loading tip ────────────────────────────────────────────────────────
    tip_y     = bot_y + int(10 * sc)
    tip_label = kern("TIP", gap=2) + "   "
    tw, _     = text_size(tip_label, f_tip)
    draw_glow_text(
        canvas, tip_label, (LM, tip_y),
        fnt=f_tip, color=GOLD,
        glow_color=(255, 200, 80, 50), glow_radius=6,
        shadow_offset=(2, 2), shadow_alpha=80,
    )
    ImageDraw.Draw(canvas).text((LM + tw, tip_y), tip_text, font=f_tip, fill=WHITE)

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def _darken(img: Image.Image, factor: float = 0.72) -> Image.Image:
    """
    Multiply every pixel channel by `factor` via NumPy.
    factor=0.72 approximates FFmpeg eq=brightness=-0.20:contrast=1.30.
    """
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    arr = np.clip(arr * factor, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _crop_fill(source: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize + centre-crop to exactly (tw, th) without distortion."""
    sr = source.width / source.height
    tr = tw / th
    if sr > tr:
        nw, nh = int(source.width * th / source.height), th
    else:
        nw, nh = tw, int(source.height * tw / source.width)
    img  = source.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top  = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def process_image(
    source:       Image.Image,
    title:        str,
    subtitle:     str,
    menu_items:   list[str],
    selected_idx: int,
    tip_text:     str,
) -> Image.Image:
    """
    Still-image pipeline:
      1. Crop-fill resize to 1280×720
      2. Darken (eq=brightness=-0.20 equivalent)
      3. Composite full UI overlay
    Returns RGBA image.
    """
    img = _crop_fill(source, TARGET_W, TARGET_H)
    img = _darken(img, factor=0.72)
    ui  = build_ui_overlay(TARGET_W, TARGET_H, title, subtitle,
                           menu_items, selected_idx, tip_text)
    img.alpha_composite(ui)
    return img


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO PIPELINE  (FFmpeg)
# ══════════════════════════════════════════════════════════════════════════════

def _ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command; raise RuntimeError with stderr on failure."""
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        stderr = r.stderr.decode("utf-8", errors="replace")
        print(f"[FFmpeg STDERR]\n{stderr}")
        raise RuntimeError(stderr[-2500:])


def process_video(
    video_bytes:  bytes,
    video_ext:    str,
    title:        str,
    subtitle:     str,
    menu_items:   list[str],
    selected_idx: int,
    tip_text:     str,
    output_path:  Path,
) -> None:
    """
    Full video pipeline:
      1. Write input bytes to temp file.
      2. FFmpeg: scale to 1280×720 + colour grade (brightness=-0.20,
         contrast=1.30, gamma=0.82) + heavy vignette.
      3. Pillow: render UI overlay PNG at 1280×720.
      4. FFmpeg: overlay PNG → final MP4
         (-crf 23, -preset fast, yuv420p, +faststart).
      5. Cleanup temp directory.
    """
    tmp = Path(tempfile.mkdtemp())
    try:
        in_path     = tmp / f"input{video_ext}"
        graded_path = tmp / "graded.mp4"
        ui_path     = tmp / "ui.png"

        in_path.write_bytes(video_bytes)

        # ── Grade + resize ────────────────────────────────────────────────────
        vf = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},"
            "eq=brightness=-0.20:contrast=1.30:gamma=0.82:saturation=0.85,"
            "vignette=PI/3.5"
        )
        _ffmpeg([
            "ffmpeg", "-y", "-i", str(in_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            str(graded_path),
        ])

        # ── UI PNG ────────────────────────────────────────────────────────────
        ui = build_ui_overlay(TARGET_W, TARGET_H, title, subtitle,
                              menu_items, selected_idx, tip_text)
        ui.save(str(ui_path), "PNG")

        # ── Overlay + final encode ─────────────────────────────────────────────
        _ffmpeg([
            "ffmpeg", "-y",
            "-i", str(graded_path),
            "-i", str(ui_path),
            "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(output_path),
        ])

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT  UI
# ══════════════════════════════════════════════════════════════════════════════

_CSS = """
<style>
html, body, [class*="css"] {
    background-color: #0b0a08;
    color: #c5b688;
    font-family: 'Georgia', 'Palatino Linotype', serif;
}
.block-container { padding-top: 1.8rem; }
h1, h2, h3, h4 {
    color: #d4b866 !important;
    letter-spacing: 4px !important;
    text-transform: uppercase;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080706 0%, #100e0b 100%) !important;
    border-right: 1px solid #2a2010;
}
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background-color: #130f0a !important;
    color: #c5b688 !important;
    border: 1px solid #3a2e18 !important;
    border-radius: 2px !important;
}
.stTextInput > label,
.stTextArea  > label,
.stSlider    > label,
.stFileUploader > label {
    color: #8a7a52 !important;
    letter-spacing: 1px;
    font-size: 0.78rem !important;
    text-transform: uppercase;
}
.stButton > button {
    width: 100%;
    background: linear-gradient(135deg, #1e1608 0%, #342510 100%);
    color: #d4b866;
    border: 1px solid #5a4018;
    border-radius: 2px;
    padding: 0.6rem 1.2rem;
    font-size: 0.82rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    transition: all 0.25s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2e2010 0%, #4a3418 100%);
    border-color: #d4b866;
    color: #f0d888;
    box-shadow: 0 0 18px rgba(212,184,102,0.28);
}
.stButton > button:active { transform: translateY(1px); }
[data-testid="stFileUploader"] section {
    background: #100e0a !important;
    border: 1px dashed #3a2e18 !important;
    border-radius: 4px !important;
}
[data-testid="stMetricValue"] { color: #d4b866 !important; }
hr { border-color: #2a2010 !important; }
</style>
"""


def _demo_preview(title: str, subtitle: str,
                  menu_items: list[str], selected_idx: int,
                  tip_text: str) -> Image.Image:
    """Live-preview on a dark grid background (no upload required)."""
    bg = Image.new("RGB", (TARGET_W, TARGET_H), (8, 7, 6))
    d  = ImageDraw.Draw(bg)
    for x in range(0, TARGET_W, 80):
        d.line([(x, 0), (x, TARGET_H)], fill=(15, 13, 10))
    for y in range(0, TARGET_H, 80):
        d.line([(0, y), (TARGET_W, y)], fill=(15, 13, 10))
    rgba = bg.convert("RGBA")
    ui   = build_ui_overlay(TARGET_W, TARGET_H, title, subtitle,
                             menu_items, selected_idx, tip_text)
    rgba.alpha_composite(ui)
    return rgba


def _sidebar() -> dict:
    with st.sidebar:
        st.markdown(
            "<h2 style='text-align:center;font-size:0.82rem;"
            "letter-spacing:5px;color:#5a4828;margin-bottom:0.2rem;'>"
            "⚔  FORGE YOUR SCREEN  ⚔</h2>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown(
            "<p style='font-size:0.68rem;letter-spacing:3px;color:#5a4a28;'>"
            "▸ TITLE CARD</p>", unsafe_allow_html=True,
        )
        title    = st.text_input("Game Title",  value="ASHEN THRONE")
        subtitle = st.text_input("Chapter",     value="The Forgotten Realm")
        st.markdown("---")

        st.markdown(
            "<p style='font-size:0.68rem;letter-spacing:3px;color:#5a4a28;'>"
            "▸ MAIN MENU</p>", unsafe_allow_html=True,
        )
        raw = st.text_area(
            "Items (one per line)",
            value="New Game\nContinue\nLoad Save\nOptions\nQuit",
            height=130,
        )
        items = [i.strip() for i in raw.splitlines() if i.strip()]
        sel   = st.slider("Selected Item", 0, max(0, len(items) - 1), 0)
        st.markdown("---")

        st.markdown(
            "<p style='font-size:0.68rem;letter-spacing:3px;color:#5a4a28;'>"
            "▸ LOADING TIP</p>", unsafe_allow_html=True,
        )
        tip = st.text_input(
            "Tip text",
            value="The deeper the darkness, the brighter the flame burns within.",
        )
        st.markdown("---")

        st.markdown(
            "<p style='font-size:0.68rem;letter-spacing:3px;color:#5a4a28;'>"
            "▸ BACKGROUND MEDIA</p>", unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Image or Video",
            type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "avi", "mkv"],
        )
        st.markdown("---")
        generate = st.button("⚔   GENERATE LOADING SCREEN")

    return dict(title=title, subtitle=subtitle, menu_items=items,
                selected_idx=sel, tip_text=tip,
                uploaded=uploaded, generate=generate)


def main() -> None:
    st.set_page_config(
        page_title="AAA Loading Screen Generator",
        page_icon="⚔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        "<h1 style='text-align:center;font-size:1.5rem;letter-spacing:8px;"
        "margin-bottom:0;'>⚔  AAA LOADING SCREEN GENERATOR  ⚔</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#4a3c1e;letter-spacing:3px;"
        "font-size:0.70rem;margin-top:4px;'>"
        "CINEMATIC  ·  DARK FANTASY  ·  1280 × 720</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Font bootstrap (once per session)
    if "font_ready" not in st.session_state:
        with st.spinner("Summoning Cinzel typeface from Google Fonts…"):
            st.session_state["font_ready"] = download_cinzel()

    if st.session_state["font_ready"]:
        st.success("✦ Cinzel typeface loaded — cinematic mode active")
    else:
        st.warning("⚠ Cinzel unavailable. Pillow default font active — output may look basic.")

    cfg = _sidebar()

    # ── Live preview (always visible) ─────────────────────────────────────────
    st.markdown("#### Live Preview")
    preview = _demo_preview(
        cfg["title"], cfg["subtitle"],
        cfg["menu_items"], cfg["selected_idx"],
        cfg["tip_text"],
    )
    st.image(preview, use_container_width=True)

    if not cfg["generate"]:
        st.caption(
            "Upload a background image or video in the sidebar, "
            "then press **⚔ GENERATE LOADING SCREEN**."
        )
        return

    if cfg["uploaded"] is None:
        st.error("Please upload a background image or video first.")
        return

    raw_bytes = cfg["uploaded"].read()
    ext       = Path(cfg["uploaded"].name).suffix.lower()
    is_video  = ext in {".mp4", ".mov", ".avi", ".mkv"}

    kwargs = dict(
        title        = cfg["title"],
        subtitle     = cfg["subtitle"],
        menu_items   = cfg["menu_items"],
        selected_idx = cfg["selected_idx"],
        tip_text     = cfg["tip_text"],
    )

    # ── VIDEO ─────────────────────────────────────────────────────────────────
    if is_video:
        out_path = OUTPUT_DIR / "loading_screen.mp4"
        with st.spinner("Grading video · building UI · encoding…  (~30 s)"):
            try:
                process_video(raw_bytes, ext, output_path=out_path, **kwargs)
            except FileNotFoundError:
                st.error(
                    "**FFmpeg not found.**\n\n"
                    "- Streamlit Cloud: add `ffmpeg` to `packages.txt`\n"
                    "- Linux: `sudo apt install ffmpeg`\n"
                    "- macOS: `brew install ffmpeg`"
                )
                return
            except RuntimeError as e:
                st.error(f"**FFmpeg error:**\n```\n{e}\n```")
                return

        st.success("✦ Video processed — 1280 × 720 · H.264 · CRF 23")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.video(str(out_path))
        with c2:
            size_mb = out_path.stat().st_size / 1_048_576
            st.metric("Resolution", "1280 × 720")
            st.metric("File size",  f"{size_mb:.2f} MB")
            st.metric("Codec",      "H.264 / AAC")
            with open(out_path, "rb") as f:
                st.download_button("⬇  Download MP4", data=f,
                                   file_name="loading_screen.mp4",
                                   mime="video/mp4")

    # ── IMAGE ─────────────────────────────────────────────────────────────────
    else:
        try:
            source = Image.open(io.BytesIO(raw_bytes))
        except Exception as e:
            st.error(f"Could not open image: {e}")
            return

        with st.spinner("Applying cinematic grade and UI overlay…"):
            result = process_image(source, **kwargs)

        out_path = OUTPUT_DIR / "loading_screen.png"
        result.save(str(out_path), "PNG", optimize=False, compress_level=6)

        st.success("✦ Image processed — 1280 × 720 · RGBA PNG")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.image(result, caption="Cinematic Loading Screen",
                     use_container_width=True)
        with c2:
            size_kb = out_path.stat().st_size / 1024
            st.metric("Resolution", "1280 × 720")
            st.metric("File size",  f"{size_kb:.0f} KB")
            st.metric("Mode",       "RGBA PNG")
            buf = io.BytesIO()
            result.save(buf, format="PNG")
            st.download_button("⬇  Download PNG", data=buf.getvalue(),
                               file_name="loading_screen.png",
                               mime="image/png")


if __name__ == "__main__":
    main()
