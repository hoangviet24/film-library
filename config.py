import os
import sys
import ctypes
from security import is_directory_writable, sanitize_for_log, verify_contained_file

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # Đường dẫn của thư mục chứa file FluentMediaPlayer.exe
        exe_dir = os.path.dirname(sys.executable)
        
        # Kiểm tra nếu PyInstaller để vlc trong thư mục _internal
        internal_vlc = os.path.join(exe_dir, "_internal", "vlc")
        if os.path.exists(internal_vlc):
            return os.path.join(exe_dir, "_internal")
            
        return exe_dir
    return os.path.dirname(os.path.abspath(__file__))

def is_portable_mode() -> bool:
    """
    Kiểm tra xem ứng dụng có đang chạy ở chế độ Portable hay không
    (dựa vào sự tồn tại của tệp đánh dấu `portable.mode` cạnh FluentMediaPlayer.exe).
    """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.exists(os.path.join(exe_dir, "portable.mode"))
    return False

def get_user_data_dir():
    """
    Trả về thư mục lưu trữ dữ liệu người dùng (lịch sử, cache).
    - Ở chế độ Portable (có file portable.mode): lưu tại thư mục `data/` cạnh file .exe nếu có quyền ghi.
    - Ở chế độ Cài đặt (Program Files): lưu vào %APPDATA%\\FluentMediaPlayer để hoạt động dưới quyền Standard User.
    - Ở môi trường dev (chạy source): lưu tại thư mục dự án.
    """
    if getattr(sys, 'frozen', False):
        if is_portable_mode():
            portable_data = os.path.join(os.path.dirname(sys.executable), "data")
            try:
                os.makedirs(portable_data, exist_ok=True)
                if is_directory_writable(portable_data):
                    return portable_data
            except OSError:
                pass
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(appdata, "FluentMediaPlayer")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    return get_base_dir()

# Tắt log bằng biến môi trường chuẩn của VLC (không dùng tham số CLI)
os.environ["VLC_VERBOSE"] = "-1"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"

app_dir = get_base_dir()
user_data_dir = get_user_data_dir()
VLC_PATH = os.path.join(app_dir, "vlc")

if sys.platform.startswith("win"):
    if os.path.exists(VLC_PATH):
        os.environ['PATH'] = VLC_PATH + os.pathsep + os.environ['PATH']
        os.environ['VLC_PLUGIN_PATH'] = os.path.join(VLC_PATH, 'plugins')
        try:
            os.add_dll_directory(VLC_PATH)
        except AttributeError:
            pass
            
        try:
            for dll_name in ("libvlccore.dll", "libvlc.dll"):
                dll_path = os.path.join(VLC_PATH, dll_name)
                if verify_contained_file(dll_path, VLC_PATH):
                    ctypes.CDLL(dll_path)
                else:
                    raise RuntimeError(f"Thư viện runtime không hợp lệ: {dll_name}")
        except Exception as e:
            print(f"Lỗi nạp DLL: {sanitize_for_log(str(e))}")

HISTORY_FILE = os.path.join(user_data_dir, "video_history.json")
DB_FILE = os.path.join(user_data_dir, "library.db")
BACKUP_DIR = os.path.join(user_data_dir, "backups")
THUMB_CACHE_DIR = os.path.join(user_data_dir, "thumb_cache")
VALID_VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.ts')

ASSETS_DIR = os.path.join(app_dir, "assets")
LOGO_ICO_PATH = os.path.join(ASSETS_DIR, "logo.ico")
LOGO_TRANSPARENT_PATH = os.path.join(ASSETS_DIR, "logo-transparent.png")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)