import os
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QIcon, QWheelEvent, QCursor
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from .overlay_panel import VideoOverlayPanel
from utils import get_app_icon
_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")

class FloatingVideoWindow(QWidget):
    """
    Cửa sổ Pop-out / Mini Player (Picture-in-Picture) luôn nổi trên các cửa sổ khác:
    - VideoOverlayPanel độc lập tích hợp Seek Slider và nút điều khiển
    - Hỗ trợ cuộn chuột trên cửa sổ nổi để tăng/giảm âm lượng tức thì
    - Đúp chuột hoặc bấm 'Thu hồi' để đưa video về cửa sổ chính
    """
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self._awaiting_user_interaction = False
        self._activation_cursor_pos = None
        
        self.setWindowTitle("Mini Player - Fluent Media Player")
        self.setGeometry(1000, 500, 520, 292)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
        self.setStyleSheet("background-color: #000000;")

        # Gắn biểu tượng cho cửa sổ Pop-out
        self.setWindowIcon(get_app_icon())

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Khung chứa video được reparent sang
        self.video_holder = QWidget(self)
        self.video_holder_layout = QVBoxLayout(self.video_holder)
        self.video_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.video_holder)

        # Overlay điều khiển nổi độc lập
        self.overlay = VideoOverlayPanel(self, self.parent_app, mode="popout")

        self.setMouseTracking(True)
        self.installEventFilter(self)

    def hide_overlay(self):
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.hide_overlay()

    def mark_deactivated(self):
        self._awaiting_user_interaction = True
        self._activation_cursor_pos = None

    def snapshot_activation_cursor(self):
        self._activation_cursor_pos = QCursor.pos()

    def _consume_hover_interaction(self) -> bool:
        app = QApplication.instance()
        if app is None or app.applicationState() != Qt.ApplicationState.ApplicationActive:
            return False
        if not self.isVisible() or self.isMinimized() or not self.isActiveWindow():
            return False
        if self._awaiting_user_interaction:
            cur_pos = QCursor.pos()
            if self._activation_cursor_pos is None:
                self._activation_cursor_pos = cur_pos
                return False
            if (cur_pos - self._activation_cursor_pos).manhattanLength() < 2:
                return False
            self._awaiting_user_interaction = False
        return True

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if QApplication.activeWindow() is not self.overlay:
                    self.hide_overlay()
                    self.mark_deactivated()
            else:
                self.snapshot_activation_cursor()
        elif event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide_overlay()
            self.mark_deactivated()

    def hideEvent(self, event):
        self.hide_overlay()
        self.mark_deactivated()
        super().hideEvent(event)

    def eventFilter(self, source, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
            if self._consume_hover_interaction():
                self.overlay.show_overlay()
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            self._awaiting_user_interaction = False
            self.parent_app.restore_video_from_popout()
            return True
        elif event.type() == QEvent.Type.Wheel:
            self._awaiting_user_interaction = False
            delta = event.angleDelta().y()
            if delta > 0:
                self.parent_app.change_volume(5)
            elif delta < 0:
                self.parent_app.change_volume(-5)
            return True
        return super().eventFilter(source, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.overlay.isVisible():
            self.overlay.reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay.isVisible():
            self.overlay.reposition()

    def show_overlay(self):
        if self.isActiveWindow():
            self._awaiting_user_interaction = False
            self.overlay.show_overlay()

    def update_play_button(self, is_playing: bool):
        self.overlay.update_play_button(is_playing)

    def closeEvent(self, event):
        self.overlay.hide_overlay()
        self.overlay.close()
        if getattr(self.parent_app, "popout_window", None) is self:
            self.parent_app.restore_video_from_popout()
        event.accept()
