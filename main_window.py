import os
import sys
import vlc
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QFileDialog, QFrame, QStackedWidget, QLabel, QPushButton
)
from PyQt6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent

import config
from config import VALID_VIDEO_EXTENSIONS
from player_controller import PlayerController
from styles import (
    MAIN_WINDOW_STYLE, CARD_STYLE, BTN_CONTROL_STYLE, 
    COLOR_ACCENT, COLOR_BG_APP
)
from utils import ThumbnailWorker, load_history, save_history, PreviewManager, setup_window_icon
from widgets import (
    LandingPage,
    PlayerControlsBar,
    PlaylistSidebar,
    FloatingVideoWindow,
    VideoOverlayPanel,
    VlcVideoWidget
)


class VideoPlayerApp(QMainWindow):
    """
    Cửa sổ chính của Fluent Media Player:
    - Bố cục tối ưu trải nghiệm: Khung phát Video chính bên trái, Playlist bên phải
    - Hỗ trợ chế độ Rạp phim (Thu gọn Playlist để tập trung xem video)
    - Tự động chuyển tập tiếp theo, ghi nhớ tiến độ phát
    - Kéo & thả tệp/thư mục trực tiếp vào cửa sổ
    - Phím tắt tiện lợi phong phú
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fluent Media Player")
        self.setGeometry(100, 40, 1180, 780)
        self.setMinimumSize(850, 550)
        self.setStyleSheet(MAIN_WINDOW_STYLE)
        self.setAcceptDrops(True)
        setup_window_icon(self)

        # Bộ điều khiển VLC Player
        self.player = PlayerController(self)
        self.player.playback_state_changed.connect(self._on_playback_state_changed)
        self.player.volume_changed.connect(self._on_volume_changed)
        self.player.rate_changed.connect(self._on_rate_changed)

        # Dữ liệu ứng dụng
        self.history = load_history()
        self.current_video_path = None
        self.movies_data = {}
        self.popout_window = None
        self.is_user_seeking = False
        self.is_fullscreen_mode = False
        self.is_playlist_visible = True
        self._was_maximized = False
        self._cursor_hidden = False

        # Worker tạo ảnh thu nhỏ (Thumbnail) bất đồng bộ
        self.thumb_worker = ThumbnailWorker()
        self.thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self.thumb_worker.start()

        # Quản lý xem trước Thumbnail (Seekbar Hover Preview - FEATURE-01)
        self.preview_manager = PreviewManager(self)
        self.preview_manager.preview_ready.connect(self._on_preview_ready)

        self.init_ui()
        self.init_shortcuts()

        # Timer cập nhật tiến độ (350ms)
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._update_progress_tick)
        self.timer.start()

    def init_ui(self):
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.stacked_widget.setLineWidth(0)
        self.stacked_widget.setStyleSheet("QStackedWidget { background-color: #000000; border: none; margin: 0px; padding: 0px; }")
        self.setCentralWidget(self.stacked_widget)

        # ============================================================
        # 1. TRANG MỞ ĐẦU (LANDING PAGE - INDEX 0)
        # ============================================================
        self.landing_page = LandingPage(self)
        self.landing_page.open_folder_clicked.connect(self.open_folder_dialog)
        self.landing_page.open_file_clicked.connect(self.open_file_dialog)
        self.landing_page.file_dropped.connect(self.handle_dropped_path)
        self.landing_page.resume_video_clicked.connect(self.play_single_file)
        self.landing_page.update_recent_history(self.history)
        self.stacked_widget.addWidget(self.landing_page)

        # ============================================================
        # 2. GIAO DIỆN PHÁT CHÍNH (MAIN PLAYER VIEW - INDEX 1)
        # ============================================================
        self.player_page = QWidget()
        player_page_layout = QHBoxLayout(self.player_page)
        player_page_layout.setContentsMargins(14, 12, 14, 14)
        player_page_layout.setSpacing(14)

        # --- CỘT TRÁI: KHUNG VIDEO VÀ THANH ĐIỀU KHIỂN ---
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Top Navigation Bar (Nút quay lại Home, Đường dẫn thư mục, Nút đổi thư mục)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_back_home = QPushButton("🏠 Trang chủ")
        self.btn_back_home.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_back_home.setToolTip("Quay lại màn hình chính")
        self.btn_back_home.clicked.connect(self.show_landing_page)
        top_bar.addWidget(self.btn_back_home)

        self.lbl_folder_path = QLabel("Chưa mở thư mục")
        self.lbl_folder_path.setStyleSheet("color: #888888; font-size: 12px; margin-left: 6px;")
        top_bar.addWidget(self.lbl_folder_path, stretch=1)

        self.btn_switch_folder = QPushButton("📁 Đổi thư mục")
        self.btn_switch_folder.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_switch_folder.clicked.connect(self.open_folder_dialog)
        top_bar.addWidget(self.btn_switch_folder)

        left_layout.addLayout(top_bar)

        # Khu vực phát Video (VlcVideoWidget)
        self.video_area_widget = QWidget()
        self.video_area_layout = QVBoxLayout(self.video_area_widget)
        self.video_area_layout.setContentsMargins(0, 0, 0, 0)

        self.video_container = VlcVideoWidget()
        self.video_container.setMinimumHeight(300)
        self.video_container.mouse_moved.connect(self._on_video_mouse_moved)
        self.video_container.mouse_left.connect(self._on_video_mouse_left)
        self.video_container.double_clicked.connect(self.toggle_fullscreen)
        self.video_area_layout.addWidget(self.video_container)

        # Placeholder khi video đang được Pop-out ra cửa sổ nổi
        self.popout_placeholder = QFrame()
        self.popout_placeholder.setMinimumHeight(280)
        self.popout_placeholder.setStyleSheet(f"""
            QFrame {{
                background-color: #141414;
                border: 2px dashed rgba(255, 255, 255, 0.15);
                border-radius: 12px;
            }}
        """)
        ph_layout = QVBoxLayout(self.popout_placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(10)

        lbl_ph_icon = QLabel("📺")
        lbl_ph_icon.setStyleSheet("font-size: 38px; background: transparent; border: none;")
        lbl_ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(lbl_ph_icon)

        lbl_ph_title = QLabel("Video đang phát ở chế độ Mini Player (Pop-out)")
        lbl_ph_title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        lbl_ph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(lbl_ph_title)

        lbl_ph_desc = QLabel("Cửa sổ nổi đang ghim trên các ứng dụng khác. Bấm nút dưới để đưa video về lại đây.")
        lbl_ph_desc.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none;")
        lbl_ph_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(lbl_ph_desc)

        btn_restore_ph = QPushButton("⤢ Thu Hồi Video Về Đây")
        btn_restore_ph.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT}; color: white; border-radius: 6px; 
                padding: 8px 18px; font-weight: bold; font-size: 13px; border: none;
            }}
            QPushButton:hover {{ background-color: #1084E3; }}
        """)
        btn_restore_ph.clicked.connect(self.restore_video_from_popout)
        ph_layout.addWidget(btn_restore_ph, alignment=Qt.AlignmentFlag.AlignCenter)

        self.popout_placeholder.hide()
        self.video_area_layout.addWidget(self.popout_placeholder)

        left_layout.addWidget(self.video_area_widget, stretch=1)

        # Thanh điều khiển PlayerControlsBar
        self.controls_bar = PlayerControlsBar(self)
        self.controls_bar.play_clicked.connect(self.toggle_play)
        self.controls_bar.prev_clicked.connect(self.play_prev_episode)
        self.controls_bar.next_clicked.connect(self.play_next_episode)
        self.controls_bar.rewind_clicked.connect(lambda: self.seek_relative(-5))
        self.controls_bar.forward_clicked.connect(lambda: self.seek_relative(5))
        self.controls_bar.seek_percentage.connect(self.seek_to_percentage)
        self.controls_bar.slider_pressed.connect(self._on_slider_pressed)
        self.controls_bar.slider_released.connect(self._on_slider_released)
        self.controls_bar.volume_changed.connect(self.set_volume)
        self.controls_bar.mute_toggled.connect(self.toggle_mute)
        self.controls_bar.speed_changed.connect(self.set_speed)
        self.controls_bar.fullscreen_clicked.connect(self.enter_fullscreen)
        self.controls_bar.popout_clicked.connect(self.open_popout_video)
        self.controls_bar.playlist_toggle_clicked.connect(self.toggle_playlist_sidebar)
        left_layout.addWidget(self.controls_bar)

        player_page_layout.addWidget(left_column, stretch=1)

        # --- CỘT PHẢI: SIDEBAR DANH SÁCH BỘ PHIM & TẬP PHIM ---
        self.sidebar = PlaylistSidebar(self)
        self.sidebar.episode_selected.connect(self.play_video_file)
        self.sidebar.change_folder_clicked.connect(self.open_folder_dialog)
        self.sidebar.close_sidebar_clicked.connect(self.toggle_playlist_sidebar)
        self.sidebar.thumbnails_needed.connect(self.thumb_worker.set_tasks)
        player_page_layout.addWidget(self.sidebar)

        self.stacked_widget.addWidget(self.player_page)

        # ============================================================
        # 3. TRANG TOÀN MÀN HÌNH (FULLSCREEN PAGE - INDEX 2)
        # ============================================================
        self.fullscreen_page = QWidget()
        self.fullscreen_page.setStyleSheet("background-color: #000000; border: none; margin: 0px; padding: 0px;")
        self.fullscreen_page_layout = QVBoxLayout(self.fullscreen_page)
        self.fullscreen_page_layout.setContentsMargins(0, 0, 0, 0)
        self.fullscreen_page_layout.setSpacing(0)
        self.fullscreen_page.setMouseTracking(True)
        self.fullscreen_page.installEventFilter(self)
        self.stacked_widget.addWidget(self.fullscreen_page)

        # Overlays điều khiển nổi
        self.main_overlay = VideoOverlayPanel(self.video_container, self, mode="main")
        self.fs_overlay = VideoOverlayPanel(self.video_container, self, mode="fullscreen")

    def init_shortcuts(self):
        """Đăng ký phím tắt thông minh và phổ biến nhất."""
        QShortcut(QKeySequence("Space"), self, self.toggle_play)
        QShortcut(QKeySequence("Left"), self, lambda: self.seek_relative(-5))
        QShortcut(QKeySequence("Right"), self, lambda: self.seek_relative(5))
        QShortcut(QKeySequence("Up"), self, lambda: self.change_volume(5))
        QShortcut(QKeySequence("Down"), self, lambda: self.change_volume(-5))
        QShortcut(QKeySequence("M"), self, self.toggle_mute)
        QShortcut(QKeySequence("F"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, self.exit_fullscreen)
        QShortcut(QKeySequence("P"), self, self.play_prev_episode)
        QShortcut(QKeySequence("Ctrl+Left"), self, self.play_prev_episode)
        QShortcut(QKeySequence("N"), self, self.play_next_episode)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.play_next_episode)
        QShortcut(QKeySequence("B"), self, self.toggle_playlist_sidebar)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_folder_dialog)
        QShortcut(QKeySequence("O"), self, self.open_file_dialog)
        QShortcut(QKeySequence("["), self, lambda: self.adjust_speed(-0.25))
        QShortcut(QKeySequence("]"), self, lambda: self.adjust_speed(0.25))

    # ---------------- ĐIỀU HƯỚNG & MỞ PHIM ----------------
    def show_landing_page(self):
        self.player.pause()
        self.landing_page.update_recent_history(self.history)
        self.stacked_widget.setCurrentIndex(0)

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục phim")
        if folder:
            self.load_folder(folder)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn tệp video", "", 
            "Video Files (*.mp4 *.mkv *.avi *.mov *.flv);;All Files (*.*)"
        )
        if file_path:
            self.play_single_file(file_path)

    def handle_dropped_path(self, path: str):
        if os.path.isdir(path):
            self.load_folder(path)
        elif os.path.isfile(path) and path.lower().endswith(VALID_VIDEO_EXTENSIONS):
            self.play_single_file(path)

    def load_folder(self, root_folder: str):
        self.lbl_folder_path.setText(root_folder)
        self.movies_data.clear()

        try:
            for root, dirs, files in os.walk(root_folder):
                v_files = [os.path.join(root, f) for f in files if f.lower().endswith(VALID_VIDEO_EXTENSIONS)]
                if v_files:
                    rel = os.path.relpath(root, root_folder)
                    name = "Tất cả tập phim" if rel == "." else rel
                    self.movies_data[name] = sorted(v_files)
        except Exception as e:
            print(f"Lỗi đọc thư mục: {e}")

        if not self.movies_data:
            return

        self.stacked_widget.setCurrentIndex(1)
        self.attach_video_to_main()
        self.sidebar.set_movies_data(self.movies_data, self.history)

        first_group = list(self.movies_data.keys())[0]
        if self.movies_data[first_group]:
            self.play_video_file(self.movies_data[first_group][0])

    def play_single_file(self, file_path: str):
        folder = os.path.dirname(file_path)
        self.lbl_folder_path.setText(folder)
        filename = os.path.basename(file_path)
        
        # Quét các tệp cùng thư mục để tạo danh sách tập liền kề
        sibling_videos = sorted([
            os.path.join(folder, f) for f in os.listdir(folder) 
            if f.lower().endswith(VALID_VIDEO_EXTENSIONS)
        ])
        if not sibling_videos:
            sibling_videos = [file_path]

        self.movies_data = {"Tập phim cùng thư mục": sibling_videos}
        self.stacked_widget.setCurrentIndex(1)
        self.attach_video_to_main()
        self.sidebar.set_movies_data(self.movies_data, self.history)
        self.play_video_file(file_path)

    def play_video_file(self, file_path: str):
        self.current_video_path = file_path
        filename = os.path.basename(file_path)

        self.preview_manager.set_video(file_path)
        self.attach_video_to_main()
        self.player.load_media(file_path)
        self.player.play()

        # Cập nhật thông tin giao diện
        self.controls_bar.update_title(filename)
        self.fs_overlay.set_title(filename)
        self.sidebar.select_episode(file_path)

        # Khôi phục vị trí xem trước đó
        history_info = self.history.get(file_path, {})
        last_sec = history_info.get("pos", 0)
        if last_sec > 1:
            QTimer.singleShot(350, lambda: self.player.set_time(int(last_sec * 1000)))

    # ---------------- ĐIỀU KHIỂN PHÁT VIDEO ----------------
    def toggle_play(self):
        self.player.toggle_play()

    def play_prev_episode(self):
        idx = self.sidebar.get_current_index()
        if idx > 0:
            prev_path = self.sidebar.get_episode_at_index(idx - 1)
            if prev_path:
                self.play_video_file(prev_path)

    def play_next_episode(self):
        idx = self.sidebar.get_current_index()
        if idx >= 0 and idx < self.sidebar.get_total_count() - 1:
            next_path = self.sidebar.get_episode_at_index(idx + 1)
            if next_path:
                self.play_video_file(next_path)

    def seek_relative(self, seconds: float):
        self.player.seek_relative(seconds)
        if self.is_fullscreen_mode:
            self.fs_overlay.show_overlay()
        elif self.popout_window:
            self.popout_window.show_overlay()
        else:
            self.main_overlay.show_overlay()

    def seek_to_percentage(self, pos_pct: float):
        self.player.seek_percentage(pos_pct)
        self.is_user_seeking = False

    def _on_slider_pressed(self):
        self.is_user_seeking = True

    def _on_slider_released(self):
        self.is_user_seeking = False

    def on_slider_pressed(self):
        self._on_slider_pressed()

    def on_slider_released(self):
        self._on_slider_released()

    def show_fullscreen_cursor(self):
        if self._cursor_hidden:
            self._cursor_hidden = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.video_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.fullscreen_page.setCursor(Qt.CursorShape.ArrowCursor)
            if hasattr(self, 'fs_overlay') and self.fs_overlay:
                self.fs_overlay.setCursor(Qt.CursorShape.ArrowCursor)

    def hide_fullscreen_cursor(self):
        if not self.is_fullscreen_mode:
            return
        if not self.is_user_seeking:
            self._cursor_hidden = True
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.video_container.setCursor(Qt.CursorShape.BlankCursor)
            self.fullscreen_page.setCursor(Qt.CursorShape.BlankCursor)
            if hasattr(self, 'fs_overlay') and self.fs_overlay:
                self.fs_overlay.setCursor(Qt.CursorShape.BlankCursor)

    def restore_cursor(self):
        self._cursor_hidden = False
        self.unsetCursor()
        self.video_container.unsetCursor()
        self.fullscreen_page.unsetCursor()
        if hasattr(self, 'fs_overlay') and self.fs_overlay:
            self.fs_overlay.unsetCursor()

    def set_volume(self, val: int):
        self.player.set_volume(val)

    def change_volume(self, delta: int):
        self.player.change_volume_relative(delta)

    def toggle_mute(self):
        self.player.toggle_mute()

    def set_speed(self, rate: float):
        self.player.set_rate(rate)

    def adjust_speed(self, delta: float):
        current_rate = self.player.get_rate()
        self.player.set_rate(round(current_rate + delta, 2))

    def toggle_playlist_sidebar(self):
        """Bật / Tắt Playlist Sidebar (Chế độ xem Rạp chiếu phim)."""
        self.is_playlist_visible = not self.is_playlist_visible
        self.sidebar.setVisible(self.is_playlist_visible)
        self.controls_bar.set_playlist_active(self.is_playlist_visible)
        QTimer.singleShot(100, self.main_overlay.reposition)

    # ---------------- HOVER & TIẾN ĐỘ ----------------
    def _on_video_mouse_moved(self):
        if self.is_fullscreen_mode:
            self.show_fullscreen_cursor()
            self.fs_overlay.show_overlay()
        elif self.popout_window is None:
            self.main_overlay.show_overlay()

    def _on_video_mouse_left(self):
        if not self.is_fullscreen_mode:
            self.main_overlay.check_and_hide_if_left()

    def eventFilter(self, watched, event):
        if hasattr(self, 'fullscreen_page') and watched == self.fullscreen_page:
            if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
                self._on_video_mouse_moved()
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                self.toggle_fullscreen()
                return True
        return super().eventFilter(watched, event)

    def _on_playback_state_changed(self, is_playing: bool):
        self.controls_bar.update_play_button(is_playing)
        self.main_overlay.update_play_button(is_playing)
        self.fs_overlay.update_play_button(is_playing)
        if self.popout_window:
            self.popout_window.update_play_button(is_playing)

    def _on_volume_changed(self, volume: int, is_muted: bool):
        self.controls_bar.update_volume(volume, is_muted)
        self.fs_overlay.update_volume(volume, is_muted)

    def _on_rate_changed(self, rate: float):
        self.controls_bar.update_speed(rate)

    def _on_thumbnail_ready(self, video_path: str, thumb_path: str):
        self.sidebar.update_thumbnail(video_path, thumb_path)

    def _on_preview_ready(self, video_path: str, bucket_sec: int, pixmap):
        self.controls_bar.update_preview_thumbnail(video_path, bucket_sec, pixmap)
        self.fs_overlay.update_preview_thumbnail(video_path, bucket_sec, pixmap)

    def _update_progress_tick(self):
        # Tự động phát tập tiếp theo khi hết video
        if self.player.get_state() == vlc.State.Ended:
            self.play_next_episode()
            return

        if self.player.is_playing() and self.current_video_path:
            total_ms = self.player.get_length()
            current_ms = self.player.get_time()

            if total_ms > 0:
                current_sec = current_ms / 1000.0
                total_sec = total_ms / 1000.0
                progress_pct = (current_sec / total_sec) * 100.0
                slider_val = int((current_ms / total_ms) * 1000)

                if not self.is_user_seeking:
                    self.controls_bar.update_slider(slider_val)
                    self.fs_overlay.update_slider(slider_val)
                    if self.popout_window:
                        self.popout_window.overlay.update_slider(slider_val)

                self.controls_bar.update_time(current_ms, total_ms)
                
                cur_str = PlayerController.format_time(current_ms)
                tot_str = PlayerController.format_time(total_ms)
                self.fs_overlay.update_time(cur_str, tot_str)
                if self.popout_window:
                    self.popout_window.overlay.update_time(cur_str, tot_str)

                # Lưu lịch sử
                self.history[self.current_video_path] = {
                    "pos": current_sec,
                    "pct": progress_pct
                }
                save_history(self.history)
                self.sidebar.update_progress(self.current_video_path, progress_pct)

    # ---------------- FULLSCREEN VIDEO ----------------
    def toggle_fullscreen(self):
        if self.is_fullscreen_mode:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.is_fullscreen_mode:
            return

        # Ghi nhớ trạng thái phóng to trước khi vào Fullscreen (BUG-01 Fix)
        self._was_maximized = self.isMaximized()

        if self.popout_window is not None:
            self.restore_video_from_popout()

        self.is_fullscreen_mode = True
        self.main_overlay.hide()

        self.video_container.setParent(self.fullscreen_page)
        self.fullscreen_page_layout.addWidget(self.video_container)
        self.video_container.setMinimumHeight(0)
        self.video_container.setMaximumHeight(16777215)
        self.video_container.show()
        self.attach_video_to_main()

        filename = os.path.basename(self.current_video_path) if self.current_video_path else "Fluent Media Player"
        self.fs_overlay.set_title(filename)
        self.fs_overlay.set_target_widget(self.video_container)
        self.fs_overlay.update_play_button(self.player.is_playing())

        self.stacked_widget.setCurrentIndex(2)
        self.showFullScreen()
        self.show_fullscreen_cursor()
        QTimer.singleShot(150, self.fs_overlay.show_overlay)

    def exit_fullscreen(self):
        if not self.is_fullscreen_mode:
            return

        self.is_fullscreen_mode = False
        self.restore_cursor()
        self.fs_overlay.hide()

        self.video_container.setParent(self.video_area_widget)
        self.video_area_layout.insertWidget(0, self.video_container)
        self.video_container.setMinimumHeight(300)
        self.video_container.show()
        self.attach_video_to_main()

        self.main_overlay.set_target_widget(self.video_container)
        self.fs_overlay.set_target_widget(self.video_container)

        self.stacked_widget.setCurrentIndex(1)
        
        # Khôi phục trạng thái cửa sổ chính xác (BUG-01 Fix)
        if getattr(self, "_was_maximized", False):
            self.showMaximized()
        else:
            self.showNormal()

        QTimer.singleShot(150, self.main_overlay.reposition)

    # ---------------- POP-OUT VIDEO (MINI PLAYER) ----------------
    def open_popout_video(self):
        if self.popout_window is not None:
            self.popout_window.raise_()
            self.popout_window.activateWindow()
            return

        if self.is_fullscreen_mode:
            self.exit_fullscreen()

        self.main_overlay.hide()
        self.fs_overlay.hide()
        self.popout_window = FloatingVideoWindow(self)

        self.video_container.setMinimumHeight(0)
        self.video_container.setMaximumHeight(16777215)
        self.video_container.setParent(self.popout_window.video_holder)
        self.popout_window.video_holder_layout.addWidget(self.video_container)
        self.video_container.show()

        # Cập nhật Win32 HWND mới cho VLC khi reparent sang Popout (BUG-05 Fix)
        self.player.set_hwnd(int(self.video_container.winId()))

        self.popout_placeholder.show()
        self.popout_window.update_play_button(self.player.is_playing())
        self.popout_window.show()

    def restore_video_from_popout(self):
        popout = self.popout_window
        self.popout_window = None

        # 1. Reparent video_container về lại cửa sổ chính TRƯỚC khi đóng popout
        self.video_container.setParent(self.video_area_widget)
        self.video_area_layout.insertWidget(0, self.video_container)
        self.video_container.setMinimumHeight(300)
        self.video_container.show()

        # 2. Ẩn placeholder và gắn lại HWND chuẩn cho VLC
        self.popout_placeholder.hide()
        self.attach_video_to_main()

        # 3. Gắn lại target cho Overlay và định vị
        self.main_overlay.set_target_widget(self.video_container)
        self.fs_overlay.set_target_widget(self.video_container)
        QTimer.singleShot(150, self.main_overlay.reposition)

        # 4. Đóng popout window an toàn nếu còn mở
        if popout is not None:
            popout.close()

        # 5. Kích hoạt cửa sổ chính nếu đang bị thu nhỏ
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def attach_video_to_main(self):
        self.player.set_hwnd(int(self.video_container.winId()))

    # ---------------- SỰ KIỆN CỬA SỔ & DRAG DROP ----------------
    def showEvent(self, event):
        super().showEvent(event)
        setup_window_icon(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_fullscreen_mode:
            self.main_overlay.reposition()
        else:
            self.fs_overlay.reposition()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self.is_fullscreen_mode:
            self.main_overlay.reposition()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.exists(path):
                self.handle_dropped_path(path)
                event.acceptProposedAction()

    def closeEvent(self, event):
        self.main_overlay.hide()
        self.fs_overlay.hide()
        if hasattr(self, 'preview_manager') and self.preview_manager:
            self.preview_manager.stop()
        if self.thumb_worker:
            self.thumb_worker.stop()
        if self.popout_window:
            popout = self.popout_window
            self.popout_window = None
            popout.close()
        self.player.stop()
        save_history(self.history)
        event.accept()
