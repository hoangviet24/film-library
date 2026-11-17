from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame

class VlcVideoWidget(QFrame):
    """
    Khung hiển thị video VLC chuyên dụng với các cờ tối ưu đồ họa:
    - WA_OpaquePaintEvent & WA_NoSystemBackground: Ngăn Qt vẽ đè nền đen lên Direct3D của VLC khi resize, fullscreen hoặc thu nhỏ.
    - WA_NativeWindow: Đảm bảo có HWND Win32 độc lập, ổn định.
    - Vô hiệu hóa paintEngine và paintEvent để giải phóng hoàn toàn Direct3D buffer.
    """
    mouse_moved = pyqtSignal()
    mouse_left = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWidth(0)
        self.setMidLineWidth(0)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #000000; border: none; outline: none; margin: 0px; padding: 0px;")

    def paintEngine(self):
        # Trả về None để loại trừ hoàn toàn engine vẽ phần mềm của Qt
        return None

    def paintEvent(self, event):
        # Không vẽ bất kỳ thứ gì đè lên VLC
        pass

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.mouse_moved.emit()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.mouse_moved.emit()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.mouse_left.emit()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.double_clicked.emit()
