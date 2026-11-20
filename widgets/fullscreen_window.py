#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Dedicated Borderless Fullscreen Window
Cửa sổ phát toàn màn hình chuyên biệt loại bỏ hoàn toàn viền cửa sổ Windows 11,
bo góc DWM và titlebar margins khi chuyển sang chế độ xem rạp toàn màn hình.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from utils import setup_window_icon


def _apply_win32_borderless_fullscreen(hwnd: int, screen) -> None:
    """
    Loại bỏ hoàn toàn DWM frame/rounded-corners/border và style khung Windows
    trên cửa sổ toàn màn hình, đồng thời căn khớp từng pixel với màn hình đích.
    """
    if not sys.platform.startswith("win") or not hwnd:
        return

    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_DONOTROUND = 1
        DWMWA_BORDER_COLOR = 34
        DWMWA_COLOR_NONE = 0xFFFFFFFE

        for attr, val in (
            (DWMWA_NCRENDERING_POLICY, DWMNCRP_DISABLED),
            (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND),
            (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE),
        ):
            v = wintypes.UINT(val)
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attr),
                ctypes.byref(v),
                ctypes.sizeof(v),
            )
    except Exception:
        pass

    try:
        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        GWL_STYLE = -16
        WS_BORDER = 0x00800000
        WS_DLGFRAME = 0x00400000
        WS_CAPTION = WS_BORDER | WS_DLGFRAME
        WS_SYSMENU = 0x00080000
        WS_THICKFRAME = 0x00040000
        FRAME_STYLES = WS_CAPTION | WS_THICKFRAME | WS_BORDER | WS_DLGFRAME | WS_SYSMENU

        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HMONITOR
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        h_wnd = wintypes.HWND(hwnd)
        cur_style = user32.GetWindowLongW(h_wnd, GWL_STYLE)
        clean_style = cur_style & ~FRAME_STYLES
        user32.SetWindowLongW(h_wnd, GWL_STYLE, clean_style)

        MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromWindow(h_wnd, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            x = int(mi.rcMonitor.left)
            y = int(mi.rcMonitor.top)
            w = int(mi.rcMonitor.right - mi.rcMonitor.left)
            h = int(mi.rcMonitor.bottom - mi.rcMonitor.top)
        elif screen is not None:
            sg = screen.geometry()
            dpr = screen.devicePixelRatio() if hasattr(screen, "devicePixelRatio") else 1.0
            x = int(round(sg.x() * dpr))
            y = int(round(sg.y() * dpr))
            w = int(round(sg.width() * dpr))
            h = int(round(sg.height() * dpr))
        else:
            return

        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(
            h_wnd,
            wintypes.HWND(0),
            x,
            y,
            w,
            h,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )
    except Exception:
        pass


class FullscreenVideoWindow(QWidget):
    """
    Cửa sổ toàn màn hình thực (FramelessWindowHint + DWM borderless) dành riêng cho phát video.
    Tách khỏi QMainWindow để giữ nguyên toàn bộ style/titlebar của cửa sổ chính khi thoát Fullscreen.
    """

    def __init__(self, parent_app):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.parent_app = parent_app
        self._closing_internally = False

        self.setWindowTitle("Fluent Media Player")
        self.setContentsMargins(0, 0, 0, 0)
        self.setMouseTracking(True)

        pal = self.palette()
        black = QColor("#000000")
        pal.setColor(QPalette.ColorRole.Window, black)
        pal.setColor(QPalette.ColorRole.Base, black)
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "background-color: #000000; border: none; outline: none; margin: 0px; padding: 0px;"
        )

        self.video_layout = QVBoxLayout(self)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setSpacing(0)

        self._init_shortcuts()

    def _init_shortcuts(self):
        shortcut_map = [
            ("Space", self.parent_app.toggle_play),
            ("Left", lambda: self.parent_app.seek_relative(-5)),
            ("Right", lambda: self.parent_app.seek_relative(5)),
            ("Up", lambda: self.parent_app.change_volume(5)),
            ("Down", lambda: self.parent_app.change_volume(-5)),
            ("M", self.parent_app.toggle_mute),
            ("F", self.parent_app.toggle_fullscreen),
            ("Escape", self.parent_app.exit_fullscreen),
            ("P", self.parent_app.play_prev_episode),
            ("Ctrl+Left", self.parent_app.play_prev_episode),
            ("N", self.parent_app.play_next_episode),
            ("Ctrl+Right", self.parent_app.play_next_episode),
            ("[", lambda: self.parent_app.adjust_speed(-0.25)),
            ("]", lambda: self.parent_app.adjust_speed(0.25)),
        ]
        for key, handler in shortcut_map:
            QShortcut(QKeySequence(key), self, handler)

    def enter_true_fullscreen(self, source_window: QWidget):
        """Đưa cửa sổ sang toàn màn hình không viền trên đúng màn hình của source_window."""
        screen = source_window.screen() if source_window is not None else QApplication.primaryScreen()
        if screen is not None:
            if self.windowHandle() is not None:
                self.windowHandle().setScreen(screen)
            self.setGeometry(screen.geometry())

        self.showFullScreen()
        self.raise_()
        self.activateWindow()

        fs_hwnd = int(self.winId())
        _apply_win32_borderless_fullscreen(fs_hwnd, screen)
        setup_window_icon(self, is_main_window=True)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.parent_app._on_video_mouse_moved()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.parent_app._on_video_mouse_moved()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.parent_app.exit_fullscreen()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.parent_app.change_volume(5)
        elif delta < 0:
            self.parent_app.change_volume(-5)
        event.accept()

    def changeEvent(self, event):
        super().changeEvent(event)
        if self._closing_internally:
            return
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                active_win = QApplication.activeWindow()
                fs_overlay = getattr(self.parent_app, "fs_overlay", None)
                if active_win is not fs_overlay and active_win is not self.parent_app:
                    self.parent_app._hide_main_overlays(mark_deactivated=True)
            else:
                self.parent_app._snapshot_activation_cursor()
        elif event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.parent_app._hide_main_overlays(mark_deactivated=True)

    def hideEvent(self, event):
        if not self._closing_internally:
            self.parent_app._hide_main_overlays(mark_deactivated=True)
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fs_overlay = getattr(self.parent_app, "fs_overlay", None)
        if fs_overlay is not None and fs_overlay.isVisible():
            fs_overlay.reposition()

    def moveEvent(self, event):
        super().moveEvent(event)
        fs_overlay = getattr(self.parent_app, "fs_overlay", None)
        if fs_overlay is not None and fs_overlay.isVisible():
            fs_overlay.reposition()

    def closeEvent(self, event):
        if self._closing_internally:
            event.accept()
            return
        self._closing_internally = True
        self.parent_app.is_fullscreen_mode = False
        self.parent_app.fullscreen_window = None
        event.accept()
        self.parent_app.close()
