from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSlider
from PyQt6.QtGui import QMouseEvent

class ClickableSlider(QSlider):
    """
    QSlider nâng cao cho phép người dùng click chuột vào bất kỳ vị trí nào
    trên thanh trượt để nhảy trực tiếp tới mốc thời gian đó (tương tự YouTube / Netflix),
    thay vì phải kéo núm tròn.
    """
    clicked_to_percentage = pyqtSignal(float)  # 0.0 -> 1.0

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            new_val = self._calculate_value(event.position().x())
            self.setValue(new_val)
            pct = new_val / max(1.0, float(self.maximum()))
            self.clicked_to_percentage.emit(pct)
            event.accept()
        super().mousePressEvent(event)

    def _calculate_value(self, mouse_x: float) -> int:
        width = max(1, self.width())
        ratio = max(0.0, min(1.0, mouse_x / width))
        val_range = self.maximum() - self.minimum()
        return int(self.minimum() + ratio * val_range)
