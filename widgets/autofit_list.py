from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget

class AutoFitListWidget(QListWidget):
    """
    QListWidget tự động tính toán và đặt chiều cao cố định vừa vặn với toàn bộ các item,
    tránh thanh cuộn lồng nhau khi nằm trong QScrollArea.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def update_height(self):
        total_height = 0
        for i in range(self.count()):
            total_height += self.sizeHintForIndex(self.model().index(i, 0)).height()
        self.setFixedHeight(max(total_height + 10, 40))
