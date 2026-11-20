#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Automated Build & Release Orchestrator
Performs PyInstaller compilation, Inno Setup installer creation,
and generates release artifacts with build-info metadata.
"""

import os
import sys
import shutil
import subprocess
import hashlib
import time
import zipfile
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "Fluent Media Player"
APP_EXE_NAME = "FluentMediaPlayer.exe"
VERSION = "2.0.1"
DIST_DIR = os.path.join(ROOT_DIR, "dist", "FluentMediaPlayer")
BUILD_DIR = os.path.join(ROOT_DIR, "build")
RELEASE_DIR = os.path.join(ROOT_DIR, "release")
PORTABLE_DIR = os.path.join(RELEASE_DIR, "portable")
INSTALLER_DIR = os.path.join(RELEASE_DIR, "installer")


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def find_iscc() -> str | None:
    """Tìm đường dẫn trình biên dịch Inno Setup (ISCC.exe)."""
    # 1. Kiểm tra PATH
    path_iscc = shutil.which("iscc") or shutil.which("ISCC")
    if path_iscc and os.path.exists(path_iscc):
        return path_iscc

    # 2. Kiểm tra các thư mục cài đặt tiêu chuẩn
    candidate_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 5\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 5\ISCC.exe"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    return None


def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def step_preflight_checks():
    log("=== BƯỚC 1: KIỂM TRA MÔI TRƯỜNG VÀ TÀI NGUYÊN ===")
    assert os.path.exists(os.path.join(ROOT_DIR, "app.spec")), "Thiếu tệp app.spec"
    assert os.path.exists(os.path.join(ROOT_DIR, "file_version_info.txt")), "Thiếu tệp file_version_info.txt"
    assert os.path.exists(os.path.join(ROOT_DIR, "assets", "logo.ico")), "Thiếu tệp assets/logo.ico"
    assert os.path.exists(os.path.join(ROOT_DIR, "assets", "logo-transparent.png")), "Thiếu tệp assets/logo-transparent.png"
    assert os.path.exists(os.path.join(ROOT_DIR, "vlc")), "Thiếu thư mục vlc"
    assert os.path.exists(os.path.join(ROOT_DIR, "installer.iss")), "Thiếu tệp installer.iss"

    iscc_path = find_iscc()
    if iscc_path:
        log(f"✓ Tìm thấy Inno Setup: {iscc_path}")
    else:
        log("⚠ Cảnh báo: Không tìm thấy ISCC.exe (Inno Setup). Sẽ chỉ đóng gói PyInstaller.")
    return iscc_path


def step_clean_temp_build():
    log("=== BƯỚC 2: DỌN DẸP THƯ MỤC BUILD CŨ ===")
    for folder in [BUILD_DIR, os.path.join(ROOT_DIR, "dist")]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                log(f"✓ Đã dọn dẹp: {folder}")
            except Exception as e:
                log(f"⚠ Không thể dọn dẹp {folder}: {e}")


def step_build_pyinstaller():
    log("=== BƯỚC 3: BIÊN DỊCH ỨNG DỤNG BẰNG PYINSTALLER ===")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "app.spec",
        "--clean",
        "--noconfirm"
    ]
    log(f"Chạy lệnh: {' '.join(cmd)}")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        log("❌ LỖI: Biên dịch PyInstaller thất bại!")
        sys.exit(1)
    log(f"✓ Hoàn tất PyInstaller trong {time.time() - t0:.1f} giây")

    exe_path = os.path.join(DIST_DIR, APP_EXE_NAME)
    if not os.path.exists(exe_path):
        log(f"❌ LỖI: Không tìm thấy tệp thực thi đầu ra: {exe_path}")
        sys.exit(1)
    log(f"✓ Tệp thực thi đầu ra: {exe_path} ({os.path.getsize(exe_path):,} bytes)")

    try:
        from security import generate_integrity_manifest
        manifest_path = generate_integrity_manifest(
            DIST_DIR,
            os.path.join(DIST_DIR, "_internal", "integrity_manifest.json"),
        )
        log(f"✓ Đã tạo manifest kiểm tra toàn vẹn: {manifest_path}")
    except Exception as exc:
        log(f"⚠ Cảnh báo không thể tạo integrity_manifest.json: {exc}")


def step_build_installer(iscc_path: str):
    log("=== BƯỚC 4: TẠO BỘ CÀI ĐẶT WINDOWS (INNO SETUP) ===")
    if not iscc_path:
        log("Bỏ qua bước tạo bộ cài đặt vì không tìm thấy ISCC.exe.")
        return None

    os.makedirs(INSTALLER_DIR, exist_ok=True)
    iss_file = os.path.join(ROOT_DIR, "installer.iss")

    cmd = [iscc_path, iss_file]
    log(f"Chạy lệnh: {' '.join(cmd)}")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        log("❌ LỖI: Đóng gói Inno Setup thất bại!")
        sys.exit(1)

    setup_exe = os.path.join(INSTALLER_DIR, "FluentMediaPlayer-Setup.exe")
    if not os.path.exists(setup_exe):
        log(f"❌ LỖI: Không tìm thấy bộ cài đặt: {setup_exe}")
        sys.exit(1)

    log(f"✓ Hoàn tất Inno Setup trong {time.time() - t0:.1f} giây")
    log(f"✓ Bộ cài đặt đầu ra: {setup_exe} ({os.path.getsize(setup_exe):,} bytes)")
    return setup_exe


def step_build_portable():
    log("=== BƯỚC 5: ĐÓNG GÓI PHIÊN BẢN PORTABLE (FOLDER + ZIP) ===")
    os.makedirs(PORTABLE_DIR, exist_ok=True)

    portable_app_dir = os.path.join(PORTABLE_DIR, "FluentMediaPlayer-Portable")
    if os.path.exists(portable_app_dir):
        shutil.rmtree(portable_app_dir)
    shutil.copytree(DIST_DIR, portable_app_dir)

    # Tạo tệp đánh dấu portable.mode để lưu toàn bộ dữ liệu vào ./data và không ghi Registry
    marker_path = os.path.join(portable_app_dir, "portable.mode")
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write("Portable Mode Enabled - User data is stored in ./data\n")

    # Tạo hướng dẫn sử dụng nhanh cho bản Portable
    readme_portable_path = os.path.join(portable_app_dir, "README-Portable.txt")
    with open(readme_portable_path, "w", encoding="utf-8") as f:
        f.write(
            f"{APP_NAME} v{VERSION} (Portable Edition)\n"
            "============================================================\n\n"
            "1. Run FluentMediaPlayer.exe directly (no installation required).\n"
            "2. Watch history and cached thumbnails are stored locally in ./data\n"
            "   so you can copy or move this entire folder (e.g. to a USB drive).\n"
            "3. Portable mode is controlled by the presence of 'portable.mode'.\n"
            "   Do not remove 'portable.mode' if you want self-contained data storage.\n"
        )

    # Nén thành file .zip với thư mục gốc FluentMediaPlayer-Portable/ bên trong
    zip_filename = f"FluentMediaPlayer-{VERSION}-Portable.zip"
    zip_path = os.path.join(PORTABLE_DIR, zip_filename)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    log(f"Đang nén bản Portable thành: {zip_path} ...")
    t0 = time.time()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(portable_app_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                arcname = os.path.relpath(full_path, PORTABLE_DIR)
                zf.write(full_path, arcname)

    log(f"✓ Hoàn tất thư mục Portable: {portable_app_dir}")
    log(f"✓ Hoàn tất tệp nén Portable ZIP trong {time.time() - t0:.1f}s: {zip_path} ({os.path.getsize(zip_path):,} bytes)")
    return portable_app_dir, zip_path


def step_organize_release(portable_app_dir: str, portable_zip: str, setup_exe: str | None):
    log("=== BƯỚC 6: TẠO BUILD-INFO VÀ HOÀN THIỆN THƯ MỤC RELEASE ===")
    os.makedirs(RELEASE_DIR, exist_ok=True)

    # Dọn dẹp thư mục cũ release/FluentMediaPlayer nếu tồn tại từ các bản build trước
    stale_dir = os.path.join(RELEASE_DIR, "FluentMediaPlayer")
    if os.path.exists(stale_dir):
        shutil.rmtree(stale_dir)

    build_info_path = os.path.join(RELEASE_DIR, "build-info.txt")
    portable_exe_path = os.path.join(portable_app_dir, APP_EXE_NAME)
    portable_exe_size = f"{os.path.getsize(portable_exe_path):,} bytes" if os.path.exists(portable_exe_path) else "N/A"
    portable_exe_hash = calculate_sha256(portable_exe_path) if os.path.exists(portable_exe_path) else "N/A"

    zip_size = f"{os.path.getsize(portable_zip):,} bytes" if os.path.exists(portable_zip) else "N/A"
    zip_hash = calculate_sha256(portable_zip) if os.path.exists(portable_zip) else "N/A"

    setup_size_str = f"{os.path.getsize(setup_exe):,} bytes" if setup_exe and os.path.exists(setup_exe) else "N/A"
    setup_hash = calculate_sha256(setup_exe) if setup_exe and os.path.exists(setup_exe) else "N/A"
    git_commit = get_git_commit()

    info_text = f"""================================================================================
FLUENT MEDIA PLAYER - BUILD & RELEASE INFORMATION
================================================================================
Product Name         : {APP_NAME}
Product Version      : {VERSION}
Build Timestamp      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Git Commit           : {git_commit}
Python Environment   : Python {sys.version.split()[0]} ({sys.platform})
Packaging Types      : Portable Edition (Folder + ZIP) & Windows Installer (Inno Setup)

FILES & CHECKSUMS:
--------------------------------------------------------------------------------
1. Portable Application Folder:
   Path   : release/portable/FluentMediaPlayer-Portable/
   Binary : release/portable/FluentMediaPlayer-Portable/{APP_EXE_NAME}
   Size   : {portable_exe_size}
   SHA256 : {portable_exe_hash}

2. Portable Archive (ZIP):
   Path   : release/portable/{os.path.basename(portable_zip)}
   Size   : {zip_size}
   SHA256 : {zip_hash}

3. Windows Installer:
   Path   : release/installer/FluentMediaPlayer-Setup.exe
   Size   : {setup_size_str}
   SHA256 : {setup_hash}

SYSTEM REQUIREMENTS:
--------------------------------------------------------------------------------
- OS: Windows 10 (1809+) or Windows 11 (64-bit)
- Python Installed: Not required (fully self-contained runtime)
- Audio/Video Codecs: Embedded VLC engine (H.264, HEVC, VP9, AV1, MPEG, AAC, etc.)
================================================================================
"""
    with open(build_info_path, "w", encoding="utf-8") as f:
        f.write(info_text.strip() + "\n")
    log(f"✓ Đã tạo build-info.txt: {build_info_path}")


def main():
    log("==================================================")
    log("BẮT ĐẦU QUY TRÌNH ĐÓNG GÓI PORTABLE & WINDOWS INSTALLER")
    log("==================================================")
    t_start = time.time()

    iscc_path = step_preflight_checks()
    step_clean_temp_build()
    step_build_pyinstaller()
    setup_exe = step_build_installer(iscc_path)
    portable_app_dir, portable_zip = step_build_portable()
    step_organize_release(portable_app_dir, portable_zip, setup_exe)

    log("==================================================")
    log(f"🎉 TẤT CẢ CÁC BƯỚC ĐÓNG GÓI HOÀN TẤT THÀNH CÔNG TRONG {time.time() - t_start:.1f}s!")
    log("==================================================")


if __name__ == "__main__":
    main()
