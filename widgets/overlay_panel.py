from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider

class VideoOverlayPanel(QWidget):
    """
    Overlay điều khiển nổi độc lập (Tool Window) hiển thị CHÍNH XÁC chỉ khi con trỏ chuột
    nằm bên trong khung phát video. Tích hợp thanh trượt tiến độ (Slider), nút chuyển tập (Tập trước / Tập tiếp)
    cho cả Fullscreen, Main Video và Pop-out.
    """
    def __init__(self, target_widget, parent_app, mode="main"):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.target_widget = target_widget
        self.parent_app = parent_app
        self.mode = mode  # "main", "fullscreen", "popout"
        self.is_slider_seeking = False
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet("background-color: transparent;")

        self.init_ui()

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(2500)
        self.hide_timer.timeout.connect(self.hide)

        self.setMouseTracking(True)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        slider_style = """
            QSlider::groove:horizontal {
                height: 5px;
                background: rgba(255, 255, 255, 0.25);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0078D4;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60A5FA;
                transform: scale(1.2);
            }
        """

        if self.mode == "fullscreen":
            layout.setContentsMargins(40, 30, 40, 30)
            
            # Top Bar: Tiêu đề phim & Nút thu nhỏ
            top_layout = QHBoxLayout()
            self.lbl_title = QLabel("🎬 Đang phát toàn màn hình", self)
            self.lbl_title.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    font-size: 15px; font-weight: bold;
                    background-color: rgba(15, 15, 15, 0.8);
                    padding: 8px 16px; border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                }
            """)
            top_layout.addWidget(self.lbl_title)
            top_layout.addStretch()

            btn_exit = QPushButton("⤡ Thu nhỏ (Esc)", self)
            btn_exit.setStyleSheet("""
                QPushButton {
                    background-color: rgba(15, 15, 15, 0.85); color: white;
                    border-radius: 8px; font-size: 13px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.2); padding: 8px 18px;
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """)
            btn_exit.clicked.connect(self.parent_app.exit_fullscreen)
            top_layout.addWidget(btn_exit)
            layout.addLayout(top_layout)
            
            layout.addStretch()
            
            # Center Controls: |◀, ↺ 5s, ▶ / ❚❚, 5s ↻, ▶|
            center_layout = QHBoxLayout()
            center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            center_layout.setSpacing(25)
            
            btn_fs_ep = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: #FFFFFF;
                    border-radius: 26px; font-size: 16px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """
            btn_side_style = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: #FFFFFF;
                    border-radius: 32px; font-size: 17px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """

            self.btn_prev = QPushButton("⏮", self)
            self.btn_prev.setFixedSize(56, 56)
            self.btn_prev.setStyleSheet(btn_fs_ep)
            self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
            self.btn_prev.clicked.connect(self.parent_app.play_prev_episode)

            self.btn_back = QPushButton("↺ 5s", self)
            self.btn_back.setFixedSize(72, 64)
            self.btn_back.setStyleSheet(btn_side_style)
            self.btn_back.setToolTip("Tua lùi 5 giây (←)")
            self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

            self.btn_play = QPushButton("▶", self)
            self.btn_play.setFixedSize(84, 84)
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #0078D4; color: white;
                    border-radius: 42px; font-size: 26px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.4);
                }
                QPushButton:hover { background-color: #1084E3; }
                QPushButton:pressed { background-color: #005A9E; }
            """)
            self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
            self.btn_play.clicked.connect(self.parent_app.toggle_play)

            self.btn_forward = QPushButton("5s ↻", self)
            self.btn_forward.setFixedSize(72, 64)
            self.btn_forward.setStyleSheet(btn_side_style)
            self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
            self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

            self.btn_next = QPushButton("⏭", self)
            self.btn_next.setFixedSize(56, 56)
            self.btn_next.setStyleSheet(btn_fs_ep)
            self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
            self.btn_next.clicked.connect(self.parent_app.play_next_episode)

            center_layout.addWidget(self.btn_prev)
            center_layout.addWidget(self.btn_back)
            center_layout.addWidget(self.btn_play)
            center_layout.addWidget(self.btn_forward)
            center_layout.addWidget(self.btn_next)
            layout.addLayout(center_layout)
            
            layout.addStretch()
            
            # Bottom Bar: Slider tiến độ + Thời gian
            bot_card = QWidget(self)
            bot_card.setStyleSheet("background-color: rgba(15, 15, 15, 0.85); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.15);")
            bot_layout = QVBoxLayout(bot_card)
            bot_layout.setContentsMargins(16, 10, 16, 10)
            bot_layout.setSpacing(6)

            self.slider = QSlider(Qt.Orientation.Horizontal, bot_card)
            self.slider.setRange(0, 1000)
            self.slider.setStyleSheet(slider_style)
            self.slider.sliderPressed.connect(self.on_slider_pressed)
            self.slider.sliderReleased.connect(self.on_slider_released)
            bot_layout.addWidget(self.slider)

            time_row = QHBoxLayout()
            self.lbl_time_cur = QLabel("00:00", bot_card)
            self.lbl_time_cur.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold; border: none; background: transparent;")
            self.lbl_time_tot = QLabel("00:00", bot_card)
            self.lbl_time_tot.setStyleSheet("color: #AAAAAA; font-size: 13px; border: none; background: transparent;")
            time_row.addWidget(self.lbl_time_cur)
            time_row.addStretch()
            time_row.addWidget(self.lbl_time_tot)
            bot_layout.addLayout(time_row)

            layout.addWidget(bot_card)
            
        elif self.mode == "popout":
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)
            
            # Top Bar
            top_layout = QHBoxLayout()
            lbl_title = QLabel("🎬 Mini Player", self)
            lbl_title.setStyleSheet("color: rgba(255, 255, 255, 220); font-weight: bold; font-size: 11px;")
            top_layout.addWidget(lbl_title)
            top_layout.addStretch()
            
            btn_restore = QPushButton("⤢ Thu hồi", self)
            btn_restore.setStyleSheet("""
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 10px; font-size: 11px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.3); padding: 4px 10px;
                }
                QPushButton:hover { background-color: #0078D4; }
            """)
            btn_restore.clicked.connect(self.parent_app.restore_video_from_popout)
            top_layout.addWidget(btn_restore)
            layout.addLayout(top_layout)
            
            layout.addStretch()
            
            # Center Controls: |◀, ↺ 5s, ▶ / ❚❚, 5s ↻, ▶|
            center_layout = QHBoxLayout()
            center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            center_layout.setSpacing(10)
            
            btn_pop_side = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 18px; font-size: 11px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                }
                QPushButton:hover { background-color: #0078D4; }
            """

            self.btn_prev = QPushButton("⏮", self)
            self.btn_prev.setFixedSize(36, 36)
            self.btn_prev.setStyleSheet(btn_pop_side)
            self.btn_prev.setToolTip("Tập trước")
            self.btn_prev.clicked.connect(self.parent_app.play_prev_episode)

            self.btn_back = QPushButton("↺", self)
            self.btn_back.setFixedSize(36, 36)
            self.btn_back.setStyleSheet(btn_pop_side)
            self.btn_back.setToolTip("Tua lùi 5s")
            self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

            self.btn_play = QPushButton("▶", self)
            self.btn_play.setFixedSize(46, 46)
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #0078D4; color: white;
                    border-radius: 23px; font-size: 17px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.3);
                }
                QPushButton:hover { background-color: #1084E3; }
            """)
            self.btn_play.clicked.connect(self.parent_app.toggle_play)

            self.btn_forward = QPushButton("↻", self)
            self.btn_forward.setFixedSize(36, 36)
            self.btn_forward.setStyleSheet(btn_pop_side)
            self.btn_forward.setToolTip("Tua tiến 5s")
            self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

            self.btn_next = QPushButton("⏭", self)
            self.btn_next.setFixedSize(36, 36)
            self.btn_next.setStyleSheet(btn_pop_side)
            self.btn_next.setToolTip("Tập tiếp")
            self.btn_next.clicked.connect(self.parent_app.play_next_episode)

            center_layout.addWidget(self.btn_prev)
            center_layout.addWidget(self.btn_back)
            center_layout.addWidget(self.btn_play)
            center_layout.addWidget(self.btn_forward)
            center_layout.addWidget(self.btn_next)
            layout.addLayout(center_layout)
            
            layout.addStretch()

            # Bottom Bar: Slider tiến độ mini
            self.slider = QSlider(Qt.Orientation.Horizontal, self)
            self.slider.setRange(0, 1000)
            self.slider.setStyleSheet(slider_style)
            self.slider.sliderPressed.connect(self.on_slider_pressed)
            self.slider.sliderReleased.connect(self.on_slider_released)
            layout.addWidget(self.slider)

            self.lbl_time = QLabel("00:00 / 00:00", self)
            self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_time.setStyleSheet("color: #CCCCCC; font-size: 11px; font-family: 'Consolas', monospace;")
            layout.addWidget(self.lbl_time)
            
        else:  # "main"
            layout.setContentsMargins(20, 20, 20, 20)
            
            top_layout = QHBoxLayout()
            top_layout.addStretch()
            btn_fs = QPushButton("⤢ Toàn màn hình", self)
            btn_fs.setStyleSheet("""
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 6px; font-size: 12px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25); padding: 6px 14px;
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """)
            btn_fs.clicked.connect(self.parent_app.enter_fullscreen)
            top_layout.addWidget(btn_fs)
            layout.addLayout(top_layout)
            
            layout.addStretch()
            
            center_layout = QHBoxLayout()
            center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            center_layout.setSpacing(18)
            
            btn_main_ep = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 22px; font-size: 15px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """
            btn_main_side = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 26px; font-size: 14px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """

            self.btn_prev = QPushButton("⏮", self)
            self.btn_prev.setFixedSize(48, 48)
            self.btn_prev.setStyleSheet(btn_main_ep)
            self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
            self.btn_prev.clicked.connect(self.parent_app.play_prev_episode)

            self.btn_back = QPushButton("↺ 5s", self)
            self.btn_back.setFixedSize(62, 52)
            self.btn_back.setStyleSheet(btn_main_side)
            self.btn_back.setToolTip("Tua lùi 5 giây (←)")
            self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

            self.btn_play = QPushButton("▶", self)
            self.btn_play.setFixedSize(68, 68)
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #0078D4; color: white;
                    border-radius: 34px; font-size: 22px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.35);
                }
                QPushButton:hover { background-color: #1084E3; }
                QPushButton:pressed { background-color: #005A9E; }
            """)
            self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
            self.btn_play.clicked.connect(self.parent_app.toggle_play)

            self.btn_forward = QPushButton("5s ↻", self)
            self.btn_forward.setFixedSize(62, 52)
            self.btn_forward.setStyleSheet(btn_main_side)
            self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
            self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

            self.btn_next = QPushButton("⏭", self)
            self.btn_next.setFixedSize(48, 48)
            self.btn_next.setStyleSheet(btn_main_ep)
            self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
            self.btn_next.clicked.connect(self.parent_app.play_next_episode)

            center_layout.addWidget(self.btn_prev)
            center_layout.addWidget(self.btn_back)
            center_layout.addWidget(self.btn_play)
            center_layout.addWidget(self.btn_forward)
            center_layout.addWidget(self.btn_next)
            layout.addLayout(center_layout)
            
            layout.addStretch()

    def set_target_widget(self, widget):
        self.target_widget = widget

    def get_target_global_rect(self) -> QRect:
        if self.target_widget and self.target_widget.isVisible():
            global_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
            return QRect(global_pos.x(), global_pos.y(), self.target_widget.width(), self.target_widget.height())
        return QRect()

    def reposition(self):
        target_rect = self.get_target_global_rect()
        if not target_rect.isNull():
            self.setGeometry(target_rect)

    def is_cursor_over_video(self) -> bool:
        target_rect = self.get_target_global_rect()
        if not target_rect.isNull():
            return target_rect.contains(QCursor.pos())
        return False

    def show_overlay(self):
        if not self.target_widget or not self.target_widget.isVisible():
            self.hide()
            return
        
        # Ở chế độ main, chỉ hiện khi chuột thật sự nằm trong khung video
        if self.mode == "main" and not self.is_cursor_over_video():
            self.hide()
            return

        self.reposition()
        self.show()
        self.raise_()
        self.hide_timer.start()

    def check_and_hide_if_left(self):
        if not self.is_cursor_over_video():
            self.hide()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.hide_timer.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.check_and_hide_if_left()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if self.mode == "fullscreen":
            self.parent_app.exit_fullscreen()
        elif self.mode == "popout":
            self.parent_app.restore_video_from_popout()
        else:
            self.parent_app.enter_fullscreen()

    def on_slider_pressed(self):
        self.is_slider_seeking = True
        self.parent_app.on_slider_pressed()

    def on_slider_released(self):
        if hasattr(self, 'slider'):
            pos_pct = self.slider.value() / 1000.0
            self.parent_app.seek_to_percentage(pos_pct)
        self.is_slider_seeking = False

    def update_slider(self, val_0_to_1000):
        if hasattr(self, 'slider') and not self.is_slider_seeking:
            self.slider.setValue(int(val_0_to_1000))

    def update_play_button(self, is_playing: bool):
        icon = "❚❚" if is_playing else "▶"
        if hasattr(self, 'btn_play'):
            self.btn_play.setText(icon)

    def update_time(self, current_str, total_str):
        if hasattr(self, 'lbl_time_cur'):
            self.lbl_time_cur.setText(current_str)
        if hasattr(self, 'lbl_time_tot'):
            self.lbl_time_tot.setText(total_str)
        if hasattr(self, 'lbl_time'):
            self.lbl_time.setText(f"{current_str} / {total_str}")

    def set_title(self, title):
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setText(f"🎬 {title}")
