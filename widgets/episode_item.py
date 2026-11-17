import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar
from styles import COLOR_ACCENT, COLOR_SUCCESS

class EpisodeItemWidget(QWidget):
    """
    Card tập phim hiện đại chuẩn Fluent Design:
    - Ảnh thumbnail 16:9 thu nhỏ bo góc tinh tế
    - Tên tập phim rõ ràng, chống tràn
    - Trạng thái xem (Đã xem xong / Đang xem X% / Chưa xem)
    - Thanh tiến độ xem phim mượt mà
    """
    def __init__(self, title: str, progress_pct: float, thumb_path: str = None, is_active: bool = False):
        super().__init__()
        self.is_active = is_active
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Khung ảnh Thumbnail (116x65 - Tỷ lệ 16:9)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(116, 65)
        self.lbl_thumb.setScaledContents(True)
        self.set_thumbnail(thumb_path)
        layout.addWidget(self.lbl_thumb)

        # Thông tin tập phim
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Tên tập
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600;")
        self.lbl_title.setWordWrap(True)
        info_layout.addWidget(self.lbl_title)

        # Trạng thái tiến độ & Thanh tiến độ
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        if progress_pct >= 90:
            status_text = "✓ Đã xem xong"
            status_color = COLOR_SUCCESS
            bar_color = COLOR_SUCCESS
        elif progress_pct > 0:
            status_text = f"Đang xem {int(progress_pct)}%"
            status_color = COLOR_ACCENT
            bar_color = COLOR_ACCENT
        else:
            status_text = "Chưa xem"
            status_color = "#777777"
            bar_color = "#444444"

        self.lbl_status = QLabel(status_text)
        self.lbl_status.setStyleSheet(f"color: {status_color}; font-size: 11px; font-weight: 500;")
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        info_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(progress_pct))
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 2px;
            }}
        """)
        info_layout.addWidget(self.progress_bar)

        layout.addLayout(info_layout, stretch=1)

    def set_title(self, title: str):
        self.lbl_title.setText(title)

    def set_thumbnail(self, thumb_path: str = None):
        if thumb_path and os.path.exists(thumb_path):
            self.lbl_thumb.setPixmap(QPixmap(thumb_path))
            self.lbl_thumb.setText("")
            self.lbl_thumb.setStyleSheet("background-color: #1A1A1A; border-radius: 6px;")
        else:
            self.lbl_thumb.setPixmap(QPixmap())
            self.lbl_thumb.setText("🎬 Đang tải...")
            self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_thumb.setStyleSheet("background-color: #222222; color: #777777; border-radius: 6px; font-size: 11px;")

    def update_progress(self, progress_pct: float):
        self.progress_bar.setValue(int(progress_pct))
        if progress_pct >= 90:
            self.lbl_status.setText("✓ Đã xem xong")
            self.lbl_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 11px; font-weight: 500;")
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: rgba(255, 255, 255, 0.1); border: none; border-radius: 2px; }}
                QProgressBar::chunk {{ background-color: {COLOR_SUCCESS}; border-radius: 2px; }}
            """)
        elif progress_pct > 0:
            self.lbl_status.setText(f"Đang xem {int(progress_pct)}%")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 500;")
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: rgba(255, 255, 255, 0.1); border: none; border-radius: 2px; }}
                QProgressBar::chunk {{ background-color: {COLOR_ACCENT}; border-radius: 2px; }}
            """)
