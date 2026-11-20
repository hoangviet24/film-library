import sys
import os
import ctypes

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(*args):
    if sys.stdout is None:
        return
    try:
        print(*args)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        text = " ".join(str(a) for a in args)
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))
    except Exception:
        pass
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

import config
from config import VALID_VIDEO_EXTENSIONS
from main_window import VideoPlayerApp
from utils import register_windows_open_with, setup_window_icon
from security import (
    FileSecurityError,
    clear_application_data,
    configure_secure_local_server,
    sanitize_for_log,
    validate_ipc_payload,
    validate_media_input,
    validate_video_path,
    verify_runtime_integrity,
)

# Đặt AppUserModelID cho Windows Taskbar & Explorer
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FluentMediaPlayer.App.1.0")
except Exception:
    pass

base_dir = config.get_base_dir()
LOGO_PATH = os.path.join(base_dir, "assets", "logo.png")
IPC_SERVER_NAME = "FluentMediaPlayer_SingleInstance_IPC"


def _open_video_path(player: VideoPlayerApp, path: str):
    """Xử lý mở và kiểm tra an toàn của tệp video được truyền từ File Explorer hoặc IPC."""
    try:
        safe_path = validate_media_input(path, VALID_VIDEO_EXTENSIONS)
    except FileSecurityError as exc:
        QMessageBox.warning(
            player,
            "Không thể mở tệp video",
            f"Tệp được yêu cầu không hợp lệ hoặc không an toàn:\n\n{sanitize_for_log(str(exc))}",
        )
        return False

    player.play_single_file(safe_path)
    return True


def main():
    # Xóa dữ liệu riêng của ứng dụng (lịch sử, cache, backup) nếu người dùng yêu cầu qua CLI
    if "--clear-app-data" in sys.argv:
        res = clear_application_data(config.user_data_dir, include_backups=True)
        _safe_print("Đã xóa dữ liệu ứng dụng:", ", ".join(res["removed"]) or "(trống)")
        if res["errors"]:
            _safe_print("Cảnh báo:", sanitize_for_log("; ".join(res["errors"])))
        sys.exit(0 if not res["errors"] else 1)

    # Kiểm tra lệnh đăng ký Open With từ dòng lệnh
    if "--register-open-with" in sys.argv:
        ok = register_windows_open_with()
        _safe_print("Đăng ký Windows Open With thành công!" if ok else "Đăng ký Windows Open With thất bại!")
        sys.exit(0 if ok else 1)

    # Kiểm tra tính toàn vẹn runtime cốt lõi (không làm gián đoạn môi trường dev)
    integrity_info = verify_runtime_integrity(base_dir)
    if not integrity_info["ok"]:
        for warn in integrity_info["warnings"]:
            _safe_print(f"[Cảnh báo toàn vẹn] {sanitize_for_log(warn)}")

    # Lấy và kiểm tra đường dẫn tệp video nếu được truyền vào từ File Explorer
    video_target = None
    cli_target_error = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip('"\'')
        if arg and not arg.startswith("--"):
            try:
                video_target = validate_video_path(arg, VALID_VIDEO_EXTENSIONS)
            except FileSecurityError as exc:
                cli_target_error = str(exc)

    # 1. Khởi tạo QApplication với PassThrough High-DPI để tránh sai lệch 1px ở viền trên Windows 11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # 2. Cơ chế Single Instance: Kiểm tra phiên bản đang chạy qua QLocalSocket
    socket = QLocalSocket(app)
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(600):
        if video_target:
            socket.write(video_target.encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)

    # 3. Khởi động QLocalServer giới hạn quyền theo User hiện tại (UserAccessOption)
    QLocalServer.removeServer(IPC_SERVER_NAME)
    server = QLocalServer(app)
    configure_secure_local_server(server)
    server.listen(IPC_SERVER_NAME)

    # 4. Khởi tạo ứng dụng chính (Primary Instance)
    player = VideoPlayerApp()

    # Cấu hình biểu tượng và Windows Taskbar Icon hoàn chỉnh
    setup_window_icon(player, app)

    def on_new_ipc_connection():
        client = server.nextPendingConnection()
        if client:
            if client.waitForReadyRead(1000):
                raw_bytes = bytes(client.readAll())
                safe_incoming = validate_ipc_payload(raw_bytes, VALID_VIDEO_EXTENSIONS, max_bytes=4096)
                if safe_incoming:
                    _open_video_path(player, safe_incoming)
            client.disconnectFromServer()

            # Kích hoạt đưa cửa sổ ứng dụng lên trên cùng
            if player.isMinimized():
                player.showNormal()
            player.show()
            player.raise_()
            player.activateWindow()

    server.newConnection.connect(on_new_ipc_connection)

    # 5. Tự động kiểm tra và đăng ký Windows Open With trong nền (HKCU) - bỏ qua ở chế độ Portable
    if not config.is_portable_mode():
        QTimer.singleShot(1200, register_windows_open_with)

    player.show()

    # 6. Nếu mở ứng dụng lần đầu bằng tệp video từ Explorer, kiểm tra & phát an toàn
    if video_target:
        QTimer.singleShot(150, lambda: _open_video_path(player, video_target))
    elif cli_target_error:
        QTimer.singleShot(
            150,
            lambda: QMessageBox.warning(
                player,
                "Không thể mở tệp video",
                sanitize_for_log(cli_target_error),
            ),
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        _safe_print("-------Error----------")
        _safe_print(sanitize_for_log(traceback.format_exc()))
        _safe_print("-------Error----------")
        is_cli_mode = any(flag in sys.argv for flag in ("--clear-app-data", "--register-open-with"))
        if (
            not is_cli_mode
            and sys.stdin is not None
            and not sys.stdin.closed
            and getattr(sys.stdin, "isatty", lambda: False)()
        ):
            input("Press Enter to exit....")
        sys.exit(1)
