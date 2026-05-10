"""
AAA Game Loading Screen Generator
Senior Video Engineer / Python Expert implementation
Cinematic quality matching Elden Ring aesthetic
"""

import os
import io
import math
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

FONT_DIR = Path("fonts")
CINZEL_REGULAR_PATH = FONT_DIR / "Cinzel-Regular.ttf"
CINZEL_BOLD_PATH    = FONT_DIR / "Cinzel-Bold.ttf"

# Google Fonts CSS API → extract actual TTF download URLs at runtime
GOOGLE_FONTS_API = (
    "https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&display=swap"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# FONT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def _extract_font_urls(css_text: str) -> list[str]:
    """Pull all src: url(...) TTF/WOFF2 links out of Google Fonts CSS."""
    import re
    return re.findall(r"url\((https://[^)]+\.(?:ttf|woff2))\)", css_text)


def download_cinzel_fonts() -> bool:
    """
    Download Cinzel Regular + Bold from Google Fonts.
    Returns True on success, False on any failure.
    """
    FONT_DIR.mkdir(exist_ok=True)

    if CINZEL_REGULAR_PATH.exists() and CINZEL_BOLD_PATH.exists():
        return True

    try:
        css = requests.get(GOOGLE_FONTS_API, headers=HEADERS, timeout=10).text
        urls = _extract_font_urls(css)

        # Fallback: direct known CDN paths (as of 2024)
        if not urls:
            urls = [
                "https://fonts.gstatic.com/s/cinzel/v23/8vIU7ww63mVu7gt79mT7.woff2",
                "https://fonts.gstatic.com/s/cinzel/v23/8vIJ7ww63mVu7gt7-GT7KHBdRpqR.woff2",
            ]

        downloaded: list[Path] = []
        for url in urls[:4]:                          # limit iterations
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()

            # Decide which slot to fill
            if not CINZEL_REGULAR_PATH.exists():
                dest = CINZEL_REGULAR_PATH
            elif not CINZEL_BOLD_PATH.exists():
                dest = CINZEL_BOLD_PATH
            else:
                break

            dest.write_bytes(r.content)
            downloaded.append(dest)

        # If we only got one file, copy it for both weights
        if CINZEL_REGULAR_PATH.exists() and not CINZEL_BOLD_PATH.exists():
            shutil.copy(CINZEL_REGULAR_PATH, CINZEL_BOLD_PATH)
        elif CINZEL_BOLD_PATH.exists() and not CINZEL_REGULAR_PATH.exists():
            shutil.copy(CINZEL_BOLD_PATH, CINZEL_REGULAR_PATH)

        return CINZEL_REGULAR_PATH.exists()

    except Exception as exc:
        st.warning(f"⚠️ Could not download Cinzel font: {exc}. Using fallback.")
        return False


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return a Cinzel font at the requested size, with graceful fallback."""
    path = CINZEL_BOLD_PATH if bold else CINZEL_REGULAR_PATH
    try:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    except Exception:
        pass
    # Last-resort: Pillow's built-in bitmap font (no kerning, but won't crash)
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────────────────────
# PILLOW DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _spaced_text(text: str, spacing: int = 4) -> str:
    """Insert extra spaces between characters for cinematic letter-spacing."""
    return (" " * spacing).join(text)


def _draw_glow_text(
    canvas: Image.Image,
    text: str,
    pos: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    glow_color: tuple[int, int, int, int] = (255, 240, 180, 120),
    glow_radius: int = 18,
    shadow_offset: tuple[int, int] = (4, 6),
) -> None:
    """
    Render text with:
      1. Soft drop-shadow
      2. Blurred outer glow layer
      3. Crisp main text on top
    All composited onto `canvas` (RGBA).
    """
    w, h = canvas.size

    # --- Drop shadow ---
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.text(
        (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1]),
        text, font=font, fill=(0, 0, 0, 180),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.alpha_composite(shadow_layer)

    # --- Glow ---
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.text(pos, text, font=font, fill=glow_color)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    canvas.alpha_composite(glow_layer)

    # --- Main text ---
    draw = ImageDraw.Draw(canvas)
    draw.text(pos, text, font=font, fill=color)


def _make_left_gradient(
    width: int, height: int, gradient_width_frac: float = 0.42
) -> Image.Image:
    """
    RGBA image: opaque black on the far left fading to transparent on the right.
    Uses a smooth cosine curve for a cinematic feel.
    """
    grad = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = grad.load()
    gw = int(width * gradient_width_frac)

    for x in range(gw):
        t = x / gw                                     # 0 → 1
        alpha = int(255 * (0.5 * (1 + math.cos(math.pi * t))))   # cosine ease
        for y in range(height):
            pixels[x, y] = (0, 0, 0, alpha)

    return grad


def _make_vignette(width: int, height: int, strength: float = 0.78) -> Image.Image:
    """Radial vignette: dark edges, transparent centre."""
    vig = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = vig.load()
    cx, cy = width / 2, height / 2
    max_dist = math.hypot(cx, cy)

    for y in range(height):
        for x in range(width):
            dist = math.hypot(x - cx, y - cy) / max_dist
            alpha = int(255 * strength * (dist ** 2.2))
            pixels[x, y] = (0, 0, 0, min(alpha, 255))

    return vig


def _build_ui_overlay(
    width: int,
    height: int,
    title: str,
    subtitle: str,
    menu_items: list[str],
    selected_index: int,
    tip_text: str,
    gold_color: tuple = (210, 180, 110, 255),
    white_color: tuple = (240, 235, 220, 255),
    dim_color: tuple = (160, 150, 130, 200),
) -> Image.Image:
    """
    Compose the complete AAA UI onto a transparent RGBA canvas:
      - Left gradient overlay
      - Vignette
      - Title with glow + shadow + letter-spacing
      - Subtitle / chapter
      - Menu items with selector
      - Loading tip at bottom
    """
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # 1. Vignette (full canvas)
    vig = _make_vignette(width, height, strength=0.72)
    canvas.alpha_composite(vig)

    # 2. Left gradient panel
    grad = _make_left_gradient(width, height, gradient_width_frac=0.46)
    canvas.alpha_composite(grad)

    # ── Typography sizes scaled to height ──────────────────────────────────
    title_size    = max(56, height // 10)
    subtitle_size = max(22, height // 32)
    menu_size     = max(26, height // 28)
    tip_size      = max(16, height // 48)
    indicator_sz  = max(20, height // 36)

    font_title    = get_font(title_size, bold=True)
    font_subtitle = get_font(subtitle_size)
    font_menu     = get_font(menu_size)
    font_tip      = get_font(tip_size)
    font_indicator= get_font(indicator_sz)

    left_margin = int(width * 0.06)
    title_y     = int(height * 0.28)

    # 3. Decorative line above title
    draw = ImageDraw.Draw(canvas)
    line_y = title_y - 24
    draw.line(
        [(left_margin, line_y), (left_margin + int(width * 0.22), line_y)],
        fill=(210, 180, 110, 160), width=2,
    )

    # 4. Title (spaced + glow)
    spaced_title = _spaced_text(title.upper(), spacing=3)
    _draw_glow_text(
        canvas, spaced_title, (left_margin, title_y),
        font=font_title, color=gold_color,
        glow_color=(255, 220, 120, 90), glow_radius=22,
        shadow_offset=(5, 7),
    )

    # measure title height
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bbox = dummy_draw.textbbox((0, 0), spaced_title, font=font_title)
    title_h = bbox[3] - bbox[1]

    # 5. Subtitle / chapter
    subtitle_y = title_y + title_h + 14
    spaced_sub = _spaced_text(subtitle.upper(), spacing=2)
    draw.text(
        (left_margin + 3, subtitle_y),
        spaced_sub, font=font_subtitle, fill=dim_color,
    )

    # 6. Thin separator
    sep_y = subtitle_y + subtitle_size + 28
    draw.line(
        [(left_margin, sep_y), (left_margin + int(width * 0.18), sep_y)],
        fill=(210, 180, 110, 100), width=1,
    )

    # 7. Menu items
    menu_start_y = sep_y + 36
    line_gap = int(menu_size * 2.1)

    for i, item in enumerate(menu_items):
        y = menu_start_y + i * line_gap
        is_selected = (i == selected_index)

        if is_selected:
            # Subtle highlight bar
            bar_w = int(width * 0.24)
            bar = Image.new("RGBA", (bar_w, line_gap - 4), (210, 180, 110, 22))
            canvas.alpha_composite(bar, dest=(left_margin - 4, y - 2))

            # Selector indicator
            draw.text(
                (left_margin, y),
                "›", font=font_indicator,
                fill=(210, 180, 110, 255),
            )
            text_x = left_margin + indicator_sz + 8
            _draw_glow_text(
                canvas, item, (text_x, y),
                font=font_menu, color=gold_color,
                glow_color=(255, 220, 100, 60), glow_radius=10,
                shadow_offset=(2, 3),
            )
        else:
            draw = ImageDraw.Draw(canvas)
            draw.text(
                (left_margin + indicator_sz + 8, y),
                item, font=font_menu, fill=dim_color,
            )

    # 8. Loading tip at bottom
    tip_y = height - int(height * 0.08)
    tip_label = _spaced_text("TIP", spacing=2) + "  "
    tip_x = left_margin

    draw = ImageDraw.Draw(canvas)
    draw.text((tip_x, tip_y), tip_label, font=font_tip, fill=gold_color)

    # measure tip label width
    bbox2 = draw.textbbox((0, 0), tip_label, font=font_tip)
    tip_label_w = bbox2[2] - bbox2[0]
    draw.text(
        (tip_x + tip_label_w, tip_y),
        tip_text, font=font_tip, fill=white_color,
    )

    return canvas


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def process_image(
    source_image: Image.Image,
    title: str,
    subtitle: str,
    menu_items: list[str],
    selected_index: int,
    tip_text: str,
) -> Image.Image:
    """Apply cinematic grade + UI overlay to a still image. Returns RGBA Image."""
    img = source_image.convert("RGBA")
    w, h = img.size

    # Darken base image slightly (simulate eq=brightness=-0.15)
    dark_layer = Image.new("RGBA", (w, h), (0, 0, 0, int(255 * 0.18)))
    img.alpha_composite(dark_layer)

    # UI overlay
    ui = _build_ui_overlay(w, h, title, subtitle, menu_items, selected_index, tip_text)
    img.alpha_composite(ui)

    return img


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO PROCESSING (FFmpeg)
# ─────────────────────────────────────────────────────────────────────────────

def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command. Raises RuntimeError with stderr on failure."""
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        print("[FFmpeg STDERR]\n", stderr)
        raise RuntimeError(f"FFmpeg failed (code {result.returncode}):\n{stderr}")


def process_video(
    video_bytes: bytes,
    video_ext: str,
    title: str,
    subtitle: str,
    menu_items: list[str],
    selected_index: int,
    tip_text: str,
    output_path: Path,
) -> None:
    """
    Full cinematic video pipeline:
      1. Write input to temp file
      2. Probe dimensions with ffprobe
      3. Apply colour-grade + vignette via FFmpeg
      4. Generate high-res UI PNG with Pillow
      5. Overlay PNG onto graded video with FFmpeg
      6. Encode with libx264 -crf 23 -preset fast
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        in_path     = tmp_dir / f"input{video_ext}"
        graded_path = tmp_dir / "graded.mp4"
        ui_png_path = tmp_dir / "ui_overlay.png"

        in_path.write_bytes(video_bytes)

        # ── Step 1: Probe video dimensions ───────────────────────────────────
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(in_path),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        dims = probe.stdout.decode().strip().split(",")
        vid_w = int(dims[0]) if len(dims) >= 2 else 1920
        vid_h = int(dims[1]) if len(dims) >= 2 else 1080

        # ── Step 2: Colour grade + vignette ──────────────────────────────────
        vf_grade = (
            "eq=brightness=-0.15:contrast=1.3:gamma=0.8,"
            "vignette=PI/4"
        )
        _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(in_path),
            "-vf", vf_grade,
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "copy",
            str(graded_path),
        ])

        # ── Step 3: Build UI PNG at video resolution ──────────────────────────
        ui_img = _build_ui_overlay(
            vid_w, vid_h, title, subtitle, menu_items, selected_index, tip_text
        )
        ui_img.save(str(ui_png_path), "PNG")

        # ── Step 4: Overlay UI PNG onto graded video ──────────────────────────
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(graded_path),
            "-i", str(ui_png_path),
            "-filter_complex", "[0:v][1:v]overlay=0:0",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ])

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────────────────

def _page_config() -> None:
    st.set_page_config(
        page_title="AAA Loading Screen Generator",
        page_icon="⚔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        /* Dark parchment theme */
        html, body, [class*="css"] {
            background-color: #0d0c0a;
            color: #c8b98a;
            font-family: 'Georgia', serif;
        }
        .stButton>button {
            background: linear-gradient(135deg, #2a2015 0%, #3d2e10 100%);
            color: #d4b866;
            border: 1px solid #6b5220;
            border-radius: 3px;
            padding: 0.5rem 1.5rem;
            font-size: 0.9rem;
            letter-spacing: 2px;
            text-transform: uppercase;
            transition: all 0.2s;
        }
        .stButton>button:hover {
            background: linear-gradient(135deg, #3d2e10 0%, #5a4218 100%);
            border-color: #d4b866;
            box-shadow: 0 0 12px rgba(212,184,102,0.3);
        }
        .stTextInput>div>div>input,
        .stTextArea textarea {
            background-color: #13110d;
            color: #c8b98a;
            border: 1px solid #3d3020;
        }
        .stSelectbox>div>div {
            background-color: #13110d;
            color: #c8b98a;
        }
        .stSlider .stSlider { color: #d4b866; }
        h1, h2, h3 { color: #d4b866 !important; letter-spacing: 3px; }
        .stSidebar { background-color: #0a0908 !important; }
        hr { border-color: #3d3020; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _page_config()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='text-align:center;letter-spacing:6px;'>⚔  AAA LOADING SCREEN GENERATOR  ⚔</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#6b5a30;letter-spacing:2px;font-size:0.85rem;'>"
        "CINEMATIC · DARK FANTASY · PROFESSIONAL GRADE"
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Font download (non-blocking) ──────────────────────────────────────────
    with st.spinner("Summoning the Cinzel font from Google Fonts..."):
        font_ok = download_cinzel_fonts()
    if font_ok:
        st.success("✦ Cinzel font ready")
    else:
        st.warning("Font fallback active — Cinzel unavailable (network issue?)")

    # ── Sidebar controls ──────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙  CONFIGURATION")
        st.markdown("---")

        st.markdown("### TITLE CARD")
        title    = st.text_input("Game / Screen Title", value="ASHEN THRONE")
        subtitle = st.text_input("Chapter / Subtitle",  value="The Forgotten Realm")

        st.markdown("### MENU ITEMS")
        raw_menu = st.text_area(
            "One item per line",
            value="New Game\nContinue\nLoad Save\nSettings\nQuit",
            height=130,
        )
        menu_items = [m.strip() for m in raw_menu.splitlines() if m.strip()]
        selected_idx = st.slider(
            "Selected Menu Item (0-indexed)",
            min_value=0, max_value=max(0, len(menu_items) - 1),
            value=0,
        )

        st.markdown("### LOADING TIP")
        tip_text = st.text_input(
            "Tip text",
            value="Patience is the armour of the wise. Study your enemy before striking.",
        )

        st.markdown("### MEDIA INPUT")
        uploaded = st.file_uploader(
            "Upload Image or Video",
            type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "avi", "mkv"],
        )

        generate = st.button("⚔  GENERATE LOADING SCREEN")

    # ── Main area ─────────────────────────────────────────────────────────────
    if not generate:
        st.info(
            "Configure your loading screen in the sidebar, upload a background "
            "image or video, then press **⚔ GENERATE LOADING SCREEN**."
        )
        # Demo preview with placeholder
        st.markdown("#### Preview Placeholder")
        placeholder = Image.new("RGB", (960, 540), color=(10, 9, 8))
        st.image(placeholder, use_container_width=True)
        return

    if uploaded is None:
        st.error("Please upload a background image or video first.")
        return

    file_bytes = uploaded.read()
    ext = Path(uploaded.name).suffix.lower()
    is_video = ext in {".mp4", ".mov", ".avi", ".mkv"}

    with st.spinner("Forging your cinematic loading screen…"):

        if is_video:
            out_path = OUTPUT_DIR / "loading_screen.mp4"
            try:
                process_video(
                    video_bytes=file_bytes,
                    video_ext=ext,
                    title=title,
                    subtitle=subtitle,
                    menu_items=menu_items,
                    selected_index=selected_idx,
                    tip_text=tip_text,
                    output_path=out_path,
                )
                st.success("✦ Video processed successfully!")

                col1, col2 = st.columns([2, 1])
                with col1:
                    st.video(str(out_path))
                with col2:
                    st.markdown("**Output details**")
                    size_mb = out_path.stat().st_size / 1_048_576
                    st.metric("File size", f"{size_mb:.2f} MB")
                    with open(out_path, "rb") as f:
                        st.download_button(
                            "⬇  Download Video",
                            data=f,
                            file_name="loading_screen.mp4",
                            mime="video/mp4",
                        )
            except FileNotFoundError:
                st.error(
                    "FFmpeg not found. Please install FFmpeg:\n\n"
                    "`sudo apt install ffmpeg`  (Linux/Streamlit Cloud)\n\n"
                    "`brew install ffmpeg`  (macOS)"
                )
            except RuntimeError as e:
                st.error(f"FFmpeg error:\n```\n{e}\n```")

        else:
            # Still image
            try:
                source = Image.open(io.BytesIO(file_bytes))
            except Exception as e:
                st.error(f"Could not open image: {e}")
                return

            result = process_image(
                source_image=source,
                title=title,
                subtitle=subtitle,
                menu_items=menu_items,
                selected_index=selected_idx,
                tip_text=tip_text,
            )

            out_path = OUTPUT_DIR / "loading_screen.png"
            result.save(str(out_path), "PNG", optimize=False)

            st.success("✦ Image processed successfully!")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.image(result, caption="Cinematic Loading Screen", use_container_width=True)
            with col2:
                st.markdown("**Output details**")
                size_kb = out_path.stat().st_size / 1024
                st.metric("Resolution", f"{result.width} × {result.height}")
                st.metric("File size", f"{size_kb:.0f} KB")

                buf = io.BytesIO()
                result.save(buf, format="PNG")
                st.download_button(
                    "⬇  Download PNG",
                    data=buf.getvalue(),
                    file_name="loading_screen.png",
                    mime="image/png",
                )


if __name__ == "__main__":
    main()
