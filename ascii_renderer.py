import cv2
import numpy as np
import sys
import shutil
import time
import os
import argparse
import msvcrt
import threading
import datetime
import random
import glob
import re

# ascii density ramp
ASCII_CHARS = np.array(list("  ..',:;+*?%$#@"), dtype="U1")
N = len(ASCII_CHARS)

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR       = "\033[2J"
HOME        = "\033[H"
RESET       = "\033[0m"

# color themes (for matrix/mono/edge modes)
THEMES = {
    "green":  "\033[32m",
    "cyan":   "\033[36m",
    "red":    "\033[31m",
    "amber":  "\033[33m",
    "white":  "\033[97m",
    "blue":   "\033[34m",
    "pink":   "\033[35m",
}
THEME_NAMES = list(THEMES.keys())

RENDER_MODES = ["truecolor", "matrix", "mono", "edge", "blocks", "threshold"]
FILTER_MODES = ["none", "blur", "sharpen", "red", "green", "blue"]

HELP_TEXT = """
  KEYS:
  m        - next render mode  (truecolor/matrix/mono/edge/blocks/threshold)
  f        - next filter       (none/blur/sharpen/red/green/blue channel)
  t        - next color theme  (green/cyan/red/amber/white/blue/pink)
  +/-      - brightness up/down
  i        - invert density ramp
  c        - toggle clock overlay
  w        - toggle watermark overlay
  d        - toggle face detection
  x        - toggle motion detection badge
  SPACE    - freeze / unfreeze frame
  s        - save screenshot (.txt + .html)
  r        - start/stop recording  (saves to recording_TIMESTAMP.txt)
  p        - playback last recording
  z / u    - zoom in / zoom out
  a        - toggle adaptive fps (auto-reduces resolution if fps < 10)
  h        - show this help
  q / Esc  - quit

  press any key to continue...
"""


# ---------------------------------------------------------------------------
# threaded camera so capture never blocks the render loop
# ---------------------------------------------------------------------------
class Camera:
    def __init__(self, idx):
        self.cap = cv2.VideoCapture(idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self._frame  = None
        self._lock   = threading.Lock()
        self._alive  = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._alive:
            ok, f = self.cap.read()
            if ok:
                with self._lock:
                    self._frame = f
            else:
                time.sleep(0.01)

    def read(self):
        with self._lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()

    def is_open(self):
        return self.cap.isOpened()

    def release(self):
        self._alive = False
        time.sleep(0.15)
        self.cap.release()


# ---------------------------------------------------------------------------
# startup animation
# ---------------------------------------------------------------------------

LOGO = [
    "   ___   ___  ___  ___   ___   ___   _   __  __ ",
    "  / _ | / __// __// _ | /   | / _ | / | /  |/  |",
    " / __ |_\\ \\ / /__ / / || / /  / / // /_ / /|_/ /",
    "/_/ |_/___/ \\___//_/_/_|/_/  /_/_(_)__(_)_/  /_/ ",
    "  Real-Time Terminal ASCII Video Renderer v2.0   ",
]

def startup_animation():
    cols, rows = get_size()
    cx = max((cols - 50) // 2, 0)
    cy = max((rows - len(LOGO) - 6) // 2, 0)

    frames = 30
    for i in range(frames):
        t = i / frames
        sys.stdout.write(HOME + CLEAR)

        # animated scanline background
        for row in range(rows - 1):
            offset = (i + row) % 6
            if offset == 0:
                sys.stdout.write(f"\033[{row+1};1H\033[90m" + ("- " * (cols // 2))[:cols] + RESET)

        # draw logo with fade-in effect
        colors = ["\033[92m", "\033[32m", "\033[32m", "\033[32m", "\033[90m"]
        for li, line in enumerate(LOGO):
            row = cy + li
            col = max(cx, 1)
            if t > li / (len(LOGO) + 2):   # stagger each line
                sys.stdout.write(f"\033[{row};{col}H{colors[li]}{line}{RESET}")

        # loading bar
        bar_row = cy + len(LOGO) + 2
        bar_w   = min(50, cols - 4)
        filled  = int(bar_w * t)
        bar     = "[" + "#" * filled + "-" * (bar_w - filled) + "]"
        pct     = int(t * 100)
        sys.stdout.write(f"\033[{bar_row};{max(cx,1)}H\033[32m{bar} {pct}%\033[0m")

        # bottom tagline
        tag = "made by Noelpm14"
        sys.stdout.write(f"\033[{bar_row+1};{max(cx,1)}H\033[90m{tag}\033[0m")

        sys.stdout.flush()
        time.sleep(0.05)

    # brief hold then fade out
    time.sleep(0.4)
    for _ in range(8):
        sys.stdout.write(HOME + CLEAR)
        sys.stdout.flush()
        time.sleep(0.04)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def get_size():
    s = shutil.get_terminal_size((120, 40))
    return s.columns, s.lines

def enable_ansi():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        m = ctypes.c_ulong()
        k.GetConsoleMode(h, ctypes.byref(m))
        k.SetConsoleMode(h, m.value | 0x0005)
    except:
        pass

def get_key():
    if msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None

def apply_filter(frame, fmode):
    if fmode == "blur":
        return cv2.GaussianBlur(frame, (5, 5), 0)
    if fmode == "sharpen":
        k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        return cv2.filter2D(frame, -1, k)
    if fmode == "red":
        f = frame.copy(); f[:, :, 0] = 0; f[:, :, 1] = 0; return f
    if fmode == "green":
        f = frame.copy(); f[:, :, 0] = 0; f[:, :, 2] = 0; return f
    if fmode == "blue":
        f = frame.copy(); f[:, :, 1] = 0; f[:, :, 2] = 0; return f
    return frame

def apply_zoom(frame, zoom):
    if zoom <= 1.0:
        return frame
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    nw, nh = int(w / zoom), int(h / zoom)
    x1, y1 = max(cx - nw // 2, 0), max(cy - nh // 2, 0)
    x2, y2 = min(x1 + nw, w), min(y1 + nh, h)
    return frame[y1:y2, x1:x2]

def enhance_contrast(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
    lab = cv2.merge((clahe.apply(l), a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def strip_ansi(s):
    return re.sub(r'\033\[[0-9;]*m', '', s)

def save_screenshot(body):
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    txt = f"screenshot_{ts}.txt"
    htm = f"screenshot_{ts}.html"

    clean = strip_ansi(body)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(clean)

    escaped = clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>body{background:#000;color:#0f0;font-family:monospace;"
        "font-size:7px;white-space:pre;line-height:1.0;}</style>"
        f"</head><body>{escaped}</body></html>"
    )
    with open(htm, "w", encoding="utf-8") as f:
        f.write(html)
    return txt, htm


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------

def build_truecolor(char_grid, resized, rows):
    b_ch = resized[:, :, 0].astype(np.uint8)
    g_ch = resized[:, :, 1].astype(np.uint8)
    r_ch = resized[:, :, 2].astype(np.uint8)
    out = []
    for ri in range(rows):
        parts = []
        pr = pg = pb = -1
        buf = []
        for c, r, g, b in zip(char_grid[ri], r_ch[ri], g_ch[ri], b_ch[ri]):
            r8, g8, b8 = int(r) & 0xF8, int(g) & 0xF8, int(b) & 0xF8
            if r8 != pr or g8 != pg or b8 != pb:
                if buf: parts.append("".join(buf)); buf = []
                parts.append(f"\033[38;2;{r8};{g8};{b8}m")
                pr, pg, pb = r8, g8, b8
            buf.append(c)
        if buf: parts.append("".join(buf))
        out.append("".join(parts) + RESET)
    return "\n".join(out)

def build_blocks(resized, rows, cols):
    # half-block chars give 2x vertical resolution
    # fg = top pixel, bg = bottom pixel
    out = []
    for ri in range(rows):
        top = resized[ri * 2]
        bot = resized[ri * 2 + 1] if ri * 2 + 1 < resized.shape[0] else top
        parts = []
        prev = None
        buf = []
        for col in range(cols):
            tr, tg, tb = int(top[col, 2]) & 0xF0, int(top[col, 1]) & 0xF0, int(top[col, 0]) & 0xF0
            br, bg, bb = int(bot[col, 2]) & 0xF0, int(bot[col, 1]) & 0xF0, int(bot[col, 0]) & 0xF0
            key = (tr, tg, tb, br, bg, bb)
            if key != prev:
                if buf: parts.append("".join(buf)); buf = []
                parts.append(f"\033[38;2;{tr};{tg};{tb}m\033[48;2;{br};{bg};{bb}m")
                prev = key
            buf.append("▀")
        if buf: parts.append("".join(buf))
        out.append("".join(parts) + RESET)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# overlays
# ---------------------------------------------------------------------------

def clock_overlay(cols):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return f"\033[1;{max(cols - 11, 1)}H\033[93m{now}\033[0m"

def watermark_overlay(text, term_rows, cols):
    c = max(cols - len(text) - 2, 1)
    return f"\033[{term_rows};{c}H\033[90m{text}\033[0m"

def motion_overlay(prev_gray, curr_gray):
    if prev_gray is None or curr_gray is None:
        return None, ""
    diff = cv2.absdiff(prev_gray, curr_gray)
    _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    pct = np.sum(mask > 0) / mask.size * 100
    badge = f"\033[1;2H\033[91m[MOTION {pct:.1f}%]\033[0m" if pct > 1.0 else ""
    return curr_gray, badge

def face_overlay(frame, cascade, term_cols, term_rows):
    if cascade is None:
        return ""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(60, 60))
    if len(faces) == 0:
        return ""
    fh, fw = frame.shape[:2]
    parts = []
    for (x, y, w, h) in faces:
        tc = max(1, int(x / fw * term_cols))
        tr = max(1, int(y / fh * term_rows))
        tc2 = min(term_cols, int((x + w) / fw * term_cols))
        tr2 = min(term_rows, int((y + h) / fh * term_rows))
        parts.append(f"\033[{tr};{tc}H\033[91m[")
        parts.append(f"\033[{tr};{tc2 - 1}H]")
        parts.append(f"\033[{tr2};{tc}H[")
        parts.append(f"\033[{tr2};{tc2 - 1}H]\033[0m")
        label = "FACE"
        parts.append(f"\033[{tr};{tc + 1}H\033[91m{label}\033[0m")
    return "".join(parts)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",       default="truecolor", choices=RENDER_MODES)
    parser.add_argument("--camera",     type=int,   default=0)
    parser.add_argument("--fps",        type=float, default=30.0)
    parser.add_argument("--brightness", type=float, default=1.2)
    parser.add_argument("--watermark",  default="made by Noelpm14")
    args = parser.parse_args()

    mode        = args.mode
    brightness  = args.brightness
    inverted    = False
    frame_count = 0
    min_dt      = 1.0 / max(args.fps, 1)

    fmode       = "none"
    theme_idx   = 0
    show_clock  = False
    show_wm     = True       # watermark on by default
    face_on     = False
    motion_on   = True       # motion badge on by default
    frozen      = False
    adaptive    = False
    recording   = False
    rec_frames  = []
    zoom        = 1.0

    prev_gray   = None
    last_frame  = None
    last_body   = ""
    status_msg  = ""
    status_ttl  = 0
    fps_history = []

    # load face cascade
    cascade = None
    try:
        p = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(p)
    except:
        pass

    print("[ASCII-CAM] Opening camera", args.camera, "...")
    cam = Camera(args.camera)
    if not cam.is_open():
        print("ERROR: can't open camera", args.camera)
        sys.exit(1)

    time.sleep(0.5)

    enable_ansi()
    sys.stdout.write(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    # run startup animation while camera warms up
    startup_animation()

    last_t  = time.perf_counter()
    fps_val = 0.0


    try:
        while True:
            t0 = time.perf_counter()

            # ---- keyboard ----
            key = get_key()
            if key in ("q", "\x1b"):
                break

            elif key == "m":
                mode = RENDER_MODES[(RENDER_MODES.index(mode) + 1) % len(RENDER_MODES)]
                status_msg = f"mode -> {mode}"; status_ttl = 80

            elif key == "f":
                fmode = FILTER_MODES[(FILTER_MODES.index(fmode) + 1) % len(FILTER_MODES)]
                status_msg = f"filter -> {fmode}"; status_ttl = 80

            elif key == "t":
                theme_idx = (theme_idx + 1) % len(THEME_NAMES)
                status_msg = f"theme -> {THEME_NAMES[theme_idx]}"; status_ttl = 80

            elif key == "+":
                brightness = min(brightness + 0.1, 3.0)
            elif key == "-":
                brightness = max(brightness - 0.1, 0.3)

            elif key == "i":
                inverted = not inverted
                status_msg = "inverted " + ("ON" if inverted else "OFF"); status_ttl = 60

            elif key == "c":
                show_clock = not show_clock
                status_msg = "clock " + ("ON" if show_clock else "OFF"); status_ttl = 60

            elif key == "w":
                show_wm = not show_wm
                status_msg = "watermark " + ("ON" if show_wm else "OFF"); status_ttl = 60

            elif key == "d":
                if cascade is not None:
                    face_on = not face_on
                    status_msg = "face detect " + ("ON" if face_on else "OFF"); status_ttl = 60
                else:
                    status_msg = "face cascade unavailable"; status_ttl = 80

            elif key == "x":
                motion_on = not motion_on
                prev_gray = None
                status_msg = "motion detect " + ("ON" if motion_on else "OFF"); status_ttl = 60

            elif key == " ":
                frozen = not frozen
                status_msg = "FROZEN" if frozen else "LIVE"; status_ttl = 60

            elif key == "a":
                adaptive = not adaptive
                status_msg = "adaptive fps " + ("ON" if adaptive else "OFF"); status_ttl = 60

            elif key == "z":
                zoom = min(zoom + 0.25, 4.0)
                status_msg = f"zoom {zoom:.2f}x"; status_ttl = 60

            elif key == "u":
                zoom = max(zoom - 0.25, 1.0)
                status_msg = f"zoom {zoom:.2f}x"; status_ttl = 60

            elif key == "s":
                if last_body:
                    tf, hf = save_screenshot(last_body)
                    status_msg = f"saved {tf}"; status_ttl = 120

            elif key == "r":
                recording = not recording
                if not recording and rec_frames:
                    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    rfn = f"recording_{ts}.txt"
                    with open(rfn, "w", encoding="utf-8") as f:
                        f.write("\n---FRAME---\n".join(rec_frames))
                    status_msg = f"saved {rfn} ({len(rec_frames)}fr)"; status_ttl = 120
                    rec_frames = []
                else:
                    status_msg = "REC started"; status_ttl = 60

            elif key == "p":
                files = sorted(glob.glob("recording_*.txt"))
                if files:
                    with open(files[-1], "r", encoding="utf-8") as f:
                        pb_frames = f.read().split("\n---FRAME---\n")
                    status_msg = f"playing {len(pb_frames)} frames"; status_ttl = 30
                    for pbf in pb_frames:
                        sys.stdout.write(HOME + pbf)
                        sys.stdout.flush()
                        time.sleep(0.05)
                else:
                    status_msg = "no recording found"; status_ttl = 60

            elif key == "h":
                sys.stdout.write(CLEAR + HOME + "\033[32m" + HELP_TEXT + RESET)
                sys.stdout.flush()
                while not msvcrt.kbhit():
                    time.sleep(0.05)
                msvcrt.getwch()
                sys.stdout.write(CLEAR)
                continue

            # ---- capture ----
            if not frozen:
                ok, raw = cam.read()
                if not ok or raw is None:
                    time.sleep(0.02)
                    continue
                raw = cv2.flip(raw, 1)
                last_frame = raw
            else:
                if last_frame is None:
                    time.sleep(0.05)
                    continue
                raw = last_frame

            frame = raw.copy()
            if zoom > 1.0:
                frame = apply_zoom(frame, zoom)
            frame = apply_filter(frame, fmode)

            cols, rows = get_size()
            render_rows = max(rows - 2, 1)

            # adaptive: shrink cols if fps tanking
            if adaptive and fps_val < 10 and cols > 80:
                cols = max(80, cols - 20)

            theme_color = THEMES[THEME_NAMES[theme_idx]]

            # ---- render mode ----
            if mode == "blocks":
                srows = max(int(render_rows / 2.2), 1)
                px_rows = srows * 2
                resized = cv2.resize(frame, (cols, px_rows), interpolation=cv2.INTER_AREA)
                resized = enhance_contrast(resized)
                body = build_blocks(resized, srows, cols)
                display_rows = srows
                gray_small = cv2.resize(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY), (cols, srows))

            else:
                srows   = max(int(render_rows / 2.2), 1)
                resized = cv2.resize(frame, (cols, srows), interpolation=cv2.INTER_AREA)
                resized = enhance_contrast(resized)
                gray    = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                gray_small = gray.copy()

                if mode == "edge":
                    gray = cv2.Canny(gray, 50, 150)
                elif mode == "threshold":
                    _, gray = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

                g_bright = np.clip(gray.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
                indices  = np.floor(g_bright.astype(np.float32) / 255.0 * (N - 1)).astype(np.int32)
                if inverted:
                    indices = (N - 1) - indices
                char_grid = ASCII_CHARS[indices]

                if mode == "truecolor":
                    body = build_truecolor(char_grid, resized, srows)
                elif mode == "matrix":
                    body = THEMES["green"] + "\n".join("".join(r) for r in char_grid) + RESET
                else:
                    # mono, edge, threshold
                    body = theme_color + "\n".join("".join(r) for r in char_grid) + RESET

                display_rows = srows

            last_body = body

            # ---- overlays ----
            extra = ""

            if motion_on and gray_small is not None:
                prev_gray, badge = motion_overlay(prev_gray, gray_small)
                extra += badge
            elif motion_on:
                prev_gray = None

            if face_on and cascade is not None and not frozen:
                extra += face_overlay(frame, cascade, cols, display_rows)

            if show_clock:
                extra += clock_overlay(cols)

            if show_wm:
                extra += watermark_overlay(args.watermark, rows, cols)

            # ---- recording ----
            if recording:
                rec_frames.append(body)
                if len(rec_frames) > 1800:
                    recording = False
                    status_msg = "REC limit reached (1800 fr)"; status_ttl = 80

            # ---- fps ----
            now     = time.perf_counter()
            fps_val = 1.0 / max(now - last_t, 1e-9)
            last_t  = now
            fps_history.append(fps_val)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)
            frame_count += 1

            # ---- HUD ----
            tags = ""
            if recording: tags += " \033[91m[REC]\033[0m\033[32m"
            if frozen:    tags += " [FRZ]"
            if inverted:  tags += " [INV]"
            if zoom > 1:  tags += f" z{zoom:.1f}x"
            if adaptive:  tags += " [ADP]"

            smsg = f"  \033[93m>> {status_msg} <<\033[0m\033[32m" if status_ttl > 0 else ""
            if status_ttl > 0: status_ttl -= 1

            hud = (
                f"\033[1m\033[32m"
                f" {mode}{tags} | {THEME_NAMES[theme_idx]} | {fmode}"
                f" | {cols}x{display_rows} | fps:{avg_fps:.1f}"
                f" | b:{brightness:.1f} | #{frame_count:05d}"
                f"{smsg}\033[0m"
            )

            sys.stdout.write(HOME + body + "\n" + hud + extra)
            sys.stdout.flush()

            elapsed = time.perf_counter() - t0
            if min_dt - elapsed > 0:
                time.sleep(min_dt - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(RESET + SHOW_CURSOR + "\n")
        sys.stdout.flush()
        cam.release()
        print("\n[ASCII-CAM] Stopped.")

if __name__ == "__main__":
    main()
