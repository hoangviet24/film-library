import os
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QIcon, QWheelEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from .overlay_panel import VideoOverlayPanel

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
        
        self.setWindowTitle("Mini Player - Fluent Media Player")
        self.setGeometry(1000, 500, 520, 292)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
        self.setStyleSheet("background-color: #000000;")

        # Gắn icon cho cửa sổ Pop-out
        if os.path.exists(_LOGO_PATH):
            self.setWindowIcon(QIcon(_LOGO_PATH))

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

    def eventFilter(self, source, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
            self.overlay.show_overlay()
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            self.parent_app.restore_video_from_popout()
            return True
        elif event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            if delta > 0:
                self.parent_app.change_volume(5)
            elif delta < 0:
                self.parent_app.change_volume(-5)
            return True
        return super().eventFilter(source, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.overlay.reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.reposition()

    def show_overlay(self):
        self.overlay.show_overlay()

    def update_play_button(self, is_playing: bool):
        self.overlay.update_play_button(is_playing)

    def closeEvent(self, event):
        self.overlay.hide()
        self.overlay.close()
        if getattr(self.parent_app, "popout_window", None) is self:
            self.parent_app.restore_video_from_popout()
        event.accept()
