from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMenu, QSizePolicy
)
from PyQt6.QtGui import QAction, QFontMetrics, QColor, QFont
from .clickable_slider import ClickableSlider
from .marquee_label import MarqueeLabel
from .preview_popup import VideoThumbnailPreview
from styles import (
    PLAYER_CONTROLS_CARD_STYLE, SEEK_SLIDER_STYLE, VOLUME_SLIDER_STYLE,
    BTN_PLAYER_GHOST_STYLE, BTN_PLAYER_SPEED_STYLE, BTN_PLAYER_ACTIVE_STYLE,
    BTN_PLAY_STYLE
)


class PlayerControlsBar(QFrame):
    """
    Thanh điều khiển phát video tối giản (Minimalist UI):
    - Hàng 1: Tiêu đề video độc lập với hiệu ứng chạy chữ ngang (MarqueeLabel) khi không gian hẹp
    - Hàng 2: Thanh tiến trình video gắn kết trực tiếp với mốc thời gian hiện tại (trái) và tổng/còn lại (phải)
    - Hàng 3: Bố cục 3 cụm cân đối — Âm lượng | Điều khiển phát chính | Tốc độ & Chế độ xem
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
        self.parent_app = parent
        self.setStyleSheet(PLAYER_CONTROLS_CARD_STYLE)
        self._show_remaining_time = False
        self._total_ms = 0
        self._current_ms = 0
        self._current_title = "Chưa phát video"
        self._speed_actions = {}

        # Popup xem trước thumbnail khi hover seekbar
        self.preview_popup = VideoThumbnailPreview(self)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(5)

        # ---------------- HÀNG 1: TIÊU ĐỀ VIDEO VỚI MARQUEE ----------------
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 2, 0)
        title_row.setSpacing(6)
        title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_title_icon = QLabel("🎬", self)
        lbl_title_icon.setFixedWidth(16)
        lbl_title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title_icon.setStyleSheet(
            "color: #888888; font-size: 11px; background: transparent; border: none;"
        )
        title_row.addWidget(lbl_title_icon)

        self.lbl_title = MarqueeLabel(
            self._current_title,
            self,
            fade_color=QColor("#161616"),
            text_color=QColor("#E0E0E0"),
        )
        title_font = QFont("Segoe UI")
        title_font.setPixelSize(12)
        title_font.setWeight(QFont.Weight.Medium)
        self.lbl_title.setFont(title_font)
        self.lbl_title.setToolTip(self._current_title)
        title_row.addWidget(self.lbl_title, stretch=1)

        main_layout.addLayout(title_row)

        # ---------------- HÀNG 2: THANH TIẾN TRÌNH & MỐC THỜI GIAN ----------------
        seek_row = QHBoxLayout()
        seek_row.setContentsMargins(2, 0, 2, 0)
        seek_row.setSpacing(10)
        seek_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_time_cur = QLabel("00:00", self)
        self.lbl_time_cur.setMinimumWidth(42)
        self.lbl_time_cur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_time_cur.setStyleSheet("""
            QLabel {
                color: #D4D4D4;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                background: transparent;
                border: none;
            }
        """)
        seek_row.addWidget(self.lbl_time_cur)

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setFixedHeight(20)
        self.seek_slider.setStyleSheet(SEEK_SLIDER_STYLE)
        self.seek_slider.sliderPressed.connect(self.slider_pressed.emit)
        self.seek_slider.sliderReleased.connect(self.slider_released.emit)
        self.seek_slider.clicked_to_percentage.connect(self.seek_percentage.emit)
        self.seek_slider.hover_moved.connect(self._on_seek_hover_moved)
        self.seek_slider.hover_left.connect(self._on_seek_hover_left)
        seek_row.addWidget(self.seek_slider, stretch=1)

        self.lbl_time_tot = QLabel("00:00", self)
        self.lbl_time_tot.setMinimumWidth(46)
        self.lbl_time_tot.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_time_tot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_time_tot.setToolTip("Bấm để chuyển đổi giữa thời lượng tổng và thời gian còn lại")
        self.lbl_time_tot.setStyleSheet("""
            QLabel {
                color: #909090;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #FFFFFF;
            }
        """)
        self.lbl_time_tot.mousePressEvent = self._toggle_time_display
        seek_row.addWidget(self.lbl_time_tot)

        # Alias tương thích ngược cho code hoặc test tham chiếu lbl_time
        self.lbl_time = self.lbl_time_tot

        main_layout.addLayout(seek_row)

        # ---------------- HÀNG 3: CÁC CỤM ĐIỀU KHIỂN CÂN ĐỐI (TRÁI / GIỮA / PHẢI) ----------------
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 2, 0, 0)
        ctrl_row.setSpacing(2)
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # === CỤM TRÁI: ÂM LƯỢNG ===
        self.btn_volume = QPushButton("🔊", self)
        self.btn_volume.setFixedSize(32, 32)
        self.btn_volume.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_volume.setToolTip("Tắt/Bật tiếng (M)")
        self.btn_volume.clicked.connect(self.mute_toggled.emit)
        ctrl_row.addWidget(self.btn_volume)

        self.volume_slider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMinimumWidth(42)
        self.volume_slider.setMaximumWidth(72)
        self.volume_slider.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.volume_slider.setFixedHeight(24)
        self.volume_slider.setStyleSheet(VOLUME_SLIDER_STYLE)
        self.volume_slider.setToolTip("Âm lượng (Lăn chuột hoặc ↑/↓)")
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        ctrl_row.addWidget(self.volume_slider)

        ctrl_row.addStretch(1)

        # === CỤM GIỮA: ĐIỀU KHIỂN PHÁT TRỌNG TÂM ===
        self.btn_prev = QPushButton("⏮", self)
        self.btn_prev.setFixedSize(32, 32)
        self.btn_prev.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        ctrl_row.addWidget(self.btn_prev)

        self.btn_rewind = QPushButton("↺ 5s", self)
        self.btn_rewind.setFixedHeight(32)
        self.btn_rewind.setMinimumWidth(42)
        self.btn_rewind.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_rewind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rewind.setToolTip("Tua lùi 5 giây (←)")
        self.btn_rewind.clicked.connect(self.rewind_clicked.emit)
        ctrl_row.addWidget(self.btn_rewind)

        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedSize(38, 38)
        self.btn_play.setStyleSheet(BTN_PLAY_STYLE)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
        self.btn_play.clicked.connect(self.play_clicked.emit)
        ctrl_row.addWidget(self.btn_play)

        self.btn_forward = QPushButton("5s ↻", self)
        self.btn_forward.setFixedHeight(32)
        self.btn_forward.setMinimumWidth(42)
        self.btn_forward.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_forward.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
        self.btn_forward.clicked.connect(self.forward_clicked.emit)
        ctrl_row.addWidget(self.btn_forward)

        self.btn_next = QPushButton("⏭", self)
        self.btn_next.setFixedSize(32, 32)
        self.btn_next.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        ctrl_row.addWidget(self.btn_next)

        ctrl_row.addStretch(1)

        # === CỤM PHẢI: TỐC ĐỘ PHÁT & CHẾ ĐỘ XEM ===
        self.btn_speed = QPushButton("1.0x", self)
        self.btn_speed.setFixedHeight(32)
        self.btn_speed.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_speed.setStyleSheet(BTN_PLAYER_SPEED_STYLE)
        self.btn_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed.setToolTip("Tốc độ phát ([ / ])")
        self._init_speed_menu()
        self._adjust_speed_button_width("1.0x")
        ctrl_row.addWidget(self.btn_speed)

        divider = QFrame(self)
        divider.setFixedSize(1, 18)
        divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.12); border: none; margin: 0px 2px;")
        ctrl_row.addWidget(divider)

        self.btn_popout = QPushButton("⧉", self)
        self.btn_popout.setFixedSize(32, 32)
        self.btn_popout.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_popout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_popout.setToolTip("Mở cửa sổ video thu nhỏ nổi (Picture-in-Picture)")
        self.btn_popout.clicked.connect(self.popout_clicked.emit)
        ctrl_row.addWidget(self.btn_popout)

        self.btn_playlist = QPushButton("📋", self)
        self.btn_playlist.setFixedSize(32, 32)
        self.btn_playlist.setStyleSheet(BTN_PLAYER_ACTIVE_STYLE)
        self.btn_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_playlist.setToolTip("Bật/Tắt khung danh sách tập (B)")
        self.btn_playlist.clicked.connect(self.playlist_toggle_clicked.emit)
        ctrl_row.addWidget(self.btn_playlist)

        self.btn_fullscreen = QPushButton("⤢", self)
        self.btn_fullscreen.setFixedSize(32, 32)
        self.btn_fullscreen.setStyleSheet(BTN_PLAYER_GHOST_STYLE)
        self.btn_fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
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
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #0078D4;
            }
        """)
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        self._speed_actions.clear()
        for spd in speeds:
            action = QAction(f"{spd}x", self)
            action.setCheckable(True)
            action.setChecked(abs(spd - 1.0) < 1e-3)
            action.triggered.connect(lambda checked, s=spd: self.speed_changed.emit(s))
            menu.addAction(action)
            self._speed_actions[round(spd, 2)] = action
        self.btn_speed.setMenu(menu)

    def _adjust_speed_button_width(self, text: str):
        fm = QFontMetrics(self.btn_speed.font())
        required = max(52, fm.horizontalAdvance(text) + 22, self.btn_speed.sizeHint().width() + 2)
        self.btn_speed.setMinimumWidth(required)
        self.btn_speed.updateGeometry()

    # ---------------- THUMBNAIL PREVIEW HOVER ----------------
    def _on_seek_hover_moved(self, val: int, pct: float, global_pos: QPoint):
        if self.parent_app and hasattr(self.parent_app, "should_allow_hover_overlay"):
            if not self.parent_app.should_allow_hover_overlay():
                self.preview_popup.hide_preview()
                return

        if self._total_ms <= 0:
            return

        hover_ms = int(pct * self._total_ms)
        slider_top_y = self.seek_slider.mapToGlobal(QPoint(0, 0)).y()

        # Lấy pixmap đã cache hoặc yêu cầu trích xuất ngầm
        pixmap = None
        video_path = getattr(self.parent_app, "current_video_path", None)
        if video_path and hasattr(self.parent_app, "preview_manager"):
            pm = self.parent_app.preview_manager
            bucket_sec = int(round(hover_ms / 2000.0) * 2)
            pixmap = pm.get_cached_preview(video_path, bucket_sec)
            if not pixmap:
                pm.request_preview(video_path, hover_ms)

        self.preview_popup.show_preview(global_pos.x(), slider_top_y, hover_ms, pixmap)

    def _on_seek_hover_left(self):
        self.preview_popup.hide_preview()

    def hide_overlays(self):
        self.preview_popup.hide_preview()
        if hasattr(self, "btn_speed") and self.btn_speed.menu() and self.btn_speed.menu().isVisible():
            self.btn_speed.menu().hide()

    def update_preview_thumbnail(self, video_path: str, bucket_sec: int, pixmap):
        if self.preview_popup.isVisible():
            self.preview_popup.set_thumbnail(pixmap)

    # ---------------- THỜI GIAN & TIẾN ĐỘ ----------------
    def _toggle_time_display(self, event):
        self._show_remaining_time = not self._show_remaining_time
        self._update_time_label()

    def _update_time_label(self):
        cur_str = self._format_time(self._current_ms)
        if self._show_remaining_time:
            remaining_ms = max(0, self._total_ms - self._current_ms)
            tot_str = "-" + self._format_time(remaining_ms)
        else:
            tot_str = self._format_time(self._total_ms)
        self.lbl_time_cur.setText(cur_str)
        self.lbl_time_tot.setText(tot_str)

    def update_time(self, current_ms: int, total_ms: int):
        self._current_ms = current_ms
        self._total_ms = total_ms
        self._update_time_label()

    def update_slider(self, val_0_to_1000: int):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(val_0_to_1000)

    def update_play_button(self, is_playing: bool):
        self.btn_play.setText("❚❚" if is_playing else "▶")

    def update_title(self, title: str):
        self._current_title = title or "Chưa phát video"
        self.lbl_title.setText(self._current_title)
        self.lbl_title.setToolTip(self._current_title)

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
        text = f"{speed}x"
        self.btn_speed.setText(text)
        rounded = round(speed, 2)
        for spd, act in self._speed_actions.items():
            act.setChecked(abs(spd - rounded) < 1e-3)
        self._adjust_speed_button_width(text)

    def set_playlist_active(self, active: bool):
        if active:
            self.btn_playlist.setStyleSheet(BTN_PLAYER_ACTIVE_STYLE)
        else:
            self.btn_playlist.setStyleSheet(BTN_PLAYER_GHOST_STYLE)

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
