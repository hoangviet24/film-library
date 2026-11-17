from .thumbnail import generate_thumbnail, get_cached_thumbnail, ThumbnailWorker
from .history import load_history, save_history
from .preview_manager import PreviewManager
from .open_with_installer import register_windows_open_with
from .window_icon import get_app_icon, apply_windows_taskbar_icon, setup_window_icon
from .video_metadata import (
    extract_video_metadata,
    invalidate_metadata_cache,
    VideoMetadataWorker,
    format_file_size,
    format_duration,
)

__all__ = [
    "generate_thumbnail",
    "get_cached_thumbnail",
    "ThumbnailWorker",
    "load_history",
    "save_history",
    "PreviewManager",
    "register_windows_open_with",
    "get_app_icon",
    "apply_windows_taskbar_icon",
    "setup_window_icon",
    "extract_video_metadata",
    "invalidate_metadata_cache",
    "VideoMetadataWorker",
    "format_file_size",
    "format_duration",
]
