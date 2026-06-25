from hashlib import blake2b
import cv2
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.use("Agg")  # Render matplotlib to memory, not a GUI window

HASH_BITS = 512
bit_distribution = [0] * HASH_BITS
frame_count = 0
last_hash = ""  # most recently computed frame hash, shown under the webcam

# Render charts every N webcam frames. Arrow keys cycle through these steps.
RENDER_STEPS = [1, 5, 10, 25, 100]
render_step_idx = 0  # start at 1 frame per render

# ── Single combined figure: 2x2 grid ────────────────────────────────────────
# Layout:
#   [webcam (OpenCV, not matplotlib)] [bit-count chart      ]
#   [stats text                     ] [pct histogram        ]
#
# The webcam cell is filled by numpy; the other three are matplotlib axes
# rendered into the same figure via a constrained layout grid.

fig = plt.figure(figsize=(20, 8), dpi=100)
fig.patch.set_facecolor("#0d0d0d")

# GridSpec: 2 rows × 2 cols; left column slightly wider (webcam + text)
gs = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[2, 1],
                      hspace=0.35, wspace=0.25,
                      left=0.05, right=0.97, top=0.95, bottom=0.07)

# Top-right: bit-count bar chart
ax_chart = fig.add_subplot(gs[0, 1])
ax_chart.set_facecolor("#1a1a1a")
ax_chart.set_xlabel("Bit Position", color="#aaaaaa", fontsize=8)
ax_chart.set_ylabel("Count of 1s", color="#aaaaaa", fontsize=8)
ax_chart.set_title("Bit Distribution of Webcam Frame Hashes", color="white", fontsize=9)
ax_chart.tick_params(colors="#666666", labelsize=6)
for sp in ax_chart.spines.values():
    sp.set_edgecolor("#333333")
bars = ax_chart.bar([f"{i}" for i in range(HASH_BITS)], bit_distribution,
                    color="#00ccff", width=1.0)
expected_line = ax_chart.axhline(y=0, color="#ff4444", linestyle="--",
                                  linewidth=1, label="Expected (50%)")
ax_chart.legend(facecolor="#222222", labelcolor="white", fontsize=7)
ax_chart.set_xticks([])

# Bottom-left: stats text
ax_text = fig.add_subplot(gs[1, 0])
ax_text.set_facecolor("#0d0d0d")
ax_text.axis("off")

# Bottom-right: percentage histogram (log scale)
ax_hist = fig.add_subplot(gs[1, 1])
ax_hist.set_facecolor("#1a1a1a")
ax_hist.set_ylabel("# Bits (log)", color="#aaaaaa", fontsize=7)
ax_hist.set_title("Distribution of Per-Bit Percentages (log scale)", color="#cccccc", fontsize=8)
ax_hist.tick_params(colors="#666666", labelsize=6)
ax_hist.set_xticks([])
for sp in ax_hist.spines.values():
    sp.set_edgecolor("#333333")

# Top-left: webcam placeholder axes (we'll blit a numpy image into this region)
ax_cam = fig.add_subplot(gs[0, 0])
ax_cam.set_facecolor("#000000")
ax_cam.axis("off")
ax_cam.set_title("Live Webcam Feed", color="white", fontsize=9)
cam_imshow = ax_cam.imshow(np.zeros((480, 640, 3), dtype=np.uint8))

# Last computed hash, displayed directly beneath the webcam preview.
# blake2b hex digests are 128 chars, so wrap onto two 64-char lines.
hash_text = ax_cam.text(0.5, -0.04, "", transform=ax_cam.transAxes,
                        color="#888888", fontsize=6, fontfamily="monospace",
                        ha="center", va="top", linespacing=1.4)


def format_hash(h: str) -> str:
    if not h:
        return ""
    return f"last hash\n{h[:64]}\n{h[64:]}"


def fig_to_bgr(f: plt.Figure, w: int, h: int) -> np.ndarray:
    """Render a matplotlib figure to a BGR numpy array at the requested pixel size."""
    f.set_size_inches(w / f.dpi, h / f.dpi)
    f.canvas.draw()
    buf = np.frombuffer(f.canvas.buffer_rgba(), dtype=np.uint8)
    buf = buf.reshape(f.canvas.get_width_height()[::-1] + (4,))
    return cv2.cvtColor(buf, cv2.COLOR_RGBA2BGR)


def update_main_chart() -> None:
    for bar, val in zip(bars, bit_distribution):
        bar.set_height(val)
    expected_line.set_ydata([frame_count / 2, frame_count / 2])
    ax_chart.relim()
    ax_chart.autoscale_view()


def compute_stats():
    if frame_count == 0:
        return [0.0] * HASH_BITS, 0.0, 0.0, 0, 0.0, 0.0, 0.0
    pcts = [v / frame_count * 100.0 for v in bit_distribution]
    avg_pct = sum(pcts) / HASH_BITS
    avg_diff = avg_pct - 50.0
    diffs = [abs(p - 50.0) for p in pcts]
    worst_bit = int(np.argmax(diffs))
    worst_pct = pcts[worst_bit]
    worst_diff = worst_pct - 50.0
    std_pct = float(np.std(pcts))
    return pcts, avg_pct, avg_diff, worst_bit, worst_pct, worst_diff, std_pct


def signed(v):
    return f"+{v:.3f}%" if v >= 0 else f"{v:.3f}%"

def diff_color(v):
    return "#ff4444" if abs(v) > 2 else "#ffcc00" if abs(v) > 0.5 else "#44ff88"


def reset_data() -> None:
    """Clear all accumulated hash data and reset the frame counter."""
    global bit_distribution, frame_count
    bit_distribution = [0] * HASH_BITS
    frame_count = 0
    print("Data reset.")


def switch_camera(direction: int) -> None:
    """Switch to the next (+1) or previous (-1) camera and reset data."""
    global cam, camera_list_idx
    new_idx = (camera_list_idx + direction) % len(camera_list)
    cam.release()
    new_cam = cv2.VideoCapture(camera_list[new_idx])
    if not new_cam.isOpened():
        print(f"Error: Could not switch to camera {camera_list[new_idx]}, staying on current.")
        cam = open_camera(camera_list[camera_list_idx])
        return
    camera_list_idx = new_idx
    cam = new_cam
    reset_data()
    print(f"Switched to camera {camera_list[camera_list_idx]} ({camera_list_idx + 1}/{len(camera_list)})")


def update_stats_and_hist() -> None:
    pcts, avg_pct, avg_diff, worst_bit, worst_pct, worst_diff, std_pct = compute_stats()

    # ── text ────────────────────────────────────────────────────────────────
    ax_text.clear()
    ax_text.set_facecolor("#0d0d0d")
    ax_text.axis("off")
    lines = [
        ("HASH RANDOMNESS STATS",                                                      0.95, "white",               11, "bold"),
        (f"Total frames:   {frame_count:,}",                                           0.78, "#00ccff",              9, "normal"),
        (f"Average bit %:  {avg_pct:.3f}%  (\u0394 {signed(avg_diff)} vs 50%)",       0.61, diff_color(avg_diff),   9, "normal"),
        (f"Std deviation:  {std_pct:.3f}%  (ideal \u2248 0%)",                        0.44, diff_color(std_pct),       9, "normal"),
        (f"Worst bit:      #{worst_bit}  at {worst_pct:.3f}%  (\u0394 {signed(worst_diff)} vs 50%)",
                                                                                      0.27, diff_color(worst_diff),  9, "normal"),
        ("[ SPACE ] Pause   [ R ] Reset   [ F11 ] Fullscreen   [ ESC ] Quit",         0.13, "#555555",              8, "normal"),
        (f"[ \u2191\u2193 ] Render every: {RENDER_STEPS[render_step_idx]} frame(s)   [ \u2190\u2192 ] Camera: {camera_list_idx + 1}/{len(camera_list)}",
                                                                                      0.03, "#555555",              8, "normal"),
    ]
    for text, y, color, size, weight in lines:
        ax_text.text(0.04, y, text, transform=ax_text.transAxes,
                     color=color, fontsize=size, fontweight=weight,
                     fontfamily="monospace", va="top")

    # ── log-scale histogram ─────────────────────────────────────────────────
    # 100 buckets: each spans 1% (0-1%, 1-2%, ... 99-100%)
    N_BUCKETS = 100
    bucket_counts = [0] * N_BUCKETS
    for p in pcts:
        bucket_counts[min(int(p), N_BUCKETS - 1)] += 1

    ax_hist.clear()
    ax_hist.set_facecolor("#1a1a1a")
    ax_hist.set_ylabel("# Bits (log)", color="#aaaaaa", fontsize=7)
    ax_hist.set_title("Distribution of Per-Bit Percentages (log scale)", color="#cccccc", fontsize=8)
    ax_hist.tick_params(colors="#666666", labelsize=6)
    for sp in ax_hist.spines.values():
        sp.set_edgecolor("#333333")

    # Stoplight colors: midpoint of bucket i is i+0.5%; compute diff vs 50%
    safe_counts = [max(c, 0.1) for c in bucket_counts]
    bar_colors = [diff_color(abs((i + 0.5) - 50)) for i in range(N_BUCKETS)]
    ax_hist.bar(range(N_BUCKETS), safe_counts, color=bar_colors, width=1.0)
    ax_hist.set_yscale("log")
    ax_hist.axvline(x=49.5, color="white", linestyle="--", linewidth=1, label="50%")
    ax_hist.legend(facecolor="#222222", labelcolor="white", fontsize=6)
    ax_hist.yaxis.set_tick_params(labelcolor="#666666")

    # X-axis: label every 10th bucket (0%, 10%, ... 100%)
    ax_hist.set_xticks([i for i in range(0, N_BUCKETS + 1, 10)])
    ax_hist.set_xticklabels([f"{i}%" for i in range(0, 101, 10)],
                             fontsize=6, color="#888888")


# ── Camera init ──────────────────────────────────────────────────────────────
def probe_cameras(max_to_check: int = 8) -> list[int]:
    """Return a list of camera indices that are actually available."""
    available = []
    for idx in range(max_to_check):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(idx)
        cap.release()
    return available

def open_camera(idx: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f"Error: Could not open camera {idx}.")
        exit()
    return cap

camera_list = probe_cameras()
if not camera_list:
    print("Error: No cameras found.")
    exit()
print(f"Found {len(camera_list)} camera(s): indices {camera_list}")

camera_list_idx = 0  # index into camera_list, not the OS camera index
cam = open_camera(camera_list[camera_list_idx])

ret, frame = cam.read()
if not ret:
    print("Error: Failed to grab initial frame.")
    cam.release()
    exit()

cam_h, cam_w = frame.shape[:2]

# Create a resizable window at a sensible default size
WIN_NAME = "Webcam Hash Analyzer"
DEFAULT_W, DEFAULT_H = 1400, 560
cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN_NAME, DEFAULT_W, DEFAULT_H)
is_fullscreen = False
is_paused = False

while True:
    ret, frame = cam.read()
    if not ret:
        print("Error: Failed to grab a frame.")
        break

    if not is_paused:
        frame_count += 1

        # Hash analysis
        digest = blake2b(frame).hexdigest()
        last_hash = digest
        bitstring = bin(int(digest, 16))[2:].zfill(len(digest) * 4)
        for ix, bit in enumerate(bitstring):
            if bit == "1":
                bit_distribution[ix] += 1

    # Always update the webcam cell so the live feed stays live even when paused
    cam_imshow.set_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    # Recompute charts on interval. When paused we still re-render every loop so
    # the charts, stats, and the "Frame #" overlay all reflect the same (frozen)
    # frame count — otherwise the overlay would freeze at a higher number than
    # the charts last rendered at, leaving the panels out of sync.
    should_render = (not is_paused and frame_count % RENDER_STEPS[render_step_idx] == 0) or is_paused
    if should_render:
        update_main_chart()
        update_stats_and_hist()
        hash_text.set_text(format_hash(last_hash))

        rect = cv2.getWindowImageRect(WIN_NAME)  # (x, y, w, h)
        win_w = max(rect[2], 320)
        win_h = max(rect[3], 200)

        combined = fig_to_bgr(fig, win_w, win_h)

        # Draw "PAUSED" in large red text with a black outline over the webcam quadrant.
        # The webcam occupies the top-left quarter of the combined image.
        if is_paused:
            cam_quad_w = win_w // 2
            cam_quad_h = (win_h * 2) // 3  # top row is 2/3 of total height
            text = "Paused"
            font = cv2.FONT_HERSHEY_DUPLEX
            scale = cam_quad_w / 300.0   # scale relative to quadrant width
            thickness = max(2, int(scale * 3))
            (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
            tx = (cam_quad_w - tw) // 2
            ty = (cam_quad_h + th) // 2
            # Black outline
            cv2.putText(combined, text, (tx, ty), font, scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
            # Red fill
            cv2.putText(combined, text, (tx, ty), font, scale, (0, 0, 255), thickness, cv2.LINE_AA)

        cv2.putText(combined, f"Frame #{frame_count}", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(WIN_NAME, combined)

    # Input: cv2.waitKeyEx(1) returns the FULL extended key code (unlike
    # pollKey()/waitKey(), whose handling of special keys varies by HighGUI
    # backend and OpenCV version — that inconsistency is why arrows/F11 worked
    # on one Windows build but not another). The 1 ms timeout keeps it
    # effectively non-blocking while still pumping the GUI event loop. We drain
    # all pending events each frame (Windows emits a two-part sequence for some
    # special keys).
    while True:
        key = cv2.waitKeyEx(1)
        if key == -1:
            break
        # On Win32, special keys arrive as their virtual-key code in the high
        # word (e.g. 0x260000 for Up). Matching on the high word makes detection
        # independent of the exact full value a given build reports. On Linux/
        # macOS the high word is 0, so the explicit code sets below handle those.
        hw = (key >> 16) if key > 0 else -1
        if key == 27:  # ESC
            print("Closing application…")
            cam.release()
            cv2.destroyAllWindows()
            plt.close(fig)
            exit()
        if key == ord(" "):
            is_paused = not is_paused
            print("Paused." if is_paused else "Resumed.")
        if key == ord("r") or key == ord("R"):
            reset_data()
        # F11 — toggle fullscreen
        # Windows high word: VK_F11 = 0x7A; some builds report scancode 0x72.
        # Linux: 65480 (XK_F11) | macOS: 63248
        F11_CODES = {7471104, 452, 7536640, 7995392, 65480, 63248}
        if key in F11_CODES or hw in (0x72, 0x7A):
            is_fullscreen = not is_fullscreen
            if is_fullscreen:
                cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(WIN_NAME, DEFAULT_W, DEFAULT_H)
        # Up/Down arrow keys — adjust render interval
        # Windows high word: VK_UP = 0x26, VK_DOWN = 0x28
        # Linux: Up=65362, Down=65364 | macOS: Up=63232, Down=63233
        UP_CODES   = {2490368, 65362, 63232}
        DOWN_CODES = {2621440, 65364, 63233}
        if key in UP_CODES or hw == 0x26:
            render_step_idx = min(render_step_idx + 1, len(RENDER_STEPS) - 1)
            print(f"Render interval: every {RENDER_STEPS[render_step_idx]} frame(s)")
        if key in DOWN_CODES or hw == 0x28:
            render_step_idx = max(render_step_idx - 1, 0)
            print(f"Render interval: every {RENDER_STEPS[render_step_idx]} frame(s)")
        # Left/Right arrow keys — switch camera
        # Windows high word: VK_LEFT = 0x25, VK_RIGHT = 0x27
        # Linux: Left=65361, Right=65363 | macOS: Left=63234, Right=63235
        LEFT_CODES  = {2424832, 65361, 63234}
        RIGHT_CODES = {2359296, 65363, 63235}
        if key in LEFT_CODES or hw == 0x25:
            switch_camera(-1)
        if key in RIGHT_CODES or hw == 0x27:
            switch_camera(+1)

cam.release()
cv2.destroyAllWindows()
plt.close(fig)
