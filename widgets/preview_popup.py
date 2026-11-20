from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QFrame

class VideoThumbnailPreview(QWidget):
    """
    Cửa sổ hiển thị ảnh xem trước (Thumbnail Preview) và mốc thời gian khi hover Seekbar
    theo phong cách chuẩn YouTube và Netflix:
    - Bo góc, viền kính mờ hiện đại đồng bộ Dark Theme
    - Tự động căn chỉnh vị trí theo con trỏ chuột, chống tràn màn hình (Screen Bounds Clamping)
    - Tách biệt luồng giải mã giúp không gián đoạn video đang phát
    """
    def __init__(self, parent=None):
        flags = (
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("PreviewCard")
        self.card.setStyleSheet("""
            QFrame#PreviewCard {
                background-color: #181818;
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 9px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(4)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Khung chứa ảnh Thumbnail (160x90 px - chuẩn 16:9)
        self.lbl_thumb = QLabel(self.card)
        self.lbl_thumb.setFixedSize(160, 90)
        self.lbl_thumb.setScaledContents(True)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet("""
            QLabel {
                background-color: #0E0E0E;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        card_layout.addWidget(self.lbl_thumb)

        # Nhãn thời gian hiển thị (Timestamp)
        self.lbl_time = QLabel("00:00", self.card)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Consolas', monospace, 'Segoe UI';
                background: transparent;
                border: none;
                margin-top: 1px;
            }
        """)
        card_layout.addWidget(self.lbl_time)

        main_layout.addWidget(self.card)
        self.adjustSize()

    def is_owner_window_active(self) -> bool:
        app = QApplication.instance()
        if app is None or app.applicationState() != Qt.ApplicationState.ApplicationActive:
            return False
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "is_owner_window_active"):
            return parent.is_owner_window_active()
        if parent is not None:
            owner = parent.window()
            if owner is None or not owner.isVisible() or owner.isMinimized() or not owner.isActiveWindow():
                return False
        return True

    def show_preview(self, global_x: int, target_top_y: int, msec: int, pixmap: QPixmap = None):
        if not self.is_owner_window_active():
            self.hide_preview()
            return

        self.lbl_time.setText(self._format_time(msec))

        if pixmap and not pixmap.isNull():
            self.lbl_thumb.setPixmap(pixmap)
        else:
            self.lbl_thumb.setText("Đang tải...")

        self.adjustSize()
        w = self.width()
        h = self.height()

        # Tìm màn hình hiện tại để chống tràn cạnh màn hình
        cursor_pt = QPoint(global_x, target_top_y)
        screen = QGuiApplication.screenAt(cursor_pt) or QGuiApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # Căn giữa theo trục X con trỏ chuột
        popup_x = global_x - (w // 2)
        popup_x = max(screen_geom.left() + 8, min(screen_geom.right() - w - 8, popup_x))

        # Đặt phía trên thanh Seekbar 10px, nếu quá sát mép trên thì hiển thị phía dưới
        popup_y = target_top_y - h - 10
        if popup_y < screen_geom.top() + 8:
            popup_y = target_top_y + 35

        self.move(popup_x, popup_y)
        if not self.isVisible():
            self.show()
            self.raise_()

    def set_thumbnail(self, pixmap: QPixmap):
        if not self.is_owner_window_active():
            self.hide_preview()
            return
        if pixmap and not pixmap.isNull():
            self.lbl_thumb.setPixmap(pixmap)

    def hide_preview(self):
        self.hide()

    @staticmethod
    def _format_time(ms: int) -> str:
        if ms < 0:
            ms = 0
        total_sec = int(ms // 1000)
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
