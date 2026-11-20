import threading
import config
from security import HistoryDatabase

_DB_LOCK = threading.Lock()
_DB_INSTANCE: HistoryDatabase | None = None
_DB_TARGET_PATH: str | None = None


def get_history_db() -> HistoryDatabase:
    """Trả về thể hiện SQLite HistoryDatabase dùng chung (thread-safe)."""
    global _DB_INSTANCE, _DB_TARGET_PATH
    with _DB_LOCK:
        target = config.DB_FILE
        if _DB_INSTANCE is None or _DB_TARGET_PATH != target:
            if _DB_INSTANCE is not None:
                try:
                    _DB_INSTANCE.close(create_final_backup=False)
                except Exception:
                    pass
            _DB_INSTANCE = HistoryDatabase(
                db_path=target,
                backup_dir=config.BACKUP_DIR,
                legacy_json_path=config.HISTORY_FILE,
            )
            _DB_TARGET_PATH = target
        return _DB_INSTANCE


def load_history() -> dict:
    """Tải thông tin tiến độ đã xem từ SQLite database có bảo vệ giao dịch."""
    try:
        return get_history_db().load_all()
    except Exception:
        return {}


def save_history(history_data: dict) -> None:
    """Đồng bộ toàn bộ thông tin tiến độ xem video vào SQLite database."""
    try:
        get_history_db().sync_save_all(history_data)
    except Exception:
        pass


def upsert_history_progress(file_path: str, pos: float, pct: float) -> None:
    """Cập nhật tiến độ của một video cụ thể theo transaction nguyên tử."""
    try:
        get_history_db().upsert_progress(file_path, pos, pct)
    except Exception:
        pass


def rename_history_entry(old_path: str, new_path: str) -> None:
    """Cập nhật đường dẫn mới trong database ngay khi đổi tên tệp."""
    try:
        get_history_db().rename_entry(old_path, new_path)
    except Exception:
        pass


def delete_history_entry(file_path: str) -> None:
    """Xóa bản ghi tiến độ khỏi database đồng bộ với thao tác xóa tệp."""
    try:
        get_history_db().delete_entry(file_path)
    except Exception:
        pass


def close_history_db(create_final_backup: bool = True) -> None:
    """Đóng kết nối SQLite an toàn và tạo bản sao lưu cuối phiên khi thoát ứng dụng."""
    global _DB_INSTANCE, _DB_TARGET_PATH
    with _DB_LOCK:
        if _DB_INSTANCE is not None:
            try:
                _DB_INSTANCE.close(create_final_backup=create_final_backup)
            except Exception:
                pass
            _DB_INSTANCE = None
            _DB_TARGET_PATH = None
