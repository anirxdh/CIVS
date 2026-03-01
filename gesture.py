import threading
import time
import os
import cv2
import numpy as np
import mediapipe as mp

# States
CALIBRATING = "calibrating"
DETECTING = "detecting"
HOLDING = "holding"
CONFIRMING = "confirming"
DONE = "done"
CANCELLED = "cancelled"

PARTIES = {
    '1': 'BJP',
    '2': 'ADMK',
    '3': 'DMK',
    '4': 'Congress',
    '5': 'TDP',
}

HOLD_SECONDS = 3

# Path to MediaPipe model files
_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
GESTURE_MODEL_PATH = os.path.join(_MODELS_DIR, "gesture_recognizer.task")
HAND_LANDMARKER_PATH = os.path.join(_MODELS_DIR, "hand_landmarker.task")


def create_gesture_recognizer():
    """Create a MediaPipe GestureRecognizer for thumbs up/down detection."""
    BaseOptions = mp.tasks.BaseOptions
    GestureRecognizer = mp.tasks.vision.GestureRecognizer
    GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=GESTURE_MODEL_PATH),
        running_mode=RunningMode.IMAGE,
        num_hands=1,
    )
    return GestureRecognizer.create_from_options(options)


def create_hand_landmarker():
    """Create a MediaPipe HandLandmarker for finger counting."""
    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=HAND_LANDMARKER_PATH),
        running_mode=RunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return HandLandmarker.create_from_options(options)


def count_fingers(hand_landmarks, handedness_label):
    """Count extended fingers from MediaPipe hand landmarks.

    Uses fingertip vs PIP joint y-coordinates for index through pinky,
    and a special x-coordinate check for the thumb.

    Returns the number of extended fingers (0-5).
    """
    landmarks = hand_landmarks

    # Landmark indices
    # Thumb: tip=4, ip=3, mcp=2
    # Index: tip=8, pip=6
    # Middle: tip=12, pip=10
    # Ring: tip=16, pip=14
    # Pinky: tip=20, pip=18

    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]

    count = 0

    # Thumb: compare x coordinate (depends on handedness)
    # In a mirrored/flipped image, left/right swap
    # Thumb is extended if tip is further from palm than IP joint
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_mcp = landmarks[2]

    # Use handedness to determine direction
    if handedness_label == "Right":
        # Right hand (in flipped image appears as left): thumb tip x < thumb ip x
        if thumb_tip.x < thumb_ip.x:
            count += 1
    else:
        # Left hand: thumb tip x > thumb ip x
        if thumb_tip.x > thumb_ip.x:
            count += 1

    # Index, middle, ring, pinky: tip y < pip y means extended
    for tip_idx, pip_idx in zip(finger_tips, finger_pips):
        if landmarks[tip_idx].y < landmarks[pip_idx].y:
            count += 1

    return count


def get_hand_bbox(hand_landmarks, frame_w, frame_h, padding=20):
    """Get bounding box around hand landmarks in pixel coordinates."""
    x_coords = [lm.x * frame_w for lm in hand_landmarks]
    y_coords = [lm.y * frame_h for lm in hand_landmarks]

    x_min = max(0, int(min(x_coords)) - padding)
    y_min = max(0, int(min(y_coords)) - padding)
    x_max = min(frame_w, int(max(x_coords)) + padding)
    y_max = min(frame_h, int(max(y_coords)) + padding)

    return x_min, y_min, x_max, y_max


class GestureSession:

    def __init__(self, camera, model, gesture_recognizer=None, hand_landmarker=None):
        self.camera = camera
        self.model = model  # CNN model (kept as fallback, not used in primary detection)
        self.gesture_recognizer = gesture_recognizer
        self.hand_landmarker = hand_landmarker

        self.state = DETECTING
        self.current_gesture = None
        self.selected_party = None
        self.hold_start_time = None
        self.hold_progress = 0.0
        self.message = "Show your hand gesture to vote."
        self.num_frames = 0

        # Confirmation hold state (thumbs up/down 3-second hold)
        self.confirm_gesture = None      # "thumbs_up" or "thumbs_down"
        self.confirm_hold_start = None
        self.confirm_hold_progress = 0.0

        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()

    def get_status(self):
        with self._lock:
            return {
                "state": self.state,
                "message": self.message,
                "current_gesture": self.current_gesture,
                "selected_party": self.selected_party,
                "hold_progress": round(self.hold_progress, 1),
                "confirm_hold_progress": round(self.confirm_hold_progress, 1),
                "calibration_progress": 100,  # No calibration needed anymore
            }

    def _detect_thumbs(self, frame):
        """Use MediaPipe GestureRecognizer to detect Thumb_Up or Thumb_Down."""
        if self.gesture_recognizer is None:
            return None
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self.gesture_recognizer.recognize(mp_image)

            if result.gestures and len(result.gestures) > 0:
                gesture = result.gestures[0][0]
                category = gesture.category_name
                score = gesture.score

                if score > 0.6:
                    if category == "Thumb_Up":
                        return "thumbs_up"
                    elif category == "Thumb_Down":
                        return "thumbs_down"
        except Exception:
            pass
        return None

    def _detect_fingers(self, frame):
        """Use MediaPipe HandLandmarker to count fingers and get hand bbox.

        Returns (finger_count, hand_bbox, landmarks) or (None, None, None).
        """
        if self.hand_landmarker is None:
            return None, None, None
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self.hand_landmarker.detect(mp_image)

            if result.hand_landmarks and len(result.hand_landmarks) > 0:
                landmarks = result.hand_landmarks[0]
                handedness = result.handedness[0][0].category_name

                finger_count = count_fingers(landmarks, handedness)
                h, w = frame.shape[:2]
                bbox = get_hand_bbox(landmarks, w, h)

                return finger_count, bbox, landmarks
        except Exception:
            pass
        return None, None, None

    def _draw_hand_overlay(self, frame, finger_count, bbox, landmarks, party_name=None):
        """Draw hand bounding box and finger count on the frame."""
        if bbox is None:
            return frame

        x_min, y_min, x_max, y_max = bbox
        h, w = frame.shape[:2]

        # Draw bounding box
        color = (0, 255, 0) if party_name else (255, 200, 0)
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)

        # Draw landmark dots
        if landmarks:
            for lm in landmarks:
                px = int(lm.x * w)
                py = int(lm.y * h)
                cv2.circle(frame, (px, py), 3, (0, 255, 255), -1)

        # Label
        if party_name:
            label = f"{finger_count} finger{'s' if finger_count != 1 else ''} - {party_name}"
        else:
            label = f"{finger_count} finger{'s' if finger_count != 1 else ''}"

        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        cv2.rectangle(
            frame,
            (x_min, y_min - text_size[1] - 10),
            (x_min + text_size[0] + 4, y_min),
            color, -1,
        )
        cv2.putText(
            frame, label,
            (x_min + 2, y_min - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (0, 0, 0), 2,
        )

        # Hold progress bar on frame
        with self._lock:
            hp = self.hold_progress
        if hp > 0:
            bar_width = int(200 * (hp / HOLD_SECONDS))
            cv2.rectangle(frame, (10, 440), (10 + bar_width, 460), (0, 255, 0), -1)
            cv2.rectangle(frame, (10, 440), (210, 460), (255, 255, 255), 2)
            cv2.putText(
                frame,
                f"Hold: {hp:.1f}s / {HOLD_SECONDS}s",
                (10, 435),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1,
            )

        return frame

    def _detection_loop(self):
        while True:
            with self._lock:
                if self.state in (DONE, CANCELLED):
                    self.camera.clear_display_frame()
                    return

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.033)
                continue

            # --- CONFIRMATION PHASE (thumbs up/down via MediaPipe) ---
            with self._lock:
                current_state = self.state

            if current_state == CONFIRMING:
                thumb_gesture = self._detect_thumbs(frame)
                now = time.time()

                # Update confirmation hold logic
                with self._lock:
                    if thumb_gesture in ("thumbs_up", "thumbs_down"):
                        if thumb_gesture == self.confirm_gesture and self.confirm_hold_start:
                            # Same gesture held — accumulate
                            held = now - self.confirm_hold_start
                            self.confirm_hold_progress = min(held, HOLD_SECONDS)
                            remaining = max(0, HOLD_SECONDS - held)
                            action = "Confirm" if thumb_gesture == "thumbs_up" else "Cancel"
                            self.message = (
                                f"Hold {action} for {remaining:.1f}s..."
                            )
                            if held >= HOLD_SECONDS:
                                if thumb_gesture == "thumbs_up":
                                    self.state = DONE
                                    self.message = f"Vote confirmed for {self.selected_party}."
                                else:
                                    self.state = CANCELLED
                                    self.message = "Vote cancelled. Restarting..."
                                self.confirm_hold_progress = HOLD_SECONDS
                        else:
                            # New gesture or switched — reset hold
                            self.confirm_gesture = thumb_gesture
                            self.confirm_hold_start = now
                            self.confirm_hold_progress = 0.0
                            action = "Confirm" if thumb_gesture == "thumbs_up" else "Cancel"
                            self.message = (
                                f"Detected {action}. Hold for {HOLD_SECONDS}s..."
                            )
                    else:
                        # No thumbs detected — reset
                        self.confirm_gesture = None
                        self.confirm_hold_start = None
                        self.confirm_hold_progress = 0.0
                        self.message = (
                            f"You selected {self.selected_party}. "
                            "Show thumbs up to confirm, thumbs down to cancel."
                        )

                    confirm_prog = self.confirm_hold_progress
                    confirm_gest = self.confirm_gesture
                    done_or_cancelled = self.state in (DONE, CANCELLED)

                # Draw confirmation overlay on camera feed
                display = frame.copy()
                cv2.putText(
                    display, "THUMBS UP = CONFIRM",
                    (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0), 2,
                )
                cv2.putText(
                    display, "THUMBS DOWN = CANCEL",
                    (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 255), 2,
                )

                # Draw confirmation hold progress bar
                if confirm_prog > 0:
                    bar_color = (0, 255, 0) if confirm_gest == "thumbs_up" else (0, 0, 255)
                    bar_width = int(200 * (confirm_prog / HOLD_SECONDS))
                    cv2.rectangle(display, (10, 440), (10 + bar_width, 460), bar_color, -1)
                    cv2.rectangle(display, (10, 440), (210, 460), (255, 255, 255), 2)
                    action = "Confirm" if confirm_gest == "thumbs_up" else "Cancel"
                    cv2.putText(
                        display,
                        f"{action}: {confirm_prog:.1f}s / {HOLD_SECONDS}s",
                        (10, 435),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1,
                    )

                self.camera.set_display_frame(display)

                if done_or_cancelled:
                    self.camera.clear_display_frame()
                    return

                time.sleep(0.033)
                continue

            # --- GESTURE DETECTION PHASE (MediaPipe HandLandmarker) ---
            finger_count, bbox, landmarks = self._detect_fingers(frame)

            detected = None
            party_name = None
            if finger_count is not None and 1 <= finger_count <= 5:
                detected = str(finger_count)
                party_name = PARTIES.get(detected)

            # Draw hand overlay on display frame
            display = frame.copy()
            if bbox is not None:
                display = self._draw_hand_overlay(
                    display, finger_count, bbox, landmarks, party_name
                )
            self.camera.set_display_frame(display)

            # Update hold logic
            self._update_hold(detected)

            self.num_frames += 1
            time.sleep(0.033)

    def _update_hold(self, detected):
        now = time.time()
        with self._lock:
            if detected and detected in PARTIES:
                if detected == self.current_gesture and self.hold_start_time:
                    held_for = now - self.hold_start_time
                    self.hold_progress = min(held_for, HOLD_SECONDS)
                    remaining = max(0, HOLD_SECONDS - held_for)
                    self.message = (
                        f"Detected {PARTIES[detected]}. "
                        f"Hold for {remaining:.1f}s to select."
                    )
                    if held_for >= HOLD_SECONDS:
                        self.selected_party = PARTIES[detected]
                        self.state = CONFIRMING
                        self.message = (
                            f"You selected {self.selected_party}. "
                            "Show thumbs up to confirm, thumbs down to cancel."
                        )
                        self.hold_progress = HOLD_SECONDS
                else:
                    self.current_gesture = detected
                    self.hold_start_time = now
                    self.hold_progress = 0.0
                    self.message = (
                        f"Detected {PARTIES[detected]}. "
                        f"Hold for {HOLD_SECONDS}s to select."
                    )
            else:
                if self.state == DETECTING:
                    self.current_gesture = None
                    self.hold_start_time = None
                    self.hold_progress = 0.0
                    self.message = "Show your hand gesture to vote."
