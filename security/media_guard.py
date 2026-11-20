#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Media Processing Security Guard
Bảo vệ quá trình đọc, giải mã và trích xuất metadata media:
- Kiểm tra tệp hợp lệ & chặn tệp giả mạo (PE executable MZ, script, HTML)
- Tùy chọn an toàn cho libVLC (--no-metadata-network-access, --no-lua) chống rò rỉ mạng / thực thi script
- Dò tìm ffprobe an toàn (loại bỏ CWD chống DLL/EXE hijacking) & giới hạn tài nguyên/thời gian chạy
- Làm sạch toàn bộ chuỗi metadata (chặn ký tự điều khiển & BiDi/RTL spoofing)
- Đường dẫn thumbnail cache băm SHA-256 chống đụng độ tên & giới hạn hoàn toàn trong thư mục cache
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

from .file_guard import (
    FileSecurityError,
    is_path_contained,
    is_reparse_point_or_symlink,
    validate_video_path,
)

DISGUISED_SIGNATURES = (
    b"MZ",          # Windows PE/DOS Executable
    b"\x7fELF",     # ELF Executable
    b"#!",          # Unix Shebang script
    b"@echo",       # Windows Batch script
    b"<?php",       # PHP script
    b"<!doctype",   # HTML document
    b"<html",       # HTML document
    b"<script",     # HTML/JS payload
)

BIDI_CONTROL_CHARS = frozenset({
    "\u200e", "\u200f",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
})


def get_safe_vlc_args() -> list[str]:
    """Tham số khởi tạo libVLC offline hoàn toàn, tắt Lua & truy vấn metadata qua mạng."""
    return [
        "--quiet",
        "--no-xlib",
        "--no-video-title-show",
        "--no-metadata-network-access",
        "--no-lua",
    ]


def check_disguised_or_invalid_media(file_path: str) -> tuple[bool, str]:
    """
    Kiểm tra tệp media có phải là tệp thường đọc được, dung lượng > 0
    và không phải tệp thực thi/script bị đổi đuôi giả mạo thành video.
    """
    try:
        if not os.path.exists(file_path):
            return False, "Tệp không tồn tại trên hệ thống."
        if not os.path.isfile(file_path):
            return False, "Đường dẫn không phải là tệp media thường."
        size = os.path.getsize(file_path)
        if size <= 0:
            return False, "Tệp video bị rỗng (0 byte)."
        with open(file_path, "rb") as f:
            head = f.read(64)
    except PermissionError:
        return False, "Không đủ quyền đọc tệp media."
    except OSError as exc:
        return False, f"Không thể đọc tệp media: {exc}"

    if not head:
        return False, "Không thể đọc dữ liệu đầu tệp media."

    head_stripped = head.lstrip()
    head_lower = head_stripped.lower()
    for sig in DISGUISED_SIGNATURES:
        if sig in (b"MZ", b"\x7fELF", b"#!"):
            if head.startswith(sig):
                return False, "Phát hiện tệp thực thi hoặc script giả mạo định dạng video."
        else:
            if head_lower.startswith(sig):
                return False, "Phát hiện nội dung web/script không phải tệp media hợp lệ."

    return True, "ok"


def validate_media_input(file_path: str, valid_extensions: tuple[str, ...]) -> str:
    """
    Kiểm tra đầu vào đầy đủ trước khi đưa cho libVLC, OpenCV hoặc FFprobe xử lý.
    """
    abs_path = validate_video_path(file_path, valid_extensions)
    ok, reason = check_disguised_or_invalid_media(abs_path)
    if not ok:
        raise FileSecurityError("invalid_path", reason)
    return abs_path


def find_safe_ffprobe() -> str | None:
    """
    Tìm ffprobe.exe trong PATH nhưng loại bỏ tuyệt đối thư mục làm việc hiện tại (CWD / '.')
    để ngăn tấn công binary hijacking khi mở video từ thư mục không tin cậy.
    """
    raw_path = os.environ.get("PATH", "")
    if not raw_path:
        return None

    try:
        cwd_norm = os.path.normcase(os.path.realpath(os.getcwd()))
    except OSError:
        cwd_norm = ""

    exe_names = ("ffprobe.exe",) if sys.platform.startswith("win") else ("ffprobe",)
    for entry in raw_path.split(os.pathsep):
        cleaned = entry.strip().strip('"')
        if not cleaned or cleaned in (".", ".\\", "./"):
            continue
        try:
            real_dir = os.path.normcase(os.path.realpath(cleaned))
        except OSError:
            continue
        if cwd_norm and real_dir == cwd_norm:
            continue
        if not os.path.isdir(real_dir):
            continue

        for name in exe_names:
            cand = os.path.join(real_dir, name)
            if os.path.isfile(cand) and not is_reparse_point_or_symlink(cand):
                return cand
    return None


def run_ffprobe_safely(
    file_path: str,
    ffprobe_bin: str,
    timeout_sec: float = 6.0,
    max_output_bytes: int = 2 * 1024 * 1024,
) -> dict | None:
    """
    Thực thi ffprobe với danh sách tham số an toàn (shell=False), giới hạn thời gian thăm dò
    (-probesize / -analyzeduration), không ghi shell và giới hạn dung lượng JSON đầu ra.
    """
    if not ffprobe_bin or not os.path.isfile(ffprobe_bin):
        return None

    abs_path = os.path.abspath(file_path)
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-probesize", "5000000",
        "-analyzeduration", "5000000",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-i", abs_path,
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
            shell=False,
            creationflags=creationflags,
        )
        if res.returncode != 0 or not res.stdout:
            return None
        if len(res.stdout) > max_output_bytes:
            return None
        data = json.loads(res.stdout.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def sanitize_metadata_text(
    value,
    max_len: int = 200,
    default: str = "Unavailable",
) -> str:
    """
    Làm sạch dữ liệu metadata trích xuất từ video trước khi hiển thị lên UI:
    - Loại bỏ null byte, ký tự điều khiển ASCII (0x00-0x1F, 0x7F)
    - Loại bỏ ký tự điều hướng BiDi/RTL (ngăn giả mạo hiển thị tên)
    - Thu gọn khoảng trắng và giới hạn độ dài chống tràn UI
    """
    if value is None:
        return default
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)

    filtered = []
    for ch in text:
        if ord(ch) < 32 or ord(ch) == 127 or ch in BIDI_CONTROL_CHARS:
            filtered.append(" ")
        else:
            filtered.append(ch)
    collapsed = re.sub(r"\s+", " ", "".join(filtered)).strip()
    if not collapsed:
        return default
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3].rstrip() + "..."
    return collapsed


def get_safe_thumbnail_path(video_path: str, cache_dir: str) -> str:
    """
    Sinh đường dẫn ảnh thumbnail cache an toàn dựa trên SHA-256 của đường dẫn chuẩn hóa,
    tránh đụng độ tên giữa các thư mục và đảm bảo không thể thoát khỏi cache_dir.
    """
    abs_cache = os.path.abspath(cache_dir)
    os.makedirs(abs_cache, exist_ok=True)
    norm_video = os.path.normcase(os.path.abspath(video_path))
    digest = hashlib.sha256(norm_video.encode("utf-8", errors="replace")).hexdigest()[:24]
    thumb_path = os.path.normpath(os.path.join(abs_cache, f"{digest}.jpg"))
    if not is_path_contained(thumb_path, abs_cache):
        raise FileSecurityError("traversal", "Đường dẫn thumbnail vượt khỏi thư mục cache cho phép.")
    return thumb_path
