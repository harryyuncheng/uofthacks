from pathlib import Path
from datetime import datetime
import time, json, math
import cv2
import mediapipe as mp
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# ---------------- Configuration (tune these) ----------------
MIRROR_X = True  # Mirror camera feed horizontally (selfie mode)
CAM_INDEX = 0
CAM_WIDTH = 3840
CAM_HEIGHT = 2160
CAM_FPS = 30

# State classification thresholds
CLOSED_TH = 1.25
OPEN_TH = 1.45
MARGIN = 0.12
HAND_CONF_TH = 0.70  # handedness confidence threshold

# Event timing
CLICK_COOLDOWN_MS = 600
SCROLL_GAIN = 2.0  # multiplier for scroll sensitivity

# Cursor mapping
CURSOR_SMOOTHING = 0.7  # exponential smoothing factor (0-1, higher = more smoothing)
CURSOR_X_GAIN = 1.0  # horizontal sensitivity multiplier
CURSOR_Y_GAIN = 1.0  # vertical sensitivity multiplier

CLOSED_STABLE_FRAMES = 4
closed_count = 0


# ---------------- CV / Hand Utils ----------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}


import cv2

def pick_camera_index(prefer_4k=True, max_idx=10):
    """Pick the best camera index. If prefer_4k, choose one that can do >= 3840x2160."""
    candidates = []
    for idx in range(max_idx):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        # try request 4K
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        cap.set(cv2.CAP_PROP_FPS, 30)

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
        # pick first >=4K, otherwise max resolution
        for idx, w, h in candidates:
            if w >= 3840 and h >= 2160:
                return idx, candidates
        # fallback highest pixel count
        best = max(candidates, key=lambda t: t[1]*t[2])
        return best[0], candidates

    return candidates[0][0], candidates

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
        right_frame.config(width=500)
        
        # Interaction canvas (resizable)
        self.canvas = tk.Canvas(right_frame, bg="black", width=480, height=400)
        self.canvas.pack(fill="both", expand=True, pady=(0, 5))
        
        # Scrollable text widget
        scroll_frame = tk.Frame(right_frame)
        scroll_frame.pack(fill="both", expand=True, pady=(0, 5))
        
        self.scroll_text = tk.Text(scroll_frame, wrap=tk.WORD, font=("Consolas", 10), bg="#1a1a1a", fg="#ffffff")
        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=self.scroll_text.yview)
        self.scroll_text.config(yscrollcommand=scrollbar.set)
        
        self.scroll_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Fill scroll area with sample text
        sample_text = "\n".join([f"Line {i}: This is sample text for scrolling. " * 3 for i in range(100)])
        self.scroll_text.insert("1.0", sample_text)
        # Keep enabled for scrolling, but make it read-only via binding
        self.scroll_text.bind("<Key>", lambda e: "break")  # Prevent typing
        
        # Buttons (relative to canvas, will be redrawn on resize)
        self.buttons = [
            {"name": "Button A", "rect": (0.1, 0.1, 0.45, 0.4), "color": "#222"},
            {"name": "Button B", "rect": (0.55, 0.1, 0.9, 0.4), "color": "#222"},
            {"name": "Scroll Zone", "rect": (0.1, 0.5, 0.9, 0.85), "color": "#111"},
        ]
        
        # Debug panel
        debug_frame = tk.Frame(right_frame, bg="#2a2a2a", relief=tk.RAISED, borderwidth=2)
        debug_frame.pack(fill="x", pady=(0, 5))
        
        debug_title = tk.Label(debug_frame, text="Debug Info", font=("Segoe UI", 10, "bold"), bg="#2a2a2a", fg="white")
        debug_title.pack(pady=(5, 2))
        
        self.debug_vars = {
            "score": tk.StringVar(value="Score: --"),
            "state": tk.StringVar(value="State: --"),
            "definitive": tk.StringVar(value="Definitive: --"),
            "hover": tk.StringVar(value="Hover: --"),
            "hand_conf": tk.StringVar(value="Hand Conf: --"),
            "scroll_delta": tk.StringVar(value="Scroll Δ: --"),
        }
        
        for var in self.debug_vars.values():
            label = tk.Label(debug_frame, textvariable=var, font=("Consolas", 9), bg="#2a2a2a", fg="#a0a0a0", anchor="w")
            label.pack(fill="x", padx=5, pady=1)
        
        # Status bar
        self.status_var = tk.StringVar(value="Status: --")
        self.status = tk.Label(right_frame, textvariable=self.status_var, font=("Segoe UI", 12), bg="#333", fg="white", anchor="w", padx=5, pady=3)
        self.status.pack(fill="x")
        
        self.draw_static()
        
        # Cursor dot
        self.cursor = self.canvas.create_oval(0, 0, 0, 0, fill="white", outline="", tags="cursor")
        
        # Event state tracking
        self.last_state = "UNKNOWN"
        self.last_click_ms = 0
        self.last_y = None
        self.scroll_accum = 0
        
        # Cursor smoothing state
        self.smoothed_x = None
        self.smoothed_y = None
        
        # Click feedback shapes (track per button)
        self.click_feedback = {}  # button_name -> canvas_item_id
        
        # Handle window resize
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.closing = False
        
    def on_canvas_resize(self, event=None):
        """Redraw static elements when canvas resizes"""
        self.draw_static()
    
    def get_canvas_size(self):
        """Get actual canvas size, handling initial 1px issue"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            # Fallback to requested size
            w = self.canvas.cget("width")
            h = self.canvas.cget("height")
            if isinstance(w, str) and w.isdigit():
                w = int(w)
            else:
                w = 480
            if isinstance(h, str) and h.isdigit():
                h = int(h)
            else:
                h = 400
        return w, h
    
    def draw_static(self):
        """Draw buttons using relative coordinates"""
        self.canvas.delete("btn")
        w, h = self.get_canvas_size()
        
        for b in self.buttons:
            x1_rel, y1_rel, x2_rel, y2_rel = b["rect"]
            x1 = int(x1_rel * w)
            y1 = int(y1_rel * h)
            x2 = int(x2_rel * w)
            y2 = int(y2_rel * h)
            
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=b["color"], outline="#555", width=3, tags="btn")
            self.canvas.create_text((x1+x2)//2, (y1+y2)//2,
                                    text=b["name"], fill="white",
                                    font=("Segoe UI", 18, "bold"), tags="btn")
    
    def hit_test(self, x, y):
        """Test if point hits any button (using relative coords)"""
        w, h = self.get_canvas_size()
        x_rel = x / w if w > 0 else 0
        y_rel = y / h if h > 0 else 0
        
        for b in self.buttons:
            x1_rel, y1_rel, x2_rel, y2_rel = b["rect"]
            if x1_rel <= x_rel <= x2_rel and y1_rel <= y_rel <= y2_rel:
                return b
        return None
    
    def set_cursor(self, x, y, state):
        """Update cursor position and color, with clamping and smoothing"""
        # Clamp to canvas bounds
        w, h = self.get_canvas_size()
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))
        
        # Apply exponential smoothing
        if self.smoothed_x is None:
            self.smoothed_x = x
            self.smoothed_y = y
        else:
            self.smoothed_x = CURSOR_SMOOTHING * self.smoothed_x + (1 - CURSOR_SMOOTHING) * x
            self.smoothed_y = CURSOR_SMOOTHING * self.smoothed_y + (1 - CURSOR_SMOOTHING) * y
        
        # Clamp smoothed values
        x_smooth = int(max(0, min(w - 1, self.smoothed_x)))
        y_smooth = int(max(0, min(h - 1, self.smoothed_y)))
        
        r = 10
        fill = "white"
        if state == "OPEN":
            fill = "red"
        elif state == "CLOSED":
            fill = "green"
        
        self.canvas.coords(self.cursor, x_smooth-r, y_smooth-r, x_smooth+r, y_smooth+r)
        self.canvas.itemconfig(self.cursor, fill=fill)
        
        # Always raise cursor to top
        self.canvas.tag_raise("cursor")
    
    def update_debug(self, score, state, definitive, hover_name, hand_conf, scroll_delta):
        """Update debug panel"""
        self.debug_vars["score"].set(f"Score: {score:.3f}" if score is not None else "Score: --")
        self.debug_vars["state"].set(f"State: {state}")
        self.debug_vars["definitive"].set(f"Definitive: {definitive}")
        self.debug_vars["hover"].set(f"Hover: {hover_name}")
        self.debug_vars["hand_conf"].set(f"Hand Conf: {hand_conf:.3f}" if hand_conf is not None else "Hand Conf: --")
        self.debug_vars["scroll_delta"].set(f"Scroll Δ: {scroll_delta:.1f}" if scroll_delta is not None else "Scroll Δ: --")
    
    def click_if_allowed(self, target_name):
        """Trigger click with cooldown and visual feedback"""
        now = int(time.time() * 1000)
        if now - self.last_click_ms < CLICK_COOLDOWN_MS:
            return False
        self.last_click_ms = now
        self.status_var.set(f"CLICK: {target_name}")
        
        # Draw click feedback shape on the button
        self.draw_click_feedback(target_name)
        
        return True
    
    def draw_click_feedback(self, button_name):
        """Draw a visual feedback shape on the clicked button"""
        # Remove old feedback for this button
        if button_name in self.click_feedback:
            self.canvas.delete(self.click_feedback[button_name])
        
        # Find button
        button = None
        for b in self.buttons:
            if b["name"] == button_name:
                button = b
                break
        
        if not button:
            return
        
        # Get button center
        w, h = self.get_canvas_size()
        x1_rel, y1_rel, x2_rel, y2_rel = button["rect"]
        cx = int((x1_rel + x2_rel) * w / 2)
        cy = int((y1_rel + y2_rel) * h / 2)
        
        # Draw a star shape (5-pointed)
        import random
        shapes = ["star", "circle", "square"]
        shape_type = random.choice(shapes)
        
        size = 30
        if shape_type == "circle":
            item = self.canvas.create_oval(cx-size, cy-size, cx+size, cy+size, 
                                          fill="yellow", outline="orange", width=3, tags="click_feedback")
        elif shape_type == "square":
            item = self.canvas.create_rectangle(cx-size, cy-size, cx+size, cy+size,
                                                fill="yellow", outline="orange", width=3, tags="click_feedback")
        else:  # star
            # Simple 5-pointed star approximation
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                r = size if i % 2 == 0 else size * 0.4
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                points.extend([px, py])
            item = self.canvas.create_polygon(points, fill="yellow", outline="orange", width=3, tags="click_feedback")
        
        self.click_feedback[button_name] = item
        
        # Remove feedback after 500ms
        def remove_feedback():
            if button_name in self.click_feedback:
                self.canvas.delete(self.click_feedback[button_name])
                del self.click_feedback[button_name]
        
        self.root.after(500, remove_feedback)
    
    def update_status(self, msg):
        self.status_var.set(msg)
    
    def scroll_text_widget(self, delta_y):
        """Scroll the text widget by delta_y pixels"""
        self.scroll_text.yview_scroll(int(-delta_y), "pixels")
    
    def on_closing(self):
        """Handle window close"""
        self.closing = True
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

# ---------------- Main loop (CV -> UI) ----------------
def main():
    ui = HandUITest()
    
    cam_index, cams = pick_camera_index(prefer_4k=True, max_idx=10)
    print("[INFO] Camera candidates:", cams)
    print("[INFO] Using cam_index:", cam_index)

    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAM_FPS)
    
    # Logging
    backend_dir = Path(__file__).resolve().parents[1]
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
    
    # Video display size (will scale to fit)
    video_display_w = 640
    video_display_h = 360
    
    def tick():
        if ui.closing:
            return
        
        ok, frame = cap.read()
        if not ok:
            ui.update_status("Camera read failed.")
            ui.root.after(30, tick)
            return
        
        h, w = frame.shape[:2]
        ts_ms = int(time.time() * 1000)
        
        # Mirror if requested (before processing, so landmarks are in mirrored space)
        if MIRROR_X:
            frame = cv2.flip(frame, 1)
        
        # Convert BGR to RGB for MediaPipe processing
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        
        # Draw on frame (still BGR at this point)
        overlay_frame = frame.copy()
        
        payload = {"timestamp_ms": ts_ms, "hands": []}
        
        # Default state
        state = "UNKNOWN"
        definitive = False
        score = None
        hand_conf = None
        cx_ui, cy_ui = ui.get_canvas_size()
        cx_ui, cy_ui = cx_ui // 2, cy_ui // 2  # center fallback
        cx, cy = w // 2, h // 2
        
        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []
        
        hovered = None
        hover_name = "none"
        scroll_delta = None
        
        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            cx, cy = palm_center_px(pts)
            score = open_closed_score(pts)
            
            # Get confidence
            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)
            
            if hand_conf is None or hand_conf >= HAND_CONF_TH:
                state, definitive = classify_state(score, CLOSED_TH, OPEN_TH, MARGIN)
            
            # Map camera coords -> UI coords
            # If frame was flipped, landmarks are already in flipped space, so no need to mirror cursor
            canvas_w, canvas_h = ui.get_canvas_size()
            cx_ui = int((cx / w) * canvas_w * CURSOR_X_GAIN)
            cy_ui = int((cy / h) * canvas_h * CURSOR_Y_GAIN)
            
            # Clamp to canvas bounds
            cx_ui = max(0, min(canvas_w - 1, cx_ui))
            cy_ui = max(0, min(canvas_h - 1, cy_ui))
            
            # Draw landmarks and info on overlay
            x1, y1, x2, y2 = hand_bbox_px(pts)
            
            if state == "OPEN":
                color = (0, 0, 255)  # RED in BGR
                thickness = 6
            elif state == "CLOSED":
                color = (0, 255, 0)  # GREEN in BGR
                thickness = 6
            else:
                color = (255, 255, 255)  # WHITE
                thickness = 3
            
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, thickness)
            cv2.circle(overlay_frame, (int(cx), int(cy)), 8, color, -1)
            
            # Draw landmarks
            mp_draw.draw_landmarks(overlay_frame, hand_landmarks[0], mp_hands.HAND_CONNECTIONS)
            
            # Label
            label = f"{state} s={score:.2f}"
            if hand_conf is not None:
                label += f" hc={hand_conf:.2f}"
            if not definitive:
                label += " (hold)"
            
            # Draw label box (larger font, same color as state)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 1.2
            thickness = 3
            (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
            pad = 8
            box_y1 = max(0, y1 - th - baseline - 2*pad)
            cv2.rectangle(overlay_frame, (x1, box_y1), (x1 + tw + 2*pad, box_y1 + th + baseline + 2*pad), color, -1)
            cv2.putText(overlay_frame, label, (x1 + pad, box_y1 + th + pad), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)
            
            payload["hands"].append({
                "hand_conf": None if hand_conf is None else round(hand_conf, 3),
                "state": state,
                "definitive": definitive,
                "score": round(score, 3),
                "center_px": {"x": int(cx), "y": int(cy)},
                "center_ui": {"x": cx_ui, "y": cy_ui},
            })
        
        # Update UI cursor
        ui.set_cursor(cx_ui, cy_ui, state)
        
        # Hit testing
        hovered = ui.hit_test(cx_ui, cy_ui)
        hover_name = hovered["name"] if hovered else "none"
        
        # Event handling: edge trigger (OPEN -> CLOSED transition)
        prev_state = ui.last_state
        ui.last_state = state
        
        clicked = False
        if state == "CLOSED" and definitive and prev_state == "OPEN" and hovered:
            clicked = ui.click_if_allowed(hover_name)
        
        # Scroll handling: track vertical movement when CLOSED in scroll zone
        if state == "CLOSED" and definitive and hovered and hovered["name"] == "Scroll Zone":
            if ui.last_y is not None:
                dy = (cy_ui - ui.last_y) * SCROLL_GAIN
                if abs(dy) > 0.5:  # threshold to avoid jitter
                    ui.scroll_text_widget(dy)
                    scroll_delta = dy
                    ui.scroll_accum += dy
            ui.last_y = cy_ui
        else:
            ui.last_y = None
            if state != "CLOSED" or not definitive:
                scroll_delta = None
        
        # Update status
        if clicked:
            ui.update_status(f"CLICK: {hover_name}")
        else:
            ui.update_status(f"State={state} (def={definitive}) hover={hover_name}")
        
        # Update debug panel
        ui.update_debug(score, state, definitive, hover_name, hand_conf, scroll_delta)
        
        # Add to payload
        payload["hovered"] = hover_name
        payload["clicked"] = clicked
        payload["scroll_delta"] = scroll_delta
        
        # Log
        line = json.dumps(payload, separators=(",", ":"))
        f.write(line + "\n")
        
        # Display video frame in Tkinter
        # Convert BGR overlay to RGB for Tkinter display
        overlay_rgb = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2RGB)
        display_frame = cv2.resize(overlay_rgb, (video_display_w, video_display_h))
        img = Image.fromarray(display_frame)
        imgtk = ImageTk.PhotoImage(image=img)
        ui.video_label.imgtk = imgtk  # Keep a reference
        ui.video_label.config(image=imgtk)
        
        # Schedule next frame
        ui.root.after(33, tick)  # ~30fps
    
    # Start loop
    ui.root.after(50, tick)
    ui.run()
    
    # Cleanup on window close
    f.close()
    hands.close()
    cap.release()
    print("[INFO] Cleanup complete.")

if __name__ == "__main__":
    main()
