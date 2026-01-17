from pathlib import Path
from datetime import datetime
import time, json, math
import cv2
import mediapipe as mp
import tkinter as tk

# ---------------- CV / Hand Utils ----------------
mp_hands = mp.solutions.hands
TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def clamp01(v): return max(0.0, min(1.0, v))

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

def classify_state(score, closed_th=1.25, open_th=1.45, margin=0.12):
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

        self.canvas_w = 900
        self.canvas_h = 600
        self.canvas = tk.Canvas(self.root, width=self.canvas_w, height=self.canvas_h, bg="black")
        self.canvas.pack(fill="both", expand=True)

        # Three big clickable regions (rectangles)
        self.buttons = [
            {"name": "Button A", "rect": (80, 80, 380, 260), "color": "#222"},
            {"name": "Button B", "rect": (520, 80, 820, 260), "color": "#222"},
            {"name": "Scroll Zone", "rect": (80, 340, 820, 540), "color": "#111"},
        ]

        self.status_var = tk.StringVar(value="Status: --")
        self.status = tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 14))
        self.status.pack(fill="x")

        self.draw_static()

        # Cursor dot
        self.cursor = self.canvas.create_oval(0, 0, 0, 0, fill="white", outline="")

        # Debounce / click gating
        self.last_click_ms = 0
        self.click_cooldown_ms = 600

        # For scroll test (optional): track last y while open
        self.last_y = None
        self.scroll_accum = 0

    def draw_static(self):
        self.canvas.delete("btn")
        for b in self.buttons:
            x1, y1, x2, y2 = b["rect"]
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=b["color"], outline="#555", width=3, tags="btn")
            self.canvas.create_text((x1+x2)//2, (y1+y2)//2,
                                    text=b["name"], fill="white",
                                    font=("Segoe UI", 24, "bold"), tags="btn")

    def hit_test(self, x, y):
        for b in self.buttons:
            x1, y1, x2, y2 = b["rect"]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return b
        return None

    def set_cursor(self, x, y, state):
        r = 10
        # color cursor by state
        fill = "white"
        if state == "OPEN":
            fill = "red"
        elif state == "CLOSED":
            fill = "green"

        self.canvas.coords(self.cursor, x-r, y-r, x+r, y+r)
        self.canvas.itemconfig(self.cursor, fill=fill)

    def click_if_allowed(self, target_name):
        now = int(time.time() * 1000)
        if now - self.last_click_ms < self.click_cooldown_ms:
            return False
        self.last_click_ms = now
        self.status_var.set(f"CLICK: {target_name}")
        return True

    def update_status(self, msg):
        self.status_var.set(msg)

    def run(self):
        self.root.mainloop()

# ---------------- Main loop (CV -> UI) ----------------
def main():
    ui = HandUITest()

    cam_index = 1
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # Optional logging (same approach as your close.py)
    backend_dir = Path(__file__).resolve().parents[1]  # .../backend (since file is in backend/CV-hand-events/)
    log_dir = backend_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = log_dir / f"ui_click_test_{session_name}.jsonl"
    f = open(log_path, "a", encoding="utf-8")
    print(f"[INFO] Logging to: {log_path}")

    CLOSED_TH = 1.25
    OPEN_TH = 1.45
    MARGIN = 0.12
    HAND_CONF_TH = 0.70  # proxy

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,              # start with 1 hand for UI test
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    def tick():
        ok, frame = cap.read()
        if not ok:
            ui.update_status("Camera read failed.")
            ui.root.after(30, tick)
            return

        h, w = frame.shape[:2]
        ts_ms = int(time.time() * 1000)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        payload = {"timestamp_ms": ts_ms, "hands": []}

        # Default state if nothing detected
        state = "UNKNOWN"
        definitive = False
        cx_ui, cy_ui = ui.canvas_w // 2, ui.canvas_h // 2  # center fallback

        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []

        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            cx, cy = palm_center_px(pts)  # use palm center
            score = open_closed_score(pts)

            # proxy confidence
            hand_conf = None
            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)

            if hand_conf is None or hand_conf >= HAND_CONF_TH:
                state, definitive = classify_state(score, CLOSED_TH, OPEN_TH, MARGIN)

            # Map camera coords -> UI coords (simple linear mapping)
            cx_ui = int((cx / w) * ui.canvas_w)
            cy_ui = int((cy / h) * ui.canvas_h)

            payload["hands"].append({
                "hand_conf": None if hand_conf is None else round(hand_conf, 3),
                "state": state,
                "definitive": definitive,
                "score": round(score, 3),
                "center_px": {"x": int(cx), "y": int(cy)},
                "center_ui": {"x": cx_ui, "y": cy_ui},
            })

        # UI cursor + interactions
        ui.set_cursor(cx_ui, cy_ui, state)

        hovered = ui.hit_test(cx_ui, cy_ui)
        hover_name = hovered["name"] if hovered else "none"

        if state == "CLOSED" and definitive and hovered:
            ui.click_if_allowed(hover_name)
        else:
            ui.update_status(f"State={state} (def={definitive}) hover={hover_name}")

        # Log
        line = json.dumps(payload, separators=(",", ":"))
        f.write(line + "\n")

        # Schedule next frame
        ui.root.after(15, tick)  # ~60fps UI tick (actual depends on camera)

    # Start loop
    ui.root.after(50, tick)
    ui.run()

    # Cleanup on window close
    f.close()
    hands.close()
    cap.release()

if __name__ == "__main__":
    main()
