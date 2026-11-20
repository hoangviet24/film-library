#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Application & IPC Integrity Guard
Bảo vệ tính toàn vẹn của các thành phần thực thi, thư viện phụ thuộc (libVLC),
và kênh giao tiếp Single-Instance QLocalServer trên Windows.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from .file_guard import (
    FileSecurityError,
    is_path_contained,
    is_reparse_point_or_symlink,
    validate_video_path,
)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_contained_file(path: str, base_dir: str) -> bool:
    """
    Xác minh tệp tồn tại, là tệp thường, không phải symlink/reparse point
    và đường dẫn thực nằm hoàn toàn bên trong base_dir.
    """
    if not path or not base_dir:
        return False
    if not os.path.isfile(path):
        return False
    if is_reparse_point_or_symlink(path):
        return False
    return is_path_contained(path, base_dir)


def generate_integrity_manifest(dist_dir: str, output_path: str) -> str:
    """
    Sinh tệp integrity_manifest.json chứa SHA-256 của các thành phần cốt lõi
    khi đóng gói bản phân phối Portable & Installer.
    """
    abs_dist = os.path.abspath(dist_dir)
    candidates = [
        "FluentMediaPlayer.exe",
        os.path.join("_internal", "vlc", "libvlc.dll"),
        os.path.join("_internal", "vlc", "libvlccore.dll"),
        os.path.join("_internal", "assets", "logo.ico"),
    ]
    files_map: dict[str, str] = {}
    for rel in candidates:
        full = os.path.join(abs_dist, rel)
        if verify_contained_file(full, abs_dist):
            files_map[rel.replace("\\", "/")] = _sha256_file(full)

    manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "files": files_map,
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    tmp_out = output_path + ".tmp"
    with open(tmp_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp_out, output_path)
    return output_path


def verify_runtime_integrity(base_dir: str) -> dict:
    """
    Kiểm tra tính toàn vẹn của thư viện runtime & tài nguyên cốt lõi khi khởi động.
    Không chặn khởi động khi chạy ở môi trường dev, chỉ cảnh báo nếu phát hiện sai lệch.
    """
    abs_base = os.path.abspath(base_dir)
    if os.path.basename(abs_base).lower() == "_internal":
        package_root = os.path.dirname(abs_base)
    else:
        package_root = abs_base

    warnings: list[str] = []
    checked = 0

    vlc_dir = os.path.join(abs_base, "vlc")
    if os.path.isdir(vlc_dir):
        for dll_name in ("libvlc.dll", "libvlccore.dll"):
            dll_path = os.path.join(vlc_dir, dll_name)
            if os.path.exists(dll_path):
                checked += 1
                if not verify_contained_file(dll_path, vlc_dir):
                    warnings.append(f"Tệp thư viện không hợp lệ hoặc là liên kết ngoài phạm vi: {dll_name}")

    ico_path = os.path.join(abs_base, "assets", "logo.ico")
    if os.path.exists(ico_path):
        checked += 1
        if not verify_contained_file(ico_path, abs_base):
            warnings.append("Tài nguyên assets/logo.ico không vượt qua kiểm tra containment.")

    manifest_path = os.path.join(abs_base, "integrity_manifest.json")
    if os.path.isfile(manifest_path) and verify_contained_file(manifest_path, abs_base):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            files_map = manifest.get("files", {}) if isinstance(manifest, dict) else {}
            if isinstance(files_map, dict):
                for rel_path, expected_hash in files_map.items():
                    if not isinstance(rel_path, str) or not isinstance(expected_hash, str):
                        continue
                    target = os.path.normpath(os.path.join(package_root, rel_path))
                    checked += 1
                    if not verify_contained_file(target, package_root):
                        warnings.append(f"Thiếu hoặc sai phạm vi tệp bắt buộc: {rel_path}")
                        continue
                    actual_hash = _sha256_file(target)
                    if actual_hash.lower() != expected_hash.strip().lower():
                        warnings.append(f"SHA-256 không khớp cho thành phần cốt lõi: {rel_path}")
        except Exception as exc:
            warnings.append(f"Không thể đọc integrity_manifest.json: {exc}")

    return {
        "ok": len(warnings) == 0,
        "warnings": warnings,
        "checked": checked,
    }


def configure_secure_local_server(server) -> None:
    """
    Giới hạn Named Pipe / LocalSocket chỉ cho phép người dùng Windows hiện tại (UserAccessOption).
    Phải gọi trước server.listen(...).
    """
    try:
        from PyQt6.QtNetwork import QLocalServer
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    except Exception:
        pass


def validate_ipc_payload(
    raw_bytes: bytes,
    valid_extensions: tuple[str, ...],
    max_bytes: int = 4096,
) -> str | None:
    """
    Kiểm tra dữ liệu đường dẫn gửi qua Single-Instance QLocalSocket:
    - Chặn payload vượt quá max_bytes
    - Giải mã UTF-8 nghiêm ngặt
    - Xác thực đường dẫn video qua validate_video_path (chặn script, UNC, traversal, tên thiết bị)
    """
    if not isinstance(raw_bytes, (bytes, bytearray)) or not raw_bytes:
        return None
    if len(raw_bytes) > max_bytes:
        return None

    try:
        text = bytes(raw_bytes).decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        return None

    if not text:
        return None

    cleaned = text.strip('"\'')
    try:
        return validate_video_path(cleaned, valid_extensions)
    except FileSecurityError:
        return None
