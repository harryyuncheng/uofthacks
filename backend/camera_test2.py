import cv2
import math
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

TIP_IDS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky tips
MCP_IDS = [5, 9, 13, 17]       # index/middle/ring/pinky MCPs (for palm center)
## MCPs are metacarpophalangeal joints, for tracking

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def hand_bbox_px(landmarks_px):
    xs = [p[0] for p in landmarks_px]
    ys = [p[1] for p in landmarks_px]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return x1, y1, x2, y2

def palm_center_px(landmarks_px):
    # wrist + MCPs averaged
    ids = [0] + MCP_IDS
    x = sum(landmarks_px[i][0] for i in ids) / len(ids)
    y = sum(landmarks_px[i][1] for i in ids) / len(ids)
    return (x, y)

# return isOpen or isClosed state
def compute_open_closed(landmarks_px):

    palm = palm_center_px(landmarks_px)

    # Scale reference: palm width between index_mcp (5) and pinky_mcp (17)
    palm_width = dist(landmarks_px[5], landmarks_px[17])
    if palm_width < 1e-6:
        return "UNKNOWN", 999.0

    mean_tip_to_palm = sum(dist(landmarks_px[i], palm) for i in TIP_IDS) / len(TIP_IDS)
    score = mean_tip_to_palm / palm_width  # normalized

    # Raw thresholds (you will tune)
    if score < 1.25:
        return "CLOSED", score
    elif score > 1.45:
        return "OPEN", score
    else:
        return "MID", score

def main():
    cam_index = 1
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv2.CAP_PROP_FPS, 30)

    cv2.namedWindow("Hand State", cv2.WINDOW_NORMAL)

    # Hysteresis memory per hand (0 and 1)
    last_state = ["OPEN", "OPEN"]

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,              # 0 faster, 1 balanced
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    ) as hands:

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # MediaPipe expects RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            h, w = frame.shape[:2]
            cv2.putText(frame, f"{w}x{h}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            if result.multi_hand_landmarks:
                for idx, hand_lms in enumerate(result.multi_hand_landmarks):
                    # Convert landmarks to pixel coords
                    lm_px = []
                    for lm in hand_lms.landmark:
                        x = int(clamp(lm.x, 0.0, 1.0) * (w - 1))
                        y = int(clamp(lm.y, 0.0, 1.0) * (h - 1))
                        lm_px.append((x, y))

                    # Bounding box
                    x1, y1, x2, y2 = hand_bbox_px(lm_px)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)

                    # Center (bbox center)
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)

                    # Open/closed score
                    raw, score = compute_open_closed(lm_px)

                    # Apply hysteresis memory so MID doesn’t flicker
                    if raw == "OPEN":
                        last_state[idx] = "OPEN"
                    elif raw == "CLOSED":
                        last_state[idx] = "CLOSED"
                    # else keep last_state

                    label = f"Hand {idx}: {last_state[idx]}  score={score:.2f}"
                    cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

                    # Draw landmarks + connections (optional but helpful)
                    mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

            cv2.imshow("Hand State", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
