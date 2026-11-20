import os
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTabWidget, QWidget, QFrame, QScrollArea, QMessageBox
)
from security import FileSecurityError, open_in_explorer_safely, sanitize_for_log
from styles import (
    DIALOG_STYLE, BTN_CONTROL_STYLE, BTN_PRIMARY_STYLE, SCROLLBAR_STYLE,
    COLOR_BG_CARD, COLOR_BG_ELEVATED, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_BORDER_SUBTLE
)
from utils import (
    get_cached_thumbnail, generate_thumbnail, get_app_icon,
    VideoMetadataWorker
)


class VideoPropertiesDialog(QDialog):
    """
    Cửa sổ hiển thị thông tin chi tiết của Video (Video Properties):
    - Thiết kế theo phong cách Windows 11 Properties kết hợp Fluent Dark Theme
    - Hiển thị nổi bật các thông số ưu tiên: Resolution, Quality, FPS, Duration, File Size
    - Chia thành 4 Tab rõ ràng: General, Video, Audio, Subtitles
    - Truy xuất metadata bất đồng bộ qua VideoMetadataWorker (FFprobe / LibVLC / OpenCV)
    """
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = os.path.abspath(file_path)
        self.worker = None

        filename = os.path.basename(self.file_path)
        self.setWindowTitle(f"{filename} - Properties")
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(540, 560)
        self.resize(580, 620)
        self.setStyleSheet(DIALOG_STYLE)
        # Tắt nút "?" mặc định trên thanh tiêu đề của Windows Dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        self._start_metadata_loading()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ============================================================
        # 1. HEADER CARD (THUMBNAIL + TÊN FILE + THÔNG SỐ ƯU TIÊN)
        # ============================================================
        self.header_card = QFrame()
        self.header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(14)

        # Thumbnail preview (16:9)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(128, 72)
        self.lbl_thumb.setScaledContents(True)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_header_thumbnail()
        header_layout.addWidget(self.lbl_thumb)

        # Tên file + Badges thông số quan trọng
        header_info = QVBoxLayout()
        header_info.setSpacing(8)
        header_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_header_title = QLabel(os.path.basename(self.file_path))
        self.lbl_header_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_header_title.setWordWrap(True)
        self.lbl_header_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_header_title.setStyleSheet("""
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 700;
            background: transparent;
            border: none;
        """)
        header_info.addWidget(self.lbl_header_title)

        # Hàng Badges ưu tiên: Quality | Resolution | FPS | Duration | File Size
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        self.badge_quality = self._create_badge("Loading...", is_accent=True)
        self.badge_resolution = self._create_badge("...")
        self.badge_fps = self._create_badge("...")
        self.badge_duration = self._create_badge("...")
        self.badge_size = self._create_badge("...")

        badges_layout.addWidget(self.badge_quality)
        badges_layout.addWidget(self.badge_resolution)
        badges_layout.addWidget(self.badge_fps)
        badges_layout.addWidget(self.badge_duration)
        badges_layout.addWidget(self.badge_size)
        badges_layout.addStretch()

        header_info.addLayout(badges_layout)
        header_layout.addLayout(header_info, stretch=1)
        main_layout.addWidget(self.header_card)

        # ============================================================
        # 2. TABS PHÂN CHIA THÔNG TIN (GENERAL / VIDEO / AUDIO / SUBTITLES)
        # ============================================================
        self.tab_widget = QTabWidget()

        self.tab_general = QWidget()
        self.tab_video = QWidget()
        self.tab_audio = QWidget()
        self.tab_subtitles = QWidget()

        self.tab_widget.addTab(self.tab_general, "General")
        self.tab_widget.addTab(self.tab_video, "Video")
        self.tab_widget.addTab(self.tab_audio, "Audio")
        self.tab_widget.addTab(self.tab_subtitles, "Subtitles")

        self._init_general_tab()
        self._init_video_tab()
        self._init_audio_tab()
        self._init_subtitles_tab()

        main_layout.addWidget(self.tab_widget, stretch=1)

        # ============================================================
        # 3. FOOTER BUTTONS
        # ============================================================
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)

        self.lbl_engine_status = QLabel("⏳ Analyzing video metadata...")
        self.lbl_engine_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        footer_layout.addWidget(self.lbl_engine_status)

        footer_layout.addStretch()

        self.btn_open_loc = QPushButton("📂 Open File Location")
        self.btn_open_loc.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_open_loc.clicked.connect(self._open_file_location)
        footer_layout.addWidget(self.btn_open_loc)

        self.btn_copy_path = QPushButton("📋 Copy Path")
        self.btn_copy_path.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_copy_path.clicked.connect(self._copy_full_path)
        footer_layout.addWidget(self.btn_copy_path)

        self.btn_close = QPushButton("OK")
        self.btn_close.setMinimumWidth(85)
        self.btn_close.setStyleSheet(BTN_PRIMARY_STYLE)
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setDefault(True)
        footer_layout.addWidget(self.btn_close)

        main_layout.addLayout(footer_layout)

    def _create_badge(self, text: str, is_accent: bool = False) -> QLabel:
        lbl = QLabel(text)
        if is_accent:
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLOR_ACCENT};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLOR_BG_ELEVATED};
                    color: {COLOR_TEXT_SECONDARY};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
        return lbl

    def _load_header_thumbnail(self):
        thumb = get_cached_thumbnail(self.file_path)
        if not thumb and os.path.exists(self.file_path):
            thumb = generate_thumbnail(self.file_path)
        if thumb and os.path.exists(thumb):
            self.lbl_thumb.setPixmap(QPixmap(thumb))
            self.lbl_thumb.setStyleSheet("background-color: #101010; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);")
        else:
            self.lbl_thumb.setText("🎬")
            self.lbl_thumb.setStyleSheet("background-color: #1C1C1C; color: #777777; font-size: 26px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);")

    def _create_kv_row(self, grid: QGridLayout, row_idx: int, label_text: str, default_val: str = "Loading...") -> QLabel:
        lbl_key = QLabel(label_text)
        lbl_key.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 500; background: transparent; border: none;")
        lbl_key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lbl_key.setFixedWidth(145)

        lbl_val = QLabel(default_val)
        lbl_val.setTextFormat(Qt.TextFormat.PlainText)
        lbl_val.setWordWrap(True)
        lbl_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_val.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        grid.addWidget(lbl_key, row_idx, 0)
        grid.addWidget(lbl_val, row_idx, 1)
        return lbl_val

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.07); border: none;")
        return line

    # ---------------- TAB 1: GENERAL ----------------
    def _init_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        self.gen_name = self._create_kv_row(grid, 0, "File Name:")
        self.gen_type = self._create_kv_row(grid, 1, "File Type:")
        self.gen_location = self._create_kv_row(grid, 2, "File Location:")
        self.gen_size = self._create_kv_row(grid, 3, "File Size:")

        grid.addWidget(self._create_separator(), 4, 0, 1, 2)

        self.gen_created = self._create_kv_row(grid, 5, "Created Date:")
        self.gen_modified = self._create_kv_row(grid, 6, "Modified Date:")
        self.gen_accessed = self._create_kv_row(grid, 7, "Last Accessed:")

        layout.addLayout(grid)
        layout.addStretch()

    # ---------------- TAB 2: VIDEO ----------------
    def _init_video_tab(self):
        layout = QVBoxLayout(self.tab_video)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        self.vid_resolution = self._create_kv_row(grid, 0, "Resolution:")
        self.vid_quality = self._create_kv_row(grid, 1, "Video Quality:")
        self.vid_fps = self._create_kv_row(grid, 2, "Frame Rate (FPS):")
        self.vid_duration = self._create_kv_row(grid, 3, "Duration:")

        grid.addWidget(self._create_separator(), 4, 0, 1, 2)

        self.vid_codec = self._create_kv_row(grid, 5, "Video Codec:")
        self.vid_bitrate = self._create_kv_row(grid, 6, "Bitrate:")
        self.vid_aspect = self._create_kv_row(grid, 7, "Aspect Ratio:")
        self.vid_pix_fmt = self._create_kv_row(grid, 8, "Pixel Format:")

        layout.addLayout(grid)
        layout.addStretch()

    # ---------------- TAB 3: AUDIO ----------------
    def _init_audio_tab(self):
        outer_layout = QVBoxLayout(self.tab_audio)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        self.audio_scroll = QScrollArea()
        self.audio_scroll.setWidgetResizable(True)
        self.audio_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.audio_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} {SCROLLBAR_STYLE}")

        self.audio_container = QWidget()
        self.audio_container.setStyleSheet("background: transparent;")
        self.audio_layout = QVBoxLayout(self.audio_container)
        self.audio_layout.setContentsMargins(12, 12, 12, 12)
        self.audio_layout.setSpacing(12)

        lbl_loading = QLabel("⏳ Loading audio stream metadata...")
        lbl_loading.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        self.audio_layout.addWidget(lbl_loading)
        self.audio_layout.addStretch()

        self.audio_scroll.setWidget(self.audio_container)
        outer_layout.addWidget(self.audio_scroll)

    # ---------------- TAB 4: SUBTITLES ----------------
    def _init_subtitles_tab(self):
        outer_layout = QVBoxLayout(self.tab_subtitles)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        self.sub_scroll = QScrollArea()
        self.sub_scroll.setWidgetResizable(True)
        self.sub_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sub_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} {SCROLLBAR_STYLE}")

        self.sub_container = QWidget()
        self.sub_container.setStyleSheet("background: transparent;")
        self.sub_layout = QVBoxLayout(self.sub_container)
        self.sub_layout.setContentsMargins(12, 12, 12, 12)
        self.sub_layout.setSpacing(12)

        lbl_loading = QLabel("⏳ Loading subtitle tracks...")
        lbl_loading.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        self.sub_layout.addWidget(lbl_loading)
        self.sub_layout.addStretch()

        self.sub_scroll.setWidget(self.sub_container)
        outer_layout.addWidget(self.sub_scroll)

    # ---------------- ASYNC METADATA WORKER ----------------
    def _start_metadata_loading(self):
        self.worker = VideoMetadataWorker(self.file_path, self)
        self.worker.metadata_ready.connect(self._on_metadata_ready)
        self.worker.start()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _on_metadata_ready(self, file_path: str, data: dict):
        general = data.get("general", {})
        video = data.get("video", {})
        audio_streams = data.get("audio_streams", [])
        subtitle_streams = data.get("subtitle_streams", [])
        exists = data.get("exists", False)

        # 1. Cập nhật Header Badges
        qual = video.get("video_quality", "Unavailable")
        res = video.get("resolution", "Unavailable")
        fps = video.get("frame_rate", "Unavailable")
        dur = video.get("duration", "Unavailable")
        sz_short = general.get("file_size_short", "Unavailable")

        self.badge_quality.setText(qual if qual != "Unavailable" else "Video")
        self.badge_resolution.setText(f"🖥 {res}" if res != "Unavailable" else "Resolution: N/A")
        self.badge_fps.setText(f"🎞 {fps}" if fps != "Unavailable" else "FPS: N/A")
        self.badge_duration.setText(f"⏱ {dur}" if dur != "Unavailable" else "Duration: N/A")
        self.badge_size.setText(f"💾 {sz_short}" if sz_short != "Unavailable" else "Size: N/A")

        # 2. Cập nhật Tab General
        self.gen_name.setText(general.get("file_name", "Unavailable"))
        self.gen_type.setText(general.get("file_type", "Unavailable"))
        self.gen_location.setText(general.get("file_location", "Unavailable"))
        self.gen_size.setText(general.get("file_size", "Unavailable"))
        self.gen_created.setText(general.get("created_date", "Unavailable"))
        self.gen_modified.setText(general.get("modified_date", "Unavailable"))
        self.gen_accessed.setText(general.get("accessed_date", "Unavailable"))

        # 3. Cập nhật Tab Video
        self.vid_resolution.setText(video.get("resolution", "Unavailable"))
        self.vid_quality.setText(video.get("video_quality", "Unavailable"))
        self.vid_fps.setText(video.get("frame_rate", "Unavailable"))
        self.vid_duration.setText(video.get("duration", "Unavailable"))
        self.vid_codec.setText(video.get("video_codec", "Unavailable"))
        self.vid_bitrate.setText(video.get("bitrate", "Unavailable"))
        self.vid_aspect.setText(video.get("aspect_ratio", "Unavailable"))
        self.vid_pix_fmt.setText(video.get("pixel_format", "Unavailable"))

        # 4. Cập nhật Tab Audio
        self.tab_widget.setTabText(2, f"Audio ({len(audio_streams)})")
        self._populate_audio_tab(audio_streams)

        # 5. Cập nhật Tab Subtitles
        self.tab_widget.setTabText(3, f"Subtitles ({len(subtitle_streams)})")
        self._populate_subtitles_tab(subtitle_streams)

        # 6. Cập nhật trạng thái Footer
        if not exists:
            err_msg = data.get("error", "File not found")
            self.lbl_engine_status.setText(f"⚠ {err_msg}")
            self.lbl_engine_status.setStyleSheet("color: #E81123; font-size: 11px; font-weight: 600;")
            self.btn_open_loc.setEnabled(False)
        else:
            engine = data.get("engine", "Analyzer")
            self.lbl_engine_status.setText(f"✓ Metadata extracted via {engine}")

    def _populate_audio_tab(self, audio_streams: list[dict]):
        self._clear_layout(self.audio_layout)

        if not audio_streams:
            empty_card = QFrame()
            empty_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_BG_ELEVATED};
                    border: 1px dashed rgba(255, 255, 255, 0.12);
                    border-radius: 8px;
                    padding: 20px;
                }}
            """)
            v_lay = QVBoxLayout(empty_card)
            v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon = QLabel("🔇")
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon.setStyleSheet("font-size: 28px; background: transparent; border: none;")
            lbl_msg = QLabel("No Audio Streams Found (Unavailable)")
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
            lbl_sub = QLabel("This video file does not contain any detectable audio track.")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; background: transparent; border: none;")
            v_lay.addWidget(lbl_icon)
            v_lay.addWidget(lbl_msg)
            v_lay.addWidget(lbl_sub)
            self.audio_layout.addWidget(empty_card)
            self.audio_layout.addStretch()
            return

        lbl_summary = QLabel(f"🔊 Total Audio Streams: {len(audio_streams)}")
        lbl_summary.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        self.audio_layout.addWidget(lbl_summary)

        for stream in audio_streams:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_BG_ELEVATED};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                    border-radius: 8px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(8)

            idx = stream.get("stream_index", 1)
            title = stream.get("title", "")
            header_text = f"Audio Stream #{idx}" + (f" — {title}" if title else "")
            lbl_title = QLabel(header_text)
            lbl_title.setTextFormat(Qt.TextFormat.PlainText)
            lbl_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            card_layout.addWidget(lbl_title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(6)
            grid.setColumnStretch(1, 1)

            self._create_kv_row(grid, 0, "Audio Codec:", stream.get("codec", "Unavailable"))
            self._create_kv_row(grid, 1, "Audio Bitrate:", stream.get("bitrate", "Unavailable"))
            self._create_kv_row(grid, 2, "Sample Rate:", stream.get("sample_rate", "Unavailable"))
            self._create_kv_row(grid, 3, "Channels:", stream.get("channels", "Unavailable"))
            self._create_kv_row(grid, 4, "Language:", stream.get("language", "Unknown"))

            card_layout.addLayout(grid)
            self.audio_layout.addWidget(card)

        self.audio_layout.addStretch()

    def _populate_subtitles_tab(self, subtitle_streams: list[dict]):
        self._clear_layout(self.sub_layout)

        if not subtitle_streams:
            empty_card = QFrame()
            empty_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_BG_ELEVATED};
                    border: 1px dashed rgba(255, 255, 255, 0.12);
                    border-radius: 8px;
                    padding: 20px;
                }}
            """)
            v_lay = QVBoxLayout(empty_card)
            v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon = QLabel("💬")
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon.setStyleSheet("font-size: 28px; background: transparent; border: none;")
            lbl_msg = QLabel("No Subtitles Available")
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
            lbl_sub = QLabel("No embedded subtitle streams or matching external subtitle files (.srt, .ass, .vtt) were found.")
            lbl_sub.setWordWrap(True)
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; background: transparent; border: none;")
            v_lay.addWidget(lbl_icon)
            v_lay.addWidget(lbl_msg)
            v_lay.addWidget(lbl_sub)
            self.sub_layout.addWidget(empty_card)
            self.sub_layout.addStretch()
            return

        lbl_count = QLabel(f"💬 Total Subtitle Tracks: {len(subtitle_streams)}")
        lbl_count.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        self.sub_layout.addWidget(lbl_count)

        for sub in subtitle_streams:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_BG_ELEVATED};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                    border-radius: 8px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(6)

            idx = sub.get("stream_index", 1)
            source = sub.get("source", "Embedded")
            title = sub.get("title", f"Subtitle #{idx}")

            lbl_title = QLabel(f"Subtitle Track #{idx} — {title}")
            lbl_title.setTextFormat(Qt.TextFormat.PlainText)
            lbl_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            card_layout.addWidget(lbl_title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(5)
            grid.setColumnStretch(1, 1)

            self._create_kv_row(grid, 0, "Subtitle Codec:", sub.get("codec", "Unavailable"))
            self._create_kv_row(grid, 1, "Language:", sub.get("language", "Unknown"))
            self._create_kv_row(grid, 2, "Source Type:", source)

            card_layout.addLayout(grid)
            self.sub_layout.addWidget(card)

        self.sub_layout.addStretch()

    def _open_file_location(self):
        try:
            open_in_explorer_safely(self.file_path)
        except (FileSecurityError, Exception) as exc:
            QMessageBox.warning(
                self,
                "Không thể mở thư mục",
                sanitize_for_log(str(exc)),
            )

    def _copy_full_path(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(os.path.normpath(self.file_path))
            self.btn_copy_path.setText("✓ Copied!")

    def _cleanup_worker(self):
        if self.worker is not None:
            try:
                self.worker.metadata_ready.disconnect(self._on_metadata_ready)
            except (TypeError, RuntimeError):
                pass
            if self.worker.isRunning():
                self.worker.quit()
                self.worker.wait(3000)

    def done(self, result: int):
        self._cleanup_worker()
        super().done(result)

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)
