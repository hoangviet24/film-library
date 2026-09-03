from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QScrollArea
from PyQt6.QtGui import QWheelEvent

class SmoothScrollArea(QScrollArea):
    """
    QScrollArea với khả năng cuộn mượt mà (Smooth scrolling) sử dụng animation nội suy
    và hỗ trợ cộng dồn quán tính khi lăn chuột liên tục.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self._target_value = 0
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setDuration(260)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta != 0:
            vbar = self.verticalScrollBar()
            min_val = vbar.minimum()
            max_val = vbar.maximum()
            
            # Nếu đang có animation, lấy mốc đích trước đó để cộng dồn mượt mà
            current_base = self._target_value if self._anim.state() == QPropertyAnimation.State.Running else vbar.value()
            
            step = int(-delta * 1.3)
            self._target_value = max(min_val, min(max_val, current_base + step))
            
            self._anim.stop()
            self._anim.setStartValue(vbar.value())
            self._anim.setEndValue(self._target_value)
            self._anim.start()
            event.accept()
        else:
            super().wheelEvent(event)
