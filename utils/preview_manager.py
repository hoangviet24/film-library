import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition
from PyQt6.QtGui import QImage, QPixmap
from config import VALID_VIDEO_EXTENSIONS
from security import FileSecurityError, validate_media_input

try:
    import cv2
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
    HAS_OPENCV = True
except ImportError:
    cv2 = None
    HAS_OPENCV = False

class _PreviewWorker(QThread):
    image_ready = pyqtSignal(str, int, QImage)  # video_path, bucket_sec, qimage

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._running = True
        self._pending_request = None  # (video_path, bucket_sec)
        self._release_requested = False
        self._cap = None
        self._current_cap_path = None

    def request(self, video_path: str, bucket_sec: int):
        with QMutexLocker(self._mutex):
            self._pending_request = (video_path, bucket_sec)
            self._cond.wakeOne()

    def release_current_capture(self):
        with QMutexLocker(self._mutex):
            self._pending_request = None
            self._release_requested = True
            self._release_cap()
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
        if not HAS_OPENCV:
            return
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
            try:
                abs_video = validate_media_input(video_path, VALID_VIDEO_EXTENSIONS)
                # Mở hoặc tái sử dụng VideoCapture
                if self._cap is None or self._current_cap_path != abs_video:
                    self._release_cap()
                    self._cap = cv2.VideoCapture(abs_video)
                    self._current_cap_path = abs_video

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
            except (FileSecurityError, Exception):
                self._release_cap()


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
        if HAS_OPENCV:
            self._worker = _PreviewWorker()
            self._worker.image_ready.connect(self._on_image_ready)
            self._worker.start()
        else:
            self._worker = None

    def set_video(self, video_path: str):
        if self._current_video_path != video_path:
            self._current_video_path = video_path
            # Giữ cache của video cũ hoặc dọn dẹp nếu quá đầy
            if len(self._cache) > self._max_cache:
                self._cache.clear()

    def get_cached_preview(self, video_path: str, bucket_sec: int) -> QPixmap | None:
        return self._cache.get((video_path, bucket_sec))

    def request_preview(self, video_path: str, msec: int):
        if not HAS_OPENCV or self._worker is None or not video_path:
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

    def release_video(self, video_path: str = None):
        """Giải phóng file handle VideoCapture để cho phép đổi tên hoặc xóa file trên Windows."""
        if self._worker is not None:
            self._worker.release_current_capture()
        if video_path:
            norm = os.path.normcase(os.path.abspath(video_path))
            keys_to_remove = [
                k for k in self._cache
                if os.path.normcase(os.path.abspath(k[0])) == norm
            ]
            for k in keys_to_remove:
                self._cache.pop(k, None)
            if self._current_video_path and os.path.normcase(os.path.abspath(self._current_video_path)) == norm:
                self._current_video_path = None

    def stop(self):
        if self._worker is not None:
            self._worker.stop()
