import os
import json
from config import HISTORY_FILE

def load_history() -> dict:
    """
    Tải thông tin tiến độ đã xem từ file JSON.
    """
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history_data: dict) -> None:
    """
    Lưu thông tin tiến độ xem video vào file JSON.
    """
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
