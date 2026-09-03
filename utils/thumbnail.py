import os
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from config import THUMB_CACHE_DIR

try:
    import cv2
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

def get_cached_thumbnail(video_path: str) -> str | None:
    """
    Trả về đường dẫn ảnh thumbnail đã cache nếu tồn tại.
    """
    try:
        filename = os.path.basename(video_path)
        thumb_path = os.path.join(THUMB_CACHE_DIR, f"{filename}.jpg")
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except Exception:
        pass
    return None

def generate_thumbnail(video_path: str) -> str | None:
    """
    Trích xuất một khung hình từ video và lưu dưới dạng ảnh JPG vào thư mục cache.
    Ưu tiên lấy khung hình ở giây thứ 5, nếu không được thì lấy khung hình đầu tiên (giây 0).
    """
    if not HAS_OPENCV:
        return None
    try:
        filename = os.path.basename(video_path)
        thumb_path = os.path.join(THUMB_CACHE_DIR, f"{filename}.jpg")
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        cap.set(cv2.CAP_PROP_POS_MSEC, 5000)
        success, frame = cap.read()
        if not success or frame is None:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            success, frame = cap.read()
            
        if success and frame is not None:
            frame = cv2.resize(frame, (120, 68), interpolation=cv2.INTER_AREA)
            cv2.imwrite(thumb_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            cap.release()
            return thumb_path
        cap.release()
    except Exception:
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
