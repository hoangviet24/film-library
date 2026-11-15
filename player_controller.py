import sys
import vlc
from PyQt6.QtCore import QObject, pyqtSignal

class PlayerController(QObject):
    """
    Bộ điều khiển phát video (Media Controller) bao bọc toàn bộ tương tác với libvlc:
    Phát, tạm dừng, tua thời gian, điều chỉnh âm lượng, tốc độ phát, và quản lý HWND.
    """
    playback_state_changed = pyqtSignal(bool)       # True: playing, False: paused/stopped
    volume_changed = pyqtSignal(int, bool)          # volume (0-100), is_muted
    rate_changed = pyqtSignal(float)                # playback rate (0.5x -> 2.0x)

    def __init__(self, parent=None):
        super().__init__(parent)
        vlc_args = [
            "--quiet",
            "--no-xlib",
            "--no-video-title-show"
        ]
        self.vlc_instance = vlc.Instance(vlc_args)
        if self.vlc_instance is None:
            self.vlc_instance = vlc.Instance()
            
        self.media_player = self.vlc_instance.media_player_new()
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)

        self._volume = 100
        self._is_muted = False
        self._rate = 1.0
        self._current_hwnd = None

    def set_hwnd(self, hwnd: int):
        self._current_hwnd = hwnd
        if sys.platform.startswith('win'):
            self.media_player.set_hwnd(int(hwnd))

    def load_media(self, file_path: str):
        media = self.vlc_instance.media_new(file_path)
        self.media_player.set_media(media)
        if self._current_hwnd:
            self.set_hwnd(self._current_hwnd)
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)
        self.set_rate(self._rate)
        self.set_volume(self._volume)

    def play(self):
        self.media_player.play()
        self.playback_state_changed.emit(True)

    def pause(self):
        self.media_player.pause()
        self.playback_state_changed.emit(False)

    def toggle_play(self) -> bool:
        if self.is_playing():
            self.pause()
            return False
        else:
            self.play()
            return True

    def stop(self):
        self.media_player.stop()
        self.playback_state_changed.emit(False)

    def is_playing(self) -> bool:
        return bool(self.media_player.is_playing())

    def get_state(self):
        return self.media_player.get_state()

    def get_time(self) -> int:
        return self.media_player.get_time()

    def set_time(self, ms: int):
        self.media_player.set_time(int(ms))

    def get_length(self) -> int:
        return self.media_player.get_length()

    def seek_relative(self, seconds: float):
        total_len = self.get_length()
        if total_len > 0:
            current_ms = self.get_time()
            target_ms = max(0, min(total_len, current_ms + int(seconds * 1000)))
            self.set_time(target_ms)

    def seek_percentage(self, pos_pct: float):
        if self.get_length() > 0:
            self.media_player.set_position(max(0.0, min(1.0, pos_pct)))

    def get_volume(self) -> int:
        return self._volume

    def set_volume(self, volume: int):
        self._volume = max(0, min(100, int(volume)))
        if self._is_muted:
            self.media_player.audio_set_volume(0)
        else:
            self.media_player.audio_set_volume(self._volume)
        self.volume_changed.emit(self._volume, self._is_muted)

    def change_volume_relative(self, delta: int):
        self.set_volume(self._volume + delta)

    def toggle_mute(self) -> bool:
        self._is_muted = not self._is_muted
        if self._is_muted:
            self.media_player.audio_set_volume(0)
        else:
            self.media_player.audio_set_volume(self._volume)
        self.volume_changed.emit(self._volume, self._is_muted)
        return self._is_muted

    def is_muted(self) -> bool:
        return self._is_muted

    def get_rate(self) -> float:
        return self._rate

    def set_rate(self, rate: float):
        self._rate = max(0.25, min(4.0, float(rate)))
        self.media_player.set_rate(self._rate)
        self.rate_changed.emit(self._rate)

    @staticmethod
    def format_time(ms: int) -> str:
        if ms < 0:
            ms = 0
        total_sec = int(ms // 1000)
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
