"""
WebSocket server that sends hand gesture data to React frontend.
Run this alongside the React app to control widgets with hand gestures.
"""
from pathlib import Path
from datetime import datetime
import time
import json
import math
import asyncio
import cv2
import mediapipe as mp
import websockets
from websockets.server import serve

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

# WebSocket server config
WS_PORT = 3001

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

# ---------------- WebSocket Server ----------------
connected_clients = set()

async def register_client(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected. Total clients: {len(connected_clients)}")

async def unregister_client(websocket):
    connected_clients.discard(websocket)
    print(f"[WS] Client disconnected. Total clients: {len(connected_clients)}")

async def send_gesture_data(payload):
    """Send gesture data to all connected clients"""
    if connected_clients:
        message = json.dumps(payload)
        disconnected = set()
        for client in connected_clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        connected_clients.difference_update(disconnected)

async def websocket_handler(websocket, path):
    await register_client(websocket)
    try:
        # Keep connection alive and wait for messages (if needed)
        async for message in websocket:
            # Echo back or handle client messages if needed
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister_client(websocket)

# ---------------- Main CV Loop ----------------
class GestureState:
    def __init__(self):
        self.last_def_state = "UNKNOWN"
        self.last_click_ms = 0
        self.closed_count = 0
        self.hover_target = None
        self.hover_until_ms = 0
        self.last_y = None
        self.smoothed_x = None
        self.smoothed_y = None

gesture_state = GestureState()

async def cv_loop():
    """Main computer vision loop that processes camera frames"""
    # --- Choose camera ---
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
    log_path = log_dir / f"gesture_server_{session_name}.jsonl"
    f = open(log_path, "a", encoding="utf-8")
    print(f"[INFO] Logging to: {log_path}")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            await asyncio.sleep(0.033)  # ~30fps
            continue

        ts_ms = int(time.time() * 1000)

        # Mirror before processing so landmarks match what you see
        if MIRROR_X:
            frame = cv2.flip(frame, 1)

        h, w = frame.shape[:2]

        # MediaPipe expects RGB input
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        # Defaults
        state = "UNKNOWN"
        definitive = False
        score = None
        hand_conf = None
        scroll_delta = None
        clicked = False

        # Cursor fallback (center of screen)
        cx_ui, cy_ui = 0.5, 0.5  # normalized 0-1
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

            # Map camera -> normalized screen coordinates (0-1)
            cx_ui = clamp01((cx / w) * CURSOR_X_GAIN)
            cy_ui = clamp01((cy / h) * CURSOR_Y_GAIN)

        # Cursor smoothing
        if gesture_state.smoothed_x is None:
            gesture_state.smoothed_x, gesture_state.smoothed_y = cx_ui, cy_ui
        else:
            gesture_state.smoothed_x = CURSOR_SMOOTHING * gesture_state.smoothed_x + (1 - CURSOR_SMOOTHING) * cx_ui
            gesture_state.smoothed_y = CURSOR_SMOOTHING * gesture_state.smoothed_y + (1 - CURSOR_SMOOTHING) * cy_ui

        cx_ui = gesture_state.smoothed_x
        cy_ui = gesture_state.smoothed_y

        # --- Robust click: stable CLOSED frames + edge trigger ---
        if state == "CLOSED" and definitive:
            gesture_state.closed_count += 1
        else:
            gesture_state.closed_count = 0

        edge_closed = False
        if definitive and state in ("OPEN", "CLOSED"):
            # edge only when last definitive was OPEN and now definitive CLOSED
            if gesture_state.last_def_state == "OPEN" and state == "CLOSED":
                edge_closed = True
            gesture_state.last_def_state = state

        # Click detection
        now_ms = int(time.time() * 1000)
        if edge_closed and gesture_state.closed_count >= CLOSED_STABLE_FRAMES:
            if now_ms - gesture_state.last_click_ms >= CLICK_COOLDOWN_MS:
                clicked = True
                gesture_state.last_click_ms = now_ms

        # --- Scroll: based on vertical motion when CLOSED ---
        if state == "CLOSED" and definitive:
            if gesture_state.last_y is not None:
                dy = (cy_ui - gesture_state.last_y) * SCROLL_GAIN * 100  # scale for UI
                if abs(dy) >= SCROLL_DY_DEADBAND:
                    scroll_delta = dy
            gesture_state.last_y = cy_ui
        else:
            gesture_state.last_y = None

        # Prepare payload for frontend
        payload = {
            "timestamp_ms": ts_ms,
            "state": state,
            "definitive": definitive,
            "score": None if score is None else round(score, 3),
            "hand_conf": None if hand_conf is None else round(hand_conf, 3),
            "cursor": {
                "x": round(cx_ui, 4),  # normalized 0-1
                "y": round(cy_ui, 4)
            },
            "clicked": clicked,
            "closed_count": gesture_state.closed_count,
            "scroll_delta": None if scroll_delta is None else round(scroll_delta, 2),
        }

        # Send to frontend via WebSocket
        await send_gesture_data(payload)

        # Log to file
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
        f.flush()

        await asyncio.sleep(0.033)  # ~30fps

    # Cleanup (shouldn't reach here, but just in case)
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

# ---------------- Main Entry Point ----------------
async def main():
    """Start WebSocket server and CV loop"""
    print(f"[INFO] Starting gesture server on port {WS_PORT}")
    print("[INFO] Make sure your React app is running and can connect to ws://localhost:3001")
    
    # Start WebSocket server
    async with serve(websocket_handler, "localhost", WS_PORT):
        print(f"[INFO] WebSocket server running on ws://localhost:{WS_PORT}")
        
        # Start CV loop as background task
        await cv_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Shutdown complete.")
