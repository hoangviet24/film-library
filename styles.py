"""
Bảng mã màu và Stylesheet chuẩn Fluent Dark UI (Windows 11 Design System)
Dùng chung cho toàn bộ ứng dụng Fluent Media Player.
"""

# Bảng mã màu tiêu chuẩn (Color Palette)
COLOR_BG_APP = "#0D0D0D"
COLOR_BG_CARD = "#161616"
COLOR_BG_ELEVATED = "#202020"
COLOR_BG_HOVER = "#2A2A2A"
COLOR_BG_INPUT = "#1C1C1C"

COLOR_ACCENT = "#0078D4"
COLOR_ACCENT_HOVER = "#1084E3"
COLOR_ACCENT_PRESSED = "#005A9E"
COLOR_ACCENT_LIGHT = "rgba(0, 120, 212, 0.25)"

COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#BBBBBB"
COLOR_TEXT_MUTED = "#757575"

COLOR_BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
COLOR_BORDER_DEFAULT = "#2D2D2D"
COLOR_BORDER_HOVER = "#444444"

COLOR_SUCCESS = "#107C41"

# Stylesheet cho cửa sổ chính
MAIN_WINDOW_STYLE = f"""
    QMainWindow {{
        background-color: {COLOR_BG_APP};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QWidget {{
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    }}
    QToolTip {{
        background-color: #1F1F1F;
        color: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}
"""

# Thanh cuộn mượt mà Fluent Scrollbar
SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
        margin: 4px 2px 4px 2px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.2);
        min-height: 35px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_ACCENT};
    }}
    QScrollBar::handle:vertical:pressed {{
        background: {COLOR_ACCENT_PRESSED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
"""

# Thanh trượt tua tiến độ video (Seek Slider)
SEEK_SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 6px;
        background: rgba(255, 255, 255, 0.16);
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {COLOR_ACCENT};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: #FFFFFF;
        width: 14px;
        height: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
"""

# Thanh trượt âm lượng (Volume Slider)
VOLUME_SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 4px;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {COLOR_ACCENT};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #FFFFFF;
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #90CAF9;
    }}
"""

# Nút điều khiển tiêu chuẩn (Icon / Text Button)
BTN_CONTROL_STYLE = f"""
    QPushButton {{
        background-color: rgba(255, 255, 255, 0.05);
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 0px 8px;
        font-size: 13px;
        font-weight: 500;
        height: 34px;
        min-height: 34px;
        max-height: 34px;
    }}

    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.22);
    }}

    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 0.03);
    }}

    QPushButton:disabled {{
        background-color: transparent;
        color: {COLOR_TEXT_MUTED};
        border-color: transparent;
    }}
"""

# Nút chức năng quan trọng (Accent Primary Button)
BTN_PRIMARY_STYLE = f"""
    QPushButton {{
        background-color: {COLOR_ACCENT};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_ACCENT_PRESSED};
    }}
"""

# Nút Play/Pause chính (Nổi bật hình tròn chuẩn 36px đồng bộ)
BTN_PLAY_STYLE = f"""
    QPushButton {{
        background-color: {COLOR_ACCENT};
        color: #FFFFFF;
        border: none;
        border-radius: 18px;
        font-size: 15px;
        font-weight: bold;
        width: 36px;
        height: 36px;
        min-width: 36px;
        min-height: 36px;
        max-width: 36px;
        max-height: 36px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_ACCENT_PRESSED};
    }}
"""

# Hộp tìm kiếm tập phim (Search Box)
SEARCH_INPUT_STYLE = f"""
    QLineEdit {{
        background-color: {COLOR_BG_INPUT};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: 7px;
        padding: 6px 12px;
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border: 1px solid {COLOR_ACCENT};
        background-color: #222222;
    }}
"""

# Thẻ Card chứa nội dung (Card Container)
CARD_STYLE = f"""
    QFrame {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: 10px;
    }}
"""

# Danh sách danh mục phim (Movies List)
MOVIES_LIST_STYLE = f"""
    QListWidget {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: 8px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 14px;
        color: {COLOR_TEXT_SECONDARY};
        border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        font-size: 13px;
        border-radius: 4px;
        margin: 2px 4px;
    }}
    QListWidget::item:hover {{
        background-color: {COLOR_BG_HOVER};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QListWidget::item:selected {{
        background-color: {COLOR_ACCENT};
        color: #FFFFFF;
        font-weight: bold;
    }}
"""

# Danh sách tập phim (Episodes List)
EPISODES_LIST_STYLE = f"""
    QListWidget {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: 8px;
        outline: none;
    }}
    QListWidget::item {{
        border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: 6px;
        margin: 3px 4px;
    }}
    QListWidget::item:hover {{
        background-color: {COLOR_BG_HOVER};
    }}
    QListWidget::item:selected {{
        background-color: #222B35;
        border: 1px solid {COLOR_ACCENT};
    }}
"""
