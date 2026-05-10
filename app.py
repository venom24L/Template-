"""
Video Game Loading Screen Generator
====================================
Streamlit + FFmpeg — zero external assets required.
Run with:  streamlit run app.py
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Game Loading Screen Generator",
    page_icon="🎮",
    layout="centered",
)

# ─────────────────────────────────────────────
# Minimal custom CSS — dark gaming aesthetic
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Share+Tech+Mono&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background: #0a0a0f;
        color: #e0e0e0;
        font-family: 'Rajdhani', sans-serif;
    }
    [data-testid="stHeader"] { background: transparent; }

    h1 { color: #00e5ff; letter-spacing: 0.08em; text-transform: uppercase; }
    h3 { color: #aaa; font-weight: 500; letter-spacing: 0.04em; }

    .stButton > button {
        background: linear-gradient(135deg, #00e5ff 0%, #0077ff 100%);
        color: #000;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 700;
        font-size: 1.1rem;
        letter-spacing: 0.1em;
        border: none;
        border-radius: 4px;
        padding: 0.6rem 2rem;
        text-transform: uppercase;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    .stTextInput > div > div > input,
    .stTextArea textarea {
        background: #12121a;
        border: 1px solid #2a2a3a;
        color: #e0e0e0;
        border-radius: 4px;
    }
    .stFileUploader { background: #12121a; border: 1px dashed #2a2a3a; border-radius: 6px; }

    .info-box {
        background: #12121a;
        border-left: 3px solid #00e5ff;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.82rem;
        color: #aaa;
        margin-bottom: 1rem;
    }
    .error-box {
        background: #1a0f0f;
        border-left: 3px solid #ff3a3a;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.8rem;
        color: #ff8888;
        white-space: pre-wrap;
        overflow-x: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Helper: locate DejaVu Sans font
# ─────────────────────────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf",
]

def find_dejavu_font() -> str | None:
    for p in FONT_PATHS:
        if Path(p).exists():
            return p
    # Last resort: ask fc-list
    try:
        result = subprocess.run(
            ["fc-list", ":family=DejaVu Sans", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return None


def check_ffmpeg() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, timeout=5, check=True
        )
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# Core FFmpeg pipeline builder
# ─────────────────────────────────────────────
def build_ffmpeg_command(
    input_path: str,
    output_path: str,
    is_image: bool,
    main_title: str,
    subtitle: str,
    font: str,
) -> list[str]:
    """
    Build a single FFmpeg command that:
      1. Converts image → 10-second 24fps loop, OR trims video to 10s.
      2. Scales to 1280×720.
      3. Applies eq (brightness/contrast), vignette, noise grain.
      4. Draws semi-transparent dark sidebar via drawbox.
      5. Draws title, subtitle, and four menu items via drawtext.
    """

    # ── Input flags ──────────────────────────────────────────
    input_flags: list[str] = []
    if is_image:
        input_flags = ["-loop", "1", "-framerate", "24", "-t", "10"]
    else:
        input_flags = ["-t", "10"]          # trim video to 10 s

    # ── Video filter chain ───────────────────────────────────
    # Escape helper for drawtext strings (colons and backslashes need escaping)
    def dt_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    mt = dt_escape(main_title or "UNTITLED")
    st_text = dt_escape(subtitle or "")

    shadow = "shadowcolor=black@0.7:shadowx=2:shadowy=2"

    # Build drawtext filters
    menu_items = ["New Game", "Continue", "Options", "Exit"]
    menu_filters = []
    for i, item in enumerate(menu_items):
        y = 230 + i * 44
        menu_filters.append(
            f"drawtext=fontfile='{font}':text='{dt_escape(item)}'"
            f":fontcolor=white:fontsize=26:x=50:y={y}:{shadow}"
        )

    subtitle_filter = ""
    if subtitle.strip():
        subtitle_filter = (
            f",drawtext=fontfile='{font}':text='{st_text}'"
            f":fontcolor=white@0.85:fontsize=28:x=30:y=148:{shadow}"
        )

    vf = (
        # 1. Scale to 1280×720, pad if needed
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,"
        # 2. Colour grading
        "eq=brightness=-0.10:contrast=1.20:saturation=0.85,"
        # 3. Dramatic vignette
        "vignette=PI/2:mode=backward,"
        # 4. Subtle film grain via geq (luma offset noise)
        "noise=alls=8:allf=t+u,"
        # 5. Dark sidebar rectangle (left 30 % of 1280 = 384 px wide)
        "drawbox=x=0:y=0:w=384:h=720:color=black@0.55:t=fill,"
        # 6. Main title
        f"drawtext=fontfile='{font}':text='{mt}'"
        f":fontcolor=white:fontsize=52:x=30:y=72:{shadow}"
        + subtitle_filter
        + ","
        + ",".join(menu_filters)
    )

    cmd = [
        "ffmpeg", "-y",
        *input_flags,
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",                      # no audio (loading screen)
        "-movflags", "+faststart",
        output_path,
    ]
    return cmd


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.markdown("# 🎮 Game Loading Screen Generator")
st.markdown(
    "### Transform any video or image into a cinematic game loading screen"
)
st.markdown(
    '<div class="info-box">'
    "Upload a video or image → add your game title → download a polished 1280×720 MP4 "
    "with a dark sidebar menu overlay, vignette, and cinematic colour grade."
    "</div>",
    unsafe_allow_html=True,
)

# ── Dependency checks ─────────────────────────────────────────────────────────
ffmpeg_ok = check_ffmpeg()
font_path = find_dejavu_font()

col_ff, col_fnt = st.columns(2)
with col_ff:
    if ffmpeg_ok:
        st.success("✅ FFmpeg found")
    else:
        st.error("❌ FFmpeg not found — install it before running.")
with col_fnt:
    if font_path:
        st.success(f"✅ Font: `{Path(font_path).name}`")
    else:
        st.error("❌ DejaVu Sans font not found.")

st.divider()

# ── Inputs ────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a video or image",
    type=["mp4", "mov", "avi", "mkv", "webm", "jpg", "jpeg", "png", "bmp", "gif"],
    help="Video: first 10 s will be used. Image: will loop for 10 s at 24 fps.",
)

main_title = st.text_input("Main Title", placeholder="CYBER ODYSSEY", max_chars=40)
subtitle = st.text_input(
    "Subtitle / Loading Hint (optional)",
    placeholder="Loading world…",
    max_chars=60,
)

generate_btn = st.button("⚡ Generate Loading Screen", use_container_width=True)

# ── Generation ────────────────────────────────────────────────────────────────
if generate_btn:
    if not ffmpeg_ok:
        st.error("FFmpeg is required. Please install it and restart the app.")
        st.stop()
    if not font_path:
        st.error(
            "DejaVu Sans font not found. Install the `fonts-dejavu-core` package "
            "(e.g. `sudo apt-get install -y fonts-dejavu-core`) and restart."
        )
        st.stop()
    if not uploaded:
        st.warning("Please upload a video or image first.")
        st.stop()
    if not main_title.strip():
        st.warning("Please enter a Main Title.")
        st.stop()

    # Determine if input is an image
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    suffix = Path(uploaded.name).suffix.lower()
    is_image = suffix in IMAGE_EXTS

    # Write upload to a temp file
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, f"input{suffix}")
        output_path = os.path.join(tmp_dir, "loading_screen.mp4")

        with open(input_path, "wb") as f:
            f.write(uploaded.read())

        cmd = build_ffmpeg_command(
            input_path=input_path,
            output_path=output_path,
            is_image=is_image,
            main_title=main_title.strip(),
            subtitle=subtitle.strip(),
            font=font_path,
        )

        # Show command for transparency / debugging
        with st.expander("🔧 FFmpeg command (click to expand)"):
            st.code(" \\\n  ".join(cmd), language="bash")

        with st.spinner("⚙️ Rendering loading screen…"):
            progress_bar = st.progress(0, text="Starting FFmpeg…")

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Simulate progress (FFmpeg doesn't give easy % without -progress)
                steps = 20
                for i in range(steps):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.4)
                    progress_bar.progress(
                        int((i + 1) / steps * 90),
                        text=f"Processing… ({int((i + 1) / steps * 90)}%)",
                    )

                stdout, stderr = proc.communicate()
                progress_bar.progress(100, text="Done!")

                if proc.returncode != 0:
                    st.markdown(
                        '<div class="error-box">'
                        "<b>FFmpeg Error:</b>\n"
                        + stderr.decode("utf-8", errors="replace")
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                    st.stop()

                # Read output before tmp_dir is deleted
                with open(output_path, "rb") as out_f:
                    video_bytes = out_f.read()

            except FileNotFoundError:
                st.error("FFmpeg binary not found. Make sure it is installed and on PATH.")
                st.stop()
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
                st.stop()

        st.success("✅ Loading screen generated!")

        # Preview + download
        st.video(video_bytes)
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in main_title)
        st.download_button(
            label="⬇️ Download MP4",
            data=video_bytes,
            file_name=f"{safe_title.replace(' ', '_')}_loading_screen.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    '<p style="text-align:center;color:#444;font-size:0.78rem;">'
    "Powered by FFmpeg · Streamlit · Zero external assets required"
    "</p>",
    unsafe_allow_html=True,
)
