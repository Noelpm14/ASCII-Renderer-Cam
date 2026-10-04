# Real-Time Terminal ASCII Video Renderer

> Live webcam → ASCII art → VS Code terminal, running at **30+ FPS** with zero-flicker rendering and 24-bit TrueColor support.

---

## Quick Start

```powershell
# Install dependencies (already satisfied on this machine)
py -m pip install -r requirements.txt

# Run with default settings (TrueColor mode, camera 0, 30 FPS cap)
py ascii_renderer.py

# Matrix green mode
py ascii_renderer.py --mode matrix

# Monochrome mode, camera index 1
py ascii_renderer.py --mode mono --camera 1

# Higher FPS cap with custom brightness
py ascii_renderer.py --fps-cap 60 --brightness 1.3
```

---

## Live Controls (while running)

| Key | Action |
|-----|--------|
| `q` / `Esc` / `Ctrl-C` | Quit cleanly |
| `m` | Cycle color modes: TrueColor → Matrix → Mono → … |
| `+` | Increase brightness (step 0.1, max 3.0) |
| `-` | Decrease brightness (step 0.1, min 0.3) |
| `i` | Invert the density ramp (dark ↔ light) |

---

## Color Modes

| Mode | Description |
|------|-------------|
| `truecolor` | 24-bit RGB per character via `ESC[38;2;R;G;Bm` |
| `matrix` | Uniform ANSI green (`ESC[32m`) — classic hacker look |
| `mono` | Plain white characters, no color codes |

---

## CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `truecolor` | Initial color mode |
| `--camera` | `0` | OpenCV camera index |
| `--fps-cap` | `30.0` | Maximum frames per second |
| `--brightness` | `1.0` | Brightness multiplier `[0.3 – 3.0]` |

---

## Architecture

```
Webcam (cv2.VideoCapture)
        │
        ▼
   cv2.flip(frame, 1)          ← mirror image
        │
        ▼
   cv2.resize → (cols, rows-2) ← dynamic terminal size
        │
        ├──▶  cv2.cvtColor BGR→GRAY
        │           │
        │           ▼
        │     brightness scale (NumPy)
        │           │
        │           ▼
        │     I = floor(G/255 × 12)   ← vectorized
        │           │
        │           ▼
        │     ASCII_CHARS[I]           ← 2D char grid
        │
        ├── TrueColor: ESC[38;2;R;G;Bm per char
        ├── Matrix:    ESC[32m  whole frame
        └── Mono:      plain characters
                │
                ▼
        ESC[H  +  sys.stdout.write()  ← zero-flicker
                │
                ▼
            HUD status line
```

---

## Technical Highlights

- **Zero-flicker rendering** — `\033[H` repositions cursor to `(0,0)` every frame instead of calling `cls/clear`, eliminating shell-process overhead.
- **Vectorized quantization** — single NumPy expression maps the entire 2D grayscale matrix to ASCII indices simultaneously.
- **Dynamic terminal geometry** — `shutil.get_terminal_size()` called each frame so resizing the VS Code panel or changing font size never crashes the stream.
- **24-bit TrueColor** — extracts per-pixel BGR channels from the resized frame and embeds them as `\033[38;2;R;G;Bm` sequences.
- **FPS telemetry** — live elapsed-time measurement with `time.perf_counter()` guards against division-by-zero.
- **Windows VT support** — `SetConsoleMode` called at startup to enable ANSI processing on native Windows consoles (VS Code terminal already supports it).
