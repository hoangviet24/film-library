import os
import sys
import ctypes

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # Đường dẫn của thư mục chứa file app.exe
        exe_dir = os.path.dirname(sys.executable)
        
        # Kiểm tra nếu PyInstaller để vlc trong thư mục _internal
        internal_vlc = os.path.join(exe_dir, "_internal", "vlc")
        if os.path.exists(internal_vlc):
            return os.path.join(exe_dir, "_internal")
            
        return exe_dir
    return os.path.dirname(os.path.abspath(__file__))

# Tắt log bằng biến môi trường chuẩn của VLC (không dùng tham số CLI)
os.environ["VLC_VERBOSE"] = "-1"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"

app_dir = get_base_dir()
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
            ctypes.CDLL(os.path.join(VLC_PATH, "libvlccore.dll"))
            ctypes.CDLL(os.path.join(VLC_PATH, "libvlc.dll"))
        except Exception as e:
            print(f"Lỗi nạp DLL: {e}")

HISTORY_FILE = os.path.join(app_dir, "video_history.json")
THUMB_CACHE_DIR = os.path.join(app_dir, "thumb_cache")
VALID_VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')

os.makedirs(THUMB_CACHE_DIR, exist_ok=True)