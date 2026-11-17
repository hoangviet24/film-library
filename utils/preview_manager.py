import os
import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition
from PyQt6.QtGui import QImage, QPixmap

class _PreviewWorker(QThread):
    image_ready = pyqtSignal(str, int, QImage)  # video_path, bucket_sec, qimage

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._running = True
        self._pending_request = None  # (video_path, bucket_sec)
        self._cap = None
        self._current_cap_path = None

    def request(self, video_path: str, bucket_sec: int):
        with QMutexLocker(self._mutex):
            self._pending_request = (video_path, bucket_sec)
            self._cond.wakeOne()

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False
            self._cond.wakeOne()
        self.quit()
        self.wait(1000)
        self._release_cap()

    def _release_cap(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
            self._current_cap_path = None

    def run(self):
        while True:
            req = None
            with QMutexLocker(self._mutex):
                while self._running and self._pending_request is None:
                    self._cond.wait(self._mutex)
                if not self._running:
                    break
                req = self._pending_request
                self._pending_request = None

            if req is None:
                continue

            video_path, bucket_sec = req
            if not os.path.exists(video_path):
                continue

            try:
                # Mở hoặc tái sử dụng VideoCapture
                if self._cap is None or self._current_cap_path != video_path:
                    self._release_cap()
                    self._cap = cv2.VideoCapture(video_path)
                    self._current_cap_path = video_path

                if not self._cap.isOpened():
                    self._release_cap()
                    continue

                self._cap.set(cv2.CAP_PROP_POS_MSEC, bucket_sec * 1000)
                success, frame = self._cap.read()
                if not success or frame is None:
                    continue

                # Resize về chuẩn 160x90 (16:9)
                frame = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
                # BGR -> RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                # QImage cần bản sao an toàn của mảng bytes
                qimg = QImage(rgb_frame.data.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888)

                if self._running:
                    self.image_ready.emit(video_path, bucket_sec, qimg)
            except Exception as e:
                pass


class PreviewManager(QObject):
    """
    Quản lý trích xuất và cache Thumbnail Preview cho thanh tiến trình video:
    - Sử dụng OpenCV trích xuất ảnh nền bất đồng bộ (Background Thread)
    - Cache bộ nhớ RAM dạng LRU để phản hồi tức thì (<1ms) khi di chuột qua lại
    - Tự động bỏ qua các frame trung gian khi di chuột nhanh để tránh giật lag
    """
    preview_ready = pyqtSignal(str, int, QPixmap)  # video_path, bucket_sec, pixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = {}  # (video_path, bucket_sec): QPixmap
        self._max_cache = 300
        self._current_video_path = None
        self._worker = _PreviewWorker()
        self._worker.image_ready.connect(self._on_image_ready)
        self._worker.start()

    def set_video(self, video_path: str):
        if self._current_video_path != video_path:
            self._current_video_path = video_path
            # Giữ cache của video cũ hoặc dọn dẹp nếu quá đầy
            if len(self._cache) > self._max_cache:
                self._cache.clear()

    def get_cached_preview(self, video_path: str, bucket_sec: int) -> QPixmap | None:
        return self._cache.get((video_path, bucket_sec))

    def request_preview(self, video_path: str, msec: int):
        if not video_path:
            return
        bucket_sec = int(round(msec / 2000.0) * 2)  # Gom nhóm 2 giây
        pixmap = self.get_cached_preview(video_path, bucket_sec)
        if pixmap:
            self.preview_ready.emit(video_path, bucket_sec, pixmap)
            return

        self._worker.request(video_path, bucket_sec)

    def _on_image_ready(self, video_path: str, bucket_sec: int, qimg: QImage):
        pixmap = QPixmap.fromImage(qimg)
        self._cache[(video_path, bucket_sec)] = pixmap
        if len(self._cache) > self._max_cache:
            # Xoá bớt phần tử đầu tiên
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self.preview_ready.emit(video_path, bucket_sec, pixmap)

    def stop(self):
        self._worker.stop()
