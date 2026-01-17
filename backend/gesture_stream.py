"""
Hand gesture streaming service for frontend integration.
Outputs hand position and state data via stdout as JSON.
"""
import sys
import time
import json
import math
import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands

TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}

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
    return mean_tip / palm_w

def classify_state(score, closed_th=1.25, open_th=1.45, margin=0.12):
    if score < (closed_th - margin):
        return "CLOSED", True
    if score > (open_th + margin):
        return "OPEN", True
    return "UNKNOWN", False

def main():
    # Configuration
    HAND_CONF_TH = 0.70
    MIRROR_X = True  # Mirror for natural interaction
    
    # Stderr for logging (stdout reserved for data stream)
    def log(msg):
        print(msg, file=sys.stderr, flush=True)
    
    log("[GESTURE] Starting hand tracking...")
    
    # Try to find an available camera (try indices 0, 1, 2)
    cap = None
    for cam_idx in [0, 1, 2]:
        log(f"[GESTURE] Trying camera index {cam_idx}...")
        test_cap = cv2.VideoCapture(cam_idx)
        if test_cap.isOpened():
            # Test if we can actually read a frame
            ret, _ = test_cap.read()
            if ret:
                log(f"[GESTURE] Successfully opened camera {cam_idx}")
                cap = test_cap
                break
            else:
                test_cap.release()
        else:
            test_cap.release()
    
    if cap is None:
        log("[GESTURE] ERROR: Could not open any camera (tried indices 0, 1, 2)")
        sys.exit(1)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    log("[GESTURE] Camera initialized")
    
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )
    
    log("[GESTURE] MediaPipe initialized, streaming data...")
    
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        
        h, w = frame.shape[:2]
        
        if MIRROR_X:
            frame = cv2.flip(frame, 1)
        
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        
        payload = {
            "timestamp": int(time.time() * 1000),
            "screen_size": {"width": w, "height": h},
            "hand": None
        }
        
        hand_landmarks = result.multi_hand_landmarks or []
        handedness = result.multi_handedness or []
        
        if hand_landmarks:
            pts = landmarks_to_px(hand_landmarks[0], w, h)
            cx, cy = palm_center_px(pts)
            score = open_closed_score(pts)
            
            # Get confidence
            hand_conf = None
            if handedness and handedness[0].classification:
                hand_conf = float(handedness[0].classification[0].score)
            
            state = "UNKNOWN"
            definitive = False
            
            if hand_conf is None or hand_conf >= HAND_CONF_TH:
                state, definitive = classify_state(score)
            
            payload["hand"] = {
                "x": int(cx),
                "y": int(cy),
                "state": state,
                "definitive": definitive,
                "confidence": round(hand_conf, 3) if hand_conf else None,
                "score": round(score, 3)
            }
        
        # Output JSON to stdout (one line per frame)
        print(json.dumps(payload), flush=True)
        
        # Small delay to prevent overwhelming the stream
        time.sleep(0.016)  # ~60fps

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[GESTURE] Shutting down gracefully", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"[GESTURE] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
