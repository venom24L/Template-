"""
Video Game Loading Screen Generator  ·  v3.0
=============================================
Faithfully reproduces the cinematic game-menu aesthetic:
  - Multi-layer golden fire glow on the title
  - Title split across two lines (small line + massive line)
  - Center-aligned menu under the title
  - Pure vignette darkness — no sidebar rectangle
  - Subtle teal cinematic colour wash
  - Version number bottom-left
Run:  streamlit run app.py
"""

import io
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import streamlit as st
from PIL import (
    Image, ImageDraw, ImageFilter,
    ImageFont, ImageEnhance, ImageChops
)

# ══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Game Loading Screen Generator",
    page_icon="⚔",
    layout="centered",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Share+Tech+Mono&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #06060e;
    color: #d8d0c0;
    font-family: 'Cinzel', serif;
}
[data-testid="stHeader"] { background: transparent; }

h1 {
    font-family: 'Cinzel', serif;
    color: #c8a050;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    text-shadow: 0 0 30px #c8a05066;
}
h3 { color: #605850; font-weight: 400; letter-spacing: 0.06em; }

.stButton > button {
    background: linear-gradient(135deg, #c8a050 0%, #7a4a10 100%);
    color: #06060e;
    font-family: 'Cinzel', serif;
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: 0.14em;
    border: none;
    border-radius: 2px;
    padding: 0.65rem 2rem;
    text-transform: uppercase;
    box-shadow: 0 0 20px #c8a05033;
    transition: opacity 0.2s, box-shadow 0.2s;
}
.stButton > button:hover { opacity: 0.85; box-shadow: 0 0 36px #c8a05077; }

.stTextInput > div > div > input,
.stSelectbox > div > div {
    background: #0e0c14;
    border: 1px solid #2a2418;
    color: #d8d0c0;
    border-radius: 2px;
    font-family: 'Share Tech Mono', monospace;
}
hr { border-color: #1e1a10; }

.info-box {
    background: #0e0c14;
    border-left: 3px solid #c8a050;
    padding: 0.85rem 1.1rem;
    border-radius: 2px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.8rem;
    color: #706050;
    margin-bottom: 1.2rem;
    line-height: 1.8;
}
.error-box {
    background: #140808;
    border-left: 3px solid #cc3333;
    padding: 0.8rem 1rem;
    border-radius: 2px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    color: #ee8888;
    white-space: pre-wrap;
    overflow-x: auto;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════
CANVAS_W, CANVAS_H = 1280, 720
FONTS_DIR = Path("fonts_cache")
FONTS_DIR.mkdir(exist_ok=True)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

FONT_STYLES = {
    "Cinzel (RPG / Fantasy)": {
        "title_url":  "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Bold.ttf",
        "body_url":   "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Regular.ttf",
        "title_file": "Cinzel-Bold.ttf",
        "body_file":  "Cinzel-Regular.ttf",
    },
    "Bebas Neue (Racing / Action)": {
        "title_url":  "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
        "body_url":   "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
        "title_file": "BebasNeue-Regular.ttf",
        "body_file":  "BebasNeue-Regular.ttf",
    },
    "Orbitron (Sci-Fi / Cyber)": {
        "title_url":  "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
        "body_url":   "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
        "title_file": "Orbitron.ttf",
        "body_file":  "Orbitron.ttf",
    },
}

COLOR_THEMES = {
    "Teal Cinematic (Cool)": {
        "wash": (0, 16, 38), "wash_str": 0.25,
        "glow_layers": [
            (100, 220, 255, 28, 220),
            ( 20, 140, 210, 18, 160),
            (  0,  60, 140, 10, 100),
        ],
        "title_color": (210, 240, 255),
        "menu_color":  (180, 210, 235),
    },
    "Amber (Warm / Classic)": {
        "wash": (40, 18, 0), "wash_str": 0.28,
        "glow_layers": [
            (255, 200,  60, 28, 220),   # bright yellow core
            (255, 140,  20, 18, 160),   # orange mid
            (180,  60,   0, 10, 100),   # deep red outer
        ],
        "title_color": (255, 245, 210),
        "menu_color":  (230, 215, 185),
    },
    "Crimson Dark": {
        "wash": (42, 0, 0), "wash_str": 0.26,
        "glow_layers": [
            (255, 100,  60, 28, 220),
            (200,  30,  10, 18, 160),
            (120,   0,   0, 10, 100),
        ],
        "title_color": (255, 220, 210),
        "menu_color":  (230, 190, 180),
    },
    "Void Purple": {
        "wash": (18, 0, 38), "wash_str": 0.26,
        "glow_layers": [
            (200, 130, 255, 28, 220),
            (140,  50, 220, 18, 160),
            ( 60,   0, 140, 10, 100),
        ],
        "title_color": (230, 210, 255),
        "menu_color":  (200, 185, 235),
    },
}

# ══════════════════════════════════════════════════════════════════
#  FONT MANAGEMENT
# ══════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def download_font(url: str, filename: str) -> Path | None:
    dest = FONTS_DIR / filename
    if dest.exists():
        return dest
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except Exception as e:
        st.warning(f"Font download failed ({filename}): {e}")
        return None


def pil_font(path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    if path and path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════
#  SYSTEM / FFMPEG HELPERS
# ══════════════════════════════════════════════════════════════════
def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False


def find_system_font() -> str | None:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf",
    ]:
        if Path(p).exists():
            return p
    try:
        res = subprocess.run(["fc-list", "--format=%{file}\n"],
                             capture_output=True, text=True, timeout=5)
        for line in res.stdout.splitlines():
            line = line.strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
#  PILLOW CORE EFFECTS
# ══════════════════════════════════════════════════════════════════

def apply_color_wash(img: Image.Image, rgb: tuple, strength: float) -> Image.Image:
    wash = Image.new("RGB", img.size, rgb)
    return Image.blend(img.convert("RGB"), wash, strength)


def apply_vignette(img: Image.Image, strength: float = 2.0) -> Image.Image:
    """Strong radial vignette — darkness from edges, not a sidebar."""
    w, h = img.size
    vig = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(vig)
    cx, cy = w // 2, h // 2
    steps = 180
    for i in range(steps, 0, -1):
        ratio = i / steps
        alpha = int(255 * (1 - ratio) ** strength)
        rx = int(cx * ratio * 1.1)
        ry = int(cy * ratio * 1.1)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    vig = vig.filter(ImageFilter.GaussianBlur(70))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = img.convert("RGB")
    img.paste(dark, mask=ImageChops.invert(vig))
    return img


def draw_fire_glow_text(
    img: Image.Image,
    text: str,
    cx: int,          # horizontal center x of the text block
    y: int,           # top-y of the text
    font: ImageFont.FreeTypeFont,
    text_color: tuple,
    glow_layers: list,  # list of (r, g, b, blur_radius, alpha)
) -> tuple[Image.Image, int]:
    """
    Draw text centered on cx, at y.
    Returns (updated_img, bottom_y_of_text).
    """
    dummy = ImageDraw.Draw(img)
    bbox  = dummy.textbbox((0, 0), text, font=font)
    tw    = bbox[2] - bbox[0]
    th    = bbox[3] - bbox[1]
    tx    = cx - tw // 2

    base = img.convert("RGBA")

    # Layer glow from outermost to innermost
    for (gr, gg, gb, blur, alpha_max) in reversed(glow_layers):
        glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        gd   = ImageDraw.Draw(glow)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                gd.text((tx + ox, y + oy), text, font=font,
                        fill=(gr, gg, gb, alpha_max))
        glow = glow.filter(ImageFilter.GaussianBlur(blur))
        base.alpha_composite(glow)

    # Drop shadow
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.text((tx + 4, y + 4), text, font=font, fill=(0, 0, 0, 180))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(4))
    base.alpha_composite(shadow_layer)

    # Crisp main text on top
    td = ImageDraw.Draw(base)
    td.text((tx, y), text, font=font, fill=(*text_color, 255))

    return base.convert("RGB"), y + th


def draw_centered_text_plain(
    draw: ImageDraw.Draw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    shadow_color: tuple = (0, 0, 0),
    shadow_offset: int = 2,
) -> int:
    """Draw center-aligned plain text with drop shadow. Returns bottom y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    tx   = cx - tw // 2
    # Shadow
    draw.text((tx + shadow_offset, y + shadow_offset),
              text, font=font, fill=(*shadow_color, 160))
    # Text
    draw.text((tx, y), text, font=font, fill=color)
    return y + th


# ══════════════════════════════════════════════════════════════════
#  IMAGE PIPELINE  (Pillow — updated for better centering & spacing)
# ══════════════════════════════════════════════════════════════════

def process_image(
    raw_bytes: bytes,
    main_title: str,
    subtitle: str,
    font_style: dict,
    theme: dict,
    version_str: str = "v 20.26",
) -> bytes:

    # ── 1. Open & fill canvas ────────────────────────────────────
    src = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    src_ratio = src.width / src.height
    tgt_ratio = CANVAS_W / CANVAS_H
    if src_ratio > tgt_ratio:
        new_h = CANVAS_H
        new_w = int(new_h * src_ratio)
    else:
        new_w = CANVAS_W
        new_h = int(new_w / src_ratio)
    src = src.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - CANVAS_W) // 2
    top  = (new_h - CANVAS_H) // 2
    img  = src.crop((left, top, left + CANVAS_W, top + CANVAS_H))

    # ── 2. Colour grading ─────────────────────────────────────────
    img = ImageEnhance.Brightness(img).enhance(0.72)
    img = ImageEnhance.Contrast(img).enhance(1.30)
    img = ImageEnhance.Color(img).enhance(0.70)

    # ── 3. Colour wash (teal/blue subtle tint by default) ─────────
    img = apply_color_wash(img, theme["wash"], theme["wash_str"])

    # ── 4. Strong vignette (natural darkness) ─────────────────────
    img = apply_vignette(img, strength=2.2)

    # ── 5. Load fonts ─────────────────────────────────────────────
    tf = download_font(font_style["title_url"], font_style["title_file"])
    bf = download_font(font_style["body_url"],  font_style["body_file"])

    f_title_big  = pil_font(tf, 110)
    f_title_sm   = pil_font(tf,  54)
    f_menu       = pil_font(bf,  30)
    f_version    = pil_font(bf,  18)

    glow_layers  = theme["glow_layers"]
    title_color  = theme["title_color"]
    menu_color   = theme["menu_color"]

    # ── 6. Title block — centered at left quarter ──────────────────
    TEXT_CX = 195          # horizontal center of the menu/title block
    # Adjusted vertical start for better overall centering
    title_y  = 280

    words = main_title.upper().split()
    if len(words) >= 2:
        top_line = " ".join(words[:-1])
        bot_line = words[-1]
    else:
        top_line = ""
        bot_line = main_title.upper()

    if top_line:
        img, after_top = draw_fire_glow_text(
            img, top_line, TEXT_CX, title_y,
            f_title_sm, title_color, glow_layers
        )
        title_y = after_top + 2
    else:
        after_top = title_y

    img, after_big = draw_fire_glow_text(
        img, bot_line, TEXT_CX, title_y,
        f_title_big, title_color, glow_layers
    )

    # ── 7. Menu items — centered under title, with selection arrow ─
    menu_items = [
        "> New Game",          # arrow added
        "Continue",
        "Select Chapter",
        "Options",
        "Exit"
    ]
    menu_start = after_big + 32
    row_h      = 50            # more spacing

    draw = ImageDraw.Draw(img)
    for i, item in enumerate(menu_items):
        my = menu_start + i * row_h
        draw_centered_text_plain(
            draw, item, TEXT_CX, my,
            f_menu, menu_color,
            shadow_color=(0, 0, 0),
            shadow_offset=2,
        )

    # ── 8. Subtitle (optional) ────────────────────────────────────
    if subtitle.strip():
        sub_y = menu_start + len(menu_items) * row_h + 14
        draw_centered_text_plain(
            draw, subtitle, TEXT_CX, sub_y,
            pil_font(bf, 22), (160, 150, 130),
        )

    # ── 9. Version number — bottom left ───────────────────────────
    draw.text((36, CANVAS_H - 38), version_str, font=f_version,
              fill=(130, 120, 100))

    # ── 10. Export PNG ────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
#  VIDEO PIPELINE  (FFmpeg — aligned with Pillow layout)
# ══════════════════════════════════════════════════════════════════

def build_ffmpeg_command(
    input_path: str,
    output_path: str,
    main_title: str,
    subtitle: str,
    font_path: str,
    theme: dict,
    version_str: str,
) -> list[str]:

    def esc(s: str) -> str:
        return (s.replace("\\", "\\\\")
                  .replace(":", "\\:")
                  .replace("'", "\\'")
                  .replace("%", "\\%"))

    words    = main_title.upper().split()
    top_line = esc(" ".join(words[:-1])) if len(words) >= 2 else ""
    bot_line = esc(words[-1] if words else "UNTITLED")
    shd      = "shadowcolor=black@0.80:shadowx=3:shadowy=3"

    # Colour wash & vignette (from theme)
    wr, wg, wb = [round(c * theme["wash_str"]) for c in theme["wash"]]
    geq = (
        f"geq="
        f"r='clip(r(X\\,Y)*0.72+{wr}\\,0\\,255)':"
        f"g='clip(g(X\\,Y)*0.72+{wg}\\,0\\,255)':"
        f"b='clip(b(X\\,Y)*0.72+{wb}\\,0\\,255)'"
    )

    # Menu items with arrow
    menu_items = [
        "> New Game",
        "Continue",
        "Select Chapter",
        "Options",
        "Exit"
    ]
    TEXT_CX = 195                # pixel position (align with Pillow)
    TITLE_Y = 280
    ROW_H   = 50
    MENU_Y0 = 490                # approximate after big title

    vf_parts = [
        "scale=1280:720:force_original_aspect_ratio=increase",
        "crop=1280:720",
        "eq=brightness=-0.28:contrast=1.30:saturation=0.70",
        geq,
        "vignette=PI/2.2:mode=backward",
        "noise=alls=6:allf=t+u",
    ]

    # Fire glow illusion (three passes)
    for blur_r, alpha in [(14, "0.55"), (8, "0.40"), (0, "1.00")]:
        fc = "white" if blur_r == 0 else f"#ffcc44@{alpha}"
        if top_line:
            vf_parts.append(
                f"drawtext=fontfile='{font_path}':text='{top_line}'"
                f":fontcolor={fc}:fontsize=54:x={TEXT_CX}-tw/2:y={TITLE_Y}"
                f":shadowcolor=black@0.80:shadowx={blur_r}:shadowy={blur_r}"
            )
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{bot_line}'"
            f":fontcolor={fc}:fontsize=110:x={TEXT_CX}-tw/2:y={TITLE_Y + (58 if top_line else 0)}"
            f":shadowcolor=black@0.80:shadowx={blur_r}:shadowy={blur_r}"
        )

    # Menu items
    for i, item in enumerate(menu_items):
        my = MENU_Y0 + i * ROW_H
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{esc(item)}'"
            f":fontcolor=white@0.88:fontsize=30:x={TEXT_CX}-tw/2:y={my}:{shd}"
        )

    if subtitle.strip():
        sub_y = MENU_Y0 + len(menu_items) * ROW_H + 14
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{esc(subtitle)}'"
            f":fontcolor=white@0.60:fontsize=22:x={TEXT_CX}-tw/2:y={sub_y}:{shd}"
        )

    vf_parts.append(
        f"drawtext=fontfile='{font_path}':text='{esc(version_str)}'"
        f":fontcolor=white@0.45:fontsize=18:x=36:y=h-38:{shd}"
    )

    return [
        "ffmpeg", "-y",
        "-t", "10",
        "-i", input_path,
        "-vf", ",".join(vf_parts),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        output_path,
    ]


# ══════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ══════════════════════════════════════════════════════════════════
st.markdown("# ⚔ Game Loading Screen Generator")
st.markdown("### Cinematic vignette · Fire glow · Centered menu · Teal wash")
st.markdown(
    '<div class="info-box">'
    "📸 <b>Image</b> → Pillow pipeline → PNG download<br>"
    "🎬 <b>Video</b> → FFmpeg pipeline → MP4 download<br>"
    "Title splits automatically: last word becomes the <b>large line</b>, rest is the small line above it.<br>"
    "e.g. <i>\"Your Text\"</i> → small <i>\"YOUR\"</i> + massive <i>\"TEXT\"</i>"
    "</div>",
    unsafe_allow_html=True,
)

ffmpeg_ok   = check_ffmpeg()
system_font = find_system_font()

c1, c2 = st.columns(2)
with c1:
    color = "#4caf50" if ffmpeg_ok else "#f44336"
    label = "✅ FFmpeg ready" if ffmpeg_ok else "❌ FFmpeg missing"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{color}">{label}</span>',
                unsafe_allow_html=True)
with c2:
    color = "#4caf50" if system_font else "#f0a030"
    label = "✅ System font" if system_font else "⚠ No system font"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{color}">{label}</span>',
                unsafe_allow_html=True)

st.divider()

uploaded = st.file_uploader(
    "Upload a video or image",
    type=["mp4", "mov", "avi", "mkv", "webm", "jpg", "jpeg", "png", "bmp", "webp"],
    help="Image → PNG via Pillow  |  Video → MP4 via FFmpeg",
)

main_title = st.text_input(
    "Game Title",
    placeholder="Your Text",
    max_chars=36,
    help='Last word becomes the BIG line. e.g. "Elden Ring" → small "ELDEN" + big "RING"',
)
subtitle = st.text_input(
    "Subtitle / Hint (optional)",
    placeholder="A new adventure awaits…",
    max_chars=60,
)
version_str = st.text_input("Version String", value="v 20.26", max_chars=20)

col_a, col_b = st.columns(2)
with col_a:
    font_choice  = st.selectbox("Font Style", list(FONT_STYLES.keys()))
with col_b:
    # Teal Cinematic becomes the default colour theme
    theme_choice = st.selectbox("Colour Theme", list(COLOR_THEMES.keys()), index=0)

font_style  = FONT_STYLES[font_choice]
color_theme = COLOR_THEMES[theme_choice]

generate_btn = st.button("⚡  Generate Loading Screen", use_container_width=True)

if generate_btn:
    if not uploaded:
        st.warning("Please upload a video or image first.")
        st.stop()
    if not main_title.strip():
        st.warning("Please enter a Game Title.")
        st.stop()

    suffix   = Path(uploaded.name).suffix.lower()
    is_image = suffix in IMAGE_EXTS
    raw      = uploaded.read()
    safe     = "".join(c if c.isalnum() or c in "_-" else "_" for c in main_title.strip())

    # ── IMAGE ──────────────────────────────────────────────────────
    if is_image:
        with st.spinner("🎨 Rendering…"):
            try:
                png = process_image(
                    raw_bytes=raw,
                    main_title=main_title.strip(),
                    subtitle=subtitle.strip(),
                    font_style=font_style,
                    theme=color_theme,
                    version_str=version_str.strip() or "v 20.26",
                )
            except Exception as exc:
                st.error(f"Pillow error: {exc}")
                st.stop()

        st.success("✅ Done!")
        st.image(png, use_container_width=True)
        st.download_button("⬇️  Download PNG", png,
                           f"{safe}_loading_screen.png", "image/png",
                           use_container_width=True)

    # ── VIDEO ──────────────────────────────────────────────────────
    else:
        if not ffmpeg_ok:
            st.error("FFmpeg is required for video processing.")
            st.stop()

        with st.spinner("⬇️ Checking font…"):
            dl = download_font(font_style["body_url"], font_style["body_file"])
            ffmpeg_font = str(dl) if (dl and dl.exists()) else system_font

        if not ffmpeg_font:
            st.error("No font available for FFmpeg text overlays.")
            st.stop()

        with tempfile.TemporaryDirectory() as tmp:
            in_p  = os.path.join(tmp, f"input{suffix}")
            out_p = os.path.join(tmp, "loading_screen.mp4")
            with open(in_p, "wb") as f:
                f.write(raw)

            cmd = build_ffmpeg_command(
                input_path=in_p,
                output_path=out_p,
                main_title=main_title.strip(),
                subtitle=subtitle.strip(),
                font_path=ffmpeg_font,
                theme=color_theme,
                version_str=version_str.strip() or "v 20.26",
            )

            with st.expander("🔧 FFmpeg command"):
                st.code(" \\\n  ".join(cmd), language="bash")

            with st.spinner("🎬 Rendering video…"):
                pbar = st.progress(0, text="Starting…")
                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for i in range(22):
                        if proc.poll() is not None:
                            break
                        time.sleep(0.35)
                        pct = int((i + 1) / 22 * 90)
                        pbar.progress(pct, text=f"Processing… {pct}%")
                    _, stderr = proc.communicate()
                    pbar.progress(100, text="Done!")

                    if proc.returncode != 0:
                        st.markdown(
                            '<div class="error-box"><b>FFmpeg Error:</b>\n'
                            + stderr.decode("utf-8", errors="replace") + "</div>",
                            unsafe_allow_html=True,
                        )
                        st.stop()

                    with open(out_p, "rb") as f:
                        mp4 = f.read()

                except FileNotFoundError:
                    st.error("FFmpeg not found on PATH.")
                    st.stop()
                except Exception as exc:
                    st.error(f"Unexpected error: {exc}")
                    st.stop()

            st.success("✅ Done!")
            st.video(mp4)
            st.download_button("⬇️  Download MP4", mp4,
                               f"{safe}_loading_screen.mp4", "video/mp4",
                               use_container_width=True)

st.divider()
st.markdown(
    '<p style="text-align:center;color:#201810;font-size:0.72rem;letter-spacing:0.1em;">'
    "POWERED BY FFMPEG · PILLOW · STREAMLIT"
    "</p>",
    unsafe_allow_html=True,
                            )
