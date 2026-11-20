from PyQt6.QtCore import Qt, QTimer, QSize, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QLinearGradient
from PyQt6.QtWidgets import QWidget, QSizePolicy


class MarqueeLabel(QWidget):
    """
    Nhãn hiển thị tiêu đề video tối giản với hiệu ứng chạy chữ ngang (Marquee):
    - Chỉ kích hoạt chạy chữ khi chiều rộng văn bản vượt quá không gian hiển thị khả dụng
    - Có khoảng dừng hợp lý ở đầu chu kỳ để người dùng dễ đọc toàn bộ tiêu đề
    - Tạm dừng khi rê chuột vào tiêu đề để đọc/xem tooltip, không làm giãn hay đẩy bố cục xung quanh
    """

    def __init__(
        self,
        text: str = "",
        parent=None,
        fade_color: QColor | str = "#161616",
        text_color: QColor | str = "#E2E2E2",
    ):
        super().__init__(parent)
        self._text = ""
        self._fade_color = QColor(fade_color)
        self._text_color = QColor(text_color)
        self._alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        self._offset = 0.0
        self._text_width = 0
        self._gap = 48
        self._scrolling = False
        self._hovered = False
        self._step_px = 1.0
        self._pause_ms = 1800
        self._tick_ms = 25

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(self._tick_ms)
        self._scroll_timer.timeout.connect(self._on_scroll_tick)

        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.setInterval(self._pause_ms)
        self._pause_timer.timeout.connect(self._on_pause_done)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        font = QFont("Segoe UI")
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)

        self.setText(text)

    def setText(self, text: str):
        self._text = text or ""
        self._offset = 0.0
        self._scroll_timer.stop()
        self._pause_timer.stop()
        self._update_marquee_state()
        self.update()

    def text(self) -> str:
        return self._text

    def setTextColor(self, color: QColor | str):
        self._text_color = QColor(color)
        self.update()

    def setFadeColor(self, color: QColor | str):
        self._fade_color = QColor(color)
        self.update()

    def setAlignment(self, alignment: Qt.AlignmentFlag):
        self._alignment = alignment
        self.update()

    def isScrolling(self) -> bool:
        return self._scrolling

    def minimumSizeHint(self) -> QSize:
        return QSize(40, self.height() or 22)

    def sizeHint(self) -> QSize:
        return QSize(180, self.height() or 22)

    def _update_marquee_state(self):
        fm = QFontMetrics(self.font())
        self._text_width = fm.horizontalAdvance(self._text)
        avail = max(0, self.width() - 4)

        if not self._text or avail <= 0 or self._text_width <= avail:
            self._scrolling = False
            self._offset = 0.0
            self._scroll_timer.stop()
            self._pause_timer.stop()
            return

        was_scrolling = self._scrolling
        self._scrolling = True

        if self.isVisible() and not self._hovered:
            if not was_scrolling or (
                not self._scroll_timer.isActive() and not self._pause_timer.isActive()
            ):
                self._offset = 0.0
                self._scroll_timer.stop()
                self._pause_timer.start(self._pause_ms)

    def _on_pause_done(self):
        if self._scrolling and self.isVisible() and not self._hovered:
            self._scroll_timer.start(self._tick_ms)

    def _on_scroll_tick(self):
        if not self._scrolling or not self._text:
            self._scroll_timer.stop()
            return

        self._offset += self._step_px
        cycle = self._text_width + self._gap
        if self._offset >= cycle:
            self._offset = 0.0
            self._scroll_timer.stop()
            if self.isVisible() and not self._hovered:
                self._pause_timer.start(self._pause_ms)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_marquee_state()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_marquee_state()

    def hideEvent(self, event):
        self._scroll_timer.stop()
        self._pause_timer.stop()
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._scroll_timer.stop()
        self._pause_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        if self._scrolling and self.isVisible():
            if self._offset > 0:
                self._scroll_timer.start(self._tick_ms)
            else:
                self._pause_timer.start(self._pause_ms)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if not self._text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self.font())
        painter.setPen(self._text_color)

        clip_w = max(0, self.width() - 4)
        clip_rect = QRect(2, 0, clip_w, self.height())
        if clip_w <= 0:
            return
        painter.setClipRect(clip_rect)

        fm = painter.fontMetrics()
        baseline_y = (self.height() + fm.ascent() - fm.descent()) // 2

        if not self._scrolling:
            if self._alignment & Qt.AlignmentFlag.AlignHCenter:
                x = max(2, 2 + (clip_w - self._text_width) // 2)
            else:
                x = 2
            painter.drawText(x, baseline_y, self._text)
            return

        x1 = 2 - int(self._offset)
        x2 = x1 + self._text_width + self._gap
        painter.drawText(x1, baseline_y, self._text)
        if x2 < self.width():
            painter.drawText(x2, baseline_y, self._text)

        # Lớp chuyển mờ nhẹ ở mép khi chữ đang cuộn (chỉ vẽ khi nền đục để tránh nhiễu trên overlay trong suốt)
        if self._fade_color.alpha() == 255 and clip_w > 36:
            fade_w = 18
            transparent = QColor(
                self._fade_color.red(),
                self._fade_color.green(),
                self._fade_color.blue(),
                0,
            )

            right_x = self.width() - fade_w
            right_grad = QLinearGradient(right_x, 0, self.width(), 0)
            right_grad.setColorAt(0.0, transparent)
            right_grad.setColorAt(1.0, self._fade_color)
            painter.fillRect(right_x, 0, fade_w, self.height(), right_grad)

            if self._offset > 0:
                left_grad = QLinearGradient(0, 0, fade_w, 0)
                left_grad.setColorAt(0.0, self._fade_color)
                left_grad.setColorAt(1.0, transparent)
                painter.fillRect(0, 0, fade_w, self.height(), left_grad)
