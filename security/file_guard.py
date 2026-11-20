#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - File System Security Guard
Bảo vệ mọi thao tác hệ thống file Windows Local:
- Chuẩn hóa & xác thực đường dẫn (chặn Path Traversal, UNC, device path, ADS, tên dành riêng Windows)
- Phát hiện Symbolic Links / NTFS Junctions / Reparse Points qua Win32 GetFileAttributesW
- Kiểm soát phạm vi thư mục được người dùng cho phép (AuthorizedScope)
- Xóa an toàn qua Windows Recycle Bin (SHFileOperationW), thử lại khi tệp đang bị khóa nhẹ (WinError 32)
- Mở File Explorer bằng Win32 Shell API (SHOpenFolderAndSelectItems), không ghép chuỗi shell
"""

from __future__ import annotations

import ctypes
import errno
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400

LOCKED_WINERRORS = {32, 33}  # ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION


class FileSecurityError(Exception):
    """Lỗi bảo mật hoặc lỗi hệ thống tệp có mã lỗi phân loại rõ ràng."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


def is_reparse_point_or_symlink(path: str) -> bool:
    """
    Kiểm tra một tệp hoặc thư mục có phải Symbolic Link / NTFS Junction / Reparse Point không.
    Kết hợp os.path.islink() với Win32 GetFileAttributesW để bắt cả Junction trên Windows.
    """
    if not path:
        return False
    try:
        if os.path.islink(path):
            return True
    except OSError:
        return True

    if sys.platform.startswith("win"):
        try:
            get_attrs = ctypes.windll.kernel32.GetFileAttributesW
            get_attrs.argtypes = [wintypes.LPCWSTR]
            get_attrs.restype = wintypes.DWORD
            attrs = get_attrs(str(path))
            if attrs != INVALID_FILE_ATTRIBUTES and bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        except Exception:
            pass
    return False


def _has_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def validate_path(raw_path: str, allow_unc: bool = False) -> str:
    """
    Kiểm tra an toàn và chuẩn hóa đường dẫn Windows.
    Chặn: chuỗi rỗng, ký tự điều khiển, device path (\\\\.\\, \\\\?\\),
    UNC path (trừ khi allow_unc=True), NTFS Alternate Data Streams (:),
    segment traversal (..), tên thiết bị dành riêng (CON, NUL, COM1...), và dấu cách/chấm cuối tên.
    """
    if not isinstance(raw_path, str):
        raise FileSecurityError("invalid_path", "Đường dẫn không hợp lệ (không phải chuỗi ký tự).")

    cleaned = raw_path.strip('"\'')
    if not cleaned or not cleaned.strip():
        raise FileSecurityError("invalid_path", "Đường dẫn tệp trống hoặc không hợp lệ.")

    if _has_control_chars(cleaned):
        raise FileSecurityError("invalid_path", "Đường dẫn chứa ký tự điều khiển không hợp lệ.")

    fwd = cleaned.replace("\\", "/")
    if fwd.startswith("//./") or fwd.startswith("//?/"):
        raise FileSecurityError("invalid_path", "Không cho phép truy cập đường dẫn thiết bị Windows (\\\\.\\ hoặc \\\\?\\).")

    if fwd.startswith("//"):
        if not allow_unc:
            raise FileSecurityError("invalid_path", "Không cho phép tự động mở đường dẫn mạng UNC.")
    else:
        # Chặn NTFS Alternate Data Streams (ADS): dấu ':' sau phần ổ đĩa (ví dụ C:\a.mp4:hidden)
        without_drive = cleaned[2:] if (len(cleaned) >= 2 and cleaned[0].isalpha() and cleaned[1] == ":") else cleaned
        if ":" in without_drive:
            raise FileSecurityError("invalid_path", "Đường dẫn chứa NTFS Alternate Data Stream (:) không hợp lệ.")

    raw_parts = [p for p in re.split(r"[\\/]+", cleaned) if p]
    for idx, seg in enumerate(raw_parts):
        if seg == "..":
            raise FileSecurityError("traversal", "Phát hiện ký tự điều hướng thư mục cha ('..') không an toàn.")
        if seg == "." and len(raw_parts) > 1:
            continue
        # Bỏ qua ổ đĩa (e.g. 'D:') hoặc tên server UNC đầu tiên
        if idx == 0 and (len(seg) == 2 and seg[0].isalpha() and seg[1] == ":"):
            continue
        if idx == 0 and fwd.startswith("//"):
            continue

        if any(ch in INVALID_FILENAME_CHARS for ch in seg):
            raise FileSecurityError("invalid_path", f"Thành phần đường dẫn chứa ký tự không hợp lệ: '{seg}'")
        if seg not in (".",) and seg.endswith((".", " ")):
            raise FileSecurityError("invalid_path", f"Tên tệp/thư mục kết thúc bằng dấu chấm hoặc khoảng trắng không hợp lệ: '{seg}'")

        stem = seg.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise FileSecurityError("reserved_name", f"Tên dành riêng của Windows không được phép sử dụng: '{seg}'")

    try:
        abs_path = os.path.normpath(os.path.abspath(cleaned))
    except Exception as exc:
        raise FileSecurityError("invalid_path", f"Không thể chuẩn hóa đường dẫn: {exc}") from exc

    return abs_path


def validate_directory_path(raw_path: str) -> str:
    """Xác thực đường dẫn thư mục tồn tại và có thể đọc được."""
    abs_dir = validate_path(raw_path)
    if not os.path.exists(abs_dir):
        raise FileSecurityError("not_found", f"Thư mục không tồn tại: {abs_dir}")
    if not os.path.isdir(abs_dir):
        raise FileSecurityError("invalid_path", f"Đường dẫn không phải là thư mục: {abs_dir}")
    try:
        with os.scandir(abs_dir):
            pass
    except PermissionError as exc:
        raise FileSecurityError("permission_denied", f"Không đủ quyền đọc thư mục: {abs_dir}") from exc
    except OSError as exc:
        raise FileSecurityError("invalid_path", f"Không thể truy cập thư mục: {exc}") from exc
    return abs_dir


def validate_video_path(raw_path: str, valid_extensions: tuple[str, ...]) -> str:
    """Xác thực đường dẫn video tồn tại, là tệp thường và thuộc định dạng video hỗ trợ."""
    abs_file = validate_path(raw_path)
    if not os.path.exists(abs_file):
        raise FileSecurityError("not_found", f"Tệp video không tồn tại: {abs_file}")
    if not os.path.isfile(abs_file):
        raise FileSecurityError("invalid_path", f"Đường dẫn không phải là tệp hợp lệ: {abs_file}")
    if valid_extensions and not abs_file.lower().endswith(valid_extensions):
        raise FileSecurityError("invalid_path", f"Định dạng tệp không được hỗ trợ: {os.path.basename(abs_file)}")
    return abs_file


def validate_new_filename(new_raw: str, required_ext: str) -> str:
    """
    Xác thực tên tệp mới khi đổi tên (không chứa thư mục, ký tự cấm, ADS hay tên thiết bị Windows)
    và luôn giữ nguyên phần mở rộng gốc.
    """
    if not isinstance(new_raw, str):
        raise FileSecurityError("invalid_path", "Tên tệp mới không hợp lệ.")

    name = new_raw.strip()
    if not name:
        raise FileSecurityError("invalid_path", "Tên tệp mới không được để trống.")
    if _has_control_chars(name):
        raise FileSecurityError("invalid_path", "Tên tệp chứa ký tự điều khiển không hợp lệ.")
    if "/" in name or "\\" in name or ".." in name:
        raise FileSecurityError("traversal", "Tên tệp không được chứa ký tự đường dẫn ('/', '\\' hoặc '..').")
    if ":" in name:
        raise FileSecurityError("invalid_path", "Tên tệp không được chứa ký tự ':'.")
    if any(ch in INVALID_FILENAME_CHARS for ch in name):
        raise FileSecurityError("invalid_path", "Tên tệp chứa ký tự không được phép trên Windows.")

    ext = required_ext if required_ext.startswith(".") else f".{required_ext}"
    if not name.lower().endswith(ext.lower()):
        candidate = name + ext
    else:
        # Giữ nguyên đuôi mở rộng chuẩn theo tệp gốc
        candidate = name[:-len(ext)] + ext

    stem = candidate[:-len(ext)]
    if not stem or not stem.strip() or stem.endswith((".", " ")):
        raise FileSecurityError("invalid_path", "Tên tệp không được kết thúc bằng dấu chấm hoặc khoảng trắng trước phần mở rộng.")
    if stem.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise FileSecurityError("reserved_name", f"Không thể đặt tên trùng tên thiết bị dành riêng của Windows: '{stem}'")
    if len(candidate) > 240:
        raise FileSecurityError("invalid_path", "Tên tệp quá dài (tối đa 240 ký tự).")
    return candidate


def is_path_contained(path: str, root_dir: str) -> bool:
    """Kiểm tra đường dẫn sau khi phân giải thực (realpath) có nằm hoàn toàn trong root_dir hay không."""
    try:
        real_target = os.path.normcase(os.path.realpath(path))
        real_root = os.path.normcase(os.path.realpath(root_dir))
        return os.path.commonpath([real_target, real_root]) == real_root
    except (ValueError, OSError):
        return False


def safe_walk_videos(
    root_folder: str,
    valid_extensions: tuple[str, ...],
    max_depth: int = 25,
    max_files: int = 20000,
) -> dict[str, list[str]]:
    """
    Quét an toàn các tệp video trong root_folder:
    - Không theo Symbolic Links / NTFS Junctions (tránh thoát phạm vi & vòng lặp vô hạn)
    - Kiểm tra containment thực tế qua os.path.realpath
    - Bỏ qua thư mục con thiếu quyền truy cập mà không làm sập ứng dụng
    """
    abs_root = validate_directory_path(root_folder)
    real_root = os.path.normcase(os.path.realpath(abs_root))
    movies_data: dict[str, list[str]] = {}
    total_found = 0

    def _on_walk_error(_err):
        pass

    for current_dir, dirnames, filenames in os.walk(abs_root, followlinks=False, onerror=_on_walk_error):
        rel = os.path.relpath(current_dir, abs_root)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth >= max_depth:
            dirnames[:] = []
        else:
            safe_dirs = []
            for d in dirnames:
                cand_dir = os.path.join(current_dir, d)
                if is_reparse_point_or_symlink(cand_dir):
                    continue
                if not is_path_contained(cand_dir, real_root):
                    continue
                safe_dirs.append(d)
            dirnames[:] = safe_dirs

        if not is_path_contained(current_dir, real_root):
            continue

        group_videos: list[str] = []
        for fname in filenames:
            if not fname.lower().endswith(valid_extensions):
                continue
            full_path = os.path.normpath(os.path.join(current_dir, fname))
            if is_reparse_point_or_symlink(full_path):
                continue
            if not is_path_contained(full_path, real_root):
                continue
            group_videos.append(full_path)
            total_found += 1
            if total_found >= max_files:
                break

        if group_videos:
            group_name = "Tất cả tập phim" if rel == "." else rel
            movies_data[group_name] = sorted(group_videos)

        if total_found >= max_files:
            break

    return movies_data


class AuthorizedScope:
    """
    Quản lý danh sách thư mục và tệp video mà người dùng đã chủ động chọn/mở trong phiên làm việc.
    Ngăn mọi thao tác ghi/xóa/đổi tên lên các tệp ngoài phạm vi người dùng đã chọn.
    """

    def __init__(self):
        self._roots: set[str] = set()
        self._explicit_files: set[str] = set()

    def clear(self):
        self._roots.clear()
        self._explicit_files.clear()

    def authorize_directory(self, folder_path: str) -> str:
        abs_dir = validate_path(folder_path)
        real_dir = os.path.normcase(os.path.realpath(abs_dir))
        self._roots.add(real_dir)
        self._roots.add(os.path.normcase(abs_dir))
        return abs_dir

    def authorize_file(self, file_path: str) -> str:
        abs_file = validate_path(file_path)
        self._explicit_files.add(os.path.normcase(abs_file))
        self._explicit_files.add(os.path.normcase(os.path.realpath(abs_file)))
        return abs_file

    def authorize_files(self, paths: list[str]):
        for p in paths:
            self.authorize_file(p)

    def is_within_scope(self, path: str, resolve_symlink: bool = True) -> bool:
        try:
            abs_p = os.path.normcase(os.path.abspath(path))
        except Exception:
            return False

        candidates = [abs_p]
        if resolve_symlink:
            try:
                candidates.append(os.path.normcase(os.path.realpath(path)))
            except Exception:
                return False

        for cand in candidates:
            if cand in self._explicit_files:
                continue
            matched = False
            for root in self._roots:
                try:
                    if os.path.commonpath([cand, root]) == root:
                        matched = True
                        break
                except ValueError:
                    continue
            if not matched:
                return False
        return True


def _is_sharing_or_lock_error(exc: OSError) -> bool:
    winerr = getattr(exc, "winerror", None)
    if winerr in LOCKED_WINERRORS:
        return True
    if exc.errno in (errno.EACCES, errno.EBUSY):
        # Trên Windows, PermissionError có thể đi kèm WinError 32 khi file đang mở
        return winerr in LOCKED_WINERRORS
    return False


def _probe_file_unlocked(abs_path: str) -> None:
    """
    Kiểm tra nhanh tệp có đang bị tiến trình khác khóa độc quyền hay thiếu quyền trước khi gọi Shell API.
    """
    try:
        fd = os.open(abs_path, os.O_RDONLY)
        os.close(fd)
    except PermissionError as exc:
        if _is_sharing_or_lock_error(exc):
            raise FileSecurityError("file_locked", f"Tệp đang được tiến trình khác sử dụng: {os.path.basename(abs_path)}") from exc
        raise FileSecurityError("permission_denied", f"Không đủ quyền truy cập tệp: {os.path.basename(abs_path)}") from exc
    except FileNotFoundError as exc:
        raise FileSecurityError("not_found", f"Tệp không còn tồn tại: {abs_path}") from exc
    except OSError as exc:
        if _is_sharing_or_lock_error(exc):
            raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_path)}") from exc


def move_to_recycle_bin(file_path: str) -> None:
    """
    Chuyển tệp vào Windows Recycle Bin qua Win32 SHFileOperationW (cho phép người dùng khôi phục).
    Có cơ chế thử lại ngắn nếu VLC/Windows mới nhả file handle.
    """
    abs_path = validate_path(file_path)
    if not os.path.exists(abs_path):
        raise FileSecurityError("not_found", f"Tệp video không còn tồn tại: {abs_path}")

    if not sys.platform.startswith("win"):
        raise FileSecurityError("recycle_failed", "Recycle Bin chỉ khả dụng trên Windows.")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    sh_op = ctypes.windll.shell32.SHFileOperationW
    sh_op.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    sh_op.restype = ctypes.c_int

    retry_delays = (0.08, 0.15, 0.25, 0.4)
    last_rc = 0
    for attempt in range(len(retry_delays) + 1):
        try:
            _probe_file_unlocked(abs_path)
        except FileSecurityError as exc:
            if exc.code == "file_locked" and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            raise

        p_from = ctypes.create_unicode_buffer(abs_path + "\0\0")
        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = ctypes.cast(p_from, wintypes.LPCWSTR)
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None

        rc = sh_op(ctypes.byref(op))
        last_rc = rc
        if rc == 0 and not op.fAnyOperationsAborted and not os.path.exists(abs_path):
            return

        # 0x20 (32) = sharing violation / file in use
        if rc in (32, 33, 0x78) and attempt < len(retry_delays):
            time.sleep(retry_delays[attempt])
            continue
        break

    if last_rc in (5, 0x78):
        # Kiểm tra lại xem do khóa tệp hay do thiếu quyền thật
        try:
            with open(abs_path, "r+b"):
                pass
        except PermissionError as exc:
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_path)}") from exc
            raise FileSecurityError("permission_denied", f"Không đủ quyền xóa tệp: {os.path.basename(abs_path)}") from exc
        except OSError as exc:
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_path)}") from exc

    raise FileSecurityError(
        "recycle_failed",
        f"Không thể đưa tệp vào Recycle Bin (mã Win32: 0x{last_rc:X}).",
    )


def safe_delete_file(
    file_path: str,
    scope: AuthorizedScope | None = None,
    use_recycle_bin: bool = True,
    allow_outside_scope: bool = False,
) -> str:
    """
    Xóa tệp video an toàn:
    - Kiểm tra đường dẫn & phạm vi người dùng cho phép
    - Nếu là symlink/reparse point: chỉ gỡ liên kết, tuyệt đối không xóa tệp đích ngoài ý muốn
    - Mặc định chuyển vào Recycle Bin; có thể dùng xóa trực tiếp nếu người dùng đã xác nhận lại
    """
    abs_target = validate_path(file_path)

    if is_reparse_point_or_symlink(abs_target):
        parent_dir = os.path.dirname(abs_target)
        if scope is not None and not allow_outside_scope:
            if not scope.is_within_scope(parent_dir, resolve_symlink=True) and not scope.is_within_scope(abs_target, resolve_symlink=False):
                raise FileSecurityError("outside_scope", "Liên kết tệp nằm ngoài phạm vi thư mục đã mở.")
        try:
            os.unlink(abs_target)
            return abs_target
        except FileNotFoundError as exc:
            raise FileSecurityError("not_found", f"Liên kết tệp không còn tồn tại: {abs_target}") from exc
        except PermissionError as exc:
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", "Tệp đang được sử dụng bởi tiến trình khác.") from exc
            raise FileSecurityError("permission_denied", "Không đủ quyền xóa liên kết tệp.") from exc
        except OSError as exc:
            raise FileSecurityError("permission_denied", f"Không thể gỡ liên kết tệp: {exc}") from exc

    if scope is not None and not allow_outside_scope:
        if not scope.is_within_scope(abs_target, resolve_symlink=True):
            raise FileSecurityError("outside_scope", f"Tệp nằm ngoài phạm vi thư mục người dùng đã chọn: {abs_target}")

    if not os.path.exists(abs_target):
        raise FileSecurityError("not_found", f"Tệp video không còn tồn tại trên ổ đĩa: {abs_target}")

    if use_recycle_bin and sys.platform.startswith("win"):
        move_to_recycle_bin(abs_target)
        return abs_target

    retry_delays = (0.08, 0.15, 0.25, 0.4)
    for attempt in range(len(retry_delays) + 1):
        try:
            os.unlink(abs_target)
            return abs_target
        except FileNotFoundError as exc:
            raise FileSecurityError("not_found", f"Tệp video không còn tồn tại: {abs_target}") from exc
        except PermissionError as exc:
            if _is_sharing_or_lock_error(exc) and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_target)}") from exc
            raise FileSecurityError("permission_denied", f"Không đủ quyền xóa tệp: {os.path.basename(abs_target)}") from exc
        except OSError as exc:
            if _is_sharing_or_lock_error(exc) and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_target)}") from exc
            raise FileSecurityError("permission_denied", f"Không thể xóa tệp: {exc}") from exc

    raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_target)}")


def safe_rename_file(
    old_path: str,
    new_filename_raw: str,
    required_ext: str,
    scope: AuthorizedScope | None = None,
    allow_overwrite: bool = False,
    allow_outside_scope: bool = False,
) -> str:
    """
    Đổi tên tệp video an toàn trong cùng thư mục cha:
    - Chặn traversal, tên thiết bị Windows, symlink thoát phạm vi, và ghi đè nhầm tệp trùng tên
    - Thử lại ngắn nếu gặp lỗi chia sẻ/khóa tạm thời (WinError 32)
    """
    abs_old = validate_path(old_path)
    if not os.path.exists(abs_old):
        raise FileSecurityError("not_found", f"Tệp video không tồn tại trên ổ đĩa: {abs_old}")
    if is_reparse_point_or_symlink(abs_old):
        raise FileSecurityError("symlink", "Không cho phép đổi tên trực tiếp Symbolic Link / Reparse Point.")

    if scope is not None and not allow_outside_scope:
        if not scope.is_within_scope(abs_old, resolve_symlink=True):
            raise FileSecurityError("outside_scope", f"Tệp nằm ngoài phạm vi thư mục người dùng đã chọn: {abs_old}")

    new_name = validate_new_filename(new_filename_raw, required_ext)
    parent_dir = os.path.dirname(abs_old)
    abs_new = os.path.normpath(os.path.join(parent_dir, new_name))

    if not is_path_contained(parent_dir, parent_dir):
        raise FileSecurityError("invalid_path", "Thư mục đích không hợp lệ.")
    if os.path.dirname(abs_new) != parent_dir:
        raise FileSecurityError("traversal", "Tệp sau khi đổi tên bắt buộc phải nằm trong cùng thư mục gốc.")

    if abs_new == os.path.normpath(abs_old):
        return abs_new

    same_case_insensitive = os.path.normcase(abs_new) == os.path.normcase(abs_old)
    if os.path.exists(abs_new) and not same_case_insensitive and not allow_overwrite:
        raise FileSecurityError(
            "already_exists",
            f"Đã tồn tại một tệp khác cùng tên trong thư mục: {new_name}",
        )

    retry_delays = (0.08, 0.15, 0.25, 0.4)
    for attempt in range(len(retry_delays) + 1):
        try:
            os.rename(abs_old, abs_new)
            if scope is not None:
                scope.authorize_file(abs_new)
            return abs_new
        except FileNotFoundError as exc:
            raise FileSecurityError("not_found", f"Tệp gốc không còn tồn tại: {abs_old}") from exc
        except FileExistsError as exc:
            raise FileSecurityError("already_exists", f"Tệp đích đã tồn tại: {new_name}") from exc
        except PermissionError as exc:
            if _is_sharing_or_lock_error(exc) and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang được sử dụng bởi tiến trình khác: {os.path.basename(abs_old)}") from exc
            raise FileSecurityError("permission_denied", f"Không đủ quyền đổi tên tệp: {os.path.basename(abs_old)}") from exc
        except OSError as exc:
            if _is_sharing_or_lock_error(exc) and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            if _is_sharing_or_lock_error(exc):
                raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_old)}") from exc
            raise FileSecurityError("permission_denied", f"Hệ điều hành từ chối đổi tên tệp: {exc}") from exc

    raise FileSecurityError("file_locked", f"Tệp đang bị khóa bởi ứng dụng khác: {os.path.basename(abs_old)}")


def open_in_explorer_safely(file_path: str) -> bool:
    """
    Mở thư mục chứa tệp bằng API chính thức của Windows Shell (SHOpenFolderAndSelectItems),
    không bao giờ ghép đường dẫn người dùng vào chuỗi lệnh shell.
    """
    abs_path = validate_path(file_path)
    if not os.path.exists(abs_path):
        raise FileSecurityError("not_found", f"Tệp không tồn tại trên hệ thống: {abs_path}")

    if sys.platform.startswith("win"):
        ole32 = ctypes.windll.ole32
        shell32 = ctypes.windll.shell32
        ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        ole32.CoInitializeEx.restype = ctypes.HRESULT
        ole32.CoUninitialize.argtypes = []

        shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell32.ILCreateFromPathW.restype = ctypes.c_void_p
        shell32.SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD
        ]
        shell32.SHOpenFolderAndSelectItems.restype = ctypes.HRESULT
        shell32.ILFree.argtypes = [ctypes.c_void_p]

        pidl = None
        coinit_hr = ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
        try:
            pidl = shell32.ILCreateFromPathW(abs_path)
            if pidl:
                hr = shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
                if hr >= 0:
                    return True
        except Exception:
            pass
        finally:
            if pidl:
                shell32.ILFree(pidl)
            if coinit_hr in (0, 1):
                ole32.CoUninitialize()

        # Dự phòng an toàn với danh sách tham số (shell=False) nếu Shell COM gặp sự cố
        subprocess.Popen(["explorer.exe", f"/select,{abs_path}"], shell=False)
        return True

    folder = os.path.dirname(abs_path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", abs_path], shell=False)
    else:
        subprocess.Popen(["xdg-open", folder], shell=False)
    return True
