import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar

class EpisodeItemWidget(QWidget):
    """
    Widget tùy biến hiển thị trong danh sách tập phim:
    Gồm ảnh thumbnail thu nhỏ (hỗ trợ cập nhật bất đồng bộ khi worker tạo xong),
    tên tập/file, và thanh hiển thị tiến độ xem.
    """
    def __init__(self, title: str, progress_pct: float, thumb_path: str = None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(120, 68)
        self.lbl_thumb.setScaledContents(True)
        self.set_thumbnail(thumb_path)

        layout.addWidget(self.lbl_thumb)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 500;")
        self.lbl_title.setWordWrap(True)
        info_layout.addWidget(self.lbl_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(progress_pct))

        bar_color = "#107C41" if progress_pct >= 92 else "#0078D4"
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #333333; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 2px; }}
        """)
        info_layout.addWidget(self.progress_bar)

        layout.addLayout(info_layout, stretch=1)

    def set_thumbnail(self, thumb_path: str = None):
        if thumb_path and os.path.exists(thumb_path):
            self.lbl_thumb.setPixmap(QPixmap(thumb_path))
            self.lbl_thumb.setText("")
            self.lbl_thumb.setStyleSheet("background-color: #1A1A1A; border-radius: 4px;")
        else:
            self.lbl_thumb.setPixmap(QPixmap())
            self.lbl_thumb.setText("🎬 Đang tải...")
            self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_thumb.setStyleSheet("background-color: #242424; color: #777777; border-radius: 4px; font-size: 11px;")
