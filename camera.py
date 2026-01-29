import cv2
import threading


class CameraAsync:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cap = None
        self.ready = False
        self.lock = threading.Lock()
        threading.Thread(target=self._init_camera, daemon=True).start()

    def _init_camera(self):
        cam = cv2.VideoCapture(0)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        with self.lock:
            self.cap = cam
            self.ready = cam.isOpened()

    def read(self):
        if not self.ready:
            return False, None
        with self.lock:
            if self.cap and self.cap.isOpened():
                return self.cap.read()
        return False, None

    def release(self):
        with self.lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
            self.cap = None
            self.ready = False
