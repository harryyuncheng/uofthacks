from pathlib import Path
from datetime import datetime
import cv2, time, json, math
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
MCP_IDS = {"index_mcp": 5, "middle_mcp": 9, "ring_mcp": 13, "pinky_mcp": 17}

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

def open_closed_state(pts, prev_state, closed_th=1.25, open_th=1.45):
    palm_w = dist(pts[5], pts[17])
    if palm_w < 1e-6:
        return prev_state, 999.0, "UNKNOWN"

    palm = palm_center_px(pts)
    mean_tip = sum(dist(pts[i], palm) for i in TIP_IDS.values()) / len(TIP_IDS)
    score = mean_tip / palm_w  # lower => more closed

    # Raw classification
    if score < closed_th:
        return "CLOSED", score, "CLOSED"
    if score > open_th:
        return "OPEN", score, "OPEN"
    # ambiguous band
    return prev_state, score, "MID"

def draw_label_box(img, x1, y1, text, color_bgr):
    # Draw a filled textbox behind text
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.8
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 6

    # Put box above the bbox if possible, otherwise inside
    box_x1 = x1
    box_y1 = y1 - th - baseline - 2*pad
    if box_y1 < 0:
        box_y1 = y1 + 2  # inside the box

    box_x2 = box_x1 + tw + 2*pad
    box_y2 = box_y1 + th + baseline + 2*pad

    cv2.rectangle(img, (box_x1, box_y1), (box_x2, box_y2), color_bgr, -1)
    cv2.putText(img, text, (box_x1 + pad, box_y2 - pad - baseline),
                font, scale, (0, 0, 0), thickness, cv2.LINE_AA)

def main():
    cam_index = 1
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv2.CAP_PROP_FPS, 30)

    cv2.namedWindow("Hand State", cv2.WINDOW_NORMAL)

    frame_id = 0

    MAX_HANDS = 2
    last_state = ["OPEN"] * MAX_HANDS  # fixed-length so indexing never crashes

    # ---- Confidence / gating knobs ----
    HAND_CONF_TH = 0.70          # handedness score threshold (proxy)
    GESTURE_MARGIN = 0.12        # how far from threshold to be "definitive"
    CLOSED_TH = 1.25
    OPEN_TH = 1.45

    log_to_file = False
    f = open("hand_stream.jsonl", "a") if log_to_file else None

    # --- session log file (one per run) ---
    LOG_DIR = Path("logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = LOG_DIR / f"hand_stream_{session_name}.jsonl"

    log_to_file = True
    f = open(log_path, "a", encoding="utf-8") if log_to_file else None
    print(f"[INFO] Logging to: {log_path}")

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_HANDS,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    ) as hands:

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h, w = frame.shape[:2]
            ts_ms = int(time.time() * 1000)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            payload = {"frame_id": frame_id, "timestamp_ms": ts_ms, "image_wh": [w, h], "hands": []}

            # Pair landmarks with handedness if available
            hand_landmarks = result.multi_hand_landmarks or []
            handedness = result.multi_handedness or []

            for i, hand_lms in enumerate(hand_landmarks):
                # handedness score (proxy for detection confidence)
                hand_conf = None
                if i < len(handedness) and handedness[i].classification:
                    hand_conf = float(handedness[i].classification[0].score)

                # Gate: if low confidence, mark unknown and optionally skip events
                if hand_conf is not None and hand_conf < HAND_CONF_TH:
                    # Still draw landmarks if you want, but do NOT classify
                    pts = landmarks_to_px(hand_lms, w, h)
                    x1, y1, x2, y2 = hand_bbox_px(pts)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 80, 80), 2)
                    draw_label_box(frame, x1, y1, f"LOWCONF {hand_conf:.2f}", (80, 80, 80))
                    continue

                pts = landmarks_to_px(hand_lms, w, h)
                x1, y1, x2, y2 = hand_bbox_px(pts)
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                state_mem, score, raw = open_closed_state(
                    pts, last_state[i],
                    closed_th=CLOSED_TH, open_th=OPEN_TH
                )
                last_state[i] = state_mem

                # Gesture confidence: how far from the ambiguous band
                # definitive if:
                #   CLOSED: score < CLOSED_TH - margin
                #   OPEN:   score > OPEN_TH + margin
                definitive = False
                final_state = "UNKNOWN"
                if score < (CLOSED_TH - GESTURE_MARGIN):
                    definitive = True
                    final_state = "CLOSED"
                elif score > (OPEN_TH + GESTURE_MARGIN):
                    definitive = True
                    final_state = "OPEN"

                tips = {name: {"x": pts[idx][0], "y": pts[idx][1]} for name, idx in TIP_IDS.items()}
                mcps = {name: {"x": pts[idx][0], "y": pts[idx][1]} for name, idx in MCP_IDS.items()}

                payload["hands"].append({
                    "hand_id": i,
                    "hand_conf": None if hand_conf is None else round(hand_conf, 3),
                    "state": final_state,
                    "state_mem": state_mem,        # smoothed memory state
                    "raw_zone": raw,               # OPEN/CLOSED/MID
                    "score": round(score, 3),
                    "definitive": definitive,
                    "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "center": {"x": cx, "y": cy},
                    "tips": tips,
                    "mcps": mcps
                })

                # ---- Drawing ----
                if final_state == "OPEN":
                    color = (0, 0, 255)   # RED in BGR
                    thickness = 4
                elif final_state == "CLOSED":
                    color = (0, 255, 0)   # GREEN
                    thickness = 4
                else:
                    color = (255, 255, 255)  # white for UNKNOWN
                    thickness = 2

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                cv2.circle(frame, (cx, cy), 6, color, -1)

                label = f"{final_state} s={score:.2f}"
                if hand_conf is not None:
                    label += f" hc={hand_conf:.2f}"
                if not definitive:
                    label += " (hold)"

                draw_label_box(frame, x1, y1, label, color)

                mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

            # Relay JSON per frame
            line = json.dumps(payload, separators=(",", ":"))
            print(line)
            if f:
                f.write(line + "\n")

            cv2.imshow("Hand State", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            frame_id += 1

    if f:
        f.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
