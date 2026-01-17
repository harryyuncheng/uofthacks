import cv2

def main():
    # Try 0, 1, 2 if needed
    cam_index = 1
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)  # CAP_DSHOW helps on Windows

    if not cap.isOpened():
        raise RuntimeError("Could not open camera. Try cam_index=1 or 2, or remove CAP_DSHOW.")

    # request a resolution (camera may ignore / choose closest)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # Create a resizable window
    cv2.namedWindow("E3117 feed", cv2.WINDOW_NORMAL)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame grab failed")
            break

        h, w = frame.shape[:2]
        cv2.putText(frame, f"{w}x{h}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("E3117 feed", frame)

        # press q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
