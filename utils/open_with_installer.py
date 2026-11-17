import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import winreg
from config import VALID_VIDEO_EXTENSIONS, get_base_dir

def get_open_command() -> tuple[str, str]:
    """
    Trả về (command_string, icon_path) phù hợp với môi trường hiện tại (EXE hoặc Python script).
    """
    base_dir = get_base_dir()
    icon_path = os.path.join(base_dir, "assets", "logo.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "assets", "logo.png")

    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        cmd = f'"{exe_path}" "%1"'
        return cmd, exe_path
    else:
        # Nếu đang chạy Python script
        py_exe = sys.executable
        # Ưu tiên pythonw.exe nếu có để không bị nháy console khi mở video từ Explorer
        pyw_exe = os.path.join(os.path.dirname(py_exe), "pythonw.exe")
        runner = pyw_exe if os.path.exists(pyw_exe) else py_exe
        
        app_script = os.path.abspath(os.path.join(base_dir, "app.py"))
        cmd = f'"{runner}" "{app_script}" "%1"'
        return cmd, icon_path

def register_windows_open_with() -> bool:
    """
    Đăng ký ứng dụng vào danh sách 'Open With' (Mở bằng) của Windows thông qua HKCU (Current User).
    Hoàn toàn không yêu cầu quyền Administrator.
    """
    if not sys.platform.startswith("win"):
        return False

    cmd, icon_path = get_open_command()
    app_id = "FluentMediaPlayer.exe"
    prog_id = "FluentMediaPlayer.Video"

    try:
        # 1. Đăng ký Application trong HKCU\Software\Classes\Applications\FluentMediaPlayer.exe
        app_key_path = f"Software\\Classes\\Applications\\{app_id}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key_path) as key:
            winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, "Fluent Media Player")

        # shell\open\command
        cmd_key_path = f"{app_key_path}\\shell\\open\\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        # DefaultIcon
        if os.path.exists(icon_path):
            icon_key_path = f"{app_key_path}\\DefaultIcon"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, icon_key_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon_path}",0')

        # SupportedTypes
        sup_key_path = f"{app_key_path}\\SupportedTypes"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, sup_key_path) as key:
            for ext in VALID_VIDEO_EXTENSIONS:
                winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "")

        # 2. Đăng ký ProgID: FluentMediaPlayer.Video
        prog_key_path = f"Software\\Classes\\{prog_id}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Tệp Video - Fluent Media Player")
            winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ, "Video File")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{prog_key_path}\\shell\\open\\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        if os.path.exists(icon_path):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{prog_key_path}\\DefaultIcon") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon_path}",0')

        # 3. Gắn vào OpenWithList và OpenWithProgids cho từng định dạng video
        for ext in VALID_VIDEO_EXTENSIONS:
            # HKCU\Software\Classes\<ext>\OpenWithList\FluentMediaPlayer.exe
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}\\OpenWithList\\{app_id}") as key:
                pass

            # HKCU\Software\Classes\<ext>\OpenWithProgids\FluentMediaPlayer.Video
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}\\OpenWithProgids") as key:
                winreg.SetValueEx(key, prog_id, 0, winreg.REG_NONE, b"")

            # HKCU\Software\Classes\SystemFileAssociations\<ext>\OpenWithList\FluentMediaPlayer.exe
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\SystemFileAssociations\\{ext}\\OpenWithList\\{app_id}") as key:
                pass

        # 4. Gắn vào SystemFileAssociations\video
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\SystemFileAssociations\\video\\OpenWithList\\{app_id}") as key:
            pass

        # 5. Đăng ký Capabilities cho Windows Default Apps
        cap_path = "Software\\FluentMediaPlayer\\Capabilities"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_path) as key:
            winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "Fluent Media Player")
            winreg.SetValueEx(key, "ApplicationDescription", 0, winreg.REG_SZ, "Trình phát video hiện đại chất lượng cao")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{cap_path}\\FileAssociations") as key:
            for ext in VALID_VIDEO_EXTENSIONS:
                winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, prog_id)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\RegisteredApplications") as key:
            winreg.SetValueEx(key, "FluentMediaPlayer", 0, winreg.REG_SZ, cap_path)

        # 6. Đăng ký AppUserModelId để Windows Taskbar luôn nhận diện Icon chính xác
        aumid_path = "Software\\Classes\\AppUserModelId\\FluentMediaPlayer.App.1.0"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, aumid_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Fluent Media Player")
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon_path)
            winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "0")

        # Thông báo cho Windows Explorer làm mới shell association
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)  # SHCNE_ASSOCCHANGED
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Lỗi đăng ký Open With: {e}")
        return False

if __name__ == "__main__":
    success = register_windows_open_with()
    if success:
        print("Đăng ký Windows Open With thành công!")
    else:
        print("Đăng ký Windows Open With thất bại.")
