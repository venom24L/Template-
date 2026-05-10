"""
AAA Game Loading Screen Generator  ·  v4.0
===========================================
Automatic Google Font download (Cinzel)  ·  Pillow overlay engine
Video → FFmpeg blends high‑res overlay  ·  Image → Pillow composite
Left gradient (40% width)  ·  Glow text with letter spacing
Fully self‑sufficient – no local fonts required
"""

import io
import os
import subprocess
import sys
import tempfile
import time
import traceback
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

# Dark cinematic UI styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Share+Tech+Mono&display=swap');
html, body, [data-testid="stAppViewContainer"] {
    background: #06060e; color: #d8d0c0; font-family: 'Cinzel', serif;
}
[data-testid="stHeader"] { background: transparent; }
h1 {
    font-family: 'Cinzel', serif; color: #c8a050; letter-spacing: 0.14em; text-transform: uppercase;
    text-shadow: 0 0 30px #c8a05066;
}
.stButton > button {
    background: linear-gradient(135deg, #c8a050 0%, #7a4a10 100%); color: #06060e;
    font-family: 'Cinzel', serif; font-weight: 700; font-size: 1rem; letter-spacing: 0.14em;
    border: none; border-radius: 2px; padding: 0.65rem 2rem; text-transform: uppercase;
    box-shadow: 0 0 20px #c8a05033; transition: opacity 0.2s, box-shadow 0.2s;
}
.stButton > button:hover { opacity: 0.85; box-shadow: 0 0 36px #c8a05077; }
.info-box {
    background: #0e0c14; border-left: 3px solid #c8a050; padding: 0.85rem 1.1rem;
    border-radius: 2px; font-family: 'Share Tech Mono', monospace; font-size: 0.8rem;
    color: #706050; margin-bottom: 1.2rem; line-height: 1.8;
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

# ── Font definitions (Cinzel Regular + Bold) ────────────────────
FONT_STYLES = {
    "Cinzel (RPG / Fantasy)": {
        "title_urls": [
            "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Bold.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/static/Cinzel-Bold.ttf",
        ],
        "body_urls": [
            "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Regular.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/static/Cinzel-Regular.ttf",
        ],
        "title_file": "Cinzel-Bold.ttf",
        "body_file":  "Cinzel-Regular.ttf",
    },
}

# ── Colour themes (wash tint + golden glow) ─────────────────────
COLOR_THEMES = {
    "Teal Cinematic (AAA Cool)": {
        "wash": (0, 22, 42), "wash_str": 0.28,
        "glow_layers": [(180,220,255,28,170), (100,200,255,18,130), (0,100,200,10,80)],
        "title_color": (220,245,255),
        "menu_color":  (230,230,230),     # crisp white for menu
        "menu_glow":   (200,230,255),
    },
    "Golden Fantasy (Warm)": {
        "wash": (45,18,0), "wash_str": 0.28,
        "glow_layers": [(255,210,80,28,190), (255,150,30,18,140), (200,80,0,10,90)],
        "title_color": (255,245,210),
        "menu_color":  (255,255,255),
        "menu_glow":   (255,240,200),
    },
}

# ── Layout settings ──────────────────────────────────────────────
TEXT_CX      = 155            # horizontal center of the menu block
LEFT_GRAD_W  = int(CANVAS_W * 0.4)   # 512 px ≈ 40% width
MENU_ROW_H   = 52             # line height
MENU_GLOW_BLUR = 5
TITLE_LETTER_SPACING = 2

# ══════════════════════════════════════════════════════════════════
#  FONT MANAGEMENT
# ══════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def download_font(urls: list[str], filename: str) -> Path | None:
    """Download a font from multiple fallback URLs, cache locally."""
    dest = FONTS_DIR / filename
    if dest.exists():
        return dest
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return dest
        except Exception:
            continue
    return None

def pil_font(path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    if path and path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()

def find_system_font() -> str | None:
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf"]:
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
#  FFMPEG CHECK
# ══════════════════════════════════════════════════════════════════
def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════
#  PILLOW: BACKGROUND EFFECTS (for image pipeline)
# ══════════════════════════════════════════════════════════════════
def apply_color_wash(img: Image.Image, rgb: tuple, strength: float) -> Image.Image:
    wash = Image.new("RGB", img.size, rgb)
    return Image.blend(img.convert("RGB"), wash, strength)

def apply_vignette(img: Image.Image, strength: float = 2.0) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = w // 2, h // 2
    for i in range(180, 0, -1):
        ratio = i / 180
        alpha = int(255 * (1 - ratio) ** strength)
        rx = int(cx * ratio * 1.2)
        ry = int(cy * ratio * 1.2)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(60))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = img.convert("RGB")
    img.paste(dark, mask=ImageChops.invert(mask))
    return img

# ══════════════════════════════════════════════════════════════════
#  PILLOW: CINEMATIC OVERLAY GENERATOR
# ══════════════════════════════════════════════════════════════════
def draw_left_gradient(canvas: Image.Image, grad_w: int):
    """Paint a left‑to‑right black gradient (80% → 0%) directly into the RGBA canvas."""
    draw = ImageDraw.Draw(canvas)
    for x in range(grad_w):
        alpha = int(204 * (1 - x / grad_w))   # 80% opaque black at x=0
        draw.line([(x, 0), (x, CANVAS_H)], fill=(0, 0, 0, alpha))

def draw_text_with_spacing(draw: ImageDraw.Draw, text: str, x: int, y: int,
                           font, fill, spacing: int = TITLE_LETTER_SPACING):
    """Character‑by‑character drawing for letter spacing. (slow but only used for title)"""
    if not text:
        return 0, y
    dummy = ImageDraw.Draw(Image.new("L", (1, 1)))
    base_x = x
    max_bottom = y
    for ch in text:
        draw.text((base_x, y), ch, font=font, fill=fill)
        bbox = draw.textbbox((base_x, y), ch, font=font)
        base_x = bbox[2] + spacing
        max_bottom = max(max_bottom, bbox[3])
    # return total width and bottom
    total_w = base_x - spacing - x
    return total_w, max_bottom

def draw_fire_glow_text_rgba(
    canvas: Image.Image,    # RGBA
    text: str,
    cx: int,
    y: int,
    font,
    text_color: tuple,
    glow_layers: list[tuple[int,int,int,int,int]],   # (r,g,b,blur,alpha)
    letter_spacing: int = 0,
) -> tuple[Image.Image, int]:
    """
    Draw centered glow text into an RGBA canvas.
    Returns updated canvas and bottom y.
    """
    # measure total width with spacing
    dummy = ImageDraw.Draw(canvas)
    if letter_spacing:
        w_total, h_total = draw_text_with_spacing(dummy, text, 0, 0, font, (0,0,0), letter_spacing)
    else:
        bbox = dummy.textbbox((0,0), text, font=font)
        w_total, h_total = bbox[2]-bbox[0], bbox[3]-bbox[1]

    tx = cx - w_total // 2

    # Draw each glow layer (innermost last) onto canvas
    for (gr, gg, gb, blur, alpha_max) in reversed(glow_layers):
        layer = Image.new("RGBA", canvas.size, (0,0,0,0))
        ld = ImageDraw.Draw(layer)
        if letter_spacing:
            draw_text_with_spacing(ld, text, tx, y, font, (gr, gg, gb, alpha_max), letter_spacing)
        else:
            ld.text((tx, y), text, font=font, fill=(gr, gg, gb, alpha_max))
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        canvas = Image.alpha_composite(canvas, layer)   # canvas must be RGBA

    # Drop shadow
    shadow = Image.new("RGBA", canvas.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    if letter_spacing:
        draw_text_with_spacing(sd, text, tx+4, y+4, font, (0,0,0,140), letter_spacing)
    else:
        sd.text((tx+4, y+4), text, font=font, fill=(0,0,0,140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    canvas = Image.alpha_composite(canvas, shadow)

    # Main text
    md = ImageDraw.Draw(canvas)
    if letter_spacing:
        draw_text_with_spacing(md, text, tx, y, font, (*text_color, 255), letter_spacing)
    else:
        md.text((tx, y), text, font=font, fill=(*text_color, 255))

    return canvas, y + h_total

def create_overlay(
    main_title: str,
    subtitle: str,
    font_style: dict,
    theme: dict,
    version_str: str,
) -> Image.Image:
    """Build a full RGBA overlay image (1280×720) with gradient, title, menu, version."""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    # 1. Left gradient (black → transparent)
    draw_left_gradient(canvas, LEFT_GRAD_W)

    # 2. Load fonts
    tf = download_font(font_style["title_urls"], font_style["title_file"])
    bf = download_font(font_style["body_urls"],  font_style["body_file"])
    f_title_big = pil_font(tf, 108)
    f_title_sm  = pil_font(tf, 52)
    f_menu      = pil_font(bf, 30)
    f_sub       = pil_font(bf, 22)
    f_version   = pil_font(bf, 18)

    glow_layers = theme["glow_layers"]
    title_color = theme["title_color"]
    menu_color  = theme["menu_color"]
    menu_glow   = theme["menu_glow"]

    # 3. Title block – split at last word
    words = main_title.upper().split()
    top_line = " ".join(words[:-1]) if len(words) > 1 else ""
    bot_line = words[-1] if words else "UNTITLED"
    title_y = 220

    if top_line:
        canvas, after_top = draw_fire_glow_text_rgba(
            canvas, top_line, TEXT_CX, title_y, f_title_sm,
            title_color, glow_layers, TITLE_LETTER_SPACING
        )
        title_y = after_top + 12
    # Big line
    canvas, after_big = draw_fire_glow_text_rgba(
        canvas, bot_line, TEXT_CX, title_y, f_title_big,
        title_color, glow_layers, TITLE_LETTER_SPACING
    )

    # 4. Menu items (crisp white, subtle outer glow)
    menu_items = ["> New Game", "Continue", "Select Chapter", "Options", "Exit"]
    menu_start = after_big + 40

    for idx, item in enumerate(menu_items):
        my = menu_start + idx * MENU_ROW_H
        # measure width for center
        dummy_draw = ImageDraw.Draw(canvas)
        bbox = dummy_draw.textbbox((0,0), item, font=f_menu)
        tw = bbox[2] - bbox[0]
        tx = TEXT_CX - tw // 2

        # Glow (white/golden)
        glow_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
        gd = ImageDraw.Draw(glow_layer)
        gd.text((tx, my), item, font=f_menu, fill=(*menu_glow, 80))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(MENU_GLOW_BLUR))
        canvas = Image.alpha_composite(canvas, glow_layer)

        # Shadow + main text
        sd = ImageDraw.Draw(canvas)
        sd.text((tx+2, my+2), item, font=f_menu, fill=(0,0,0,160))
        sd.text((tx, my), item, font=f_menu, fill=(*menu_color, 255))

    # 5. Subtitle (optional)
    if subtitle.strip():
        sub_y = menu_start + len(menu_items) * MENU_ROW_H + 18
        bbox = dummy_draw.textbbox((0,0), subtitle, font=f_sub)
        tw = bbox[2] - bbox[0]
        tx = TEXT_CX - tw // 2
        # subtle shadow
        ImageDraw.Draw(canvas).text((tx+2, sub_y+2), subtitle, font=f_sub, fill=(0,0,0,120))
        ImageDraw.Draw(canvas).text((tx, sub_y), subtitle, font=f_sub, fill=(180,175,165,255))

    # 6. Version bottom‑left
    ver_draw = ImageDraw.Draw(canvas)
    ver_draw.text((36, CANVAS_H-45), version_str, font=f_version, fill=(130,120,100,220))

    return canvas

# ══════════════════════════════════════════════════════════════════
#  IMAGE PIPELINE (Pillow composite)
# ══════════════════════════════════════════════════════════════════
def process_image(raw_bytes: bytes, main_title: str, subtitle: str,
                  font_style: dict, theme: dict, version_str: str) -> bytes:
    # 1. Open and fill canvas (cover crop)
    src = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    ratio = src.width / src.height
    tgt_ratio = CANVAS_W / CANVAS_H
    if ratio > tgt_ratio:
        new_h = CANVAS_H
        new_w = int(new_h * ratio)
    else:
        new_w = CANVAS_W
        new_h = int(new_w / ratio)
    src = src.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - CANVAS_W) // 2
    top  = (new_h - CANVAS_H) // 2
    bg = src.crop((left, top, left + CANVAS_W, top + CANVAS_H))

    # 2. Cinematic grading (moody and dramatic)
    bg = ImageEnhance.Brightness(bg).enhance(0.72)      # darken
    bg = ImageEnhance.Contrast(bg).enhance(1.30)        # high contrast
    bg = ImageEnhance.Color(bg).enhance(0.70)           # slightly desaturate
    bg = apply_color_wash(bg, theme["wash"], theme["wash_str"])
    bg = apply_vignette(bg, strength=2.0)

    # 3. Generate overlay
    overlay = create_overlay(main_title, subtitle, font_style, theme, version_str)

    # 4. Composite overlay onto background
    bg_rgba = bg.convert("RGBA")
    final = Image.alpha_composite(bg_rgba, overlay).convert("RGB")

    # 5. Export PNG
    buf = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════
#  VIDEO PIPELINE (Generate overlay PNG → FFmpeg blend)
# ══════════════════════════════════════════════════════════════════
def process_video(input_video_path: str, output_video_path: str,
                  main_title: str, subtitle: str, font_style: dict,
                  theme: dict, version_str: str) -> None:
    # 1. Create overlay PNG and save to temp file
    overlay_img = create_overlay(main_title, subtitle, font_style, theme, version_str)
    overlay_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    overlay_img.save(overlay_path, format="PNG")

    # 2. Build FFmpeg command
    #    Video processing: scale, crop, darken, contrast, color tint, vignette,
    #    then overlay the PNG on top.
    #    The overlay has left gradient, title glow, menu, etc. with transparent background.
    #    We combine everything in one filter_complex.
    wash_rgb = theme["wash"]
    wash_str = theme["wash_str"]
    # geq for subtle colour wash (add tint to each channel)
    # after the main eq, we add a geq that blends the wash color
    # g = channel + wash_channel * wash_str (but we also have darkening)
    # Actually we can do: eq=brightness=-0.15:contrast=1.3, then colorbalance to add tint.
    # For simplicity, use colorbalance to shift shadows/midtones.
    # We'll use: colorbalance=rs=... :gs=... :bs=... with small values.
    # Compute tint: each channel shift = wash_channel * wash_str / 2 (since colorbalance uses -1..1)
    rs = wash_rgb[0] * wash_str * 0.003   # arbitrary mapping
    gs = wash_rgb[1] * wash_str * 0.003
    bs = wash_rgb[2] * wash_str * 0.003

    filter_complex = (
        f"[0:v]"
        f"scale=1280:720:force_original_aspect_ratio=increase,"
        f"crop=1280:720,"
        f"eq=brightness=-0.15:contrast=1.3,"
        f"colorbalance=rs={rs:.3f}:gs={gs:.3f}:bs={bs:.3f},"
        f"vignette=PI/2.4:mode=backward"
        f"[bg];"
        f"[bg][1:v]overlay=0:0"
    )

    cmd = [
        "ffmpeg", "-y",
        "-t", "10",
        "-i", input_video_path,
        "-i", overlay_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        output_video_path,
    ]

    # Debug print
    print(" ".join(cmd))

    # 3. Run FFmpeg
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{stderr.decode('utf-8', errors='replace')}")
    finally:
        os.unlink(overlay_path)  # clean up temporary overlay

# ══════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ══════════════════════════════════════════════════════════════════
st.markdown("# ⚔ Game Loading Screen Generator")
st.markdown("### AAA cinematic · Pillow overlay · FFmpeg blend · Auto‑font")
st.markdown(
    '<div class="info-box">'
    "📸 **Image** → Pillow composite → PNG download<br>"
    "🎬 **Video** → Pillow overlay + FFmpeg blend → MP4 download<br>"
    "Title splits automatically (<i>\"Your Text\"</i> → small \"YOUR\" + big \"TEXT\")<br>"
    "No manual fonts – everything downloads on first run."
    '</div>', unsafe_allow_html=True
)

ffmpeg_ok = check_ffmpeg()
sys_font = find_system_font()

c1, c2 = st.columns(2)
with c1:
    col = "#4caf50" if ffmpeg_ok else "#f44336"
    lbl = "✅ FFmpeg ready" if ffmpeg_ok else "❌ FFmpeg missing"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{col}">{lbl}</span>', unsafe_allow_html=True)
with c2:
    col = "#4caf50" if sys_font else "#f0a030"
    lbl = "✅ System font" if sys_font else "⚠ No system font (fallback may be used)"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{col}">{lbl}</span>', unsafe_allow_html=True)

st.divider()

uploaded = st.file_uploader(
    "Upload a video or image",
    type=["mp4","mov","avi","mkv","webm","jpg","jpeg","png","bmp","webp"],
    help="Image → PNG   |   Video → MP4"
)

main_title = st.text_input("Game Title", placeholder="Your Text", max_chars=36,
                           help='Last word becomes the BIG line. e.g. "Elden Ring" → small "ELDEN" + big "RING"')
subtitle = st.text_input("Subtitle / Hint (optional)", placeholder="A new adventure awaits…", max_chars=60)
version_str = st.text_input("Version String", value="v 20.26", max_chars=20)

col_a, col_b = st.columns(2)
with col_a:
    font_choice = st.selectbox("Font Style", list(FONT_STYLES.keys()))
with col_b:
    theme_choice = st.selectbox("Colour Theme", list(COLOR_THEMES.keys()), index=0)

font_style = FONT_STYLES[font_choice]
color_theme = COLOR_THEMES[theme_choice]

if st.button("⚡  Generate Loading Screen", use_container_width=True):
    if not uploaded:
        st.warning("Please upload a video or image first.")
        st.stop()
    if not main_title.strip():
        st.warning("Please enter a Game Title.")
        st.stop()

    suffix = Path(uploaded.name).suffix.lower()
    is_image = suffix in IMAGE_EXTS
    raw = uploaded.read()
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in main_title.strip())

    # ── IMAGE ──────────────────────────────────────────────────────
    if is_image:
        with st.spinner("🎨 Rendering cinematic image…"):
            try:
                png = process_image(raw, main_title.strip(), subtitle.strip(),
                                    font_style, color_theme, version_str.strip() or "v 20.26")
            except Exception as exc:
                st.error(f"Pillow error: {exc}")
                traceback.print_exc()
                st.stop()
        st.success("✅ Done!")
        st.image(png, use_container_width=True)
        st.download_button("⬇️  Download PNG", png,
                           f"{safe_name}_loading_screen.png", "image/png",
                           use_container_width=True)

    # ── VIDEO ──────────────────────────────────────────────────────
    else:
        if not ffmpeg_ok:
            st.error("FFmpeg is required for video processing.")
            st.stop()

        # Check font availability (for overlay creation – download happens inside)
        # We'll let create_overlay handle it; if it fails, we catch the error.
        with tempfile.TemporaryDirectory() as tmp:
            in_p = os.path.join(tmp, f"input{suffix}")
            out_p = os.path.join(tmp, "loading_screen.mp4")
            with open(in_p, "wb") as f:
                f.write(raw)

            with st.spinner("🎬 Rendering cinematic video…"):
                pbar = st.progress(0, text="Starting…")
                try:
                    process_video(in_p, out_p, main_title.strip(), subtitle.strip(),
                                  font_style, color_theme, version_str.strip() or "v 20.26")
                    pbar.progress(100, text="Done!")
                except Exception as exc:
                    st.error(f"Video processing failed: {exc}")
                    traceback.print_exc()
                    st.stop()

            with open(out_p, "rb") as f:
                mp4 = f.read()

        st.success("✅ Done!")
        st.video(mp4)
        st.download_button("⬇️  Download MP4", mp4,
                           f"{safe_name}_loading_screen.mp4", "video/mp4",
                           use_container_width=True)

st.divider()
st.markdown(
    '<p style="text-align:center;color:#201810;font-size:0.72rem;letter-spacing:0.1em;">'
    "POWERED BY FFMPEG · PILLOW · STREAMLIT"
    "</p>",
    unsafe_allow_html=True,
  )
