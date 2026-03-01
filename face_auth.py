import threading
import time
import os
import cv2
import numpy as np

STATE_IDLE = "idle"
STATE_DETECTING = "detecting"
STATE_FACE_FOUND = "face_found"
STATE_VERIFYING = "verifying"
STATE_VERIFIED = "verified"
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
        self.message = "Initializing camera..."
        self._lock = threading.Lock()
        self._thread = None
        self._draw_thread = None
        self._draw_label = "Scanning..."
        self._draw_color = None  # None = yellow/scanning, string = green/labeled
        self._drawing_active = False

    def start(self):
        with self._lock:
            self.state = STATE_DETECTING
            self.message = "Scanning for face..."
            self._drawing_active = True
        self._draw_thread = threading.Thread(target=self._draw_loop, daemon=True)
        self._draw_thread.start()
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

    def _detect_faces(self, frame):
        """Detect faces and return list of (x, y, w, h) rectangles."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )
        return faces

    def _draw_face_boxes(self, frame, label=None, faces=None):
        """Draw bounding boxes on the frame. Returns the annotated frame."""
        if faces is None:
            faces = self._detect_faces(frame)

        color = (0, 255, 0) if label else (255, 200, 0)
        display_label = label if label else "Scanning..."

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            text_size = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(
                frame,
                (x, y - text_size[1] - 10),
                (x + text_size[0] + 4, y),
                color, -1,
            )
            cv2.putText(
                frame, display_label,
                (x + 2, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 0, 0), 2,
            )

        return frame, faces

    def _draw_loop(self):
        """Continuously reads camera frames, detects faces, draws boxes at ~30fps.
        Runs independently from the verification thread so the feed stays smooth."""
        while True:
            with self._lock:
                if not self._drawing_active:
                    return
                label = self._draw_label

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.033)
                continue

            display = frame.copy()
            display, _ = self._draw_face_boxes(display, label=label)
            self.camera.set_display_frame(display)
            time.sleep(0.033)  # ~30fps

    def stop(self):
        """Forcefully stop all threads (drawing + auth). Call before transitioning away."""
        with self._lock:
            self._drawing_active = False
            # Force auth loop to exit on next state check
            if self.state not in (STATE_MATCHED, STATE_FAILED):
                self.state = STATE_FAILED
        self.camera.clear_display_frame()

    def _stop_drawing(self):
        with self._lock:
            self._drawing_active = False
        self.camera.clear_display_frame()

    def _auth_loop(self):
        from deepface import DeepFace
        from db import get_all_unvoted_voters

        time.sleep(0.5)

        # --- STEP 1: Detect a face ---
        # The draw loop is already running and showing "Scanning..." boxes.
        # We just need to wait until a face is detected.
        face_found = False
        detect_start = time.time()

        while not face_found and (time.time() - detect_start) < 30:
            with self._lock:
                if self.state not in (STATE_DETECTING,):
                    self._stop_drawing()
                    return

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            faces = self._detect_faces(frame)

            if len(faces) > 0:
                face_found = True
                with self._lock:
                    self.state = STATE_FACE_FOUND
                    self.message = "Face detected. Hold still..."
                    self._draw_label = "Face Detected"

                # Let the draw loop show "Face Detected" for 1.5 seconds
                time.sleep(1.5)
            else:
                with self._lock:
                    self.message = "Scanning for face... Please look at the camera."
                time.sleep(0.1)

        if not face_found:
            with self._lock:
                self.state = STATE_FAILED
                self.message = "No face detected. Please try again."
            self._stop_drawing()
            return

        # --- STEP 2: Verify against database ---
        with self._lock:
            self.state = STATE_VERIFYING
            self.message = "Checking voter database..."
            self._draw_label = "Verifying..."

        # The draw loop keeps running at ~30fps with "Verifying..." label
        # while we do the slow DeepFace checks here.

        attempts = 0
        while attempts < self.max_attempts:
            with self._lock:
                if self.state != STATE_VERIFYING:
                    break

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.2)
                continue

            temp_path = "/tmp/hgvs_auth_frame.jpg"
            cv2.imwrite(temp_path, frame)

            voters = get_all_unvoted_voters()
            if not voters:
                with self._lock:
                    self.state = STATE_FAILED
                    self.message = "No registered voters found. Please contact the administrator."
                self._stop_drawing()
                return

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

                        with self._lock:
                            self.matched_voter = voter
                            self.state = STATE_VERIFIED
                            self.message = f"Identity verified: {matched_name}"
                            self._draw_label = matched_name

                        # Draw loop shows name label at 30fps for 3 seconds
                        time.sleep(3.0)

                        # Now set matched so frontend redirects
                        with self._lock:
                            self.state = STATE_MATCHED
                            self.message = f"Welcome, {matched_name}. Redirecting to voting..."
                        self._stop_drawing()
                        return
                except Exception:
                    continue

            attempts += 1
            with self._lock:
                self.message = f"Checking voter database... (Attempt {attempts}/{self.max_attempts})"
            time.sleep(0.3)

        self._stop_drawing()
        with self._lock:
            if self.state == STATE_VERIFYING:
                self.state = STATE_FAILED
                self.message = "Identity verification failed. Please contact the polling officer."
