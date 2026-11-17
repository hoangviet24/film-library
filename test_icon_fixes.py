import os
import sys
import ctypes
from ctypes import wintypes
from PIL import Image
import numpy as np

# Đảm bảo đường dẫn root có trong sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import config
from utils.window_icon import (
    get_app_icon, apply_windows_taskbar_icon, setup_window_icon,
    APP_USER_MODEL_ID
)
from utils.open_with_installer import register_windows_open_with
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from main_window import VideoPlayerApp


def test_icon_suite():
    print("=== STARTING TASKBAR ICON & TRANSPARENT LOGO TEST SUITE ===")

    # 1. Kiểm tra logo-transparent.png
    print("\n--- 1. Testing logo-transparent.png ---")
    trans_path = os.path.join(root_dir, "assets", "logo-transparent.png")
    assert os.path.exists(trans_path), f"File {trans_path} must exist"

    im_trans = Image.open(trans_path)
    assert im_trans.format == "PNG", f"Expected PNG, got {im_trans.format}"
    assert im_trans.size[0] >= 1024 and im_trans.size[1] >= 1024, f"Expected >= 1024x1024, got {im_trans.size}"
    assert im_trans.mode == "RGBA", f"Expected RGBA mode, got {im_trans.mode}"

    arr = np.array(im_trans)
    alpha = arr[:, :, 3]
    assert alpha.min() == 0, "Alpha channel must have fully transparent pixels (min == 0)"
    assert alpha.max() == 255, "Alpha channel must have fully opaque pixels (max == 255)"
    unique_alphas = len(np.unique(alpha))
    assert unique_alphas > 50, f"Expected smooth anti-aliased alpha levels, got {unique_alphas}"
    print(f"✓ logo-transparent.png is valid: {im_trans.size}, {im_trans.mode}, {unique_alphas} alpha levels")

    # 2. Kiểm tra logo.ico
    print("\n--- 2. Testing logo.ico ---")
    ico_path = os.path.join(root_dir, "assets", "logo.ico")
    assert os.path.exists(ico_path), f"File {ico_path} must exist"

    im_ico = Image.open(ico_path)
    assert im_ico.format == "ICO", f"Expected ICO, got {im_ico.format}"
    expected_sizes = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
    actual_sizes = set(im_ico.info.get("sizes", []))
    assert expected_sizes.issubset(actual_sizes), f"Missing standard sizes: {expected_sizes - actual_sizes}"
    print(f"✓ logo.ico contains all 7 Windows standard sizes: {actual_sizes}")

    # 3. Khởi tạo QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # 4. Kiểm tra get_app_icon
    print("\n--- 3. Testing QIcon creation ---")
    app_icon = get_app_icon()
    assert not app_icon.isNull(), "QIcon must not be null"
    pix16 = app_icon.pixmap(16, 16)
    pix32 = app_icon.pixmap(32, 32)
    pix256 = app_icon.pixmap(256, 256)
    assert not pix16.isNull() and not pix32.isNull() and not pix256.isNull(), "QIcon pixmaps must render cleanly"
    print("✓ get_app_icon renders 16x16, 32x32, 256x256 pixmaps cleanly")

    # 5. Kiểm tra Main Window Icon & Win32 Taskbar Properties
    print("\n--- 4. Testing Main Window Taskbar & Win32 Integration ---")
    player = VideoPlayerApp()
    player.show()
    app.processEvents()

    hwnd = int(player.winId())
    user32 = ctypes.windll.user32
    WM_GETICON = 0x007F
    ICON_SMALL = 0
    ICON_BIG = 1

    h_big = user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
    h_small = user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
    assert h_big != 0, "WM_GETICON(ICON_BIG) must return a valid HICON handle"
    assert h_small != 0, "WM_GETICON(ICON_SMALL) must return a valid HICON handle"

    GCLP_HICON = -14
    GCLP_HICONSM = -34
    GetClassLongPtr = user32.GetClassLongPtrW if hasattr(user32, 'GetClassLongPtrW') else user32.GetClassLongW
    class_hicon = GetClassLongPtr(hwnd, GCLP_HICON)
    class_hiconsm = GetClassLongPtr(hwnd, GCLP_HICONSM)
    assert class_hicon != 0, "GCLP_HICON must be set on window class"
    assert class_hiconsm != 0, "GCLP_HICONSM must be set on window class"
    print(f"✓ Win32 HWND Icons confirmed: BIG={h_big}, SMALL={h_small}, CLASS={class_hicon}")

    # 6. Kiểm tra Minimize và Restore
    print("\n--- 5. Testing Minimize & Restore state ---")
    player.showMinimized()
    app.processEvents()
    player.showNormal()
    app.processEvents()
    h_big_after = user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
    assert h_big_after != 0, "Icon must persist after minimize & restore"
    print("✓ Icon persists cleanly after minimize and restore")

    # 7. Kiểm tra Popup Mode (FloatingVideoWindow)
    print("\n--- 6. Testing Popup Mode Window Icon ---")
    player.open_popout_video()
    app.processEvents()
    popout = player.popout_window
    assert popout is not None, "Popup window must be instantiated"
    pop_hwnd = int(popout.winId())
    pop_hbig = user32.SendMessageW(pop_hwnd, WM_GETICON, ICON_BIG, 0)
    assert pop_hbig != 0, "Popup window must have its own valid HICON"
    print(f"✓ Popup window icon confirmed: BIG={pop_hbig}")
    player.restore_video_from_popout()
    app.processEvents()

    # 8. Kiểm tra Windows Registry
    print("\n--- 7. Testing Registry AppUserModelId Registration ---")
    reg_ok = register_windows_open_with()
    assert reg_ok is True, "register_windows_open_with must succeed"
    print("✓ Registry AppUserModelId and Open With keys verified")

    player.close()
    app.processEvents()
    print("\n=== ALL ICON AND TASKBAR TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    test_icon_suite()
