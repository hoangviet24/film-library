import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
import config  # Nạp cấu hình & đường dẫn VLC
from main_window import VideoPlayerApp
# Đặt AppUserModelID cho Windows
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FluentMediaPlayer.App.1.0")
except Exception:
    pass

# Lấy đường dẫn root chuẩn
base_dir = config.get_base_dir()
LOGO_PATH = os.path.join(base_dir, "assets", "logo.png")


def main():
    app = QApplication(sys.argv)

    if os.path.exists(LOGO_PATH):
        app_icon = QIcon(LOGO_PATH)
        app.setWindowIcon(app_icon)

    player = VideoPlayerApp()

    if os.path.exists(LOGO_PATH):
        player.setWindowIcon(QIcon(LOGO_PATH))

    player.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("-------Error----------")
        print(traceback.format_exc())
        print("-------Error----------")
        
        # Đảm bảo chỉ gọi input() nếu stdin thực sự tồn tại (khi bật console)
        if sys.stdin and not sys.stdin.closed:
            input("Press Enter to exit....")