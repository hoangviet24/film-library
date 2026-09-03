import os
import sys
import vlc
import config
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QListWidgetItem, QPushButton, QSlider, QLabel, 
    QFileDialog, QFrame, QStackedWidget
)
from PyQt6.QtGui import QKeySequence, QShortcut

import config  # Khởi tạo VLC DLL trên Windows nếu cần
from config import VALID_VIDEO_EXTENSIONS
from utils import get_cached_thumbnail, ThumbnailWorker, load_history, save_history
from widgets import (
    AutoFitListWidget,
    EpisodeItemWidget,
    FloatingVideoWindow,
    VideoOverlayPanel,
    SmoothScrollArea,
    VlcVideoWidget
)


class VideoPlayerApp(QMainWindow):
    """
    Cửa sổ chính của ứng dụng phát video Fluent Media Player
    với đầy đủ tính năng chuyển tập phim tiếp theo/lùi lại (Prev/Next Episode),
    tự động phát tập tiếp theo khi hết phim, thanh trượt đồng bộ và giao diện hiện đại.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fluent Media Player")
        self.setGeometry(100, 40, 1150, 850)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F0F0F;
                color: #FFFFFF;
            }
            QLabel {
                color: #E0E0E0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        vlc_dir = config.VLC_PATH
        vlc_arg = [
            "--quiet", 
            "--no-xlib", 
            "--no-video-title-show",
            f'--plugin-path={os.path.join(vlc_dir, "plugins")}',
            f'--libvlc-path={os.path.join(vlc_dir, "libvlc.dll")}'
        ]
        # Khởi tạo VLC Instance & Media Player (Tắt log spam console)
        self.vlc_instance = vlc.Instance(vlc_arg)
        if self.vlc_instance is None:
            self.vlc_instance = vlc.Instance()
        if self.vlc_instance:
            self.media_player = self.vlc_instance.media_player_new()
        else:
            raise Exception(f"VLC instance is None! Check in {config.VLC_PATH}")
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)

        self.history = load_history()
        self.current_video_path = None
        self.movies_data = {}
        self.popout_window = None
        self.is_user_seeking = False
        self.is_fullscreen_mode = False

        # Khởi tạo Worker chạy ngầm tạo Thumbnail bất đồng bộ
        self.thumb_worker = ThumbnailWorker()
        self.thumb_worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumb_worker.start()

        self.init_ui()

        # Timer cập nhật tiến độ phát
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.update_ui_state)
        self.timer.start()

    def init_ui(self):
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # ---------------- 1. LANDING PAGE ----------------
        landing_widget = QWidget()
        landing_layout = QVBoxLayout(landing_widget)
        landing_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        landing_layout.setSpacing(20)

        lbl_app_logo = QLabel("🎬")
        lbl_app_logo.setStyleSheet("font-size: 64px;")
        lbl_app_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        landing_layout.addWidget(lbl_app_logo)

        lbl_welcome = QLabel("Chào mừng đến với Fluent Media Player")
        lbl_welcome.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFFFFF;")
        lbl_welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        landing_layout.addWidget(lbl_welcome)

        lbl_sub = QLabel("Trải nghiệm xem phim mượt mà, hiện đại và tiện lợi")
        lbl_sub.setStyleSheet("font-size: 13px; color: #888888; margin-bottom: 10px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        landing_layout.addWidget(lbl_sub)

        btn_start_open = QPushButton("📁 Chọn Thư Mục Phim")
        btn_start_open.setFixedSize(280, 56)
        btn_start_open.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; color: white; border-radius: 8px; 
                font-size: 15px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #1084E3; }
            QPushButton:pressed { background-color: #005A9E; }
        """)
        btn_start_open.clicked.connect(self.open_folder)
        landing_layout.addWidget(btn_start_open, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stacked_widget.addWidget(landing_widget)

        # ---------------- 2. MAIN SCROLLABLE UI (SMOOTH SCROLL) ----------------
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #0F0F0F;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(25, 25, 25, 0.6);
                width: 8px;
                margin: 4px 2px 4px 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.22);
                min-height: 35px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #0078D4;
            }
            QScrollBar::handle:vertical:pressed {
                background: #106EBE;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)

        self.main_content = QWidget()
        self.main_content_layout = QVBoxLayout(self.main_content)
        self.main_content_layout.setContentsMargins(24, 16, 24, 24)
        self.main_content_layout.setSpacing(16)

        # Top Action Bar
        self.top_bar_widget = QWidget()
        self.top_bar = QHBoxLayout(self.top_bar_widget)
        self.top_bar.setContentsMargins(0, 0, 0, 0)

        btn_change_folder = QPushButton("📁 Chọn Thư Mục Khác")
        btn_change_folder.setStyleSheet("""
            QPushButton {
                background-color: #202020; color: #E0E0E0; border-radius: 6px; 
                padding: 8px 16px; font-weight: bold; border: 1px solid #333333;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2D2D2D; border-color: #444444; color: #FFFFFF; }
        """)
        btn_change_folder.clicked.connect(self.open_folder)
        self.top_bar.addWidget(btn_change_folder)
        
        self.lbl_current_folder = QLabel("Chưa chọn thư mục")
        self.lbl_current_folder.setStyleSheet("color: #888888; font-size: 13px; margin-left: 10px;")
        self.top_bar.addWidget(self.lbl_current_folder)
        self.top_bar.addStretch()
        self.main_content_layout.addWidget(self.top_bar_widget)

        # KHUNG CHỨA VIDEO CHUYÊN DỤNG (VlcVideoWidget)
        self.video_area_widget = QWidget()
        self.video_area_layout = QVBoxLayout(self.video_area_widget)
        self.video_area_layout.setContentsMargins(0, 0, 0, 0)

        self.video_container = VlcVideoWidget()
        self.video_container.setMinimumHeight(280)  # Giới hạn tối thiểu khi thu nhỏ
        self.video_container.mouse_moved.connect(self.on_video_mouse_moved)
        self.video_container.mouse_left.connect(self.on_video_mouse_left)
        self.video_container.double_clicked.connect(self.toggle_fullscreen)
        self.video_area_layout.addWidget(self.video_container)

        # Placeholder khi video chuyển sang chế độ Pop-out
        self.popout_placeholder = QFrame()
        self.popout_placeholder.setMinimumHeight(240)
        self.popout_placeholder.setStyleSheet("background-color: #181818; border: 2px dashed #333333; border-radius: 10px;")
        placeholder_layout = QVBoxLayout(self.popout_placeholder)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ph_title = QLabel("📺 Video đang phát ở chế độ Mini Player (Pop-out)")
        lbl_ph_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        lbl_ph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ph_desc = QLabel("Bạn có thể điều khiển trên cửa sổ nổi hoặc bấm nút bên dưới để đưa video về đây.")
        lbl_ph_desc.setStyleSheet("color: #888888; font-size: 12px; margin-top: 4px;")
        lbl_ph_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_restore_main = QPushButton("⤢ Thu hồi Video về Cửa Sổ Chính")
        btn_restore_main.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; color: white; border-radius: 6px; 
                padding: 8px 18px; font-weight: bold; margin-top: 10px; border: none;
            }
            QPushButton:hover { background-color: #1084E3; }
        """)
        btn_restore_main.clicked.connect(self.restore_video_from_popout)
        placeholder_layout.addWidget(lbl_ph_title)
        placeholder_layout.addWidget(lbl_ph_desc)
        placeholder_layout.addWidget(btn_restore_main, alignment=Qt.AlignmentFlag.AlignCenter)
        self.popout_placeholder.hide()
        self.video_area_layout.addWidget(self.popout_placeholder)

        self.main_content_layout.addWidget(self.video_area_widget)

        # OVERLAY CONTROLS ĐỘC LẬP (KHÔNG GÂY MÀN ĐEN)
        self.main_overlay = VideoOverlayPanel(self.video_container, self, mode="main")
        self.fs_overlay = VideoOverlayPanel(self.video_container, self, mode="fullscreen")

        # CONTROLS BAR BÊN DƯỚI VIDEO
        self.controls_card = QFrame()
        self.controls_card.setStyleSheet("""
            QFrame {
                background-color: #181818;
                border-radius: 10px;
                border: 1px solid #282828;
                padding: 10px 16px;
            }
        """)
        controls_layout = QVBoxLayout(self.controls_card)
        controls_layout.setSpacing(10)

        # Thanh trượt tiến độ (Slider)
        self.slider_progress = QSlider(Qt.Orientation.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #2E2E2E;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0078D4;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60A5FA;
                transform: scale(1.2);
            }
        """)
        self.slider_progress.sliderPressed.connect(self.on_slider_pressed)
        self.slider_progress.sliderReleased.connect(self.on_slider_released)
        controls_layout.addWidget(self.slider_progress)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)
        
        btn_ctrl_style = """
            QPushButton {
                background-color: #242424; color: #FFFFFF;
                border-radius: 6px; padding: 7px 12px; font-size: 13px; font-weight: 500;
                border: 1px solid #333333;
            }
            QPushButton:hover { background-color: #333333; border-color: #444444; }
        """

        # Nút Tập trước
        btn_prev_ep = QPushButton("⏮")
        btn_prev_ep.setStyleSheet(btn_ctrl_style)
        btn_prev_ep.setToolTip("Tập trước (Ctrl+← / P)")
        btn_prev_ep.clicked.connect(self.play_prev_episode)
        btn_bar.addWidget(btn_prev_ep)

        # Nút Tua lùi 5s
        btn_back = QPushButton("↺ 5s")
        btn_back.setStyleSheet(btn_ctrl_style)
        btn_back.setToolTip("Tua lùi 5 giây (←)")
        btn_back.clicked.connect(lambda: self.seek_relative(-5))
        btn_bar.addWidget(btn_back)

        # Nút Play / Pause chính
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; border-radius: 20px;
                font-size: 16px; color: white; border: none; font-weight: bold;
            }
            QPushButton:hover { background-color: #1084E3; }
            QPushButton:pressed { background-color: #005A9E; }
        """)
        self.btn_play.setToolTip("Phát / Tạm dừng (Space)")
        self.btn_play.clicked.connect(self.toggle_play)
        btn_bar.addWidget(self.btn_play)

        # Nút Tua tiến 5s
        btn_forward = QPushButton("5s ↻")
        btn_forward.setStyleSheet(btn_ctrl_style)
        btn_forward.setToolTip("Tua tiến 5 giây (→)")
        btn_forward.clicked.connect(lambda: self.seek_relative(5))
        btn_bar.addWidget(btn_forward)

        # Nút Tập tiếp theo
        btn_next_ep = QPushButton("⏭")
        btn_next_ep.setStyleSheet(btn_ctrl_style)
        btn_next_ep.setToolTip("Tập tiếp theo (Ctrl+→ / N)")
        btn_next_ep.clicked.connect(self.play_next_episode)
        btn_bar.addWidget(btn_next_ep)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #AAAAAA; font-size: 12px; font-family: 'Consolas', monospace; margin-left: 8px;")
        btn_bar.addWidget(self.lbl_time)

        btn_bar.addStretch()

        # NÚT FULLSCREEN DEDICATED
        self.btn_fullscreen = QPushButton("⤢ Fullscreen")
        self.btn_fullscreen.setStyleSheet(btn_ctrl_style)
        self.btn_fullscreen.setToolTip("Xem toàn màn hình (F)")
        self.btn_fullscreen.clicked.connect(self.enter_fullscreen)
        btn_bar.addWidget(self.btn_fullscreen)

        # NÚT POP-OUT
        self.btn_popout = QPushButton("⧉ Pop-out Mini")
        self.btn_popout.setStyleSheet(btn_ctrl_style)
        self.btn_popout.setToolTip("Mở cửa sổ video thu nhỏ nổi trên các ứng dụng khác")
        self.btn_popout.clicked.connect(self.open_popout_video)
        btn_bar.addWidget(self.btn_popout)

        controls_layout.addLayout(btn_bar)
        self.main_content_layout.addWidget(self.controls_card)

        # ---------------- BỐ CỤC DỌC: PHIM TRÊN - TẬP DƯỚI ----------------
        self.lbl_movies_header = QLabel("🎬 DANH SÁCH BỘ PHIM")
        self.lbl_movies_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #0078D4; margin-top: 8px;")
        self.main_content_layout.addWidget(self.lbl_movies_header)

        self.list_movies = AutoFitListWidget()
        self.list_movies.setStyleSheet("""
            QListWidget {
                background-color: #181818;
                border-radius: 8px;
                border: 1px solid #242424;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-bottom: 1px solid #222222;
                color: #CCCCCC;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #202020;
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #0078D4;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        self.list_movies.itemClicked.connect(self.on_movie_selected)
        self.main_content_layout.addWidget(self.list_movies)

        self.lbl_episodes_header = QLabel("🎞️ CÁC TẬP PHIM & TIẾN ĐỘ")
        self.lbl_episodes_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #0078D4; margin-top: 8px;")
        self.main_content_layout.addWidget(self.lbl_episodes_header)

        self.list_episodes = AutoFitListWidget()
        self.list_episodes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_episodes.setStyleSheet("""
            QListWidget {
                background-color: #181818;
                border-radius: 8px;
                border: 1px solid #242424;
            }
            QListWidget::item {
                border-bottom: 1px solid #222222;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #222222;
            }
            QListWidget::item:selected {
                background-color: #2A2A2A;
                border: 1px solid #0078D4;
            }
        """)
        self.list_episodes.itemClicked.connect(self.on_episode_selected)
        self.main_content_layout.addWidget(self.list_episodes)

        self.scroll_area.setWidget(self.main_content)
        self.stacked_widget.addWidget(self.scroll_area)

        # ---------------- 3. FULLSCREEN PAGE (VIDEO 100%) ----------------
        # Trang riêng cho chế độ toàn màn hình, video_container sẽ được reparent vào đây
        self.fullscreen_page = QWidget()
        self.fullscreen_page.setStyleSheet("background-color: #000000;")
        self.fullscreen_page_layout = QVBoxLayout(self.fullscreen_page)
        self.fullscreen_page_layout.setContentsMargins(0, 0, 0, 0)
        self.fullscreen_page_layout.setSpacing(0)
        self.stacked_widget.addWidget(self.fullscreen_page)  # index 2

        # Phím tắt Toàn màn hình & Phím điều khiển
        QShortcut(QKeySequence("F"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, self.exit_fullscreen)
        QShortcut(QKeySequence("Space"), self, self.toggle_play)
        QShortcut(QKeySequence("Left"), self, lambda: self.seek_relative(-5))
        QShortcut(QKeySequence("Right"), self, lambda: self.seek_relative(5))
        QShortcut(QKeySequence("Ctrl+Left"), self, self.play_prev_episode)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.play_next_episode)
        QShortcut(QKeySequence("P"), self, self.play_prev_episode)
        QShortcut(QKeySequence("N"), self, self.play_next_episode)

    # ---------------- HOVER VÀ CUỘN ----------------
    def on_video_mouse_moved(self):
        if self.is_fullscreen_mode:
            self.fs_overlay.show_overlay()
        elif self.popout_window is None:
            self.main_overlay.show_overlay()

    def on_video_mouse_left(self):
        if not self.is_fullscreen_mode:
            self.main_overlay.check_and_hide_if_left()

    def on_scroll_changed(self):
        if not self.is_fullscreen_mode:
            self.main_overlay.hide()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self.is_fullscreen_mode:
            self.main_overlay.reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_fullscreen_mode:
            self.main_overlay.reposition()
            # Video luôn chiếm 70% chiều cao cửa sổ chính
            video_h = int(self.height() * 0.70)
            self.video_container.setFixedHeight(max(video_h, 280))
        else:
            self.fs_overlay.reposition()

    # ---------------- CHUYỂN TẬP PHIM (PREV / NEXT EPISODE) ----------------
    def get_current_episode_index(self) -> int:
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == self.current_video_path:
                return i
        return -1

    def play_prev_episode(self):
        idx = self.get_current_episode_index()
        if idx > 0:
            self.list_episodes.setCurrentRow(idx - 1)
            prev_item = self.list_episodes.item(idx - 1)
            self.on_episode_selected(prev_item)

    def play_next_episode(self):
        idx = self.get_current_episode_index()
        if idx >= 0 and idx < self.list_episodes.count() - 1:
            self.list_episodes.setCurrentRow(idx + 1)
            next_item = self.list_episodes.item(idx + 1)
            self.on_episode_selected(next_item)

    # ---------------- FULLSCREEN VIDEO (TỨC THÌ, KHÔNG ĐỔI HWND) ----------------
    def toggle_fullscreen(self):
        if self.is_fullscreen_mode:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.is_fullscreen_mode:
            return
        
        if self.popout_window is not None:
            self.restore_video_from_popout()

        self.is_fullscreen_mode = True
        self.main_overlay.hide()

        # Reparent video_container lên fullscreen_page (index 2) → video chiếm 100% màn hình
        self.video_container.setParent(self.fullscreen_page)
        self.fullscreen_page_layout.addWidget(self.video_container)
        self.video_container.setMinimumHeight(0)
        self.video_container.setMaximumHeight(16777215)

        filename = os.path.basename(self.current_video_path) if self.current_video_path else "Fluent Media Player"
        self.fs_overlay.set_title(filename)
        self.fs_overlay.set_target_widget(self.video_container)
        self.fs_overlay.update_play_button(self.media_player.is_playing())

        self.stacked_widget.setCurrentIndex(2)
        self.showFullScreen()
        QTimer.singleShot(150, self.fs_overlay.show_overlay)

    def exit_fullscreen(self):
        if not self.is_fullscreen_mode:
            return
        
        self.is_fullscreen_mode = False
        self.fs_overlay.hide()

        # Reparent video_container về lại video_area_widget trong scroll area
        self.video_container.setParent(self.video_area_widget)
        self.video_area_layout.insertWidget(0, self.video_container)
        self.main_overlay.set_target_widget(self.video_container)
        self.fs_overlay.set_target_widget(self.video_container)

        self.stacked_widget.setCurrentIndex(1)
        self.showNormal()

        # Khôi phục tỷ lệ 70% sau khi thoát fullscreen
        def restore_size():
            video_h = int(self.height() * 0.70)
            self.video_container.setFixedHeight(max(video_h, 280))
            self.main_overlay.reposition()

        QTimer.singleShot(150, restore_size)

    # ---------------- POP-OUT VIDEO (REPARENTING CHUẨN XÁC) ----------------
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
        
        # Reparent video_container sang popout_window
        self.video_container.setParent(self.popout_window.video_holder)
        self.popout_window.video_holder_layout.addWidget(self.video_container)
        
        self.popout_placeholder.show()
        self.popout_window.update_play_button(self.media_player.is_playing())
        self.popout_window.show()

    def restore_video_from_popout(self):
        if self.popout_window is not None:
            popout_ref = self.popout_window
            self.popout_window = None
            popout_ref.close()

        # Reparent video_container về lại cửa sổ chính
        self.video_container.setParent(self.video_area_widget)
        self.video_area_layout.insertWidget(0, self.video_container)
        self.popout_placeholder.hide()

        self.main_overlay.set_target_widget(self.video_container)
        self.fs_overlay.set_target_widget(self.video_container)
        QTimer.singleShot(150, self.main_overlay.reposition)

    def attach_video_to_main(self):
        if sys.platform.startswith('win'):
            self.media_player.set_hwnd(int(self.video_container.winId()))

    # ---------------- LOGIC PHÁT VIDEO & QUẢN LÝ TẬP ----------------
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục phim")
        if folder:
            self.lbl_current_folder.setText(folder)
            self.attach_video_to_main()
            self.stacked_widget.setCurrentIndex(1)
            self.scan_movies_safe(folder)

    def scan_movies_safe(self, root_folder):
        self.movies_data.clear()
        self.list_movies.clear()
        self.list_episodes.clear()

        try:
            for root, dirs, files in os.walk(root_folder):
                video_files = [os.path.join(root, f) for f in files if f.lower().endswith(VALID_VIDEO_EXTENSIONS)]
                if video_files:
                    rel_path = os.path.relpath(root, root_folder)
                    group_name = "Phim Gốc / Khác" if rel_path == "." else rel_path
                    self.movies_data[group_name] = sorted(video_files)
        except Exception as e:
            print(f"Lỗi quét thư mục: {e}")

        for group in self.movies_data.keys():
            self.list_movies.addItem(group)

        self.list_movies.update_height()

        if self.list_movies.count() > 0:
            self.list_movies.setCurrentRow(0)
            self.on_movie_selected(self.list_movies.item(0))

    def on_movie_selected(self, item):
        group_name = item.text()
        self.list_episodes.clear()
        
        videos = self.movies_data.get(group_name, [])
        missing_thumbs = []

        for file_path in videos:
            filename = os.path.basename(file_path)
            history_data = self.history.get(file_path, {})
            progress_pct = history_data.get("pct", 0)

            # Kiểm tra nhanh ảnh thumbnail trong cache
            cached_thumb = get_cached_thumbnail(file_path)
            if not cached_thumb:
                missing_thumbs.append(file_path)

            ep_widget = EpisodeItemWidget(filename, progress_pct, cached_thumb)
            
            list_item = QListWidgetItem(self.list_episodes)
            list_item.setSizeHint(QSize(0, 84))
            list_item.setData(Qt.ItemDataRole.UserRole, file_path)

            self.list_episodes.addItem(list_item)
            self.list_episodes.setItemWidget(list_item, ep_widget)

        self.list_episodes.update_height()

        # Đẩy danh sách video chưa có thumbnail cho worker chạy ngầm xử lý
        if missing_thumbs:
            self.thumb_worker.set_tasks(missing_thumbs)

        # TỰ ĐỘNG CHỌN & PHÁT VIDEO ĐẦU TIÊN
        if self.list_episodes.count() > 0:
            self.list_episodes.setCurrentRow(0)
            first_item = self.list_episodes.item(0)
            self.on_episode_selected(first_item)

    def on_thumbnail_ready(self, video_path, thumb_path):
        """
        Nhận tín hiệu từ Worker chạy ngầm khi tạo xong thumbnail và cập nhật giao diện.
        """
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == video_path:
                widget = self.list_episodes.itemWidget(item)
                if widget and hasattr(widget, 'set_thumbnail'):
                    widget.set_thumbnail(thumb_path)
                break

    def on_episode_selected(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        self.current_video_path = file_path

        # Đảm bảo video render đúng vào video_container
        if sys.platform.startswith('win'):
            self.media_player.set_hwnd(int(self.video_container.winId()))

        media = self.vlc_instance.media_new(file_path)
        self.media_player.set_media(media)
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)
        self.media_player.play()
        self.update_play_buttons(True)

        history_data = self.history.get(file_path, {})
        last_pos_sec = history_data.get("pos", 0)
        QTimer.singleShot(350, lambda: self.media_player.set_time(int(last_pos_sec * 1000)))

        filename = os.path.basename(file_path)
        self.fs_overlay.set_title(filename)

    def toggle_play(self):
        if self.media_player.is_playing():
            self.media_player.pause()
            self.update_play_buttons(False)
        else:
            self.media_player.play()
            self.update_play_buttons(True)

    def update_play_buttons(self, is_playing: bool):
        self.btn_play.setText("❚❚" if is_playing else "▶")
        self.main_overlay.update_play_button(is_playing)
        self.fs_overlay.update_play_button(is_playing)
        if self.popout_window:
            self.popout_window.update_play_button(is_playing)

    def seek_relative(self, seconds):
        if self.media_player.get_length() > 0:
            current_time = self.media_player.get_time()
            target_time = max(0, current_time + (seconds * 1000))
            self.media_player.set_time(int(target_time))
            if self.is_fullscreen_mode:
                self.fs_overlay.show_overlay()
            elif self.popout_window:
                self.popout_window.show_overlay()
            else:
                self.main_overlay.show_overlay()

    def on_slider_pressed(self):
        self.is_user_seeking = True

    def on_slider_released(self):
        if self.media_player.get_length() > 0:
            pos_pct = self.slider_progress.value() / 1000.0
            self.media_player.set_position(pos_pct)
        self.is_user_seeking = False

    def seek_to_percentage(self, pos_pct: float):
        if self.media_player.get_length() > 0:
            self.media_player.set_position(pos_pct)
        self.is_user_seeking = False

    def update_ui_state(self):
        # Tự động chuyển sang tập tiếp theo khi xem xong video
        if self.media_player.get_state() == vlc.State.Ended:
            self.play_next_episode()
            return

        if self.media_player.is_playing() and self.current_video_path:
            total_ms = self.media_player.get_length()
            current_ms = self.media_player.get_time()

            if total_ms > 0:
                current_sec = current_ms / 1000.0
                total_sec = total_ms / 1000.0
                progress_pct = (current_sec / total_sec) * 100
                slider_val = int((current_ms / total_ms) * 1000)

                if not self.is_user_seeking:
                    self.slider_progress.setValue(slider_val)
                    self.fs_overlay.update_slider(slider_val)
                    if self.popout_window:
                        self.popout_window.overlay.update_slider(slider_val)
                
                cur_str = f"{int(current_sec//60):02d}:{int(current_sec%60):02d}"
                tot_str = f"{int(total_sec//60):02d}:{int(total_sec%60):02d}"
                self.lbl_time.setText(f"{cur_str} / {tot_str}")
                self.fs_overlay.update_time(cur_str, tot_str)
                if self.popout_window:
                    self.popout_window.overlay.update_time(cur_str, tot_str)

                self.history[self.current_video_path] = {
                    "pos": current_sec,
                    "pct": progress_pct
                }
                save_history(self.history)

                # Cập nhật thanh tiến độ trên danh sách tập
                for i in range(self.list_episodes.count()):
                    item = self.list_episodes.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.current_video_path:
                        widget = self.list_episodes.itemWidget(item)
                        if widget and hasattr(widget, 'progress_bar'):
                            widget.progress_bar.setValue(int(progress_pct))

    def closeEvent(self, event):
        self.main_overlay.hide()
        self.fs_overlay.hide()
        if self.thumb_worker:
            self.thumb_worker.stop()
        if self.popout_window:
            self.popout_window.close()
        save_history(self.history)
        event.accept()
