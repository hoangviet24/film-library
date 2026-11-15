import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QListWidget, QListWidgetItem, 
    QComboBox, QPushButton, QFrame
)
from styles import (
    CARD_STYLE, SEARCH_INPUT_STYLE, EPISODES_LIST_STYLE, 
    SCROLLBAR_STYLE, BTN_CONTROL_STYLE, COLOR_ACCENT
)
from .episode_item import EpisodeItemWidget
from utils import get_cached_thumbnail

class PlaylistSidebar(QFrame):
    """
    Sidebar chứa danh sách các bộ phim & tập phim:
    - Tìm kiếm tức thì theo tên tập
    - Chuyển đổi giữa các bộ phim / phần phim (Subfolder Selector)
    - Hiển thị thumbnail, trạng thái đã xem / đang xem
    - Hỗ trợ đóng mở chế độ Rạp phim (Theater mode)
    """
    episode_selected = pyqtSignal(str)          # video_path
    change_folder_clicked = pyqtSignal()
    close_sidebar_clicked = pyqtSignal()
    thumbnails_needed = pyqtSignal(list)        # list of video paths needing thumbs

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        self._movies_data = {}
        self._current_group = ""
        self._all_items_data = []  # list of (file_path, list_item)
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
        layout.addWidget(self.list_episodes, stretch=1)

        # Trạng thái rỗng khi tìm kiếm không ra kết quả
        self.lbl_empty = QLabel("Không tìm thấy tập phim nào phù hợp.")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #777777; font-size: 13px; padding: 20px 0;")
        self.lbl_empty.hide()
        layout.addWidget(self.lbl_empty)

    def set_movies_data(self, movies_data: dict, history_data: dict):
        self._movies_data = dict(movies_data)
        self._history = dict(history_data)
        
        self.combo_group.blockSignals(True)
        self.combo_group.clear()
        
        groups = list(self._movies_data.keys())
        if len(groups) > 1:
            for g in groups:
                count = len(self._movies_data[g])
                self.combo_group.addItem(f"{g} ({count})", g)
            self.combo_group.show()
        else:
            self.combo_group.hide()
        self.combo_group.blockSignals(False)

        if groups:
            self._load_group_episodes(groups[0])

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
            self._all_items_data.append((file_path, filename.lower(), list_item, item_widget))

        if missing_thumbs:
            self.thumbnails_needed.emit(missing_thumbs)

        # Áp dụng bộ lọc tìm kiếm nếu có
        query = self.search_input.text().strip().lower()
        if query:
            self._filter(query)

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
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
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
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == video_path:
                widget = self.list_episodes.itemWidget(item)
                if widget and hasattr(widget, 'set_thumbnail'):
                    widget.set_thumbnail(thumb_path)
                break

    def update_progress(self, video_path: str, progress_pct: float):
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == video_path:
                widget = self.list_episodes.itemWidget(item)
                if widget and hasattr(widget, 'update_progress'):
                    widget.update_progress(progress_pct)
                break
