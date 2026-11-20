import os
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from config import THUMB_CACHE_DIR, VALID_VIDEO_EXTENSIONS
from security import (
    FileSecurityError,
    get_safe_thumbnail_path,
    validate_media_input,
    verify_contained_file,
)

try:
    import cv2
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def get_cached_thumbnail(video_path: str) -> str | None:
    """
    Trả về đường dẫn ảnh thumbnail đã cache an toàn (băm SHA-256 theo đường dẫn tuyệt đối)
    nằm hoàn toàn trong THUMB_CACHE_DIR.
    """
    try:
        if not video_path:
            return None
        thumb_path = get_safe_thumbnail_path(video_path, THUMB_CACHE_DIR)
        if verify_contained_file(thumb_path, THUMB_CACHE_DIR) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except Exception:
        pass
    return None


def generate_thumbnail(video_path: str) -> str | None:
    """
    Trích xuất một khung hình từ video hợp lệ và lưu nguyên tử (atomic replace)
    vào ảnh JPG trong thư mục cache.
    """
    if not HAS_OPENCV or not video_path:
        return None
    cap = None
    tmp_path = None
    try:
        abs_video = validate_media_input(video_path, VALID_VIDEO_EXTENSIONS)
        thumb_path = get_safe_thumbnail_path(abs_video, THUMB_CACHE_DIR)
        if verify_contained_file(thumb_path, THUMB_CACHE_DIR) and os.path.getsize(thumb_path) > 0:
            return thumb_path

        cap = cv2.VideoCapture(abs_video)
        if not cap.isOpened():
            return None

        cap.set(cv2.CAP_PROP_POS_MSEC, 5000)
        success, frame = cap.read()
        if not success or frame is None:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            success, frame = cap.read()

        if success and frame is not None:
            frame = cv2.resize(frame, (120, 68), interpolation=cv2.INTER_AREA)
            tmp_path = thumb_path + ".tmp.jpg"
            if cv2.imwrite(tmp_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85]) and os.path.exists(tmp_path):
                os.replace(tmp_path, thumb_path)
                tmp_path = None
                return thumb_path
    except (FileSecurityError, Exception):
        pass
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return None


class ThumbnailWorker(QThread):
    """
    Worker chạy ngầm (Background Thread) để tạo thumbnail video bất đồng bộ,
    giúp giao diện ứng dụng hoàn toàn mượt mà, không bị đơ/treo khi chọn thư mục nhiều video.
    """
    thumbnail_ready = pyqtSignal(str, str)  # video_path, thumb_path

    def __init__(self):
        super().__init__()
        self._queue = []
        self._mutex = QMutex()
        self._running = True

    def set_tasks(self, video_paths: list):
        with QMutexLocker(self._mutex):
            self._queue = list(video_paths)

    def add_task(self, video_path: str):
        with QMutexLocker(self._mutex):
            if video_path not in self._queue:
                self._queue.append(video_path)

    def clear_tasks(self):
        with QMutexLocker(self._mutex):
            self._queue.clear()

    def stop(self):
        self._running = False
        self.clear_tasks()
        self.quit()
        self.wait(800)

    def run(self):
        while self._running:
            video_path = None
            with QMutexLocker(self._mutex):
                if self._queue:
                    video_path = self._queue.pop(0)

            if video_path:
                thumb = generate_thumbnail(video_path)
                if thumb and self._running:
                    self.thumbnail_ready.emit(video_path, thumb)
            else:
                self.msleep(50)
