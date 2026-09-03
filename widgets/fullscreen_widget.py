from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider

class FullscreenOverlayWidget(QWidget):
    """
    Lớp Overlay điều khiển nổi trên màn hình Fullscreen với thiết kế hiện đại,
    tự động hiển thị khi di chuột và ẩn sau 2.5 giây.
    """
    def __init__(self, parent_app, parent_container):
        super().__init__(parent_container)
        self.parent_app = parent_app
        self.parent_container = parent_container
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)

        # Top Bar (Tiêu đề video & Nút thu nhỏ)
        top_layout = QHBoxLayout()
        self.lbl_title = QLabel("Đang phát toàn màn hình", self)
        self.lbl_title.setStyleSheet("color: rgba(255, 255, 255, 220); font-size: 16px; font-weight: bold; background: transparent;")
        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()

        self.btn_exit_fs = QPushButton("⛶ Thu nhỏ (Esc)", self)
        self.btn_exit_fs.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 160); color: white;
                border-radius: 6px; font-size: 13px; font-weight: bold;
                border: 1px solid rgba(255,255,255,60); padding: 8px 16px;
            }
            QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
        """)
        self.btn_exit_fs.clicked.connect(self.parent_app.exit_fullscreen)
        top_layout.addWidget(self.btn_exit_fs)
        layout.addLayout(top_layout)

        layout.addStretch()

        # Center Controls (Tua -5s, Play/Pause, Tua +5s)
        center_layout = QHBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(30)

        btn_style_center = """
            QPushButton {
                background-color: rgba(0, 0, 0, 180); color: white;
                border-radius: 35px; font-size: 22px; font-weight: bold;
                border: 1px solid rgba(255,255,255,70);
            }
            QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
        """

        self.btn_back = QPushButton("⏪ -5s", self)
        self.btn_back.setFixedSize(90, 70)
        self.btn_back.setStyleSheet(btn_style_center)
        self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedSize(80, 80)
        self.btn_play.setStyleSheet(btn_style_center)
        self.btn_play.clicked.connect(self.parent_app.toggle_play)

        self.btn_forward = QPushButton("+5s ⏩", self)
        self.btn_forward.setFixedSize(90, 70)
        self.btn_forward.setStyleSheet(btn_style_center)
        self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

        center_layout.addWidget(self.btn_back)
        center_layout.addWidget(self.btn_play)
        center_layout.addWidget(self.btn_forward)
        layout.addLayout(center_layout)

        layout.addStretch()

        # Bottom Bar (Thời gian phát)
        bottom_layout = QHBoxLayout()
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time = QLabel("00:00 / 00:00", self)
        self.lbl_time.setStyleSheet("""
            QLabel {
                color: #FFFFFF; font-size: 14px; font-weight: bold;
                background-color: rgba(0, 0, 0, 160);
                border-radius: 12px; padding: 4px 14px;
            }
        """)
        bottom_layout.addWidget(self.lbl_time)
        layout.addLayout(bottom_layout)

        self.timer_hide = QTimer(self)
        self.timer_hide.setInterval(2500)
        self.timer_hide.timeout.connect(self.hide)

    def show_overlay(self):
        self.setGeometry(0, 0, self.parent_container.width(), self.parent_container.height())
        self.show()
        self.raise_()
        self.timer_hide.start()

    def update_play_button(self, text):
        self.btn_play.setText(text)

    def update_time(self, time_str):
        self.lbl_time.setText(time_str)

    def set_title(self, title):
        self.lbl_title.setText(title)
