from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QCursor, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMenu
)
from .clickable_slider import ClickableSlider
from styles import (
    SEEK_SLIDER_STYLE, VOLUME_SLIDER_STYLE, COLOR_ACCENT, 
    COLOR_ACCENT_HOVER, COLOR_ACCENT_PRESSED
)

class VideoOverlayPanel(QWidget):
    """
    Overlay điều khiển nổi độc lập (Tool Window) hiển thị mượt mà trên khung phát video
    khi di chuột vào và tự động ẩn đi sau 2.5 giây khi không thao tác.
    Hỗ trợ 3 chế độ: "main", "fullscreen", "popout".
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

        if self.mode == "fullscreen":
            layout.setContentsMargins(40, 30, 40, 30)
            
            # Top Bar: Tiêu đề phim & Nút thu nhỏ
            top_layout = QHBoxLayout()
            self.lbl_title = QLabel("🎬 Đang phát toàn màn hình", self)
            self.lbl_title.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    font-size: 15px; font-weight: bold;
                    background-color: rgba(15, 15, 15, 0.85);
                    padding: 8px 18px; border-radius: 8px;
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
            
            # Center Controls: ⏮, ↺ 5s, ▶ / ❚❚, 5s ↻, ⏭
            center_layout = QHBoxLayout()
            center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            center_layout.setSpacing(25)
            
            btn_circle_style = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: #FFFFFF;
                    border-radius: 28px; font-size: 17px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """

            self.btn_prev = QPushButton("⏮", self)
            self.btn_prev.setFixedSize(56, 56)
            self.btn_prev.setStyleSheet(btn_circle_style)
            self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
            self.btn_prev.clicked.connect(self.parent_app.play_prev_episode)

            self.btn_back = QPushButton("↺ 5s", self)
            self.btn_back.setFixedSize(70, 60)
            self.btn_back.setStyleSheet(btn_circle_style)
            self.btn_back.setToolTip("Tua lùi 5 giây (←)")
            self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

            self.btn_play = QPushButton("▶", self)
            self.btn_play.setFixedSize(84, 84)
            self.btn_play.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT}; color: white;
                    border-radius: 42px; font-size: 28px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.4);
                }}
                QPushButton:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}
                QPushButton:pressed {{ background-color: {COLOR_ACCENT_PRESSED}; }}
            """)
            self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
            self.btn_play.clicked.connect(self.parent_app.toggle_play)

            self.btn_forward = QPushButton("5s ↻", self)
            self.btn_forward.setFixedSize(70, 60)
            self.btn_forward.setStyleSheet(btn_circle_style)
            self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
            self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

            self.btn_next = QPushButton("⏭", self)
            self.btn_next.setFixedSize(56, 56)
            self.btn_next.setStyleSheet(btn_circle_style)
            self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
            self.btn_next.clicked.connect(self.parent_app.play_next_episode)

            center_layout.addWidget(self.btn_prev)
            center_layout.addWidget(self.btn_back)
            center_layout.addWidget(self.btn_play)
            center_layout.addWidget(self.btn_forward)
            center_layout.addWidget(self.btn_next)
            layout.addLayout(center_layout)
            
            layout.addStretch()
            
            # Bottom Bar: Card chứa Slider + Âm lượng + Thời gian
            bot_card = QWidget(self)
            bot_card.setStyleSheet("background-color: rgba(15, 15, 15, 0.88); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.15);")
            bot_layout = QVBoxLayout(bot_card)
            bot_layout.setContentsMargins(18, 12, 18, 12)
            bot_layout.setSpacing(8)

            self.slider = ClickableSlider(Qt.Orientation.Horizontal, bot_card)
            self.slider.setRange(0, 1000)
            self.slider.setStyleSheet(SEEK_SLIDER_STYLE)
            self.slider.sliderPressed.connect(self.on_slider_pressed)
            self.slider.sliderReleased.connect(self.on_slider_released)
            self.slider.clicked_to_percentage.connect(self.parent_app.seek_to_percentage)
            bot_layout.addWidget(self.slider)

            bottom_row = QHBoxLayout()
            self.lbl_time_cur = QLabel("00:00", bot_card)
            self.lbl_time_cur.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold; border: none; background: transparent;")
            bottom_row.addWidget(self.lbl_time_cur)

            self.lbl_time_tot = QLabel("00:00", bot_card)
            self.lbl_time_tot.setStyleSheet("color: #AAAAAA; font-size: 13px; border: none; background: transparent;")
            bottom_row.addWidget(self.lbl_time_tot)

            bottom_row.addStretch()

            # Âm lượng trong Fullscreen
            self.btn_fs_volume = QPushButton("🔊", bot_card)
            self.btn_fs_volume.setFixedSize(32, 32)
            self.btn_fs_volume.setStyleSheet("background: transparent; color: white; font-size: 14px; border: none;")
            self.btn_fs_volume.clicked.connect(self.parent_app.toggle_mute)
            bottom_row.addWidget(self.btn_fs_volume)

            self.slider_fs_volume = ClickableSlider(Qt.Orientation.Horizontal, bot_card)
            self.slider_fs_volume.setRange(0, 100)
            self.slider_fs_volume.setValue(100)
            self.slider_fs_volume.setFixedWidth(80)
            self.slider_fs_volume.setStyleSheet(VOLUME_SLIDER_STYLE)
            self.slider_fs_volume.valueChanged.connect(self.parent_app.set_volume)
            bottom_row.addWidget(self.slider_fs_volume)

            bot_layout.addLayout(bottom_row)
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
            
            # Center Controls: ⏮, ↺, ▶ / ❚❚, ↻, ⏭
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
            self.btn_play.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT}; color: white;
                    border-radius: 23px; font-size: 18px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.3);
                }}
                QPushButton:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}
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
            self.slider = ClickableSlider(Qt.Orientation.Horizontal, self)
            self.slider.setRange(0, 1000)
            self.slider.setStyleSheet(SEEK_SLIDER_STYLE)
            self.slider.sliderPressed.connect(self.on_slider_pressed)
            self.slider.sliderReleased.connect(self.on_slider_released)
            self.slider.clicked_to_percentage.connect(self.parent_app.seek_to_percentage)
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
            
            btn_main_circle = """
                QPushButton {
                    background-color: rgba(20, 20, 20, 0.85); color: white;
                    border-radius: 24px; font-size: 15px; font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                }
                QPushButton:hover { background-color: #0078D4; border-color: #0078D4; }
            """

            self.btn_prev = QPushButton("⏮", self)
            self.btn_prev.setFixedSize(48, 48)
            self.btn_prev.setStyleSheet(btn_main_circle)
            self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
            self.btn_prev.clicked.connect(self.parent_app.play_prev_episode)

            self.btn_back = QPushButton("↺ 5s", self)
            self.btn_back.setFixedSize(62, 52)
            self.btn_back.setStyleSheet(btn_main_circle)
            self.btn_back.setToolTip("Tua lùi 5 giây (←)")
            self.btn_back.clicked.connect(lambda: self.parent_app.seek_relative(-5))

            self.btn_play = QPushButton("▶", self)
            self.btn_play.setFixedSize(68, 68)
            self.btn_play.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT}; color: white;
                    border-radius: 34px; font-size: 22px; font-weight: bold;
                    border: 2px solid rgba(255, 255, 255, 0.35);
                }}
                QPushButton:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}
                QPushButton:pressed {{ background-color: {COLOR_ACCENT_PRESSED}; }}
            """)
            self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
            self.btn_play.clicked.connect(self.parent_app.toggle_play)

            self.btn_forward = QPushButton("5s ↻", self)
            self.btn_forward.setFixedSize(62, 52)
            self.btn_forward.setStyleSheet(btn_main_circle)
            self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
            self.btn_forward.clicked.connect(lambda: self.parent_app.seek_relative(5))

            self.btn_next = QPushButton("⏭", self)
            self.btn_next.setFixedSize(48, 48)
            self.btn_next.setStyleSheet(btn_main_circle)
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

    def update_volume(self, volume: int, is_muted: bool):
        if hasattr(self, 'slider_fs_volume'):
            self.slider_fs_volume.blockSignals(True)
            self.slider_fs_volume.setValue(volume)
            self.slider_fs_volume.blockSignals(False)
        if hasattr(self, 'btn_fs_volume'):
            self.btn_fs_volume.setText("🔇" if (is_muted or volume == 0) else "🔊")

    def set_title(self, title):
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setText(f"🎬 {title}")
