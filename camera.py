import cv2
import numpy as np
import threading
import time


class CameraManager:
    _instance = None
    _init_lock = threading.Lock()

    def __init__(self):
        self._cap = None
        self._frame = None
        self._display_frame = None
        self._lock = threading.Lock()
        self._running = False
        self._reader_thread = None

    @classmethod
    def get_instance(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = CameraManager()
            return cls._instance

    def start(self):
        if self._running:
            return True
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            print("ERROR: Could not open camera")
            return False
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        return True

    def stop(self):
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
        if self._cap:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._frame = None
            self._display_frame = None

    def is_running(self):
        return self._running

    def read_frame(self):
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def set_display_frame(self, frame):
        """Set an annotated frame to be shown in the MJPEG stream."""
        with self._lock:
            self._display_frame = frame

    def clear_display_frame(self):
        """Clear the display frame overlay, reverting to raw camera feed."""
        with self._lock:
            self._display_frame = None

    def _reader_loop(self):
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.01)
                continue
            ret, frame = self._cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.01)

    def generate_mjpeg(self):
        while True:
            with self._lock:
                if self._display_frame is not None:
                    frame = self._display_frame.copy()
                elif self._frame is not None:
                    frame = self._frame.copy()
                else:
                    frame = None
            if frame is None:
                time.sleep(0.05)
                continue
            ret, buffer = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            if ret:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + buffer.tobytes()
                    + b'\r\n'
                )
            time.sleep(1 / 25)
