"""
Hand gesture streaming service for frontend integration.
Outputs hand position and state data via stdout as JSON.
Refined version matching tune_refined.py logic.
"""
from __future__ import annotations

import sys
import time
import json
import math
import cv2
import mediapipe as mp
from dataclasses import dataclass

# ============================================================
# CONFIG (Matching tune_refined.py)
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
    use_dshow: bool = False           # Windows: DirectShow backend

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
    pinch_close_th: float = 0.60
    pinch_open_th: float = 0.71 

    # Optional gating by handedness confidence (proxy)
    hand_conf_th: float = 0.70

    # Debounce / stability
    state_dwell_ms: int = 110         # ignore flip-flops inside this window

CFG = Config()

# ============================================================
# MediaPipe IDs
# ============================================================
mp_hands = mp.solutions.hands

THUMB_TIP = 4
INDEX_TIP = 8
INDEX_MCP = 5
PINKY_MCP = 17
WRIST = 0

# ============================================================
# Helpers
# ============================================================

def log(msg):
    print(msg, file=sys.stderr, flush=True)

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
    return prev_state if prev_state in ("OPEN", "CLOSED") else "OPEN"

# ============================================================
# Camera
# ============================================================

def pick_camera_index(cfg: Config) -> int:
    candidates = []
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
        log("No cameras found.")
        return 0

    if cfg.prefer_4k:
        for idx, w, h in candidates:
            if w >= cfg.cam_width and h >= cfg.cam_height:
                return idx

    best = max(candidates, key=lambda t: t[1] * t[2])
    return best[0]

def open_capture(index: int, cfg: Config) -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if cfg.use_dshow else 0
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.cam_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.cam_height)
    cap.set(cv2.CAP_PROP_FPS, cfg.cam_fps)
    return cap

# ============================================================
# Main Loop
# ============================================================

def main():
    log("[GESTURE] Starting refined hand tracking...")

    if CFG.cam_index is None:
        cam_index = pick_camera_index(CFG)
    else:
        cam_index = CFG.cam_index
    
    log(f"[GESTURE] Selected camera index: {cam_index}")

    try:
        cap = open_capture(cam_index, CFG)
    except Exception as e:
        log(f"[GESTURE] Error opening camera: {e}")
        sys.exit(1)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=CFG.max_hands,
        model_complexity=CFG.model_complexity,
        min_detection_confidence=CFG.min_det_conf,
        min_tracking_confidence=CFG.min_track_conf,
    )

    log("[GESTURE] MediaPipe initialized, data stream active.")

    state_mem = "OPEN"
    last_state_change_ms = 0
    
    # Cursor smoothing memory
    smoothed_x = None
    smoothed_y = None

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue

        ts_ms = int(time.time() * 1000)
        h, w = frame.shape[:2]

        if CFG.mirror_x:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        payload = {
            "timestamp": ts_ms,
            "screen_size": {"width": w, "height": h},
            "hand": None
        }

        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []

        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            pinch_norm = pinch_norm_score(pts)

            hand_conf = None
            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)

            proposed = classify_pinch_binary(pinch_norm, state_mem, CFG)
            now = ts_ms
            if proposed != state_mem:
                if (now - last_state_change_ms) >= CFG.state_dwell_ms:
                    state_mem = proposed
                    last_state_change_ms = now
            state = state_mem

            cx, cy = palm_center_px(pts)

            # Apply smoothing
            if smoothed_x is None:
                smoothed_x, smoothed_y = float(cx), float(cy)
            else:
                a = CFG.cursor_smoothing
                smoothed_x = a * smoothed_x + (1 - a) * cx
                smoothed_y = a * smoothed_y + (1 - a) * cy
            
            payload["hand"] = {
                "x": int(smoothed_x),
                "y": int(smoothed_y),
                "state": state,
                "definitive": True,
                "confidence": round(hand_conf, 3) if hand_conf else None,
                "score": round(pinch_norm, 3)
            }

        print(json.dumps(payload), flush=True)
        time.sleep(0.016) # ~60 FPS cap

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        log(f"[GESTURE] Exception: {e}")
        sys.exit(1)
