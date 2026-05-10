"""
Video Game Loading Screen Generator  ·  v2.0
=============================================
Streamlit + FFmpeg (video) + Pillow (image)
Auto-downloads cinematic fonts from Google Fonts via GitHub.
Run with:  streamlit run app.py
"""

import io
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance, ImageChops

# ══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Game Loading Screen Generator",
    page_icon="⚔",
    layout="centered",
)

# ══════════════════════════════════════════════════════════════════
#  STREAMLIT THEME
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Share+Tech+Mono&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #080810;
    color: #dde0e8;
    font-family: 'Cinzel', serif;
}
[data-testid="stHeader"] { background: transparent; }

h1 {
    font-family: 'Cinzel', serif;
    color: #c8a96e;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    text-shadow: 0 0 28px #c8a96e55;
}
h3 { color: #6a7080; font-weight: 400; letter-spacing: 0.06em; }

.stButton > button {
    background: linear-gradient(135deg, #c8a96e 0%, #8b5e2a 100%);
    color: #080810;
    font-family: 'Cinzel', serif;
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: 0.14em;
    border: none;
    border-radius: 3px;
    padding: 0.65rem 2rem;
    text-transform: uppercase;
    transition: opacity 0.2s, box-shadow 0.2s;
    box-shadow: 0 0 18px #c8a96e33;
}
.stButton > button:hover { opacity: 0.88; box-shadow: 0 0 32px #c8a96e77; }

.stTextInput > div > div > input,
.stSelectbox > div > div {
    background: #10101e;
    border: 1px solid #2a2840;
    color: #dde0e8;
    border-radius: 3px;
    font-family: 'Share Tech Mono', monospace;
}
hr { border-color: #1e1e30; }

.info-box {
    background: #10101e;
    border-left: 3px solid #c8a96e;
    padding: 0.85rem 1.1rem;
    border-radius: 3px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.8rem;
    color: #7a8090;
    margin-bottom: 1.2rem;
    line-height: 1.7;
}
.error-box {
    background: #140a0a;
    border-left: 3px solid #cc3333;
    padding: 0.8rem 1rem;
    border-radius: 3px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    color: #ee8888;
    white-space: pre-wrap;
    overflow-x: auto;
}
.badge { font-family: 'Share Tech Mono', monospace; font-size: 0.82rem; }
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
    "Teal Cinematic": {"wash": (0, 20, 45),   "accent": (160, 215, 255), "glow": (100, 180, 255)},
    "Amber RPG":      {"wash": (35, 18, 0),    "accent": (200, 169, 110), "glow": (220, 180, 80)},
    "Crimson Dark":   {"wash": (45, 0, 0),     "accent": (220, 75,  75),  "glow": (255, 60,  60)},
    "Void Purple":    {"wash": (22, 0, 45),    "accent": (175, 95, 255),  "glow": (200, 120, 255)},
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


def get_pil_font(path: Path | None, size: int) -> ImageFont.FreeTypeFont:
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
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    try:
        res = subprocess.run(
            ["fc-list", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=5,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
#  PILLOW HELPERS
# ══════════════════════════════════════════════════════════════════

def apply_color_wash(img: Image.Image, wash_rgb: tuple, strength: float = 0.22) -> Image.Image:
    wash = Image.new("RGB", img.size, wash_rgb)
    return Image.blend(img.convert("RGB"), wash, strength)


def apply_vignette(img: Image.Image) -> Image.Image:
    w, h = img.size
    vignette = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(vignette)
    cx, cy = w // 2, h // 2
    for i in range(130, 0, -1):
        ratio = i / 130
        alpha = int(255 * (1 - ratio) ** 1.9)
        rx = int(cx * ratio * 1.05)
        ry = int(cy * ratio * 1.05)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    vignette = vignette.filter(ImageFilter.GaussianBlur(55))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = img.convert("RGB")
    img.paste(dark, mask=ImageChops.invert(vignette))
    return img


def draw_gradient_sidebar(img: Image.Image, width: int = 460) -> Image.Image:
    """Left-to-right gradient: opaque black → fully transparent."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    h = img.height
    for x in range(width):
        t = x / width
        alpha = int(195 * (1 - t ** 0.55))   # ease-out curve
        draw.line([(x, 0), (x, h)], fill=(0, 0, 0, alpha))
    base = img.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


def text_with_glow(
    img: Image.Image,
    text: str,
    pos: tuple,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    glow_color: tuple,
    glow_radius: int = 14,
) -> Image.Image:
    """Draw text with a blurred outer glow + drop shadow."""
    x, y = pos

    # Glow layer
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    for ox in (-2, 0, 2):
        for oy in (-2, 0, 2):
            gd.text((x + ox, y + oy), text, font=font, fill=(*glow_color, 140))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))

    base = img.convert("RGBA")
    base.alpha_composite(glow_layer)
    img = base.convert("RGB")

    # Shadow + main text
    draw = ImageDraw.Draw(img)
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 190))
    draw.text((x, y), text, font=font, fill=color)
    return img


# ══════════════════════════════════════════════════════════════════
#  IMAGE PIPELINE  (Pillow)
# ══════════════════════════════════════════════════════════════════

def process_image(
    raw_bytes: bytes,
    main_title: str,
    subtitle: str,
    font_style: dict,
    theme: dict,
) -> bytes:

    # 1. Open & resize to 1280×720
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

    # 2. Colour grading
    img = ImageEnhance.Brightness(img).enhance(0.87)
    img = ImageEnhance.Contrast(img).enhance(1.24)
    img = ImageEnhance.Color(img).enhance(0.78)

    # 3. Cinematic colour wash
    img = apply_color_wash(img, theme["wash"], strength=0.22)

    # 4. Vignette
    img = apply_vignette(img)

    # 5. Gradient sidebar
    img = draw_gradient_sidebar(img, width=480)

    # 6. Load fonts (downloaded or fallback)
    tf = download_font(font_style["title_url"], font_style["title_file"])
    bf = download_font(font_style["body_url"],  font_style["body_file"])
    f_title    = get_pil_font(tf, 66)
    f_subtitle = get_pil_font(bf, 30)
    f_menu     = get_pil_font(bf, 29)
    f_hint     = get_pil_font(bf, 20)

    accent = theme["accent"]
    glow   = theme["glow"]

    # 7. Main title with outer glow
    img = text_with_glow(
        img,
        text=main_title.upper(),
        pos=(40, 64),
        font=f_title,
        color=(255, 255, 255),
        glow_color=glow,
        glow_radius=18,
    )

    draw = ImageDraw.Draw(img)

    # 8. Subtitle
    if subtitle.strip():
        draw.text((42, 152), subtitle, font=f_subtitle, fill=(200, 205, 215))

    # 9. Thin accent separator
    sep_y = 196
    draw.line([(40, sep_y), (340, sep_y)], fill=(*accent, 100), width=1)

    # 10. Menu items — generous spacing, selection arrow on first
    menu_items = ["New Game", "Continue", "Options", "Exit"]
    start_y    = 214
    row_h      = 58          # generous line spacing

    for i, item in enumerate(menu_items):
        my = start_y + i * row_h
        if i == 0:
            # Active item: accent colour + › arrow
            draw.text((40, my), "›", font=f_menu, fill=(*accent, 255))
            draw.text((65, my), item, font=f_menu, fill=(*accent, 255))
        else:
            # Inactive: dimmed white
            draw.text((65, my), item, font=f_menu, fill=(185, 190, 200))

    # 11. Bottom hint bar
    hint_y = CANVAS_H - 40
    draw.line([(0, hint_y - 10), (CANVAS_W, hint_y - 10)], fill=(255, 255, 255, 16), width=1)
    draw.text((CANVAS_W // 2, hint_y), "PRESS START", font=f_hint,
              fill=(140, 145, 155), anchor="mm")

    # 12. Export PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
#  VIDEO PIPELINE  (FFmpeg)
# ══════════════════════════════════════════════════════════════════

def build_ffmpeg_command(
    input_path: str,
    output_path: str,
    main_title: str,
    subtitle: str,
    font_path: str,
    wash: tuple,
) -> list[str]:

    def esc(s: str) -> str:
        return (s.replace("\\", "\\\\")
                  .replace(":", "\\:")
                  .replace("'", "\\'")
                  .replace("%", "\\%"))

    mt  = esc(main_title.upper() or "UNTITLED")
    sbt = esc(subtitle or "")
    shd = "shadowcolor=black@0.75:shadowx=3:shadowy=3"

    # Colour wash via per-channel geq
    wr, wg, wb = [round(c * 0.22) for c in wash]
    geq = (
        f"geq="
        f"r='clip(r(X\\,Y)*0.88+{wr}\\,0\\,255)':"
        f"g='clip(g(X\\,Y)*0.88+{wg}\\,0\\,255)':"
        f"b='clip(b(X\\,Y)*0.88+{wb}\\,0\\,255)'"
    )

    menu_items = ["New Game", "Continue", "Options", "Exit"]
    menu_parts = []
    for i, item in enumerate(menu_items):
        my = 222 + i * 58
        if i == 0:
            menu_parts.append(
                f"drawtext=fontfile='{font_path}':text='› {esc(item)}'"
                f":fontcolor=#a8c8ff:fontsize=29:x=50:y={my}:{shd}"
            )
        else:
            menu_parts.append(
                f"drawtext=fontfile='{font_path}':text='{esc(item)}'"
                f":fontcolor=white@0.78:fontsize=29:x=65:y={my}:{shd}"
            )

    vf_parts = [
        "scale=1280:720:force_original_aspect_ratio=decrease",
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "eq=brightness=-0.10:contrast=1.22:saturation=0.78",
        geq,
        "vignette=PI/2:mode=backward",
        "noise=alls=7:allf=t+u",
        # Two-layer gradient sidebar approximation
        "drawbox=x=0:y=0:w=480:h=720:color=black@0.70:t=fill",
        "drawbox=x=0:y=0:w=220:h=720:color=black@0.18:t=fill",
        # Title — double pass for glow illusion
        f"drawtext=fontfile='{font_path}':text='{mt}':fontcolor=white:fontsize=62:x=40:y=64"
        f":shadowcolor=#6699ff@0.55:shadowx=0:shadowy=0",
        f"drawtext=fontfile='{font_path}':text='{mt}':fontcolor=white:fontsize=62:x=40:y=64:{shd}",
    ]

    if subtitle.strip():
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{sbt}'"
            f":fontcolor=white@0.80:fontsize=29:x=42:y=152:{shd}"
        )

    # Separator line approximation via a thin drawbox
    vf_parts.append("drawbox=x=40:y=196:w=300:h=1:color=white@0.25:t=fill")

    vf_parts += menu_parts

    # Bottom hint
    vf_parts.append(
        f"drawtext=fontfile='{font_path}':text='PRESS START'"
        f":fontcolor=white@0.40:fontsize=20:x=(w-text_w)/2:y=h-36:{shd}"
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
st.markdown("### Cinematic grade · Auto fonts · Gradient overlay · Glow title")
st.markdown(
    '<div class="info-box">'
    "📸 <b>Image upload</b> → processed entirely by Pillow → PNG download<br>"
    "🎬 <b>Video upload</b> → first 10 s processed by FFmpeg → MP4 download<br>"
    "Cinematic fonts are downloaded automatically — nothing to install manually."
    "</div>",
    unsafe_allow_html=True,
)

# ── Status badges ─────────────────────────────────────────────────
ffmpeg_ok   = check_ffmpeg()
system_font = find_system_font()

c1, c2 = st.columns(2)
with c1:
    if ffmpeg_ok:
        st.markdown('<span class="badge" style="color:#4caf50">✅ FFmpeg ready</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge" style="color:#f44336">❌ FFmpeg missing (video disabled)</span>', unsafe_allow_html=True)
with c2:
    if system_font:
        st.markdown('<span class="badge" style="color:#4caf50">✅ System font found</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge" style="color:#f0a030">⚠ No system font — will use downloaded font</span>', unsafe_allow_html=True)

st.divider()

# ── Inputs ────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a video or image",
    type=["mp4", "mov", "avi", "mkv", "webm", "jpg", "jpeg", "png", "bmp", "webp"],
    help="Image → PNG via Pillow   |   Video → MP4 via FFmpeg",
)

main_title = st.text_input("Main Title", placeholder="ELDEN ODYSSEY", max_chars=36)
subtitle   = st.text_input("Subtitle / Hint (optional)", placeholder="A new adventure awaits…", max_chars=60)

col_a, col_b = st.columns(2)
with col_a:
    font_choice  = st.selectbox("Font Style", list(FONT_STYLES.keys()))
with col_b:
    theme_choice = st.selectbox("Colour Theme", list(COLOR_THEMES.keys()))

font_style  = FONT_STYLES[font_choice]
color_theme = COLOR_THEMES[theme_choice]

generate_btn = st.button("⚡  Generate Loading Screen", use_container_width=True)

# ── Generation ────────────────────────────────────────────────────
if generate_btn:
    if not uploaded:
        st.warning("Please upload a video or image first.")
        st.stop()
    if not main_title.strip():
        st.warning("Please enter a Main Title.")
        st.stop()

    suffix   = Path(uploaded.name).suffix.lower()
    is_image = suffix in IMAGE_EXTS
    raw      = uploaded.read()
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in main_title.strip())

    # ── IMAGE PATH ────────────────────────────────────────────────
    if is_image:
        with st.spinner("🎨 Rendering with Pillow…"):
            try:
                png_bytes = process_image(
                    raw_bytes=raw,
                    main_title=main_title.strip(),
                    subtitle=subtitle.strip(),
                    font_style=font_style,
                    theme=color_theme,
                )
            except Exception as exc:
                st.error(f"Pillow error: {exc}")
                st.stop()

        st.success("✅ Image loading screen ready!")
        st.image(png_bytes, use_container_width=True)
        st.download_button(
            "⬇️  Download PNG",
            data=png_bytes,
            file_name=f"{safe_name}_loading_screen.png",
            mime="image/png",
            use_container_width=True,
        )

    # ── VIDEO PATH ────────────────────────────────────────────────
    else:
        if not ffmpeg_ok:
            st.error("FFmpeg is required for video processing.")
            st.stop()

        with st.spinner("⬇️ Checking font…"):
            dl_font    = download_font(font_style["body_url"], font_style["body_file"])
            ffmpeg_font = str(dl_font) if (dl_font and dl_font.exists()) else system_font

        if not ffmpeg_font:
            st.error("No font available for FFmpeg text overlays. Font download may have failed.")
            st.stop()

        with tempfile.TemporaryDirectory() as tmp:
            in_path  = os.path.join(tmp, f"input{suffix}")
            out_path = os.path.join(tmp, "loading_screen.mp4")

            with open(in_path, "wb") as f:
                f.write(raw)

            cmd = build_ffmpeg_command(
                input_path=in_path,
                output_path=out_path,
                main_title=main_title.strip(),
                subtitle=subtitle.strip(),
                font_path=ffmpeg_font,
                wash=color_theme["wash"],
            )

            with st.expander("🔧 FFmpeg command"):
                st.code(" \\\n  ".join(cmd), language="bash")

            with st.spinner("🎬 Rendering video…"):
                pbar = st.progress(0, text="Starting FFmpeg…")
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
                            + stderr.decode("utf-8", errors="replace")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                        st.stop()

                    with open(out_path, "rb") as f:
                        mp4_bytes = f.read()

                except FileNotFoundError:
                    st.error("FFmpeg binary not found. Ensure it is installed and on PATH.")
                    st.stop()
                except Exception as exc:
                    st.error(f"Unexpected error: {exc}")
                    st.stop()

            st.success("✅ Video loading screen ready!")
            st.video(mp4_bytes)
            st.download_button(
                "⬇️  Download MP4",
                data=mp4_bytes,
                file_name=f"{safe_name}_loading_screen.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

# ── Footer ────────────────────────────────────────────────────────
st.divider()
st.markdown(
    '<p style="text-align:center;color:#282838;font-size:0.74rem;letter-spacing:0.1em;">'
    "POWERED BY FFMPEG · PILLOW · STREAMLIT"
    "</p>",
    unsafe_allow_html=True,
)
