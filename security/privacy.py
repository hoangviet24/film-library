#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Privacy & Standard User Permissions Manager
- Làm sạch đường dẫn chứa tên người dùng Windows khi ghi log
- Kiểm tra quyền Standard User / khả năng ghi thư mục mà không chỉnh sửa ACL
- Hỗ trợ xóa sạch toàn bộ dữ liệu ứng dụng (lịch sử, cache, backup) mà không đụng tới video của người dùng
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import sys
import tempfile

from .file_guard import is_path_contained, is_reparse_point_or_symlink

APP_OWNED_DIRS = ("thumb_cache", "backups")
APP_OWNED_FILE_PREFIXES = (
    "library.db",
    "video_history.json",
)


def sanitize_for_log(text: str) -> str:
    """Ẩn thư mục cá nhân (%USERPROFILE% / tên tài khoản Windows) khỏi nội dung log/lỗi."""
    if not text:
        return text
    out = str(text)
    candidates = []
    try:
        candidates.append(os.path.expanduser("~"))
    except Exception:
        pass
    if os.environ.get("USERPROFILE"):
        candidates.append(os.environ["USERPROFILE"])

    for profile_dir in candidates:
        if profile_dir and len(profile_dir) > 3:
            norm = os.path.normpath(profile_dir)
            out = re.sub(re.escape(norm), "%USERPROFILE%", out, flags=re.IGNORECASE)
            fwd = norm.replace("\\", "/")
            out = re.sub(re.escape(fwd), "%USERPROFILE%", out, flags=re.IGNORECASE)
    return out


def is_running_as_admin() -> bool:
    """Kiểm tra xem tiến trình có đang chạy dưới quyền Administrator hay Standard User."""
    if not sys.platform.startswith("win"):
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_directory_writable(path: str) -> bool:
    """
    Kiểm tra thư mục có quyền ghi thực sự bằng tệp tạm (không tự ý chỉnh sửa ACL/quyền Windows).
    """
    if not path or not os.path.isdir(path):
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".write_test_", delete=True):
            pass
        return True
    except (OSError, PermissionError):
        return False


def clear_application_data(user_data_dir: str, include_backups: bool = True) -> dict:
    """
    Xóa sạch các tệp dữ liệu thuộc riêng ứng dụng bên trong user_data_dir
    (SQLite DB, backups, video_history.json cũ, thumb_cache, file tạm).
    Tuyệt đối không thao tác ra ngoài user_data_dir hoặc đi theo symlink.
    """
    removed: list[str] = []
    errors: list[str] = []

    if not user_data_dir or not os.path.isdir(user_data_dir):
        return {"removed": removed, "errors": errors}

    abs_dir = os.path.abspath(user_data_dir)
    if is_reparse_point_or_symlink(abs_dir):
        errors.append("Thư mục dữ liệu là liên kết symlink/reparse point; từ chối xóa hàng loạt.")
        return {"removed": removed, "errors": errors}

    for entry in os.listdir(abs_dir):
        full = os.path.join(abs_dir, entry)
        low = entry.lower()

        is_app_dir = (low == "thumb_cache") or (include_backups and low == "backups")
        is_app_file = low.startswith(APP_OWNED_FILE_PREFIXES) or low.endswith(".tmp")

        if not (is_app_dir or is_app_file):
            continue

        if is_reparse_point_or_symlink(full):
            try:
                os.unlink(full)
                removed.append(entry)
            except OSError as exc:
                errors.append(f"{entry}: {exc}")
            continue

        if not is_path_contained(full, abs_dir):
            errors.append(f"Bỏ qua mục vượt khỏi phạm vi user_data_dir: {entry}")
            continue

        try:
            if os.path.isdir(full) and is_app_dir:
                shutil.rmtree(full)
                removed.append(entry)
            elif os.path.isfile(full) and is_app_file:
                os.remove(full)
                removed.append(entry)
        except OSError as exc:
            errors.append(f"{entry}: {exc}")

    return {"removed": removed, "errors": errors}
