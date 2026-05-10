"""
Video Game Loading Screen Generator  ·  v3.1 – AAA Cinematic Edition
===================================================================
New in this version:
  • Smooth left‑side dark gradient (80% black → transparent) behind menu
  • Title: bold, 2px letter‑spacing, extreme fire glow
  • Menu items: outer white glow + better line spacing
  • Video pipeline: gamma/saturation colour grading, soft vignette, gradient overlay
  • Robust Google Font download (Cinzel, Bebas Neue, Orbitron) with local fallback
  • FFmpeg command printed to console for debug
Run:  streamlit run app.py
"""

import io, os, subprocess, sys, tempfile, time, traceback
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
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  CONSTANTS & DEFAULTS
# ══════════════════════════════════════════════════════════════════
CANVAS_W, CANVAS_H = 1280, 720
FONTS_DIR = Path("fonts_cache")
FONTS_DIR.mkdir(exist_ok=True)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ── Google Fonts (raw GitHub URLs, multiple fallbacks) ──
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
    "Bebas Neue (Racing / Action)": {
        "title_urls": [
            "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf",
        ],
        "body_urls": [
            "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf",
        ],
        "title_file": "BebasNeue-Regular.ttf",
        "body_file":  "BebasNeue-Regular.ttf",
    },
    "Orbitron (Sci-Fi / Cyber)": {
        "title_urls": [
            "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron[wght].ttf",
        ],
        "body_urls": [
            "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
            "https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron[wght].ttf",
        ],
        "title_file": "Orbitron.ttf",
        "body_file":  "Orbitron.ttf",
    },
}

# Colour themes — now used by both Pillow and FFmpeg
COLOR_THEMES = {
    "Teal Cinematic (AAA Cool)": {
        "wash": (0, 22, 42), "wash_str": 0.28,
        "glow_layers": [(120,210,255,28,200), (20,130,210,18,140), (0,50,130,10,90)],
        "title_color": (220,245,255),
        "menu_color":  (190,215,230),
        "menu_glow": (200,230,255),
    },
    "Amber Warm (Classic Fantasy)": {
        "wash": (45,18,0), "wash_str": 0.28,
        "glow_layers": [(255,200,60,28,220), (255,140,20,18,160), (180,60,0,10,100)],
        "title_color": (255,245,210),
        "menu_color":  (230,215,185),
        "menu_glow": (255,230,140),
    },
    "Crimson Dark (Brutal)": {
        "wash": (42,0,0), "wash_str": 0.26,
        "glow_layers": [(255,100,60,28,220), (200,30,10,18,160), (120,0,0,10,100)],
        "title_color": (255,220,210),
        "menu_color":  (230,190,180),
        "menu_glow": (255,100,60),
    },
    "Void Purple (Mysterious)": {
        "wash": (18,0,38), "wash_str": 0.26,
        "glow_layers": [(200,130,255,28,220), (140,50,220,18,160), (60,0,140,10,100)],
        "title_color": (230,210,255),
        "menu_color":  (200,185,235),
        "menu_glow": (210,140,255),
    },
}

# ── Layout settings ──────────────────────────────────────────────
TEXT_CX   = 135          # horizontal center of the menu block (left quarter)
GRADIENT_W = 380         # width of the left‑side dark gradient
MENU_ROW_H = 52          # line height for menu items
MENU_GLOW_BLUR = 5       # radius of outer glow on menu text

# ══════════════════════════════════════════════════════════════════
#  FONT MANAGEMENT (cache_resource – persists across sessions)
# ══════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def download_font(urls: list[str], filename: str) -> Path | None:
    dest = FONTS_DIR / filename
    if dest.exists():
        return dest
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"Font downloaded: {filename}")
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
    """Return path to an available system font (truetype)."""
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
#  FFMPEG CHECK
# ══════════════════════════════════════════════════════════════════
def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
#  PILLOW EFFECTS
# ══════════════════════════════════════════════════════════════════

def apply_color_wash(img: Image.Image, rgb: tuple, strength: float) -> Image.Image:
    wash = Image.new("RGB", img.size, rgb)
    return Image.blend(img.convert("RGB"), wash, strength)


def apply_vignette(img: Image.Image, strength: float = 2.0) -> Image.Image:
    """Soft radial vignette – darkens edges, leaves centre unaffected."""
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


def draw_left_gradient(img: Image.Image) -> Image.Image:
    """
    Overlay a left‑to‑right gradient: black@0.8 -> fully transparent.
    Width GRADIENT_W px. Creates a cinematic dark zone behind the menu.
    """
    grad = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grad)
    for x in range(GRADIENT_W):
        alpha = int(204 * (1 - x / GRADIENT_W))   # 80% black at left edge
        draw.line([(x, 0), (x, img.height)], fill=(0, 0, 0, alpha))
    # Blend onto RGB image
    out = img.convert("RGBA")
    out.alpha_composite(grad)
    return out.convert("RGB")


def draw_text_with_spacing(
    draw: ImageDraw.Draw | Image.Image,
    text: str,
    x: int,
    y: int,
    font,
    fill,
    spacing: int = 2,
) -> tuple[int, int]:
    """
    Draw text character by character, increasing x by char-width + spacing.
    Returns (text_width, bottom_y) of the whole string.
    Works on any drawable (ImageDraw or Image).
    Is slow but only used for the main title.
    """
    if not text:
        return 0, y
    # Determine total width including spacing
    total_w = 0
    heights = []
    im = Image.new("L", (1, 1))   # dummy to get character bboxes
    dummy_draw = ImageDraw.Draw(im)
    for ch in text:
        bbox = dummy_draw.textbbox((0, 0), ch, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        total_w += w + spacing
        heights.append(h)
    total_w -= spacing   # remove trailing spacing
    # Start drawing
    from PIL import ImageFont as IF
    base_x = x
    max_bottom = y + max(heights) if heights else y
    for ch, h in zip(text, heights):
        draw.text((base_x, y), ch, font=font, fill=fill)
        bbox = draw.textbbox((base_x, y), ch, font=font)
        base_x = bbox[2] + spacing
    return total_w, max_bottom


def draw_fire_glow_text(
    img: Image.Image,
    text: str,
    cx: int,
    y: int,
    font,
    text_color: tuple,
    glow_layers: list[tuple[int,int,int,int,int]],
    letter_spacing: int = 0,
) -> tuple[Image.Image, int]:
    """
    Draw title text centred at cx, with multi‑pass fire glow and drop shadow.
    Returns (updated_img, bottom_y_of_text).
    Optional letter_spacing in pixels.
    """
    # Calculate size of the whole string (with spacing)
    dummy = ImageDraw.Draw(img)
    if letter_spacing:
        # measure using our spacing function
        w_total, h_total = _measure_spaced_text(text, font, letter_spacing)
    else:
        bbox = dummy.textbbox((0, 0), text, font=font)
        w_total = bbox[2] - bbox[0]
        h_total = bbox[3] - bbox[1]

    tx = cx - w_total // 2

    base = img.convert("RGBA")

    # 1. Glow layers (innermost last)
    for (gr, gg, gb, blur, alpha_max) in reversed(glow_layers):
        glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        if letter_spacing:
            draw_text_with_spacing(gd, text, tx, y, font,
                                   fill=(gr, gg, gb, alpha_max),
                                   spacing=letter_spacing)
        else:
            gd.text((tx, y), text, font=font, fill=(gr, gg, gb, alpha_max))
        glow = glow.filter(ImageFilter.GaussianBlur(blur))
        base.alpha_composite(glow)

    # 2. Drop shadow
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    if letter_spacing:
        draw_text_with_spacing(sd, text, tx + 4, y + 4, font,
                               fill=(0, 0, 0, 160), spacing=letter_spacing)
    else:
        sd.text((tx + 4, y + 4), text, font=font, fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    base.alpha_composite(shadow)

    # 3. Sharp main text
    td = ImageDraw.Draw(base)
    if letter_spacing:
        draw_text_with_spacing(td, text, tx, y, font,
                               fill=(*text_color, 255), spacing=letter_spacing)
    else:
        td.text((tx, y), text, font=font, fill=(*text_color, 255))

    return base.convert("RGB"), y + h_total


def _measure_spaced_text(text: str, font, spacing: int) -> tuple[int, int]:
    """Helper: return total width and height of spaced text."""
    dummy = ImageDraw.Draw(Image.new("L", (1,1)))
    w_total = 0
    max_h = 0
    for ch in text:
        bbox = dummy.textbbox((0, 0), ch, font=font)
        w_total += (bbox[2] - bbox[0]) + spacing
        max_h = max(max_h, bbox[3] - bbox[1])
    w_total -= spacing
    return w_total, max_h


def draw_menu_item_with_glow(
    img: Image.Image,
    text: str,
    cx: int,
    y: int,
    font,
    color: tuple,
    glow_color: tuple,
) -> int:
    """
    Draw a single menu item centred at cx, with a subtle outer glow.
    Returns bottom y of the text.
    """
    # Measure
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw // 2

    base = img.convert("RGBA")

    # Glow layer (white/blur)
    glow_img = Image.new("RGBA", base.size, (0,0,0,0))
    gd = ImageDraw.Draw(glow_img)
    gd.text((tx, y), text, font=font, fill=(*glow_color, 90))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(MENU_GLOW_BLUR))
    base.alpha_composite(glow_img)

    # Drop shadow
    shadow = Image.new("RGBA", base.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.text((tx+2, y+2), text, font=font, fill=(0,0,0,160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    base.alpha_composite(shadow)

    # Main text
    main_draw = ImageDraw.Draw(base)
    main_draw.text((tx, y), text, font=font, fill=(*color, 255))

    return base.convert("RGB"), y + th


def draw_plain_text_centered(
    draw: ImageDraw.Draw,
    text: str,
    cx: int,
    y: int,
    font,
    color: tuple,
    shadow=True,
) -> int:
    """Simpler centred text (used for subtitle / version)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw // 2
    if shadow:
        draw.text((tx+2, y+2), text, font=font, fill=(0,0,0,140))
    draw.text((tx, y), text, font=font, fill=color)
    return y + th


# ══════════════════════════════════════════════════════════════════
#  IMAGE PIPELINE  (Pillow)
# ══════════════════════════════════════════════════════════════════
def process_image(
    raw_bytes: bytes,
    main_title: str,
    subtitle: str,
    font_style: dict,
    theme: dict,
    version_str: str = "v 20.26",
) -> bytes:
    src = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    # Fill canvas → cover (centre crop)
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

    # 1. Base colour grade (soft)
    enh = ImageEnhance.Brightness(img).enhance(0.80)
    enh = ImageEnhance.Contrast(enh).enhance(1.18)
    enh = ImageEnhance.Color(enh).enhance(0.85)
    img = enh

    # 2. Colour wash
    img = apply_color_wash(img, theme["wash"], theme["wash_str"])

    # 3. Vignette
    img = apply_vignette(img, strength=2.0)

    # 4. Left‑side cinematic gradient
    img = draw_left_gradient(img)

    # 5. Load fonts
    tf = download_font(font_style["title_urls"], font_style["title_file"])
    bf = download_font(font_style["body_urls"],  font_style["body_file"])

    f_title_big = pil_font(tf, 108)
    f_title_sm  = pil_font(tf, 52)
    f_menu      = pil_font(bf, 30)
    f_sub       = pil_font(bf, 22)
    f_version   = pil_font(bf, 18)

    glow_layers  = theme["glow_layers"]
    title_color  = theme["title_color"]
    menu_color   = theme["menu_color"]
    menu_glow    = theme.get("menu_glow", (200,200,200))

    # 6. Build title block – last word huge, rest small
    words = main_title.upper().split()
    top_line = " ".join(words[:-1]) if len(words) > 1 else ""
    bot_line = words[-1] if words else "UNTITLED"

    # Starting position (vertical)
    title_y = 210

    # Small top line (with letter spacing + fire glow)
    if top_line:
        img, after_top = draw_fire_glow_text(
            img, top_line, TEXT_CX, title_y,
            f_title_sm, title_color, glow_layers,
            letter_spacing=2
        )
        title_y = after_top + 8
    else:
        after_top = title_y

    # Big bottom line (with letter spacing + fire glow)
    img, after_big = draw_fire_glow_text(
        img, bot_line, TEXT_CX, title_y,
        f_title_big, title_color, glow_layers,
        letter_spacing=2
    )

    # 7. Menu items – clean centred list with outer glow
    menu_items = ["> New Game", "Continue", "Select Chapter", "Options", "Exit"]
    menu_start_y = after_big + 36

    # We'll draw on an RGBA version to composite glows
    img_rgba = img.convert("RGBA")
    draw_plain = ImageDraw.Draw(img_rgba)   # used for final plain layer
    for idx, item in enumerate(menu_items):
        my = menu_start_y + idx * MENU_ROW_H
        # Draw glow effect (uses its own compositing)
        glow_img = Image.new("RGBA", img_rgba.size, (0,0,0,0))
        gd = ImageDraw.Draw(glow_img)
        # Calculate x for glow
        bbox = gd.textbbox((0,0), item, font=f_menu)
        tw = bbox[2] - bbox[0]
        tx = TEXT_CX - tw // 2
        gd.text((tx, my), item, font=f_menu, fill=(*menu_glow, 80))
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(MENU_GLOW_BLUR))
        img_rgba.alpha_composite(glow_img)
        # Drop shadow + main text
        sd = ImageDraw.Draw(img_rgba)
        sd.text((tx+2, my+2), item, font=f_menu, fill=(0,0,0,160))
        sd.text((tx, my), item, font=f_menu, fill=(*menu_color, 255))
    img = img_rgba.convert("RGB")   # collapse to RGB for rest

    # 8. Subtitle
    if subtitle.strip():
        sub_y = menu_start_y + len(menu_items) * MENU_ROW_H + 20
        draw = ImageDraw.Draw(img)
        draw_plain_text_centered(draw, subtitle, TEXT_CX, sub_y,
                                 f_sub, (160,150,140))

    # 9. Version bottom‑left
    draw = ImageDraw.Draw(img)
    draw.text((42, CANVAS_H - 45), version_str, font=f_version,
              fill=(120,110,100))

    # 10. Export PNG
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════
#  VIDEO PIPELINE  (FFmpeg)
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
        return s.replace("\\","\\\\").replace(":","\\:").replace("'","\\'").replace("%","\\%")

    words      = main_title.upper().split()
    top_line   = esc(" ".join(words[:-1])) if len(words) > 1 else ""
    bot_line   = esc(words[-1] if words else "UNTITLED")
    sub_esc    = esc(subtitle.strip())
    ver_esc    = esc(version_str)

    # ── Color grading parameters (soft gamma + saturation) ──────
    # Instead of harsh eq, we use gamma and saturation gently.
    # The wash is already applied via geq.
    grade = "eq=gamma=1.10:saturation=1.15"

    # ── Wash (tint) ──────────────────────────────────────────────
    wr, wg, wb = [round(c * theme["wash_str"]) for c in theme["wash"]]
    geq = (
        f"geq="
        f"r='clip(r(X\\,Y)*0.80+{wr}\\,0\\,255)':"
        f"g='clip(g(X\\,Y)*0.80+{wg}\\,0\\,255)':"
        f"b='clip(b(X\\,Y)*0.80+{wb}\\,0\\,255)'"
    )

    # ── Left gradient overlay (dark fade) ────────────────────────
    # Darken left 35% of the frame: factor = 0.2 + 0.8*(x/(W*0.35))
    grad_geq = (
        f"geq="
        f"r='r(X\\,Y)*(0.2+0.8*clip(X/(W*0.35)\\,0\\,1))':"
        f"g='g(X\\,Y)*(0.2+0.8*clip(X/(W*0.35)\\,0\\,1))':"
        f"b='b(X\\,Y)*(0.2+0.8*clip(X/(W*0.35)\\,0\\,1))'"
    )

    # ── Soft vignette ────────────────────────────────────────────
    vignette_effect = "vignette=PI/2.4:mode=backward"

    # ── Menu items ───────────────────────────────────────────────
    menu_items = ["> New Game", "Continue", "Select Chapter", "Options", "Exit"]
    menu_y0   = 470   # approximate start after big title (will be adjusted)
    row_h     = 52
    shd       = "shadowcolor=black@0.85:shadowx=3:shadowy=3"

    # Title positions (approximate same as Pillow)
    title_y = 230
    # Build filter chain
    vf_parts = [
        # 1. Cover scale
        "scale=1280:720:force_original_aspect_ratio=increase",
        "crop=1280:720",
        # 2. Soft grade
        grade,
        # 3. Colour wash
        geq,
        # 4. Left gradient (darken left side)
        grad_geq,
        # 5. Vignette
        vignette_effect,
        # 6. Add subtle grain
        "noise=alls=5:allf=t+u",
    ]

    # Title with fire glow (three passes)
    for blur_r, alpha in [(16, "0.60"), (10, "0.45"), (0, "1.00")]:
        fc = f"#ffd060@{alpha}" if blur_r == 0 else "white"
        # Top line
        if top_line:
            vf_parts.append(
                f"drawtext=fontfile='{font_path}':text='{top_line}'"
                f":fontcolor={fc}:fontsize=52:x={TEXT_CX}-tw/2:y={title_y}"
                f":shadowcolor=black@0.8:shadowx={blur_r}:shadowy={blur_r}"
            )
        # Bottom line
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{bot_line}'"
            f":fontcolor={fc}:fontsize=108:x={TEXT_CX}-tw/2:y={title_y + (56 if top_line else 0)}"
            f":shadowcolor=black@0.8:shadowx={blur_r}:shadowy={blur_r}"
        )

    # Menu items (with glow? We can't easily do blurred glow via FFmpeg in a simple way,
    # but we can simulate a faint white shadow to mimic glow)
    for i, item in enumerate(menu_items):
        my = menu_y0 + i * row_h
        # Draw white "glow" shadow (slightly blurred) and then main text
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{esc(item)}'"
            f":fontcolor=white@0.5:fontsize=30:x={TEXT_CX}-tw/2:y={my}"
            f":shadowcolor=white@0.3:shadowx=3:shadowy=3"
        )
        # Main text
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{esc(item)}'"
            f":fontcolor=white@0.9:fontsize=30:x={TEXT_CX}-tw/2:y={my}:{shd}"
        )

    # Subtitle
    if sub_esc:
        sub_y = menu_y0 + len(menu_items)*row_h + 20
        vf_parts.append(
            f"drawtext=fontfile='{font_path}':text='{sub_esc}'"
            f":fontcolor=white@0.6:fontsize=22:x={TEXT_CX}-tw/2:y={sub_y}:{shd}"
        )

    # Version
    vf_parts.append(
        f"drawtext=fontfile='{font_path}':text='{ver_esc}'"
        f":fontcolor=white@0.45:fontsize=18:x=42:y=h-45:{shd}"
    )

    full_command = [
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
    return full_command


# ══════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ══════════════════════════════════════════════════════════════════
st.markdown("# ⚔ Game Loading Screen Generator")
st.markdown("### AAA cinematic style · Fire glow · Left gradient · Teal grade")
st.markdown(
    '<div class="info-box">'
    "📸 **Image** → Pillow (PNG) &nbsp;&nbsp;|&nbsp;&nbsp; 🎬 **Video** → FFmpeg (MP4)<br>"
    "Title splits automatically: last word = large line, rest = small line above.<br>"
    "For the first run the app downloads the selected Google Font – subsequent runs are instant."
    "</div>",
    unsafe_allow_html=True,
)

ffmpeg_ok   = check_ffmpeg()
system_font = find_system_font()

c1, c2 = st.columns(2)
with c1:
    col = "#4caf50" if ffmpeg_ok else "#f44336"
    lbl = "✅ FFmpeg ready" if ffmpeg_ok else "❌ FFmpeg missing"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{col}">{lbl}</span>', unsafe_allow_html=True)
with c2:
    col = "#4caf50" if system_font else "#f0a030"
    lbl = "✅ System font" if system_font else "⚠ No system font"
    st.markdown(f'<span style="font-family:monospace;font-size:0.82rem;color:{col}">{lbl}</span>', unsafe_allow_html=True)

st.divider()

uploaded = st.file_uploader(
    "Upload a video or image",
    type=["mp4","mov","avi","mkv","webm","jpg","jpeg","png","bmp","webp"],
    help="Image → PNG (Pillow)   |   Video → MP4 (FFmpeg)",
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
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in main_title.strip())

    # ── IMAGE ──────────────────────────────────────────────────────
    if is_image:
        with st.spinner("🎨 Rendering cinematic image…"):
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

        with st.spinner("⬇️ Checking font…"):
            dl = download_font(font_style["body_urls"], font_style["body_file"])
            ffmpeg_font = str(dl) if (dl and dl.exists()) else system_font

        if not ffmpeg_font:
            st.error("No font available for FFmpeg text overlays. Please upload a custom font or install DejaVu.")
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

            # Print full command to console (for debugging)
            print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

            with st.expander("🔧 FFmpeg command"):
                st.code(" \\\n  ".join(cmd), language="bash")

            with st.spinner("🎬 Rendering cinematic video…"):
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
                    traceback.print_exc()
                    st.stop()

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
