from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMenu, QWidget
)
from PyQt6.QtGui import QAction, QFontMetrics
from .clickable_slider import ClickableSlider
from .preview_popup import VideoThumbnailPreview
from styles import (
    CARD_STYLE, SEEK_SLIDER_STYLE, VOLUME_SLIDER_STYLE,
    BTN_CONTROL_STYLE, BTN_PLAY_STYLE, COLOR_ACCENT
)

class PlayerControlsBar(QFrame):
    """
    Thanh điều khiển phía dưới video chuẩn YouTube / Netflix hiện đại:
    - Thanh tiến trình (Seekbar) trải dài toàn chiều rộng với Thumbnail Preview khi hover
    - Hàng nút điều khiển đồng nhất kích thước (36px), căn chỉnh thẳng hàng tuyệt đối
    - Nhóm trái: Play/Pause, Tập trước, Tua 5s, Tập tiếp, Âm lượng (icon + slider), Thời lượng
    - Nhóm giữa: Tiêu đề video tự co giãn thông minh
    - Nhóm phải: Tốc độ phát (Menu), Pop-out Mini, Bật/Tắt Danh sách tập, Toàn màn hình
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
        self.setStyleSheet(CARD_STYLE)
        self._show_remaining_time = False
        self._total_ms = 0
        self._current_ms = 0
        self._current_title = "Chưa phát video"
        
        # Popup xem trước thumbnail khi hover seekbar
        self.preview_popup = VideoThumbnailPreview(self)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(6)

        # ---------------- HÀNG 1: SEEKBAR TRẢI DÀI TOÀN BỘ CHIỀU RỘNG (YOUTUBE / NETFLIX STYLE) ----------------
        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setStyleSheet(SEEK_SLIDER_STYLE)
        self.seek_slider.sliderPressed.connect(self.slider_pressed.emit)
        self.seek_slider.sliderReleased.connect(self.slider_released.emit)
        self.seek_slider.clicked_to_percentage.connect(self.seek_percentage.emit)
        self.seek_slider.hover_moved.connect(self._on_seek_hover_moved)
        self.seek_slider.hover_left.connect(self._on_seek_hover_left)
        main_layout.addWidget(self.seek_slider)

        # ---------------- HÀNG 2: CÁC NÚT ĐIỀU KHIỂN ĐỒNG NHẤT CHIỀU CAO 36PX ----------------
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # === NHÓM TRÁI: ĐIỀU KHIỂN PHÁT, ÂM LƯỢNG VÀ THỜI GIAN ===
        # Play / Pause chính (36x36 tròn nổi bật)
        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.setStyleSheet(BTN_PLAY_STYLE)
        self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
        self.btn_play.clicked.connect(self.play_clicked.emit)
        ctrl_row.addWidget(self.btn_play)

        # Tập trước
        self.btn_prev = QPushButton("⏮", self)
        self.btn_prev.setFixedSize(36, 36)
        self.btn_prev.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_prev.setToolTip("Tập trước (Ctrl+← / P)")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        ctrl_row.addWidget(self.btn_prev)

        # Tua lùi 5s
        self.btn_rewind = QPushButton("↺ 5s", self)
        self.btn_rewind.setFixedSize(46, 36)
        self.btn_rewind.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_rewind.setToolTip("Tua lùi 5 giây (←)")
        self.btn_rewind.clicked.connect(self.rewind_clicked.emit)
        ctrl_row.addWidget(self.btn_rewind)

        # Tua tiến 5s
        self.btn_forward = QPushButton("5s ↻", self)
        self.btn_forward.setFixedSize(46, 36)
        self.btn_forward.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_forward.setToolTip("Tua tiến 5 giây (→)")
        self.btn_forward.clicked.connect(self.forward_clicked.emit)
        ctrl_row.addWidget(self.btn_forward)

        # Tập tiếp theo
        self.btn_next = QPushButton("⏭", self)
        self.btn_next.setFixedSize(36, 36)
        self.btn_next.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_next.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        ctrl_row.addWidget(self.btn_next)

        # Âm lượng
        self.btn_volume = QPushButton("🔊", self)
        self.btn_volume.setFixedSize(36, 36)
        self.btn_volume.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_volume.setToolTip("Tắt/Bật tiếng (M)")
        self.btn_volume.clicked.connect(self.mute_toggled.emit)
        ctrl_row.addWidget(self.btn_volume)

        self.volume_slider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(70)
        self.volume_slider.setFixedHeight(36)
        self.volume_slider.setStyleSheet(VOLUME_SLIDER_STYLE)
        self.volume_slider.setToolTip("Âm lượng (Lăn chuột hoặc ↑/↓)")
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        ctrl_row.addWidget(self.volume_slider)

        # Hiển thị thời gian: 00:00 / 00:00
        self.lbl_time = QLabel("00:00 / 00:00", self)
        self.lbl_time.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_time.setToolTip("Bấm để chuyển đổi giữa thời lượng tổng và thời gian còn lại")
        self.lbl_time.setStyleSheet("""
            QLabel {
                color: #CCCCCC;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                padding-left: 6px;
                padding-right: 6px;
            }
            QLabel:hover {
                color: #FFFFFF;
            }
        """)
        self.lbl_time.mousePressEvent = self._toggle_time_display
        ctrl_row.addWidget(self.lbl_time)

        # === NHÓM GIỮA: TIÊU ĐỀ PHIM CO GIÃN TỰ ĐỘNG ===
        ctrl_row.addSpacing(10)
        self.lbl_title = QLabel(self._current_title, self)
        self.lbl_title.setStyleSheet("color: #AAAAAA; font-size: 12px; font-weight: 500;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_row.addWidget(self.lbl_title, stretch=1)
        ctrl_row.addSpacing(10)

        # === NHÓM PHẢI: TỐC ĐỘ, POP-OUT, PLAYLIST, FULLSCREEN ===
        # Tốc độ phát (Pill Menu)
        self.btn_speed = QPushButton("1.0x", self)
        self.btn_speed.setFixedSize(50, 36)
        self.btn_speed.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_speed.setToolTip("Tốc độ phát ([ / ])")
        self._init_speed_menu()
        ctrl_row.addWidget(self.btn_speed)

        # Pop-out Mini Player
        self.btn_popout = QPushButton("⧉ Mini", self)
        self.btn_popout.setFixedHeight(36)
        self.btn_popout.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_popout.setToolTip("Mở cửa sổ video thu nhỏ nổi (Picture-in-Picture)")
        self.btn_popout.clicked.connect(self.popout_clicked.emit)
        ctrl_row.addWidget(self.btn_popout)

        # Bật/Tắt Playlist Sidebar (Rạp phim)
        self.btn_playlist = QPushButton("📋 Danh sách", self)
        self.btn_playlist.setFixedHeight(36)
        self.btn_playlist.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_playlist.setToolTip("Bật/Tắt khung danh sách tập (B)")
        self.btn_playlist.clicked.connect(self.playlist_toggle_clicked.emit)
        ctrl_row.addWidget(self.btn_playlist)

        # Toàn màn hình
        self.btn_fullscreen = QPushButton("⤢", self)
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
        self.lbl_time.setText(f"{cur_str} / {tot_str}")

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
        self._current_title = title
        # Giới hạn hiển thị tiêu đề để không đẩy lệch các nút điều khiển
        metrics = QFontMetrics(self.lbl_title.font())
        elided = metrics.elidedText(f"🎬 {title}", Qt.TextElideMode.ElideMiddle, 280)
        self.lbl_title.setText(elided)
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
                    border: none; border-radius: 8px;
                    padding: 0px 8px; font-size: 13px; font-weight: bold;
                    height: 36px; min-height: 36px; max-height: 36px;
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
