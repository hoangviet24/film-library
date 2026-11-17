import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QListWidget, QListWidgetItem, 
    QComboBox, QPushButton, QFrame, QMenu
)
from styles import (
    CARD_STYLE, SEARCH_INPUT_STYLE, EPISODES_LIST_STYLE, 
    SCROLLBAR_STYLE, BTN_CONTROL_STYLE, COLOR_ACCENT,
    CONTEXT_MENU_STYLE
)
from .episode_item import EpisodeItemWidget
from utils import get_cached_thumbnail


class PlaylistSidebar(QFrame):
    """
    Sidebar chứa danh sách các bộ phim & tập phim:
    - Tìm kiếm tức thì theo tên tập
    - Chuyển đổi giữa các bộ phim / phần phim (Subfolder Selector)
    - Hiển thị thumbnail, trạng thái đã xem / đang xem
    - Context Menu (Chuột phải) quản lý video chuẩn Windows File Explorer:
      Open/Play, Add Video, Rename, Remove from Playlist, Delete, Open File Location, Properties
    - Hỗ trợ đóng mở chế độ Rạp phim (Theater mode)
    """
    episode_selected = pyqtSignal(str)                  # video_path
    change_folder_clicked = pyqtSignal()
    close_sidebar_clicked = pyqtSignal()
    thumbnails_needed = pyqtSignal(list)                # list of video paths needing thumbs

    # Tín hiệu Context Menu & Quản lý tệp
    add_video_requested = pyqtSignal()
    rename_video_requested = pyqtSignal(str)            # video_path
    remove_from_playlist_requested = pyqtSignal(str)    # video_path
    delete_video_requested = pyqtSignal(str)            # video_path
    open_file_location_requested = pyqtSignal(str)      # video_path
    properties_requested = pyqtSignal(str)              # video_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        self._movies_data = {}
        self._history = {}
        self._current_group = ""
        self._all_items_data = []  # list of [file_path, name_lower, list_item, item_widget]
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---------------- HEADER ----------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.lbl_header = QLabel("📋 DANH SÁCH TẬP")
        self.lbl_header.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        header_layout.addWidget(self.lbl_header)

        self.lbl_count = QLabel("(0)")
        self.lbl_count.setStyleSheet("color: #888888; font-size: 13px;")
        header_layout.addWidget(self.lbl_count)

        header_layout.addStretch()

        self.btn_add_video = QPushButton("＋")
        self.btn_add_video.setFixedSize(30, 30)
        self.btn_add_video.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_add_video.setToolTip("Thêm video vào danh sách phát (Add Video)")
        self.btn_add_video.clicked.connect(self.add_video_requested.emit)
        header_layout.addWidget(self.btn_add_video)

        self.btn_change_folder = QPushButton("📁")
        self.btn_change_folder.setFixedSize(30, 30)
        self.btn_change_folder.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_change_folder.setToolTip("Chọn thư mục phim khác")
        self.btn_change_folder.clicked.connect(self.change_folder_clicked.emit)
        header_layout.addWidget(self.btn_change_folder)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet(BTN_CONTROL_STYLE)
        self.btn_close.setToolTip("Thu gọn danh sách (Phím B)")
        self.btn_close.clicked.connect(self.close_sidebar_clicked.emit)
        header_layout.addWidget(self.btn_close)

        layout.addLayout(header_layout)

        # ---------------- HỘP TÌM KIẾM TẬP PHIM ----------------
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Tìm kiếm tập phim...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(SEARCH_INPUT_STYLE)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # ---------------- CHỌN BỘ PHIM / THƯ MỤC CON ----------------
        self.combo_group = QComboBox()
        self.combo_group.setStyleSheet(f"""
            QComboBox {{
                background-color: #202020;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border-color: {COLOR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #222222;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                selection-background-color: {COLOR_ACCENT};
                outline: none;
                padding: 4px;
            }}
        """)
        self.combo_group.currentTextChanged.connect(self._on_group_changed)
        self.combo_group.hide()
        layout.addWidget(self.combo_group)

        # ---------------- DANH SÁCH CÁC TẬP PHIM ----------------
        self.list_episodes = QListWidget()
        self.list_episodes.setStyleSheet(EPISODES_LIST_STYLE + SCROLLBAR_STYLE)
        self.list_episodes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_episodes.itemClicked.connect(self._on_item_clicked)
        self.list_episodes.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_episodes.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_episodes, stretch=1)

        # Trạng thái rỗng khi tìm kiếm không ra kết quả
        self.lbl_empty = QLabel("Không tìm thấy tập phim nào phù hợp.")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #777777; font-size: 13px; padding: 20px 0;")
        self.lbl_empty.hide()
        layout.addWidget(self.lbl_empty)

    # ---------------- CONTEXT MENU CHUỘT PHẢI ----------------
    def _show_context_menu(self, pos: QPoint):
        item = self.list_episodes.itemAt(pos)
        selected_path = None

        if item is not None:
            # Chọn đúng item dưới con trỏ chuột trước khi mở menu
            self.list_episodes.setCurrentItem(item)
            selected_path = item.data(Qt.ItemDataRole.UserRole)

        has_item = bool(selected_path)
        file_exists = bool(selected_path and os.path.exists(selected_path))

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        act_play = QAction("▶  Open / Play", menu)
        act_play.setEnabled(has_item and file_exists)
        if has_item:
            act_play.triggered.connect(lambda: self.episode_selected.emit(selected_path))
        menu.addAction(act_play)

        act_add = QAction("➕  Add Video...", menu)
        act_add.setEnabled(True)
        act_add.triggered.connect(self.add_video_requested.emit)
        menu.addAction(act_add)

        menu.addSeparator()

        act_rename = QAction("✏️  Rename...", menu)
        act_rename.setEnabled(has_item and file_exists)
        if has_item:
            act_rename.triggered.connect(lambda: self.rename_video_requested.emit(selected_path))
        menu.addAction(act_rename)

        act_remove = QAction("➖  Remove from Playlist", menu)
        act_remove.setEnabled(has_item)
        if has_item:
            act_remove.triggered.connect(lambda: self.remove_from_playlist_requested.emit(selected_path))
        menu.addAction(act_remove)

        act_delete = QAction("🗑️  Delete...", menu)
        act_delete.setEnabled(has_item and file_exists)
        if has_item:
            act_delete.triggered.connect(lambda: self.delete_video_requested.emit(selected_path))
        menu.addAction(act_delete)

        menu.addSeparator()

        act_open_loc = QAction("📂  Open File Location", menu)
        act_open_loc.setEnabled(has_item and file_exists)
        if has_item:
            act_open_loc.triggered.connect(lambda: self.open_file_location_requested.emit(selected_path))
        menu.addAction(act_open_loc)

        menu.addSeparator()

        act_props = QAction("ℹ️  Properties", menu)
        act_props.setEnabled(has_item)
        if has_item:
            act_props.triggered.connect(lambda: self.properties_requested.emit(selected_path))
        menu.addAction(act_props)

        global_pos = self.list_episodes.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    # ---------------- QUẢN LÝ DỮ LIỆU DANH SÁCH ----------------
    def get_current_group(self) -> str:
        return self._current_group

    def set_movies_data(self, movies_data: dict, history_data: dict):
        self._movies_data = {k: list(v) for k, v in movies_data.items()}
        self._history = dict(history_data)
        self._refresh_group_combo()

        groups = list(self._movies_data.keys())
        if groups:
            target = self._current_group if self._current_group in self._movies_data else groups[0]
            self._load_group_episodes(target)
        else:
            self._current_group = ""
            self.list_episodes.clear()
            self._all_items_data.clear()
            self.lbl_count.setText("(0 tập)")

    def _refresh_group_combo(self):
        self.combo_group.blockSignals(True)
        self.combo_group.clear()
        groups = list(self._movies_data.keys())
        if len(groups) > 1:
            for idx, g in enumerate(groups):
                count = len(self._movies_data[g])
                self.combo_group.addItem(f"{g} ({count})", g)
                if g == self._current_group:
                    self.combo_group.setCurrentIndex(idx)
            self.combo_group.show()
        else:
            self.combo_group.hide()
        self.combo_group.blockSignals(False)

    def _on_group_changed(self, text):
        group_key = self.combo_group.currentData()
        if not group_key and self.combo_group.count() > 0:
            group_key = list(self._movies_data.keys())[0]
        if group_key in self._movies_data:
            self._load_group_episodes(group_key)

    def _load_group_episodes(self, group_name: str):
        self._current_group = group_name
        self.list_episodes.clear()
        self._all_items_data.clear()

        videos = self._movies_data.get(group_name, [])
        self.lbl_count.setText(f"({len(videos)} tập)")

        missing_thumbs = []

        for file_path in videos:
            filename = os.path.basename(file_path)
            history = self._history.get(file_path, {})
            progress_pct = history.get("pct", 0)

            cached_thumb = get_cached_thumbnail(file_path)
            if not cached_thumb:
                missing_thumbs.append(file_path)

            item_widget = EpisodeItemWidget(filename, progress_pct, cached_thumb)
            
            list_item = QListWidgetItem(self.list_episodes)
            list_item.setSizeHint(QSize(0, 80))
            list_item.setData(Qt.ItemDataRole.UserRole, file_path)

            self.list_episodes.addItem(list_item)
            self.list_episodes.setItemWidget(list_item, item_widget)
            self._all_items_data.append([file_path, filename.lower(), list_item, item_widget])

        if missing_thumbs:
            self.thumbnails_needed.emit(missing_thumbs)

        # Áp dụng bộ lọc tìm kiếm nếu có
        query = self.search_input.text().strip().lower()
        if query:
            self._filter(query)

    def add_videos_to_playlist(self, new_paths: list[str], history_data: dict = None) -> list[str]:
        """Thêm một hoặc nhiều video vào nhóm hiện tại của Playlist."""
        if history_data is not None:
            self._history = dict(history_data)

        if not self._current_group or self._current_group not in self._movies_data:
            self._current_group = "Danh sách phát"
            if self._current_group not in self._movies_data:
                self._movies_data[self._current_group] = []

        existing_norms = {
            os.path.normcase(os.path.abspath(p))
            for p in self._movies_data[self._current_group]
        }

        added = []
        missing_thumbs = []

        for raw_path in new_paths:
            abs_p = os.path.abspath(raw_path)
            norm_p = os.path.normcase(abs_p)
            if norm_p in existing_norms or not os.path.isfile(abs_p):
                continue

            existing_norms.add(norm_p)
            self._movies_data[self._current_group].append(abs_p)
            added.append(abs_p)

            filename = os.path.basename(abs_p)
            history = self._history.get(abs_p, {})
            progress_pct = history.get("pct", 0)

            cached_thumb = get_cached_thumbnail(abs_p)
            if not cached_thumb:
                missing_thumbs.append(abs_p)

            item_widget = EpisodeItemWidget(filename, progress_pct, cached_thumb)
            list_item = QListWidgetItem(self.list_episodes)
            list_item.setSizeHint(QSize(0, 80))
            list_item.setData(Qt.ItemDataRole.UserRole, abs_p)

            self.list_episodes.addItem(list_item)
            self.list_episodes.setItemWidget(list_item, item_widget)
            self._all_items_data.append([abs_p, filename.lower(), list_item, item_widget])

        if added:
            videos = self._movies_data.get(self._current_group, [])
            self.lbl_count.setText(f"({len(videos)} tập)")
            self._refresh_group_combo()
            query = self.search_input.text().strip().lower()
            if query:
                self._filter(query)

        if missing_thumbs:
            self.thumbnails_needed.emit(missing_thumbs)

        return added

    def rename_video_item(self, old_path: str, new_path: str):
        """Cập nhật tên và đường dẫn của một video trong Playlist ngay lập tức."""
        old_norm = os.path.normcase(os.path.abspath(old_path))
        new_abs = os.path.abspath(new_path)
        new_name = os.path.basename(new_abs)

        for grp, paths in self._movies_data.items():
            for idx, p in enumerate(paths):
                if os.path.normcase(os.path.abspath(p)) == old_norm:
                    paths[idx] = new_abs

        for entry in self._all_items_data:
            if os.path.normcase(os.path.abspath(entry[0])) == old_norm:
                entry[0] = new_abs
                entry[1] = new_name.lower()
                list_item = entry[2]
                widget = entry[3]
                list_item.setData(Qt.ItemDataRole.UserRole, new_abs)
                if widget and hasattr(widget, "set_title"):
                    widget.set_title(new_name)

        query = self.search_input.text().strip().lower()
        if query:
            self._filter(query)

    def remove_video_item(self, target_path: str) -> str | None:
        """
        Xóa một video khỏi danh sách phát hiện tại.
        Trả về đường dẫn của tập liền kề tiếp theo (hoặc trước đó) nếu có.
        """
        target_norm = os.path.normcase(os.path.abspath(target_path))

        # Xóa khỏi dữ liệu nhóm
        for grp, paths in list(self._movies_data.items()):
            self._movies_data[grp] = [
                p for p in paths
                if os.path.normcase(os.path.abspath(p)) != target_norm
            ]

        # Tìm vị trí trong QListWidget để xóa
        removed_row = -1
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item:
                item_path = item.data(Qt.ItemDataRole.UserRole)
                if item_path and os.path.normcase(os.path.abspath(item_path)) == target_norm:
                    removed_row = i
                    break

        if removed_row >= 0:
            taken = self.list_episodes.takeItem(removed_row)
            del taken

        self._all_items_data = [
            entry for entry in self._all_items_data
            if os.path.normcase(os.path.abspath(entry[0])) != target_norm
        ]

        videos = self._movies_data.get(self._current_group, [])
        self.lbl_count.setText(f"({len(videos)} tập)")
        self._refresh_group_combo()

        query = self.search_input.text().strip().lower()
        if query:
            self._filter(query)

        # Xác định tập liền kề nếu cần chuyển tập
        total = self.list_episodes.count()
        if total > 0 and removed_row >= 0:
            next_idx = min(removed_row, total - 1)
            next_item = self.list_episodes.item(next_idx)
            if next_item:
                return next_item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_search_changed(self, text: str):
        self._filter(text.strip().lower())

    def _filter(self, query: str):
        visible_count = 0
        for file_path, name_lower, list_item, widget in self._all_items_data:
            match = query in name_lower
            list_item.setHidden(not match)
            if match:
                visible_count += 1

        if visible_count == 0 and len(self._all_items_data) > 0:
            self.lbl_empty.show()
            self.list_episodes.hide()
        else:
            self.lbl_empty.hide()
            self.list_episodes.show()

    def _on_item_clicked(self, item: QListWidgetItem):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.episode_selected.emit(file_path)

    def select_episode(self, file_path: str):
        if not file_path:
            self.list_episodes.clearSelection()
            return
        target_norm = os.path.normcase(os.path.abspath(file_path))
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and os.path.normcase(os.path.abspath(p)) == target_norm:
                    self.list_episodes.setCurrentItem(item)
                    self.list_episodes.scrollToItem(item)
                    break

    def get_current_index(self) -> int:
        return self.list_episodes.currentRow()

    def get_total_count(self) -> int:
        return self.list_episodes.count()

    def get_episode_at_index(self, index: int) -> str | None:
        if 0 <= index < self.list_episodes.count():
            item = self.list_episodes.item(index)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def update_thumbnail(self, video_path: str, thumb_path: str):
        target_norm = os.path.normcase(os.path.abspath(video_path))
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and os.path.normcase(os.path.abspath(p)) == target_norm:
                    widget = self.list_episodes.itemWidget(item)
                    if widget and hasattr(widget, 'set_thumbnail'):
                        widget.set_thumbnail(thumb_path)
                    break

    def update_progress(self, video_path: str, progress_pct: float):
        target_norm = os.path.normcase(os.path.abspath(video_path))
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and os.path.normcase(os.path.abspath(p)) == target_norm:
                    widget = self.list_episodes.itemWidget(item)
                    if widget and hasattr(widget, 'update_progress'):
                        widget.update_progress(progress_pct)
                    break
