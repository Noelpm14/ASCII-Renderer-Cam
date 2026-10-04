# Real-Time Terminal ASCII Video Renderer

# ASCII Video Renderer
A high-performance command-line application that captures live webcam feed and renders it as real-time ASCII art directly in your terminal. It features a retro startup animation, multiple render modes, live filters, and interactive overlays.
A real-time command-line application that converts live webcam feed into high-performance ASCII art inside the terminal.
## Features
- **Multiple Render Modes:** Truecolor, Matrix, Monochrome, Edge detection, Blocks (2x resolution), and Threshold.
- **Live Filters & Themes:** Blur, sharpen, color channel isolation, and customizable color themes (cyan, amber, pink, etc.).
- **Interactive Overlays:** Live motion detection, face detection boxes, clock, and a custom watermark.
- **Tools:** Freeze frame, screenshot saving (TXT + HTML), local recording & playback, and live zoom.
- **Zero-Flicker Engine:** Uses ANSI escape codes and batched TrueColor rendering for maximum FPS without screen tearing.
Developed by **Noelpm14**.
## Requirements
Ensure you have Python installed, then install the dependencies:
```cmd
---
## Quick Start
### Prerequisites
```bash
pip install opencv-python numpy
```
## How to Run
**On Windows (Easiest):**
Simply double-click the included `run.bat` file. It will automatically open a maximized terminal and start the renderer.
**Via Command Line:**
```cmd
### Run
Double-click `run.bat` or execute:
```bash
python ascii_renderer.py
```
## Live Controls

| Key | Action |
|-----|--------|
| `q` / `Esc` / `Ctrl-C` | Quit cleanly |
| `m` | Cycle color modes: TrueColor → Matrix → Mono → … |
| `+` | Increase brightness (step 0.1, max 3.0) |
| `-` | Decrease brightness (step 0.1, min 0.3) |
| `i` | Invert the density ramp (dark ↔ light) |

## Controls
| Key | Description |
| :--- | :--- |
| `m` | Cycle render mode (truecolor, matrix, edge, etc.) |
| `f` | Cycle filters (blur, sharpen, RGB channels) |
| `t` | Cycle color themes |
