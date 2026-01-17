import cv2, time, json, math
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

## MCPs are metacarpophalangeal joints, for tracking
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

def open_closed_state(pts, prev_state):
    # palm width (index_mcp ↔ pinky_mcp)
    palm_w = dist(pts[5], pts[17])
    if palm_w < 1e-6:
        return prev_state, 999.0

    palm = palm_center_px(pts)

    # palm to finger normalized 
    mean_tip = sum(dist(pts[i], palm) for i in TIP_IDS.values()) / len(TIP_IDS)
    score = mean_tip / palm_w  # lower => more closed

    # tunable hysteresis thresholds
    CLOSED_TH = 1.25
    OPEN_TH = 1.45

    if score < CLOSED_TH:
        return "CLOSED", score # isClosed state
    if score > OPEN_TH:
        return "OPEN", score #isOpen state
    return prev_state, score  

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
    last_state = ["OPEN", "OPEN"]  # per-hand memory

    # log to file
    log_to_file = False
    f = open("hand_stream.jsonl", "a") if log_to_file else None

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
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

            if result.multi_hand_landmarks:
                for i, hand_lms in enumerate(result.multi_hand_landmarks):
                    pts = landmarks_to_px(hand_lms, w, h)

                    x1, y1, x2, y2 = hand_bbox_px(pts)
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    state, score = open_closed_state(pts, last_state[i])
                    last_state[i] = state

                    tips = {name: {"x": pts[idx][0], "y": pts[idx][1]} for name, idx in TIP_IDS.items()}
                    mcps = {name: {"x": pts[idx][0], "y": pts[idx][1]} for name, idx in MCP_IDS.items()}

                    payload["hands"].append({
                        "hand_id": i,
                        "state": state,
                        "score": round(score, 3),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "center": {"x": cx, "y": cy},
                        "tips": tips,
                        "mcps": mcps
                    })

                    # draw visuals
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
                    cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)
                    cv2.putText(frame, f"{state} score={score:.2f}", (x1, max(25, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

            # info relay
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
