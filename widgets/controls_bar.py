from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMenu
)
from PyQt6.QtGui import QAction
from .clickable_slider import ClickableSlider
from styles import (
    CARD_STYLE, SEEK_SLIDER_STYLE, VOLUME_SLIDER_STYLE,
    BTN_CONTROL_STYLE, BTN_PLAY_STYLE, COLOR_ACCENT
)

class PlayerControlsBar(QFrame):
    """
    Thanh điều khiển phía dưới video được thiết kế theo chuẩn Fluent UI hiện đại:
    - Thanh tua trực quan hỗ trợ click trực tiếp
    - Nhóm nút điều khiển trung tâm (Tập trước, tua 5s, Play/Pause, tua 5s, Tập tiếp)
    - Nhãn tên tập phim hiện tại
    - Bộ chỉnh âm lượng (Mute + Slider)
    - Nút chọn tốc độ phát (0.5x -> 2.0x)
    - Nút Pop-out Mini, Toàn màn hình và Thu gọn/Mở danh sách tập (Rạp chiếu phim)
    """
    play_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    fullscreen_clicked = pyqtSignal()
    popout_clicked = pyqtSignal()
    playlist_toggle_clicked = pyqtSignal()
    
    seek_percentage = pyqtSignal(float)
    slider_pressed = pyqtSignal()
    slider_released = pyqtSignal()
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal()
    speed_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self._show_remaining_time = False
        self._total_ms = 0
        self._current_ms = 0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(6)

        # ---------------- HÀNG 1: SEEK SLIDER & THỜI GIAN ----------------
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        self.lbl_time_cur = QLabel("00:00")
        self.lbl_time_cur.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold; font-family: 'Consolas', monospace;")
        slider_row.addWidget(self.lbl_time_cur)

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setStyleSheet(SEEK_SLIDER_STYLE)
        self.seek_slider.sliderPressed.connect(self.slider_pressed.emit)
        self.seek_slider.sliderReleased.connect(self.slider_released.emit)
        self.seek_slider.clicked_to_percentage.connect(self.seek_percentage.emit)
        slider_row.addWidget(self.seek_slider, stretch=1)

        self.lbl_time_tot = QLabel("00:00")
        self.lbl_time_tot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_time_tot.setToolTip("Bấm để chuyển đổi giữa thời lượng tổng và thời gian còn lại")
        self.lbl_time_tot.setStyleSheet("color: #999999; font-size: 12px; font-family: 'Consolas', monospace;")
        self.lbl_time_tot.mousePressEvent = self._toggle_time_display
        slider_row.addWidget(self.lbl_time_tot)

        main_layout.addLayout(slider_row)

        # ---------------- HÀNG 2: CÁC NÚT ĐIỀU KHIỂN CHÍNH ----------------
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        # Nhóm Trái: Tên tập phim hiện tại
        self.lbl_title = QLabel("Chưa phát video")
        self.lbl_title.setStyleSheet("color: #E0E0E0; font-size: 13px; font-weight: bold; max-width: 260px;")
        self.lbl_title.setWordWrap(False)
        ctrl_row.addWidget(self.lbl_title)

        ctrl_row.addStretch(1)

        # Nhóm Giữa: Điều khiển phát
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(36, 36)
        self.btn_prev.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        ctrl_row.addWidget(self.btn_prev)

        self.btn_rewind = QPushButton("↺ 5s")
        self.btn_rewind.setFixedHeight(36)
        self.btn_rewind.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_rewind.setToolTip("Tua lùi 5 giây (←)")
        self.btn_rewind.clicked.connect(self.rewind_clicked.emit)
        ctrl_row.addWidget(self.btn_rewind)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(42, 42)
        self.btn_play.setStyleSheet(BTN_PLAY_STYLE)
        self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
        self.btn_play.clicked.connect(self.play_clicked.emit)
        ctrl_row.addWidget(self.btn_play)

        self.btn_forward = QPushButton("5s ↻")
        self.btn_forward.setFixedHeight(36)
        self.btn_forward.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
        self.btn_forward.clicked.connect(self.forward_clicked.emit)
        ctrl_row.addWidget(self.btn_forward)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(36, 36)
        self.btn_next.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        ctrl_row.addWidget(self.btn_next)

        ctrl_row.addStretch(1)

        # Nhóm Phải: Âm lượng, Tốc độ, Pop-out, Playlist toggle, Fullscreen
        # Âm lượng
        self.btn_volume = QPushButton("🔊")
        self.btn_volume.setFixedSize(36, 36)
        self.btn_volume.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_volume.setToolTip("Tắt/Bật tiếng (M)")
        self.btn_volume.clicked.connect(self.mute_toggled.emit)
        ctrl_row.addWidget(self.btn_volume)

        self.volume_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(75)
        self.volume_slider.setStyleSheet(VOLUME_SLIDER_STYLE)
        self.volume_slider.setToolTip("Âm lượng (Lăn chuột hoặc ↑/↓)")
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        ctrl_row.addWidget(self.volume_slider)

        # Tốc độ phát (Speed Menu)
        self.btn_speed = QPushButton("1.0x")
        self.btn_speed.setFixedHeight(36)
        self.btn_speed.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_speed.setToolTip("Tốc độ phát ([ / ])")
        self._init_speed_menu()
        ctrl_row.addWidget(self.btn_speed)

        # Pop-out Mini
        self.btn_popout = QPushButton("⧉ Pop-out")
        self.btn_popout.setFixedHeight(36)
        self.btn_popout.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_popout.setToolTip("Mở cửa sổ video thu nhỏ nổi (Picture-in-Picture)")
        self.btn_popout.clicked.connect(self.popout_clicked.emit)
        ctrl_row.addWidget(self.btn_popout)

        # Ẩn/Hiện Playlist (Chế độ Rạp phim)
        self.btn_playlist = QPushButton("📋 Danh sách")
        self.btn_playlist.setFixedHeight(36)
        self.btn_playlist.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_playlist.setToolTip("Bật/Tắt khung danh sách tập (B)")
        self.btn_playlist.clicked.connect(self.playlist_toggle_clicked.emit)
        ctrl_row.addWidget(self.btn_playlist)

        # Fullscreen
        self.btn_fullscreen = QPushButton("⤢")
        self.btn_fullscreen.setFixedSize(36, 36)
        self.btn_fullscreen.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_fullscreen.setToolTip("Toàn màn hình (F / Đúp chuột)")
        self.btn_fullscreen.clicked.connect(self.fullscreen_clicked.emit)
        ctrl_row.addWidget(self.btn_fullscreen)

        main_layout.addLayout(ctrl_row)

    def _init_speed_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #202020;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #0078D4;
            }
        """)
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        for spd in speeds:
            action = QAction(f"{spd}x", self)
            action.triggered.connect(lambda checked, s=spd: self.speed_changed.emit(s))
            menu.addAction(action)
        self.btn_speed.setMenu(menu)

    def _toggle_time_display(self, event):
        self._show_remaining_time = not self._show_remaining_time
        self._update_tot_label()

    def _update_tot_label(self):
        if self._show_remaining_time:
            remaining_ms = max(0, self._total_ms - self._current_ms)
            self.lbl_time_tot.setText("-" + self._format_time(remaining_ms))
        else:
            self.lbl_time_tot.setText(self._format_time(self._total_ms))

    def update_time(self, current_ms: int, total_ms: int):
        self._current_ms = current_ms
        self._total_ms = total_ms
        self.lbl_time_cur.setText(self._format_time(current_ms))
        self._update_tot_label()

    def update_slider(self, val_0_to_1000: int):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(val_0_to_1000)

    def update_play_button(self, is_playing: bool):
        self.btn_play.setText("❚❚" if is_playing else "▶")

    def update_title(self, title: str):
        display_title = title if len(title) <= 30 else title[:27] + "..."
        self.lbl_title.setText(f"🎬 {display_title}")
        self.lbl_title.setToolTip(title)

    def update_volume(self, volume: int, is_muted: bool):
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        if is_muted or volume == 0:
            self.btn_volume.setText("🔇")
        elif volume < 50:
            self.btn_volume.setText("🔉")
        else:
            self.btn_volume.setText("🔊")

    def update_speed(self, speed: float):
        self.btn_speed.setText(f"{speed}x")

    def set_playlist_active(self, active: bool):
        if active:
            self.btn_playlist.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT}; color: white;
                    border: none; border-radius: 7px;
                    padding: 6px 12px; font-size: 13px; font-weight: bold;
                }}
            """)
        else:
            self.btn_playlist.setStyleSheet(BTN_CONTROL_STYLE)

    @staticmethod
    def _format_time(ms: int) -> str:
        if ms < 0:
            ms = 0
        total_sec = int(ms // 1000)
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
