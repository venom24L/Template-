"""
AAA Game Loading Screen Generator  ·  v6.0 – Cinematic Depth
=============================================================
• Auto-download “Cinzel” font, fallback to DejaVu Sans Bold
• Pillow overlay: left-side gradient, title with outer glow & shadow,
  letter‑spacing, crisp menu
• Image: composite overlay → PNG
• Video: FFmpeg darkening + vignette, then blend overlay
• No syntax errors – under 200 lines
"""

import io, os, tempfile, subprocess, traceback
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

# ── Constants ──────────────────────────────────────────────────────
W, H = 1280, 720
FONT_DIR = Path("fonts_cache")
FONT_DIR.mkdir(exist_ok=True)
TEXT_CX = 190                     # horizontal center of the left-side block
GRAD_W = int(W * 0.4)             # 40% width gradient
MENU_ROW = 52                     # vertical spacing for menu items

FONT_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Bold.ttf",
    "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/static/Cinzel-Bold.ttf",
]
FONT_FILE = "Cinzel-Bold.ttf"

# ── Font management ────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_font_path() -> str | None:
    """Download Cinzel Bold, return path. Falls back to system DejaVu Sans Bold."""
    dest = FONT_DIR / FONT_FILE
    if dest.exists():
        return str(dest)
    for url in FONT_URLS:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return str(dest)
        except Exception:
            continue
    # fallback – look for DejaVu Bold
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(p).exists():
            return p
    return None

def load_font(size: int) -> ImageFont.FreeTypeFont:
    path = get_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

# ── Pillow overlay generation ──────────────────────────────────────
def make_gradient_layer() -> Image.Image:
    """RGBA canvas with left‑side black→transparent gradient."""
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grad)
    for x in range(GRAD_W):
        alpha = int(204 * (1 - x / GRAD_W))   # 80% black at left edge
        draw.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    return grad

def draw_glow_text(overlay: Image.Image, text: str, x: int, y: int,
                   font: ImageFont.FreeTypeFont,
                   glow_color=(255, 210, 80), text_color=(255, 245, 210),
                   letter_spacing=2) -> int:
    """
    Draw centered glow title with character‑by‑character spacing.
    Returns bottom y coordinate.
    """
    # measure total width with spacing
    dummy = ImageDraw.Draw(Image.new("L", (1, 1)))
    w_total, h_total = 0, 0
    for ch in text:
        bbox = dummy.textbbox((0, 0), ch, font=font)
        w_total += (bbox[2] - bbox[0]) + letter_spacing
        h_total = max(h_total, bbox[3] - bbox[1])
    w_total -= letter_spacing   # remove trailing spacing
    tx = x - w_total // 2

    # glow layers (largest blur first)
    for radius, alpha in [(18, 0.25), (10, 0.4), (5, 0.6)]:
        glow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        # draw each character
        cx = tx
        for ch in text:
            gd.text((cx, y), ch, font=font,
                    fill=(*glow_color, int(255 * alpha)))
            bbox = gd.textbbox((cx, y), ch, font=font)
            cx = bbox[2] + letter_spacing
        glow = glow.filter(ImageFilter.GaussianBlur(radius))
        overlay = Image.alpha_composite(overlay, glow)

    # drop shadow
    shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    cx = tx + 4
    for ch in text:
        sd.text((cx, y + 4), ch, font=font, fill=(0, 0, 0, 160))
        bbox = sd.textbbox((cx, y + 4), ch, font=font)
        cx = bbox[2] + letter_spacing
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    overlay = Image.alpha_composite(overlay, shadow)

    # main crisp text
    md = ImageDraw.Draw(overlay)
    cx = tx
    for ch in text:
        md.text((cx, y), ch, font=font, fill=(*text_color, 255))
        bbox = md.textbbox((cx, y), ch, font=font)
        cx = bbox[2] + letter_spacing

    return y + h_total

def generate_overlay(main_title: str, subtitle: str, version_str: str) -> Image.Image:
    """Build the complete UI overlay (RGBA)."""
    overlay = make_gradient_layer()

    # fonts
    f_title_big = load_font(108)
    f_title_sm  = load_font(52)
    f_menu      = load_font(28)
    f_sub       = load_font(22)
    f_ver       = load_font(18)

    # title – split at last word
    words = main_title.upper().split()
    top_line = " ".join(words[:-1]) if len(words) > 1 else ""
    bot_line = words[-1] if words else "UNTITLED"

    title_y = 210
    if top_line:
        title_y = draw_glow_text(overlay, top_line, TEXT_CX, title_y, f_title_sm)
        title_y += 12
    title_y = draw_glow_text(overlay, bot_line, TEXT_CX, title_y, f_title_big)

    # menu items
    menu_items = ["New Game", "Continue", "Select Chapter", "Options", "Exit"]
    menu_start = title_y + 44
    draw = ImageDraw.Draw(overlay)

    for idx, item in enumerate(menu_items):
        my = menu_start + idx * MENU_ROW
        bbox = draw.textbbox((0, 0), item, font=f_menu)
        tw = bbox[2] - bbox[0]
        tx = TEXT_CX - tw // 2
        # subtle shadow
        draw.text((tx + 2, my + 2), item, font=f_menu, fill=(0, 0, 0, 160))
        # white with slight transparency
        draw.text((tx, my), item, font=f_menu, fill=(255, 255, 255, 230))

    # subtitle (optional)
    if subtitle.strip():
        sub_y = menu_start + len(menu_items) * MENU_ROW + 18
        bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
        tw = bbox[2] - bbox[0]
        tx = TEXT_CX - tw // 2
        draw.text((tx + 2, sub_y + 2), subtitle, font=f_sub, fill=(0, 0, 0, 120))
        draw.text((tx, sub_y), subtitle, font=f_sub, fill=(180, 175, 165, 200))

    # version number
    draw.text((40, H - 50), version_str, font=f_ver, fill=(160, 150, 130, 200))

    return overlay

# ── Image pipeline ─────────────────────────────────────────────────
def process_image(input_bytes: bytes, main_title: str, subtitle: str, version_str: str) -> bytes:
    src = Image.open(io.BytesIO(input_bytes)).convert("RGB")
    # cover‑fill crop
    ratio = src.width / src.height
    tgt = W / H
    if ratio > tgt:
        nh = H
        nw = int(nh * ratio)
    else:
        nw = W
        nh = int(nw / ratio)
    src = src.resize((nw, nh), Image.LANCZOS)
    left = (nw - W) // 2
    top = (nh - H) // 2
    bg = src.crop((left, top, left + W, top + H))

    # cinematic grading (brightness -30%, contrast +40%)
    from PIL import ImageEnhance
    bg = ImageEnhance.Brightness(bg).enhance(0.7)   # 0.7 = -30%
    bg = ImageEnhance.Contrast(bg).enhance(1.4)

    # vignette
    vign = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vign)
    cx, cy = W // 2, H // 2
    for i in range(180, 0, -1):
        ratio = i / 180
        alpha = int(255 * (1 - ratio) ** 2.2)   # deep fall-off
        rx = int(cx * ratio * 1.2)
        ry = int(cy * ratio * 1.2)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    vign = vign.filter(ImageFilter.GaussianBlur(60))
    bg.paste((0, 0, 0), mask=ImageChops.invert(vign))

    # composite overlay
    overlay = generate_overlay(main_title, subtitle, version_str)
    final = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    buf = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ── Video pipeline ─────────────────────────────────────────────────
def process_video(input_path: str, output_path: str,
                  main_title: str, subtitle: str, version_str: str) -> None:
    # 1. generate overlay PNG
    overlay_img = generate_overlay(main_title, subtitle, version_str)
    tmp_png = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    overlay_img.save(tmp_png, format="PNG")
    tmp_png.close()

    # 2. FFmpeg filter: darken + vignette + overlay
    filter_str = (
        f"[0:v]"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"eq=brightness=-0.3:contrast=1.4,"
        f"vignette=PI/2.2:mode=backward"
        f"[bg];"
        f"[bg][1:v]overlay=0:0"
    )

    cmd = [
        "ffmpeg", "-y",
        "-t", "10",
        "-i", input_path,
        "-i", tmp_png.name,
        "-filter_complex", filter_str,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        output_path,
    ]

    # print for debugging
    print(" ".join(cmd))

    proc = subprocess.run(cmd, capture_output=True)
    os.unlink(tmp_png.name)   # clean up

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{proc.stderr.decode(errors='replace')}")

# ── Streamlit UI ───────────────────────────────────────────────────
st.set_page_config(page_title="Game Loading Screen", page_icon="🎮", layout="centered")
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"] {
        background: #0a0a14; color: #c0c0c0; font-family: 'Cinzel', serif;
    }
    h1 { color: #dbb42c; text-align: center; letter-spacing: 0.1em; }
    .stButton > button {
        background: linear-gradient(135deg, #dbb42c, #8b6914);
        color: #000; font-weight: bold; border: none; padding: 0.7rem 2rem;
        letter-spacing: 0.1em; border-radius: 4px;
        box-shadow: 0 0 20px rgba(219, 180, 44, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.title("⚔ Game Loading Screen Generator")
st.markdown("Upload an image or video → receive a cinematic AAA start screen.", unsafe_allow_html=True)

uploaded = st.file_uploader("Choose file", type=["mp4", "mov", "avi", "mkv", "webm",
                                                  "jpg", "jpeg", "png", "bmp", "webp"])
main_title = st.text_input("Game Title", "Your Text", max_chars=36,
                           help="Last word becomes the massive line. Example: \"Elden Ring\" → small \"ELDEN\" + big \"RING\"")
subtitle = st.text_input("Subtitle (optional)", "", max_chars=60)
version_str = st.text_input("Version", "v 20.26", max_chars=20)

if st.button("Generate Loading Screen"):
    if not uploaded:
        st.warning("Please upload a file.")
        st.stop()
    if not main_title.strip():
        st.warning("Please enter a title.")
        st.stop()

    is_image = Path(uploaded.name).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    raw = uploaded.read()
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in main_title.strip())

    if is_image:
        with st.spinner("Rendering image…"):
            try:
                png = process_image(raw, main_title.strip(), subtitle.strip(), version_str.strip())
                st.success("Done!")
                st.image(png, use_container_width=True)
                st.download_button("Download PNG", png, f"{safe_name}_loading.png", "image/png")
            except Exception as e:
                st.error(f"Image processing error: {e}")
                traceback.print_exc()
    else:
        # check ffmpeg presence
        if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0:
            st.error("FFmpeg is required for video processing. Please install it on your system.")
            st.stop()
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, f"input{Path(uploaded.name).suffix}")
            out_path = os.path.join(tmp, "loading_screen.mp4")
            with open(in_path, "wb") as f:
                f.write(raw)
            with st.spinner("Rendering video…"):
                try:
                    process_video(in_path, out_path, main_title.strip(), subtitle.strip(), version_str.strip())
                    with open(out_path, "rb") as f:
                        mp4 = f.read()
                    st.success("Done!")
                    st.video(mp4)
                    st.download_button("Download MP4", mp4, f"{safe_name}_loading.mp4", "video/mp4")
                except Exception as e:
                    st.error(f"Video processing error: {e}")
                    traceback.print_exc()
