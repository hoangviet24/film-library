import sys
import os
import ctypes
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

import config
from config import VALID_VIDEO_EXTENSIONS
from main_window import VideoPlayerApp
from utils import register_windows_open_with, setup_window_icon

# Đặt AppUserModelID cho Windows Taskbar & Explorer
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FluentMediaPlayer.App.1.0")
except Exception:
    pass

base_dir = config.get_base_dir()
LOGO_PATH = os.path.join(base_dir, "assets", "logo.png")
IPC_SERVER_NAME = "FluentMediaPlayer_SingleInstance_IPC"


def _open_video_path(player: VideoPlayerApp, path: str):
    """Xử lý mở và kiểm tra tính hợp lệ của tệp video được truyền từ File Explorer."""
    path = os.path.abspath(path.strip('\"\''))
    if not os.path.exists(path):
        QMessageBox.warning(
            player,
            "Không tìm thấy tệp",
            f"Tệp video sau không tồn tại trên hệ thống:\n\n{path}"
        )
        return False

    if not path.lower().endswith(VALID_VIDEO_EXTENSIONS):
        ext_list = ", ".join(VALID_VIDEO_EXTENSIONS)
        QMessageBox.warning(
            player,
            "Định dạng không hỗ trợ",
            f"Ứng dụng hiện không hỗ trợ định dạng tệp này:\n{path}\n\nCác định dạng được hỗ trợ: {ext_list}"
        )
        return False

    player.play_single_file(path)
    return True


def main():
    # Kiểm tra lệnh đăng ký Open With từ dòng lệnh
    if "--register-open-with" in sys.argv:
        ok = register_windows_open_with()
        print("Đăng ký Windows Open With thành công!" if ok else "Đăng ký Windows Open With thất bại!")
        sys.exit(0 if ok else 1)

    # Lấy đường dẫn tệp video nếu được truyền vào từ File Explorer
    video_target = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip('\"\'')
        if not arg.startswith("--"):
            video_target = os.path.abspath(arg)

    # 1. Khởi tạo QApplication trước để hỗ trợ event loop và QLocalSocket
    app = QApplication(sys.argv)

    # 2. Cơ chế Single Instance: Kiểm tra phiên bản đang chạy qua QLocalSocket
    socket = QLocalSocket(app)
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(600):
        # Ứng dụng đã có một instance đang chạy -> gửi đường dẫn video sang instance đó
        if video_target:
            socket.write(video_target.encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)

    # 3. Khởi động QLocalServer ngay lập tức để đón nhận các instance tiếp theo
    QLocalServer.removeServer(IPC_SERVER_NAME)
    server = QLocalServer(app)
    server.listen(IPC_SERVER_NAME)

    # 4. Khởi tạo ứng dụng chính (Primary Instance)
    player = VideoPlayerApp()

    # Cấu hình biểu tượng và Windows Taskbar Icon hoàn chỉnh
    setup_window_icon(player, app)

    def on_new_ipc_connection():
        client = server.nextPendingConnection()
        if client:
            if client.waitForReadyRead(1000):
                incoming_data = bytes(client.readAll()).decode("utf-8", errors="ignore").strip()
                if incoming_data:
                    _open_video_path(player, incoming_data)
            client.disconnectFromServer()

            # Kích hoạt đưa cửa sổ ứng dụng lên trên cùng
            if player.isMinimized():
                player.showNormal()
            player.show()
            player.raise_()
            player.activateWindow()

    server.newConnection.connect(on_new_ipc_connection)

    # 4. Tự động kiểm tra và đăng ký Windows Open With trong nền (HKCU)
    QTimer.singleShot(1200, register_windows_open_with)

    player.show()

    # 5. Nếu mở ứng dụng lần đầu bằng tệp video từ Explorer, tự động phát ngay
    if video_target:
        QTimer.singleShot(150, lambda: _open_video_path(player, video_target))

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("-------Error----------")
        print(traceback.format_exc())
        print("-------Error----------")
        if sys.stdin and not sys.stdin.closed:
            input("Press Enter to exit....")
