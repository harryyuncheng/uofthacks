import mediapipe as mp
print("mediapipe file:", mp.__file__)
print("mediapipe version:", getattr(mp, "__version__", "no __version__"))
print("has solutions:", hasattr(mp, "solutions"))
