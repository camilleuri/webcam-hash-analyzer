This script was made as a demo for the CYPHER Lab at the University of Rhode Island.

# Webcam Hash Analyzer

A live visualization that hashes webcam frames with **BLAKE2b** and watches the
output bits for uniformity. Every frame becomes a 512-bit digest; the tool keeps
a running tally of how often each bit position comes up `1` and charts how close
each bit sits to the ideal **50%**.

It's a small, hands-on way to *see* the avalanche/uniformity property of a
cryptographic hash: even though consecutive webcam frames are highly correlated,
a good hash should still scatter its output bits so that, over time, every
position trends toward an even split of ones and zeros.

> **Note:** This is an educational/visual toy, not a formal randomness test
> suite. For rigorous analysis of a PRNG or hash, use something like Dieharder
> or the NIST Statistical Test Suite.

---

## What you'll see

The window is a single 2×2 dashboard:

| | Left | Right |
|---|---|---|
| **Top** | Live webcam feed, with the most recent BLAKE2b hex digest displayed beneath it (split across two 64-character lines) | Bit-distribution bar chart (count of `1`s per bit position, with the expected-50% line) |
| **Bottom** | Running stats readout | Histogram of per-bit percentages on a log scale |

The stats panel reports:

- **Total frames** processed so far
- **Average bit %** across all 512 bits, and its delta from 50%
- **Standard deviation** of the per-bit percentages (ideal ≈ 0%)
- **Worst bit** — the single bit position furthest from 50%

Values are color-coded as a stoplight: green (within 0.5% of 50%), yellow
(0.5–2%), red (more than 2% off). Early on, with only a handful of frames, the
numbers swing wildly; they settle toward 50% as the frame count climbs.

---

## How it works

For each captured frame:

1. The raw frame buffer is hashed with `blake2b` (default 512-bit / 64-byte digest).
2. The hex digest is expanded to its 512-bit binary string.
3. For every position that is `1`, the corresponding counter in `bit_distribution` is incremented.
4. Percentages (`count / frame_count × 100`) drive the charts and stats.

The live feed updates every frame for smoothness, but the charts only re-render
every *N* frames (configurable at runtime) to keep things responsive. Matplotlib
draws into an off-screen buffer, which is composited into the OpenCV window.

---

## Requirements

- **Python 3.8+**
- A working webcam
- Python packages:
  - `opencv-python`
  - `matplotlib`
  - `numpy`

`hashlib` (for BLAKE2b) is part of the Python standard library.

---

## Installation

```bash
pip install opencv-python matplotlib numpy
```

(Optional but recommended — use a virtual environment:)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install opencv-python matplotlib numpy
```

---

## Usage

```bash
python webcam_hash_analyzer.py
```

On launch the tool probes camera indices 0–7, opens the first one that works,
and prints a list of all available cameras to stdout. A resizable window titled
**"Webcam Hash Analyzer"** opens at a sensible default size — resize it freely
and the dashboard re-renders to fit.

### Controls

| Key | Action |
|---|---|
| `SPACE` | Pause / resume — the live feed keeps running but hashing stops; a "Paused" overlay appears over the webcam quadrant |
| `R` | Reset all accumulated data and the frame counter |
| `↑` | Increase the render interval (render *less* often) |
| `↓` | Decrease the render interval (render *more* often) |
| `←` / `→` | Cycle to the previous / next detected camera (resets data on switch) |
| `F11` | Toggle fullscreen (restores to the default window size when exited) |
| `ESC` | Quit |

All controls work across Windows, Linux, and macOS — the tool matches the
platform-specific key codes returned by `cv2.pollKey()` for each.

The render interval cycles through **1 → 5 → 10 → 25 → 100** frames per chart
update. Rendering less frequently lowers CPU load and lets the camera run at a
higher effective frame rate.

---

## Interpreting the results

- **Average bit % near 50% with a small std deviation** is the healthy,
  expected outcome — BLAKE2b's output is well-distributed.
- A **worst bit** that stays a few percent off after only a few hundred frames
  is normal statistical noise; with more frames it should drift back toward 50%.
- Persistent, large, structured deviations would be the interesting (and
  surprising) result — but with a sound hash and enough frames, you shouldn't
  see them.

More frames = tighter convergence. Let it run for a while before reading too
much into the numbers.

---

## CYPHER AI Marking

Ideation (A0), Code (A3), README document (A4)

https://web.uri.edu/cypher/ai-marking/
