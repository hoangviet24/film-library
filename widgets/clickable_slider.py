from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import QSlider
from PyQt6.QtGui import QMouseEvent

class ClickableSlider(QSlider):
    """
    QSlider nâng cao cho phép người dùng click chuột vào bất kỳ vị trí nào
    trên thanh trượt để nhảy trực tiếp tới mốc thời gian đó (tương tự YouTube / Netflix),
    đồng thời hỗ trợ sự kiện hover để hiển thị Thumbnail Preview.
    """
    clicked_to_percentage = pyqtSignal(float)       # 0.0 -> 1.0
    hover_moved = pyqtSignal(int, float, QPoint)    # val, pct, global_pos
    hover_left = pyqtSignal()

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            new_val = self._calculate_value(event.position().x())
            self.setValue(new_val)
            pct = new_val / max(1.0, float(self.maximum()))
            self.clicked_to_percentage.emit(pct)
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        val = self._calculate_value(event.position().x())
        pct = val / max(1.0, float(self.maximum()))
        global_pt = event.globalPosition().toPoint()
        self.hover_moved.emit(val, pct, global_pt)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hover_left.emit()
        super().leaveEvent(event)

    def _calculate_value(self, mouse_x: float) -> int:
        width = max(1, self.width())
        ratio = max(0.0, min(1.0, mouse_x / width))
        val_range = self.maximum() - self.minimum()
        return int(self.minimum() + ratio * val_range)
