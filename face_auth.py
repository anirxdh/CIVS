import threading
import time
import os
import cv2
import numpy as np

STATE_IDLE = "idle"
STATE_DETECTING = "detecting"
STATE_MATCHED = "matched"
STATE_FAILED = "failed"

# OpenCV face detector (Haar cascade, ships with OpenCV)
_FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(_FACE_CASCADE_PATH)


class FaceAuthSession:

    def __init__(self, camera, max_attempts=30):
        self.camera = camera
        self.max_attempts = max_attempts
        self.state = STATE_IDLE
        self.matched_voter = None
        self.message = "Initializing camera for identity verification..."
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        with self._lock:
            self.state = STATE_DETECTING
            self.message = "Please look directly at the camera."
        self._thread = threading.Thread(target=self._auth_loop, daemon=True)
        self._thread.start()

    def get_status(self):
        with self._lock:
            return {
                "state": self.state,
                "message": self.message,
                "voter_name": self.matched_voter["name"] if self.matched_voter else None,
                "voter_id": self.matched_voter["voter_id"] if self.matched_voter else None,
            }

    def _draw_face_boxes(self, frame, label=None):
        """Detect faces and draw bounding boxes on the frame. Returns the annotated frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )

        color = (0, 255, 0) if label else (255, 200, 0)  # green if matched, cyan-ish otherwise
        display_label = label if label else "Verifying..."

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            # Label background
            text_size = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(
                frame,
                (x, y - text_size[1] - 10),
                (x + text_size[0] + 4, y),
                color,
                -1,
            )
            cv2.putText(
                frame, display_label,
                (x + 2, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 0, 0), 2,
            )

        return frame

    def _auth_loop(self):
        from deepface import DeepFace
        from db import get_all_unvoted_voters

        time.sleep(1)

        attempts = 0
        matched_name = None

        while attempts < self.max_attempts:
            with self._lock:
                if self.state != STATE_DETECTING:
                    break

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.2)
                continue

            # Draw face bounding boxes on every frame and push to display
            display = frame.copy()
            display = self._draw_face_boxes(display, label=matched_name)
            self.camera.set_display_frame(display)

            # Save frame for DeepFace verification
            temp_path = "/tmp/hgvs_auth_frame.jpg"
            cv2.imwrite(temp_path, frame)

            voters = get_all_unvoted_voters()
            if not voters:
                with self._lock:
                    self.state = STATE_FAILED
                    self.message = "No registered voters found. Please contact the administrator."
                break

            for voter in voters:
                try:
                    result = DeepFace.verify(
                        img1_path=temp_path,
                        img2_path=voter["photo_path"],
                        model_name="ArcFace",
                        detector_backend="opencv",
                        enforce_detection=False,
                    )
                    if result["verified"]:
                        matched_name = voter["name"]
                        # Draw one more frame with the matched name
                        display = frame.copy()
                        display = self._draw_face_boxes(display, label=matched_name)
                        self.camera.set_display_frame(display)

                        with self._lock:
                            self.state = STATE_MATCHED
                            self.matched_voter = voter
                            self.message = f"Identity verified. Welcome, {voter['name']}."
                        # Keep the display frame showing for a moment
                        time.sleep(1)
                        self.camera.clear_display_frame()
                        return
                except Exception:
                    continue

            attempts += 1
            with self._lock:
                self.message = f"Verifying identity... Please look at the camera. (Attempt {attempts}/{self.max_attempts})"

            time.sleep(0.8)

        self.camera.clear_display_frame()
        with self._lock:
            if self.state == STATE_DETECTING:
                self.state = STATE_FAILED
                self.message = "Identity verification failed. Please contact the polling officer."
