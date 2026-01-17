from pathlib import Path
from datetime import datetime
import time, json, math, random
import cv2
import mediapipe as mp
import tkinter as tk
from PIL import Image, ImageTk

# // branch test 

# ---------------- Configuration (tune these) ----------------
MIRROR_X = True            # Mirror camera feed horizontally (selfie mode)
FORCE_CAM_INDEX = 1        # Set to an int to force OBSBOT/Emeet index. Set to None to auto-pick best.
CAM_WIDTH = 3840
CAM_HEIGHT = 2160
CAM_FPS = 30

# State classification thresholds
CLOSED_TH = 1.25
OPEN_TH = 1.45
MARGIN = 0.12
HAND_CONF_TH = 0.70  # handedness confidence threshold

# Event timing / robustness
CLICK_COOLDOWN_MS = 600
CLOSED_STABLE_FRAMES = 4     # require this many consecutive definitive CLOSED frames before click edge can fire
HOVER_STICK_MS = 180         # keep last hover briefly to prevent jitter dropping hover

# Scroll
SCROLL_GAIN = 2.0            # multiplier for scroll sensitivity
SCROLL_DY_DEADBAND = 2.0     # pixels deadband to ignore micro jitter

# Cursor mapping
CURSOR_SMOOTHING = 0.7       # exponential smoothing factor (0-1, higher = smoother)
CURSOR_X_GAIN = 1.0
CURSOR_Y_GAIN = 1.0

# ---------------- CV / Hand Utils ----------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}

def pick_camera_index(prefer_4k=True, max_idx=10):
    """
    Pick the best camera index. Prefer a camera that actually returns >= 3840x2160 after setting.
    Note: some cameras ignore requested resolution; we validate via a real frame read.
    """
    candidates = []
    for idx in range(max_idx):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAM_FPS)

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            continue

        h, w = frame.shape[:2]
        candidates.append((idx, w, h))
        cap.release()

    if not candidates:
        raise RuntimeError("No cameras found.")

    if prefer_4k:
        for idx, w, h in candidates:
            if w >= CAM_WIDTH and h >= CAM_HEIGHT:
                return idx, candidates
        best = max(candidates, key=lambda t: t[1] * t[2])
        return best[0], candidates

    return candidates[0][0], candidates

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def clamp01(v):
    return max(0.0, min(1.0, v))

def landmarks_to_px(hand_lms, w, h):
    pts = []
    for lm in hand_lms.landmark:
        x = int(clamp01(lm.x) * (w - 1))
        y = int(clamp01(lm.y) * (h - 1))
        pts.append((x, y))
    return pts

def hand_bbox_px(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def palm_center_px(pts):
    ids = [0, 5, 9, 13, 17]  # wrist + MCPs
    x = sum(pts[i][0] for i in ids) / len(ids)
    y = sum(pts[i][1] for i in ids) / len(ids)
    return (x, y)

def open_closed_score(pts):
    palm_w = dist(pts[5], pts[17])
    if palm_w < 1e-6:
        return 999.0
    palm = palm_center_px(pts)
    mean_tip = sum(dist(pts[i], palm) for i in TIP_IDS.values()) / len(TIP_IDS)
    return mean_tip / palm_w  # lower => more closed

def classify_state(score, closed_th=CLOSED_TH, open_th=OPEN_TH, margin=MARGIN):
    # definitive gating
    if score < (closed_th - margin):
        return "CLOSED", True
    if score > (open_th + margin):
        return "OPEN", True
    return "UNKNOWN", False

# ---------------- UI ----------------
class HandUITest:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Hand Click Test (CLOSE = click)")
        self.root.geometry("1400x800")

        # Main container with video on left, interaction on right
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Left: Video panel
        video_frame = tk.Frame(main_frame, bg="black")
        video_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.video_label = tk.Label(video_frame, bg="black")
        self.video_label.pack(fill="both", expand=True)

        # Right: Interaction panel
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=False, padx=(5, 0))
        right_frame.config(width=520)

        # Interaction canvas (resizable)
        self.canvas = tk.Canvas(right_frame, bg="black", width=500, height=420)
        self.canvas.pack(fill="both", expand=True, pady=(0, 5))

        # Scrollable text widget
        scroll_frame = tk.Frame(right_frame)
        scroll_frame.pack(fill="both", expand=True, pady=(0, 5))

        self.scroll_text = tk.Text(scroll_frame, wrap=tk.WORD, font=("Consolas", 10),
                                   bg="#1a1a1a", fg="#ffffff")
        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=self.scroll_text.yview)
        self.scroll_text.config(yscrollcommand=scrollbar.set)

        self.scroll_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        sample_text = "\n".join([f"Line {i}: This is sample text for scrolling. " * 2 for i in range(1, 200)])
        self.scroll_text.insert("1.0", sample_text)
        self.scroll_text.bind("<Key>", lambda e: "break")  # read-only

        # Buttons (relative)
        self.buttons = [
            {"name": "Button A", "rect": (0.10, 0.10, 0.45, 0.40), "color": "#222"},
            {"name": "Button B", "rect": (0.55, 0.10, 0.90, 0.40), "color": "#222"},
            {"name": "Scroll Zone", "rect": (0.10, 0.52, 0.90, 0.88), "color": "#111"},
        ]

        # Debug panel
        debug_frame = tk.Frame(right_frame, bg="#2a2a2a", relief=tk.RAISED, borderwidth=2)
        debug_frame.pack(fill="x", pady=(0, 5))

        tk.Label(debug_frame, text="Debug Info", font=("Segoe UI", 10, "bold"),
                 bg="#2a2a2a", fg="white").pack(pady=(5, 2))

        self.debug_vars = {
            "score": tk.StringVar(value="Score: --"),
            "state": tk.StringVar(value="State: --"),
            "definitive": tk.StringVar(value="Definitive: --"),
            "hover": tk.StringVar(value="Hover: --"),
            "hand_conf": tk.StringVar(value="Hand Conf: --"),
            "closed_frames": tk.StringVar(value="Closed frames: --"),
            "scroll_delta": tk.StringVar(value="Scroll Δ: --"),
        }
        for var in self.debug_vars.values():
            tk.Label(debug_frame, textvariable=var, font=("Consolas", 9),
                     bg="#2a2a2a", fg="#a0a0a0", anchor="w").pack(fill="x", padx=5, pady=1)

        # Status bar
        self.status_var = tk.StringVar(value="Status: --")
        self.status = tk.Label(right_frame, textvariable=self.status_var,
                               font=("Segoe UI", 12), bg="#333", fg="white",
                               anchor="w", padx=5, pady=3)
        self.status.pack(fill="x")

        self.draw_static()

        # Cursor dot
        self.cursor = self.canvas.create_oval(0, 0, 0, 0, fill="white", outline="", tags="cursor")

        # State tracking (robust click)
        self.last_def_state = "UNKNOWN"   # last definitive state (OPEN/CLOSED), ignores UNKNOWN
        self.last_click_ms = 0
        self.closed_count = 0

        # Hover stickiness
        self.hover_target = None
        self.hover_until_ms = 0

        # Scroll tracking
        self.last_y = None

        # Cursor smoothing
        self.smoothed_x = None
        self.smoothed_y = None

        # Click feedback shape ids
        self.click_feedback = {}

        # Window events
        self.canvas.bind("<Configure>", lambda e: self.draw_static())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.closing = False

    def get_canvas_size(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            # fallback to configured defaults
            w = 500
            h = 420
        return w, h

    def draw_static(self):
        self.canvas.delete("btn")
        w, h = self.get_canvas_size()
        for b in self.buttons:
            x1r, y1r, x2r, y2r = b["rect"]
            x1 = int(x1r * w); y1 = int(y1r * h)
            x2 = int(x2r * w); y2 = int(y2r * h)
            self.canvas.create_rectangle(x1, y1, x2, y2,
                                         fill=b["color"], outline="#555", width=3, tags="btn")
            self.canvas.create_text((x1+x2)//2, (y1+y2)//2,
                                    text=b["name"], fill="white",
                                    font=("Segoe UI", 18, "bold"), tags="btn")
        self.canvas.tag_raise("cursor")

    def hit_test(self, x, y):
        w, h = self.get_canvas_size()
        if w <= 0 or h <= 0:
            return None
        xr = x / w
        yr = y / h
        for b in self.buttons:
            x1r, y1r, x2r, y2r = b["rect"]
            if x1r <= xr <= x2r and y1r <= yr <= y2r:
                return b
        return None

    def set_cursor(self, x, y, state):
        w, h = self.get_canvas_size()
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        if self.smoothed_x is None:
            self.smoothed_x, self.smoothed_y = x, y
        else:
            self.smoothed_x = CURSOR_SMOOTHING * self.smoothed_x + (1 - CURSOR_SMOOTHING) * x
            self.smoothed_y = CURSOR_SMOOTHING * self.smoothed_y + (1 - CURSOR_SMOOTHING) * y

        xs = int(max(0, min(w - 1, self.smoothed_x)))
        ys = int(max(0, min(h - 1, self.smoothed_y)))

        r = 10
        fill = "white"
        if state == "OPEN":
            fill = "red"
        elif state == "CLOSED":
            fill = "green"

        self.canvas.coords(self.cursor, xs-r, ys-r, xs+r, ys+r)
        self.canvas.itemconfig(self.cursor, fill=fill)
        self.canvas.tag_raise("cursor")

    def update_debug(self, score, state, definitive, hover_name, hand_conf, closed_frames, scroll_delta):
        self.debug_vars["score"].set(f"Score: {score:.3f}" if score is not None else "Score: --")
        self.debug_vars["state"].set(f"State: {state}")
        self.debug_vars["definitive"].set(f"Definitive: {definitive}")
        self.debug_vars["hover"].set(f"Hover: {hover_name}")
        self.debug_vars["hand_conf"].set(f"Hand Conf: {hand_conf:.3f}" if hand_conf is not None else "Hand Conf: --")
        self.debug_vars["closed_frames"].set(f"Closed frames: {closed_frames}")
        self.debug_vars["scroll_delta"].set(f"Scroll Δ: {scroll_delta:.1f}" if scroll_delta is not None else "Scroll Δ: --")

    def update_status(self, msg):
        self.status_var.set(msg)

    def click_if_allowed(self, target_name):
        now = int(time.time() * 1000)
        if now - self.last_click_ms < CLICK_COOLDOWN_MS:
            return False
        self.last_click_ms = now
        self.status_var.set(f"CLICK: {target_name}")
        self.draw_click_feedback(target_name)
        return True

    def draw_click_feedback(self, button_name):
        # remove old for this button
        if button_name in self.click_feedback:
            self.canvas.delete(self.click_feedback[button_name])

        # find button
        button = next((b for b in self.buttons if b["name"] == button_name), None)
        if not button:
            return

        w, h = self.get_canvas_size()
        x1r, y1r, x2r, y2r = button["rect"]
        cx = int((x1r + x2r) * w / 2)
        cy = int((y1r + y2r) * h / 2)

        shape_type = random.choice(["star", "circle", "square"])
        size = 30

        if shape_type == "circle":
            item = self.canvas.create_oval(cx-size, cy-size, cx+size, cy+size,
                                           fill="yellow", outline="orange", width=3, tags="click_feedback")
        elif shape_type == "square":
            item = self.canvas.create_rectangle(cx-size, cy-size, cx+size, cy+size,
                                                fill="yellow", outline="orange", width=3, tags="click_feedback")
        else:
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                r = size if i % 2 == 0 else size * 0.4
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                points.extend([px, py])
            item = self.canvas.create_polygon(points, fill="yellow", outline="orange", width=3, tags="click_feedback")

        self.click_feedback[button_name] = item
        self.canvas.tag_raise("cursor")

        def remove_feedback():
            if button_name in self.click_feedback:
                self.canvas.delete(self.click_feedback[button_name])
                del self.click_feedback[button_name]

        self.root.after(500, remove_feedback)

    def scroll_text_widget(self, delta_pixels):
        # Tk text widget supports pixel scrolling on Windows in many cases; if not smooth, switch to "units"
        try:
            self.scroll_text.yview_scroll(int(-delta_pixels), "pixels")
        except tk.TclError:
            self.scroll_text.yview_scroll(int(-delta_pixels / 12), "units")

    def on_closing(self):
        self.closing = True
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# ---------------- Main loop (CV -> UI) ----------------
def main():
    ui = HandUITest()

    # --- Choose camera (force OBSBOT index OR auto-pick best 4K) ---
    if FORCE_CAM_INDEX is not None:
        cam_index = int(FORCE_CAM_INDEX)
        print(f"[INFO] Forcing camera index: {cam_index}")
    else:
        cam_index, cams = pick_camera_index(prefer_4k=True, max_idx=10)
        print("[INFO] Camera candidates:", cams)
        print("[INFO] Auto-picked cam_index:", cam_index)

    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {cam_index}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAM_FPS)

    # Read one frame to confirm actual resolution
    ok, test_frame = cap.read()
    if ok and test_frame is not None:
        th, tw = test_frame.shape[:2]
        print(f"[INFO] Actual capture resolution: {tw}x{th} (requested {CAM_WIDTH}x{CAM_HEIGHT})")
    else:
        print("[WARN] Could not read test frame to confirm resolution.")

    # --- Logging ---
    backend_dir = Path(__file__).resolve().parents[1]  # .../backend
    log_dir = backend_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = log_dir / f"ui_click_test_{session_name}.jsonl"
    f = open(log_path, "a", encoding="utf-8")
    print(f"[INFO] Logging to: {log_path}")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    def get_video_target_size():
        vw = ui.video_label.winfo_width()
        vh = ui.video_label.winfo_height()
        if vw <= 1 or vh <= 1:
            return 800, 600
        return vw, vh

    def tick():
        if ui.closing:
            return

        ok, frame = cap.read()
        if not ok or frame is None:
            ui.update_status("Camera read failed.")
            ui.root.after(30, tick)
            return

        ts_ms = int(time.time() * 1000)

        # Mirror before processing so landmarks match what you see
        if MIRROR_X:
            frame = cv2.flip(frame, 1)

        h, w = frame.shape[:2]

        # MediaPipe expects RGB input
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        # Draw overlay on BGR frame
        overlay = frame.copy()

        # Defaults
        state = "UNKNOWN"
        definitive = False
        score = None
        hand_conf = None
        scroll_delta = None
        clicked = False

        # Cursor fallback
        cw, ch = ui.get_canvas_size()
        cx_ui, cy_ui = cw // 2, ch // 2
        cx, cy = w // 2, h // 2

        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []

        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            cx, cy = palm_center_px(pts)
            score = open_closed_score(pts)

            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)

            if hand_conf is None or hand_conf >= HAND_CONF_TH:
                state, definitive = classify_state(score)

            # Map camera -> canvas
            cw, ch = ui.get_canvas_size()
            cx_ui = int((cx / w) * cw * CURSOR_X_GAIN)
            cy_ui = int((cy / h) * ch * CURSOR_Y_GAIN)
            cx_ui = max(0, min(cw - 1, cx_ui))
            cy_ui = max(0, min(ch - 1, cy_ui))

            # Draw bbox / center / landmarks
            x1, y1, x2, y2 = hand_bbox_px(pts)

            if state == "OPEN":
                color = (0, 0, 255)     # red in BGR
                box_th = 7
            elif state == "CLOSED":
                color = (0, 255, 0)     # green
                box_th = 7
            else:
                color = (255, 255, 255) # white
                box_th = 3

            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, box_th)
            cv2.circle(overlay, (int(cx), int(cy)), 9, color, -1)
            mp_draw.draw_landmarks(overlay, hand_landmarks[0], mp_hands.HAND_CONNECTIONS)

            label = f"{state} s={score:.2f}"
            if hand_conf is not None:
                label += f" hc={hand_conf:.2f}"
            if not definitive:
                label += " (hold)"

            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 1.25
            thick = 3
            (tw, th), base = cv2.getTextSize(label, font, scale, thick)
            pad = 10
            by1 = max(0, y1 - th - base - 2 * pad)
            cv2.rectangle(overlay, (x1, by1), (x1 + tw + 2 * pad, by1 + th + base + 2 * pad), color, -1)
            cv2.putText(overlay, label, (x1 + pad, by1 + th + pad),
                        font, scale, (0, 0, 0), thick, cv2.LINE_AA)

        # Update cursor on UI
        ui.set_cursor(cx_ui, cy_ui, state)

        # --- Hover with stickiness to fight jitter ---
        now_ms = int(time.time() * 1000)
        hit = ui.hit_test(cx_ui, cy_ui)
        if hit:
            ui.hover_target = hit
            ui.hover_until_ms = now_ms + HOVER_STICK_MS
        else:
            if now_ms > ui.hover_until_ms:
                ui.hover_target = None

        hovered = ui.hover_target
        hover_name = hovered["name"] if hovered else "none"

        # --- Robust click: stable CLOSED frames + edge trigger using last definitive state ---
        if state == "CLOSED" and definitive:
            ui.closed_count += 1
        else:
            ui.closed_count = 0

        edge_closed = False
        if definitive and state in ("OPEN", "CLOSED"):
            # edge only when last definitive was OPEN and now definitive CLOSED
            if ui.last_def_state == "OPEN" and state == "CLOSED":
                edge_closed = True
            ui.last_def_state = state  # update only on definitive OPEN/CLOSED

        if hovered and edge_closed and ui.closed_count >= CLOSED_STABLE_FRAMES:
            clicked = ui.click_if_allowed(hover_name)

        # --- Scroll: ONLY when CLOSED+definitive over Scroll Zone, based on vertical motion ---
        if state == "CLOSED" and definitive and hovered and hover_name == "Scroll Zone":
            if ui.last_y is not None:
                dy = (cy_ui - ui.last_y) * SCROLL_GAIN
                if abs(dy) >= SCROLL_DY_DEADBAND:
                    ui.scroll_text_widget(dy)
                    scroll_delta = dy
            ui.last_y = cy_ui
        else:
            ui.last_y = None

        # Status + debug
        if clicked:
            ui.update_status(f"CLICK: {hover_name}")
        else:
            ui.update_status(f"State={state} (def={definitive}) hover={hover_name}")

        ui.update_debug(score, state, definitive, hover_name, hand_conf, ui.closed_count, scroll_delta)

        # Log
        payload = {
            "timestamp_ms": ts_ms,
            "cam_index": cam_index,
            "state": state,
            "definitive": definitive,
            "score": None if score is None else round(score, 3),
            "hand_conf": None if hand_conf is None else round(hand_conf, 3),
            "center_px": {"x": int(cx), "y": int(cy)},
            "center_ui": {"x": int(cx_ui), "y": int(cy_ui)},
            "hovered": hover_name,
            "clicked": clicked,
            "closed_count": ui.closed_count,
            "scroll_delta": None if scroll_delta is None else round(scroll_delta, 2),
        }
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")

        # Display video in Tkinter (convert BGR -> RGB exactly once)
        vw, vh = get_video_target_size()
        overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        display = cv2.resize(overlay_rgb, (vw, vh), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(display)
        imgtk = ImageTk.PhotoImage(image=img)
        ui.video_label.imgtk = imgtk
        ui.video_label.configure(image=imgtk)

        ui.root.after(33, tick)  # ~30fps

    ui.root.after(50, tick)
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
