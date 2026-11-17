import sys
import os
import ctypes
from ctypes import wintypes
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget, QApplication
import config

APP_USER_MODEL_ID = "FluentMediaPlayer.App.1.0"

def get_app_icon() -> QIcon:
    """
    Tạo đối tượng QIcon chất lượng cao chứa đầy đủ các kích thước chuẩn Windows
    từ logo.ico và logo-transparent.png.
    """
    base_dir = config.get_base_dir()
    ico_path = os.path.join(base_dir, "assets", "logo.ico")
    transparent_png = os.path.join(base_dir, "assets", "logo-transparent.png")
    fallback_png = os.path.join(base_dir, "assets", "logo.png")

    icon = QIcon()
    if os.path.exists(ico_path):
        icon.addFile(ico_path)
    if os.path.exists(transparent_png):
        icon.addFile(transparent_png)
    elif os.path.exists(fallback_png):
        icon.addFile(fallback_png)

    return icon


def apply_windows_taskbar_icon(window: QWidget, app_id: str = APP_USER_MODEL_ID, is_main_window: bool = True):
    """
    Tích hợp sâu biểu tượng ứng dụng vào Windows Taskbar thông qua Win32 API:
    1. Thiết lập explicit Win32 HWND Icons (WM_SETICON cho ICON_BIG 32x32 và ICON_SMALL 16x16)
    2. Ghi đè Class Icon của cửa sổ (SetClassLongPtrW với GCLP_HICON và GCLP_HICONSM)
    3. Gán Shell Property Store (SHGetPropertyStoreForWindow) với PKEY_AppUserModel_ID
       và PKEY_AppUserModel_RelaunchIconResource, ngăn chặn tuyệt đối việc Windows Taskbar
       hiển thị biểu tượng mặc định của python.exe.
    """
    if not sys.platform.startswith("win"):
        return

    base_dir = config.get_base_dir()
    ico_path = os.path.abspath(os.path.join(base_dir, "assets", "logo.ico"))
    if not os.path.exists(ico_path):
        return

    try:
        hwnd = int(window.winId())
        if not hwnd:
            return
    except Exception:
        return

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    # 1. Nạp Win32 HICON chuẩn cho Taskbar (32x32) và Titlebar (16x16)
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010
    h_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
    h_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1

    if h_big:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
    if h_small:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)

    if not is_main_window:
        return

    # 2. Ghi đè Window Class Icon trong Win32 để Windows Taskbar và Alt-Tab luôn nhận diện đúng
    GCLP_HICON = -14
    GCLP_HICONSM = -34
    try:
        if hasattr(user32, 'SetClassLongPtrW'):
            SetClassLong = user32.SetClassLongPtrW
            SetClassLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            SetClassLong.restype = ctypes.c_void_p
        else:
            SetClassLong = user32.SetClassLongW
            SetClassLong.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            SetClassLong.restype = wintypes.LONG

        if h_big:
            SetClassLong(hwnd, GCLP_HICON, h_big)
        if h_small:
            SetClassLong(hwnd, GCLP_HICONSM, h_small)
    except Exception:
        pass

    # 3. Gán Shell Property Store (PKEY_AppUserModel_ID & PKEY_AppUserModel_RelaunchIconResource)
    try:
        class GUID(ctypes.Structure):
            _fields_ = [
                ('Data1', wintypes.DWORD),
                ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD),
                ('Data4', ctypes.c_byte * 8)
            ]

        class PROPERTYKEY(ctypes.Structure):
            _fields_ = [
                ('fmtid', GUID),
                ('pid', wintypes.DWORD)
            ]

        PKEY_AppUserModel_ID = PROPERTYKEY(
            GUID(0x9F4C2855, 0x9F79, 0x4B39, (ctypes.c_byte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
            5
        )

        PKEY_AppUserModel_RelaunchIconResource = PROPERTYKEY(
            GUID(0x9F4C2855, 0x9F79, 0x4B39, (ctypes.c_byte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
            2
        )

        class PROPVARIANT(ctypes.Structure):
            _fields_ = [
                ('vt', ctypes.c_ushort),
                ('wReserved1', wintypes.WORD),
                ('wReserved2', wintypes.WORD),
                ('wReserved3', wintypes.WORD),
                ('pwszVal', wintypes.LPWSTR),
                ('dummy', ctypes.c_longlong)
            ]

        class IPropertyStoreVtbl(ctypes.Structure):
            pass

        class IPropertyStore(ctypes.Structure):
            pass

        ReleaseFunc = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
        SetValueFunc = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))
        CommitFunc = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)

        IPropertyStoreVtbl._fields_ = [
            ('QueryInterface', ctypes.c_void_p),
            ('AddRef', ctypes.c_void_p),
            ('Release', ReleaseFunc),
            ('GetCount', ctypes.c_void_p),
            ('GetAt', ctypes.c_void_p),
            ('GetValue', ctypes.c_void_p),
            ('SetValue', SetValueFunc),
            ('Commit', CommitFunc)
        ]
        IPropertyStore._fields_ = [('lpVtbl', ctypes.POINTER(IPropertyStoreVtbl))]

        IID_IPropertyStore = GUID(0x886d8eeb, 0x8cf2, 0x4446, (ctypes.c_byte * 8)(0x8d, 0x02, 0xcd, 0xba, 0x1d, 0xbd, 0xcf, 0x99))

        pPropStore = ctypes.POINTER(IPropertyStore)()
        hr = shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(IID_IPropertyStore), ctypes.byref(pPropStore))
        if hr == 0 and pPropStore:
            # Gán AppUserModelID
            pv_id = PROPVARIANT()
            pv_id.vt = 31  # VT_LPWSTR
            pv_id.pwszVal = app_id
            pPropStore.contents.lpVtbl.contents.SetValue(pPropStore, ctypes.byref(PKEY_AppUserModel_ID), ctypes.byref(pv_id))

            # Gán Icon Resource
            pv_icon = PROPVARIANT()
            pv_icon.vt = 31
            pv_icon.pwszVal = f"{ico_path},0"
            pPropStore.contents.lpVtbl.contents.SetValue(pPropStore, ctypes.byref(PKEY_AppUserModel_RelaunchIconResource), ctypes.byref(pv_icon))

            pPropStore.contents.lpVtbl.contents.Commit(pPropStore)
            pPropStore.contents.lpVtbl.contents.Release(pPropStore)
    except Exception:
        pass


def setup_window_icon(window: QWidget, app: QApplication = None, is_main_window: bool = True):
    """
    Cấu hình toàn diện biểu tượng cửa sổ và Taskbar cho ứng dụng.
    """
    icon = get_app_icon()
    if app is not None:
        app.setWindowIcon(icon)
    window.setWindowIcon(icon)
    apply_windows_taskbar_icon(window, is_main_window=is_main_window)
