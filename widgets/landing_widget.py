import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from styles import (
    BTN_PRIMARY_STYLE, BTN_CONTROL_STYLE, CARD_STYLE, 
    COLOR_ACCENT, COLOR_BG_CARD
)
from utils import get_cached_thumbnail

class LandingPage(QWidget):
    """
    Trang mở đầu (Welcome / Landing Page) chuẩn Fluent Design:
    - Khu vực Kéo & Thả (Drag & Drop) tệp/thư mục phim trực tiếp
    - Nút mở thư mục và mở tệp video riêng lẻ
    - Danh sách các video vừa xem gần đây để tiếp tục xem tức thì (Recent History)
    """
    open_folder_clicked = pyqtSignal()
    open_file_clicked = pyqtSignal()
    file_dropped = pyqtSignal(str)              # video or folder path dropped
    resume_video_clicked = pyqtSignal(str)      # file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(24)

        # ---------------- KHU VỰC HERO & KÉO THẢ (DROP ZONE) ----------------
        self.drop_card = QFrame()
        self.drop_card.setFixedSize(540, 280)
        self.drop_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 2px dashed rgba(255, 255, 255, 0.2);
                border-radius: 16px;
            }}
        """)
        card_layout = QVBoxLayout(self.drop_card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(14)

        lbl_logo = QLabel("🎬")
        lbl_logo.setStyleSheet("font-size: 54px; background: transparent; border: none;")
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_logo)

        lbl_welcome = QLabel("Fluent Media Player")
        lbl_welcome.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF; background: transparent; border: none;")
        lbl_welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_welcome)

        lbl_desc = QLabel("Kéo thả thư mục hoặc tệp video vào đây để bắt đầu xem")
        lbl_desc.setStyleSheet("font-size: 13px; color: #999999; background: transparent; border: none;")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_open_folder = QPushButton("📁 Chọn Thư Mục Phim")
        self.btn_open_folder.setStyleSheet(BTN_PRIMARY_STYLE)
        self.btn_open_folder.setFixedHeight(40)
        self.btn_open_folder.clicked.connect(self.open_folder_clicked.emit)
        btn_row.addWidget(self.btn_open_folder)

        self.btn_open_file = QPushButton("🎬 Chọn Tệp Video")
        self.btn_open_file.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_open_file.setFixedHeight(40)
        self.btn_open_file.clicked.connect(self.open_file_clicked.emit)
        btn_row.addWidget(self.btn_open_file)

        card_layout.addLayout(btn_row)
        main_layout.addWidget(self.drop_card, alignment=Qt.AlignmentFlag.AlignCenter)

        # ---------------- DANH SÁCH XEM GẦN ĐÂY (RECENT HISTORY) ----------------
        self.recent_container = QWidget()
        self.recent_container.setFixedWidth(540)
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(8)

        self.lbl_recent_header = QLabel("🕒 TIẾP TỤC XEM GẦN ĐÂY")
        self.lbl_recent_header.setStyleSheet("color: #0078D4; font-size: 12px; font-weight: bold; margin-bottom: 2px;")
        self.recent_layout.addWidget(self.lbl_recent_header)

        self.recent_items_layout = QVBoxLayout()
        self.recent_items_layout.setSpacing(6)
        self.recent_layout.addLayout(self.recent_items_layout)

        main_layout.addWidget(self.recent_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.recent_container.hide()

    def update_recent_history(self, history_data: dict):
        # Dọn dẹp danh sách cũ
        while self.recent_items_layout.count() > 0:
            item = self.recent_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Lấy tối đa 3 video gần đây nhất có tồn tại trên máy
        valid_items = []
        for path, info in reversed(list(history_data.items())):
            if os.path.exists(path):
                valid_items.append((path, info))
            if len(valid_items) >= 3:
                break

        if not valid_items:
            self.recent_container.hide()
            return

        self.recent_container.show()

        for file_path, info in valid_items:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1A1A;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 8px;
                    padding: 4px;
                }}
                QFrame:hover {{
                    background-color: #242424;
                    border-color: {COLOR_ACCENT};
                }}
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(10, 6, 10, 6)
            r_layout.setSpacing(10)

            filename = os.path.basename(file_path)
            pct = int(info.get("pct", 0))

            lbl_info = QLabel(f"🎞️ {filename} ({pct}%)")
            lbl_info.setStyleSheet("color: #E0E0E0; font-size: 13px; font-weight: 500; border: none; background: transparent;")
            r_layout.addWidget(lbl_info, stretch=1)

            btn_resume = QPushButton("▶ Tiếp tục")
            btn_resume.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT}; color: white;
                    border-radius: 5px; padding: 4px 10px; font-size: 11px; font-weight: bold; border: none;
                }}
                QPushButton:hover {{ background-color: #1084E3; }}
            """)
            btn_resume.clicked.connect(lambda checked, p=file_path: self.resume_video_clicked.emit(p))
            r_layout.addWidget(btn_resume)

            self.recent_items_layout.addWidget(row)

    # ---------------- HỖ TRỢ KÉO & THẢ (DRAG & DROP) ----------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1C2430;
                    border: 2px dashed {COLOR_ACCENT};
                    border-radius: 16px;
                }}
            """)

    def dragLeaveEvent(self, event):
        self.drop_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 2px dashed rgba(255, 255, 255, 0.2);
                border-radius: 16px;
            }}
        """)

    def dropEvent(self, event: QDropEvent):
        self.drop_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 2px dashed rgba(255, 255, 255, 0.2);
                border-radius: 16px;
            }}
        """)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.exists(path):
                self.file_dropped.emit(path)
                event.acceptProposedAction()
