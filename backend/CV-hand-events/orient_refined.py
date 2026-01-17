# refined.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import time, json, math, random

import cv2
import mediapipe as mp
import tkinter as tk
from PIL import Image, ImageTk

# ============================================================
# CONFIG (single place to change camera + thresholds)
# ============================================================

@dataclass(frozen=True)
class Config:
    # Camera / capture
    prefer_4k: bool = True
    cam_index: int | None = None      # None => auto-pick best; set an int to force
    cam_width: int = 3840
    cam_height: int = 2160
    cam_fps: int = 30
    max_probe_idx: int = 10           # how many indices to scan when auto-picking
    use_dshow: bool = True            # Windows: DirectShow backend

    # UX / view
    mirror_x: bool = True             # selfie mode: flip frame before MP + display
    cursor_smoothing: float = 0.70    # 0..1 (higher = smoother, more lag)
    cursor_x_gain: float = 1.00
    cursor_y_gain: float = 1.00

    # Hand model
    max_hands: int = 1
    min_det_conf: float = 0.60
    min_track_conf: float = 0.60
    model_complexity: int = 1

    # Pinch classification (thumb tip <-> index tip), normalized by palm width
    # closed if pinch_norm <= pinch_close_th
    # open   if pinch_norm >= pinch_open_th
    pinch_close_th: float = 0.28
    pinch_open_th: float = 0.35 # increase by same delta

    # Optional gating by handedness confidence (proxy)
    hand_conf_th: float = 0.70

    # Debounce / stability
    state_dwell_ms: int = 110         # ignore flip-flops inside this window
    closed_stable_frames: int = 3     # require N consecutive CLOSED frames for click
    click_cooldown_ms: int = 450

    # Scroll
    scroll_gain: float = 2.0          # sensitivity multiplier
    scroll_deadzone_px: float = 1.5   # ignore tiny dy jitter


CFG = Config()

# ============================================================
# MediaPipe IDs
# ============================================================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Tips + MCPs we care about
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_MCP = 5
PINKY_MCP = 17
WRIST = 0

# ============================================================
# Camera selection (OBSbot 4K) + capture open
# ============================================================

def open_capture(index: int, cfg: Config) -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if cfg.use_dshow else 0
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open camera index {index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.cam_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.cam_height)
    cap.set(cv2.CAP_PROP_FPS, cfg.cam_fps)
    return cap

def pick_camera_index(cfg: Config) -> tuple[int, list[tuple[int, int, int]]]:
    """
    Probe indices [0..max_probe_idx-1]. Prefer one that returns >= requested resolution.
    Returns (best_index, candidates[(idx,w,h)]).
    """
    candidates: list[tuple[int, int, int]] = []
    backend = cv2.CAP_DSHOW if cfg.use_dshow else 0

    for idx in range(cfg.max_probe_idx):
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.cam_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.cam_height)
        cap.set(cv2.CAP_PROP_FPS, cfg.cam_fps)

        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            candidates.append((idx, w, h))

        cap.release()

    if not candidates:
        raise RuntimeError("No cameras found (0..max_probe_idx).")

    if cfg.prefer_4k:
        for idx, w, h in candidates:
            if w >= cfg.cam_width and h >= cfg.cam_height:
                return idx, candidates

    best = max(candidates, key=lambda t: t[1] * t[2])
    return best[0], candidates

# ============================================================
# Geometry + classification
# ============================================================

def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))

def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def landmarks_to_px(hand_lms, w: int, h: int) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for lm in hand_lms.landmark:
        x = int(clamp01(lm.x) * (w - 1))
        y = int(clamp01(lm.y) * (h - 1))
        pts.append((x, y))
    return pts

def hand_bbox_px(pts: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def palm_center_px(pts: list[tuple[int, int]]) -> tuple[float, float]:
    ids = [WRIST, INDEX_MCP, 9, 13, PINKY_MCP]
    x = sum(pts[i][0] for i in ids) / len(ids)
    y = sum(pts[i][1] for i in ids) / len(ids)
    return (x, y)

def pinch_norm_score(pts: list[tuple[int, int]]) -> float:
    """
    Pinch distance (thumb_tip <-> index_tip) normalized by palm width (index_mcp <-> pinky_mcp).
    Smaller => more pinched/closed.
    """
    palm_w = dist(pts[INDEX_MCP], pts[PINKY_MCP])
    if palm_w < 1e-6:
        return 999.0
    pinch = dist(pts[THUMB_TIP], pts[INDEX_TIP])
    return pinch / palm_w

def classify_pinch_binary(
    pinch_norm: float,
    prev_state: str,
    cfg: Config
) -> str:
    """
    HARD BINARY output: always returns OPEN or CLOSED.
    Uses hysteresis via (close_th, open_th) and falls back to prev_state inside band.
    """
    if pinch_norm <= cfg.pinch_close_th:
        return "CLOSED"
    if pinch_norm >= cfg.pinch_open_th:
        return "OPEN"
    # ambiguous band => keep memory (still binary)
    return prev_state if prev_state in ("OPEN", "CLOSED") else "OPEN"

# ============================================================
# UI
# ============================================================

class HandUITest:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pinch Click Test (THUMB+INDEX pinch = click)")
        self.root.geometry("1400x800")

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Left: video
        video_frame = tk.Frame(main_frame, bg="black")
        video_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.video_label = tk.Label(video_frame, bg="black")
        self.video_label.pack(fill="both", expand=True)

        # Right: interaction + scroll + debug
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=False, padx=(5, 0))
        right_frame.config(width=520)

        self.canvas = tk.Canvas(right_frame, bg="black", width=500, height=420)
        self.canvas.pack(fill="both", expand=True, pady=(0, 6))

        scroll_frame = tk.Frame(right_frame)
        scroll_frame.pack(fill="both", expand=True, pady=(0, 6))

        self.scroll_text = tk.Text(
            scroll_frame, wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#1a1a1a", fg="#ffffff"
        )
        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=self.scroll_text.yview)
        self.scroll_text.config(yscrollcommand=scrollbar.set)

        self.scroll_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        sample_text = "\n".join([f"Line {i}: scrolling test content " * 2 for i in range(140)])
        self.scroll_text.insert("1.0", sample_text)
        self.scroll_text.bind("<Key>", lambda e: "break")  # read-only

        # Buttons in relative coords (0..1)
        self.buttons = [
            {"name": "Button A", "rect": (0.08, 0.10, 0.46, 0.40), "color": "#222"},
            {"name": "Button B", "rect": (0.54, 0.10, 0.92, 0.40), "color": "#222"},
            {"name": "Scroll Zone", "rect": (0.08, 0.52, 0.92, 0.86), "color": "#111"},
        ]

        debug_frame = tk.Frame(right_frame, bg="#2a2a2a", relief=tk.RAISED, borderwidth=2)
        debug_frame.pack(fill="x", pady=(0, 6))

        tk.Label(
            debug_frame, text="Debug Info",
            font=("Segoe UI", 10, "bold"),
            bg="#2a2a2a", fg="white"
        ).pack(pady=(5, 2))

        self.debug_vars = {
            "pinch_norm": tk.StringVar(value="pinch_norm: --"),
            "state": tk.StringVar(value="state: --"),
            "hover": tk.StringVar(value="hover: --"),
            "hand_conf": tk.StringVar(value="hand_conf: --"),
            "scroll_delta": tk.StringVar(value="scroll_delta: --"),
            "cam": tk.StringVar(value="cam: --"),
        }
        for var in self.debug_vars.values():
            tk.Label(
                debug_frame, textvariable=var,
                font=("Consolas", 9),
                bg="#2a2a2a", fg="#a0a0a0",
                anchor="w"
            ).pack(fill="x", padx=6, pady=1)

        self.status_var = tk.StringVar(value="Status: --")
        self.status = tk.Label(
            right_frame, textvariable=self.status_var,
            font=("Segoe UI", 12),
            bg="#333", fg="white",
            anchor="w", padx=6, pady=4
        )
        self.status.pack(fill="x")

        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.closing = False

        self.draw_static()

        # Cursor (keep above buttons)
        self.cursor = self.canvas.create_oval(0, 0, 0, 0, fill="white", outline="", tags="cursor")

        # Cursor smoothing state
        self.smoothed_x = None
        self.smoothed_y = None

        # Click feedback
        self.click_feedback: dict[str, int] = {}

        # For scroll
        self.last_y = None

        # For click stability / gating
        self.closed_run = 0
        self.last_click_ms = 0
        self.prev_state = "OPEN"

    def on_canvas_resize(self, event=None):
        self.draw_static()

    def get_canvas_size(self) -> tuple[int, int]:
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            try:
                w = int(self.canvas.cget("width"))
                h = int(self.canvas.cget("height"))
            except Exception:
                w, h = 500, 420
        return w, h

    def draw_static(self):
        self.canvas.delete("btn")
        w, h = self.get_canvas_size()
        for b in self.buttons:
            x1r, y1r, x2r, y2r = b["rect"]
            x1, y1 = int(x1r * w), int(y1r * h)
            x2, y2 = int(x2r * w), int(y2r * h)
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=b["color"], outline="#555", width=3, tags="btn")
            self.canvas.create_text(
                (x1 + x2) // 2, (y1 + y2) // 2,
                text=b["name"], fill="white",
                font=("Segoe UI", 18, "bold"),
                tags="btn"
            )
        self.canvas.tag_raise("cursor")

    def hit_test(self, x: int, y: int):
        w, h = self.get_canvas_size()
        xr = x / w if w > 0 else 0
        yr = y / h if h > 0 else 0
        for b in self.buttons:
            x1r, y1r, x2r, y2r = b["rect"]
            if x1r <= xr <= x2r and y1r <= yr <= y2r:
                return b
        return None

    def set_cursor(self, x: int, y: int, state: str, cfg: Config):
        w, h = self.get_canvas_size()
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        if self.smoothed_x is None:
            self.smoothed_x, self.smoothed_y = float(x), float(y)
        else:
            a = cfg.cursor_smoothing
            self.smoothed_x = a * self.smoothed_x + (1 - a) * x
            self.smoothed_y = a * self.smoothed_y + (1 - a) * y

        xs = int(max(0, min(w - 1, self.smoothed_x)))
        ys = int(max(0, min(h - 1, self.smoothed_y)))

        r = 10
        fill = "white"
        if state == "OPEN":
            fill = "red"
        elif state == "CLOSED":
            fill = "green"

        self.canvas.coords(self.cursor, xs - r, ys - r, xs + r, ys + r)
        self.canvas.itemconfig(self.cursor, fill=fill)
        self.canvas.tag_raise("cursor")

        return xs, ys  # return smoothed pixel coords (useful for scroll)

    def draw_click_feedback(self, button_name: str):
        if button_name in self.click_feedback:
            self.canvas.delete(self.click_feedback[button_name])

        button = next((b for b in self.buttons if b["name"] == button_name), None)
        if not button:
            return

        w, h = self.get_canvas_size()
        x1r, y1r, x2r, y2r = button["rect"]
        cx = int((x1r + x2r) * w / 2)
        cy = int((y1r + y2r) * h / 2)

        size = 30
        shape_type = random.choice(["star", "circle", "square"])
        if shape_type == "circle":
            item = self.canvas.create_oval(cx - size, cy - size, cx + size, cy + size,
                                           fill="yellow", outline="orange", width=3, tags="click_feedback")
        elif shape_type == "square":
            item = self.canvas.create_rectangle(cx - size, cy - size, cx + size, cy + size,
                                                fill="yellow", outline="orange", width=3, tags="click_feedback")
        else:
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                rr = size if i % 2 == 0 else size * 0.4
                points.extend([cx + rr * math.cos(angle), cy + rr * math.sin(angle)])
            item = self.canvas.create_polygon(points, fill="yellow", outline="orange", width=3, tags="click_feedback")

        self.click_feedback[button_name] = item

        def remove():
            if button_name in self.click_feedback:
                self.canvas.delete(self.click_feedback[button_name])
                del self.click_feedback[button_name]

        self.root.after(500, remove)

    def try_click(self, target_name: str, cfg: Config) -> bool:
        now = int(time.time() * 1000)
        if now - self.last_click_ms < cfg.click_cooldown_ms:
            return False
        self.last_click_ms = now
        self.status_var.set(f"CLICK: {target_name}")
        self.draw_click_feedback(target_name)
        return True

    def scroll_text_widget(self, delta_y: float):
        self.scroll_text.yview_scroll(int(-delta_y), "pixels")

    def update_debug(self, pinch_norm, state, hover_name, hand_conf, scroll_delta, cam_info):
        self.debug_vars["pinch_norm"].set(f"pinch_norm: {pinch_norm:.3f}" if pinch_norm is not None else "pinch_norm: --")
        self.debug_vars["state"].set(f"state: {state}")
        self.debug_vars["hover"].set(f"hover: {hover_name}")
        self.debug_vars["hand_conf"].set(f"hand_conf: {hand_conf:.3f}" if hand_conf is not None else "hand_conf: --")
        self.debug_vars["scroll_delta"].set(f"scroll_delta: {scroll_delta:.1f}" if scroll_delta is not None else "scroll_delta: --")
        self.debug_vars["cam"].set(cam_info)

    def update_status(self, msg: str):
        self.status_var.set(msg)

    def on_closing(self):
        self.closing = True
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()

# ============================================================
# Logging path (backend/logs)
# ============================================================

def make_logfile(prefix: str) -> Path:
    backend_dir = Path(__file__).resolve().parents[1]  # .../backend (since refined.py is in backend/cv-hand-events/)
    log_dir = backend_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return log_dir / f"{prefix}_{session}.jsonl"

# ============================================================
# Main
# ============================================================

def main():
    ui = HandUITest()

    # Choose camera index (OBSbot 4K) in ONE place
    if CFG.cam_index is None:
        cam_index, candidates = pick_camera_index(CFG)
    else:
        cam_index, candidates = CFG.cam_index, []

    print("[INFO] Camera candidates:", candidates)
    print("[INFO] Using cam_index:", cam_index)

    cap = open_capture(cam_index, CFG)

    # Log file
    log_path = make_logfile("ui_pinch_test")
    f = open(log_path, "a", encoding="utf-8")
    print(f"[INFO] Logging to: {log_path}")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=CFG.max_hands,
        model_complexity=CFG.model_complexity,
        min_detection_confidence=CFG.min_det_conf,
        min_tracking_confidence=CFG.min_track_conf,
    )

    # Video display size (scaled to label each tick)
    video_display_w = 820
    video_display_h = 460

    # Binary state memory + debounce
    state_mem = "OPEN"
    last_state_change_ms = 0

    def tick():
        nonlocal state_mem, last_state_change_ms

        if ui.closing:
            return

        ok, frame = cap.read()
        if not ok or frame is None:
            ui.update_status("Camera read failed.")
            ui.root.after(33, tick)
            return

        ts_ms = int(time.time() * 1000)
        h, w = frame.shape[:2]

        # Mirror (selfie) BEFORE mediapipe so landmarks + display match the cursor
        if CFG.mirror_x:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        overlay = frame.copy()

        # Defaults
        pinch_norm = None
        hand_conf = None
        state = state_mem  # binary at all times
        cx_ui, cy_ui = ui.get_canvas_size()
        cx_ui, cy_ui = cx_ui // 2, cy_ui // 2
        scroll_delta = None

        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []

        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            pinch_norm = pinch_norm_score(pts)

            # handedness score (proxy), optional
            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)

            # Classify binary pinch, but apply dwell/debounce against rapid flips
            proposed = classify_pinch_binary(pinch_norm, state_mem, CFG)
            now = ts_ms
            if proposed != state_mem:
                if (now - last_state_change_ms) >= CFG.state_dwell_ms:
                    state_mem = proposed
                    last_state_change_ms = now
            state = state_mem

            # Cursor point: palm center (more stable than fingertip)
            cx, cy = palm_center_px(pts)

            canvas_w, canvas_h = ui.get_canvas_size()
            cx_ui = int((cx / w) * canvas_w * CFG.cursor_x_gain)
            cy_ui = int((cy / h) * canvas_h * CFG.cursor_y_gain)
            cx_ui = max(0, min(canvas_w - 1, cx_ui))
            cy_ui = max(0, min(canvas_h - 1, cy_ui))

            # Draw bbox + label on video
            x1, y1, x2, y2 = hand_bbox_px(pts)

            if state == "OPEN":
                color = (0, 0, 255)    # red
                thickness = 6
            else:
                color = (0, 255, 0)    # green
                thickness = 6

            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness)

            # Draw palm center
            cv2.circle(overlay, (int(cx), int(cy)), 8, color, -1)

            # Draw landmarks
            mp_draw.draw_landmarks(overlay, hand_landmarks[0], mp_hands.HAND_CONNECTIONS)

            # Label box
            label = f"{state} pinch_norm={pinch_norm:.3f}"
            if hand_conf is not None:
                label += f" hc={hand_conf:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 1.1
            t = 3
            (tw, th), base = cv2.getTextSize(label, font, scale, t)
            pad = 8
            top = max(0, y1 - th - base - 2 * pad)
            cv2.rectangle(overlay, (x1, top), (x1 + tw + 2 * pad, top + th + base + 2 * pad), color, -1)
            cv2.putText(overlay, label, (x1 + pad, top + th + pad), font, scale, (0, 0, 0), t, cv2.LINE_AA)

        # Gate by hand_conf if you want: if low confidence, keep last state (still binary)
        if hand_conf is not None and hand_conf < CFG.hand_conf_th:
            state = state_mem

        # Update cursor (keep above buttons)
        xs, ys = ui.set_cursor(cx_ui, cy_ui, state, CFG)

        # Hit test
        hovered = ui.hit_test(xs, ys)
        hover_name = hovered["name"] if hovered else "none"

        # CLICK: require CLOSED stable frames + edge-ish behavior
        clicked = False
        if state == "CLOSED" and hovered and hover_name != "Scroll Zone":
            ui.closed_run += 1
        else:
            ui.closed_run = 0

        if ui.closed_run >= CFG.closed_stable_frames:
            # only click once per closed run: lockout until opened again
            if ui.prev_state == "OPEN":
                clicked = ui.try_click(hover_name, CFG)
            ui.prev_state = "CLOSED"
        else:
            if state == "OPEN":
                ui.prev_state = "OPEN"

        # SCROLL: only when CLOSED and hovering Scroll Zone; dy from smoothed cursor
        if state == "CLOSED" and hovered and hover_name == "Scroll Zone":
            if ui.last_y is not None:
                dy = (ys - ui.last_y) * CFG.scroll_gain
                if abs(dy) >= CFG.scroll_deadzone_px:
                    ui.scroll_text_widget(dy)
                    scroll_delta = dy
            ui.last_y = ys
        else:
            ui.last_y = None

        # Status + debug
        if clicked:
            ui.update_status(f"CLICK: {hover_name}")
        else:
            ui.update_status(f"state={state} hover={hover_name}")

        cam_info = f"cam_index={cam_index} {w}x{h}"
        ui.update_debug(pinch_norm, state, hover_name, hand_conf, scroll_delta, cam_info)

        # Log JSONL
        payload = {
            "timestamp_ms": ts_ms,
            "cam_index": cam_index,
            "image_wh": [w, h],
            "mirror_x": CFG.mirror_x,
            "hand": {
                "state": state,
                "pinch_norm": None if pinch_norm is None else round(pinch_norm, 4),
                "hand_conf": None if hand_conf is None else round(hand_conf, 4),
                "cursor_ui": {"x": int(xs), "y": int(ys)},
                "hovered": hover_name,
                "clicked": bool(clicked),
                "scroll_delta": None if scroll_delta is None else float(scroll_delta),
            }
        }
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")

        # Show video in Tkinter (correct color: BGR -> RGB)
        overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        display = cv2.resize(overlay_rgb, (video_display_w, video_display_h), interpolation=cv2.INTER_AREA)
        imgtk = ImageTk.PhotoImage(image=Image.fromarray(display))
        ui.video_label.imgtk = imgtk
        ui.video_label.config(image=imgtk)

        ui.root.after(33, tick)  # ~30fps

    ui.root.after(80, tick)
    ui.run()

    # Cleanup
    try:
        f.close()
    except Exception:
        pass
    try:
        hands.close()
    except Exception:
        pass
    try:
        cap.release()
    except Exception:
        pass
    print("[INFO] Cleanup complete.")

if __name__ == "__main__":
    main()
