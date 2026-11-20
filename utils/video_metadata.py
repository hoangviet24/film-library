import os
import json
import math
import struct
import threading
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from security import (
    FileSecurityError,
    check_disguised_or_invalid_media,
    find_safe_ffprobe,
    get_safe_vlc_args,
    run_ffprobe_safely,
    sanitize_metadata_text,
    validate_path,
    verify_contained_file,
)

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    import vlc
    HAS_VLC = True
except ImportError:
    HAS_VLC = False


# Bộ nhớ đệm Metadata trong RAM (Key: normpath -> (mtime, size, metadata_dict))
_METADATA_CACHE = {}
_CACHE_LOCK = threading.Lock()


VIDEO_TYPE_MAP = {
    ".mp4": "MP4 Video (.mp4)",
    ".mkv": "Matroska Video (.mkv)",
    ".avi": "AVI Video (.avi)",
    ".mov": "QuickTime Movie (.mov)",
    ".flv": "Flash Video (.flv)",
    ".wmv": "Windows Media Video (.wmv)",
    ".webm": "WebM Video (.webm)",
    ".m4v": "MPEG-4 Video (.m4v)",
    ".ts": "MPEG Transport Stream (.ts)",
}

VIDEO_CODEC_MAP = {
    "h264": "H.264 / AVC",
    "avc1": "H.264 / AVC",
    "avc": "H.264 / AVC",
    "hevc": "H.265 / HEVC",
    "h265": "H.265 / HEVC",
    "hev1": "H.265 / HEVC",
    "hvc1": "H.265 / HEVC",
    "av1": "AV1 (AOMedia Video 1)",
    "av01": "AV1 (AOMedia Video 1)",
    "vp9": "Google VP9",
    "vp8": "Google VP8",
    "mpeg4": "MPEG-4 Part 2",
    "mp4v": "MPEG-4 Part 2",
    "mpeg2video": "MPEG-2 Video",
    "mpeg1video": "MPEG-1 Video",
    "wmv3": "Windows Media Video 9",
    "vc1": "VC-1",
    "prores": "Apple ProRes",
    "mjpeg": "Motion JPEG",
}

AUDIO_CODEC_MAP = {
    "aac": "AAC (Advanced Audio Coding)",
    "mp4a": "AAC (Advanced Audio Coding)",
    "mp3": "MP3 (MPEG Audio Layer III)",
    "mpga": "MPEG Audio",
    "ac3": "AC-3 (Dolby Digital)",
    "a52": "AC-3 (Dolby Digital)",
    "eac3": "E-AC-3 (Dolby Digital Plus)",
    "dts": "DTS Coherent Acoustics",
    "flac": "FLAC (Free Lossless Audio Codec)",
    "opus": "Opus Audio",
    "vorbis": "Vorbis Audio",
    "pcm_s16le": "PCM 16-bit Little Endian",
    "pcm_s24le": "PCM 24-bit Little Endian",
    "wmav2": "Windows Media Audio 2",
    "alac": "Apple Lossless (ALAC)",
}

SUBTITLE_CODEC_MAP = {
    "subrip": "SubRip (SRT)",
    "srt": "SubRip (SRT)",
    "subt": "SubRip / Text Subtitle",
    "ass": "Advanced SubStation Alpha (ASS)",
    "ssa": "SubStation Alpha (SSA)",
    "mov_text": "MPEG-4 Timed Text (TX3G)",
    "tx3g": "MPEG-4 Timed Text (TX3G)",
    "webvtt": "WebVTT",
    "vtt": "WebVTT",
    "hdmv_pgs_subtitle": "Blu-ray Presentation Graphic Stream (PGS)",
    "pgs": "Blu-ray Presentation Graphic Stream (PGS)",
    "dvd_subtitle": "DVD VobSub ( DVD Subtitle )",
    "spu": "DVD VobSub",
    "dvb_subtitle": "DVB Subtitle",
}

LANGUAGE_CODE_MAP = {
    "vi": "Vietnamese (Tiếng Việt)",
    "vie": "Vietnamese (Tiếng Việt)",
    "en": "English (Tiếng Anh)",
    "eng": "English (Tiếng Anh)",
    "ja": "Japanese (Tiếng Nhật)",
    "jpn": "Japanese (Tiếng Nhật)",
    "ko": "Korean (Tiếng Hàn)",
    "kor": "Korean (Tiếng Hàn)",
    "zh": "Chinese (Tiếng Trung)",
    "chi": "Chinese (Tiếng Trung)",
    "zho": "Chinese (Tiếng Trung)",
    "fr": "French (Tiếng Pháp)",
    "fre": "French (Tiếng Pháp)",
    "fra": "French (Tiếng Pháp)",
    "de": "German (Tiếng Đức)",
    "ger": "German (Tiếng Đức)",
    "deu": "German (Tiếng Đức)",
    "es": "Spanish (Tiếng Tây Ban Nha)",
    "spa": "Spanish (Tiếng Tây Ban Nha)",
    "ru": "Russian (Tiếng Nga)",
    "rus": "Russian (Tiếng Nga)",
    "th": "Thai (Tiếng Thái)",
    "tha": "Thai (Tiếng Thái)",
    "id": "Indonesian (Tiếng Indonesia)",
    "ind": "Indonesian (Tiếng Indonesia)",
    "und": "Undefined (Chưa xác định)",
}


def format_file_size(size_bytes: int) -> str:
    """Định dạng dung lượng tệp sang KB, MB, GB kèm số byte chính xác."""
    if size_bytes < 0:
        return "Unavailable"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB ({size_bytes:,} bytes)"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB ({size_bytes:,} bytes)"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB ({size_bytes:,} bytes)"


def format_file_size_short(size_bytes: int) -> str:
    """Định dạng dung lượng ngắn gọn cho thanh tóm tắt."""
    if size_bytes < 0:
        return "Unavailable"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def format_duration(seconds: float) -> str:
    """Định dạng thời lượng từ giây sang HH:MM:SS."""
    if seconds is None or seconds <= 0:
        return "Unavailable"
    total_sec = int(round(seconds))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_bitrate(bps: int | float | None) -> str:
    """Định dạng tốc độ bit sang kbps hoặc Mbps."""
    if not bps or bps <= 0:
        return "Unavailable"
    kbps = bps / 1000.0
    if kbps >= 1000:
        return f"{kbps / 1000.0:.2f} Mbps ({int(round(kbps)):,} kbps)"
    return f"{int(round(kbps)):,} kbps"


def classify_video_quality(width: int, height: int) -> str:
    """Phân loại chất lượng độ phân giải chuẩn (480p, 720p, 1080p, 1440p, 2160p 4K...)."""
    if not width or not height or width <= 0 or height <= 0:
        return "Unavailable"
    short_side = min(width, height)
    long_side = max(width, height)

    if long_side >= 7600 or short_side >= 4300:
        return "4320p (8K UHD)"
    elif long_side >= 3800 or short_side >= 2100:
        return "2160p (4K UHD)"
    elif long_side >= 2500 or short_side >= 1400:
        return "1440p (2K QHD)"
    elif long_side >= 1900 or short_side >= 1000:
        return "1080p (Full HD)"
    elif long_side >= 1200 or short_side >= 700:
        return "720p (HD)"
    elif long_side >= 800 or short_side >= 460:
        return "480p (SD)"
    elif short_side >= 350:
        return "360p"
    else:
        return f"{short_side}p"


def calculate_aspect_ratio(width: int, height: int, dar_str: str = None) -> str:
    """Tính toán tỷ lệ khung hình chuẩn (16:9, 21:9, 4:3...)."""
    if dar_str and ":" in dar_str and dar_str not in ("0:1", "N/A", "0:0"):
        return dar_str
    if not width or not height or width <= 0 or height <= 0:
        return "Unavailable"

    ratio = width / height
    # Kiểm tra các tỷ lệ phổ biến với sai số nhỏ
    common_ratios = [
        (16 / 9, "16:9"),
        (4 / 3, "4:3"),
        (21 / 9, "21:9"),
        (64 / 27, "21:9 (64:27)"),
        (43 / 18, "21:9 (43:18)"),
        (18 / 9, "18:9 (2:1)"),
        (1 / 1, "1:1"),
        (9 / 16, "9:16 (Vertical)"),
        (2.39, "2.39:1 (Anamorphic)"),
        (2.35, "2.35:1 (CinemaScope)"),
        (1.85, "1.85:1 (Widescreen)"),
    ]
    for target, label in common_ratios:
        if abs(ratio - target) < 0.03:
            return label

    g = math.gcd(width, height)
    return f"{width // g}:{height // g}"


def format_channels(channels: int, layout: str = None) -> str:
    """Định dạng số kênh âm thanh (Mono, Stereo, 5.1, 7.1...)."""
    if not channels or channels <= 0:
        return "Unavailable"
    if layout:
        layout_clean = layout.strip().lower()
        if layout_clean == "mono":
            return "1 channel (Mono)"
        elif layout_clean == "stereo":
            return "2 channels (Stereo)"
        elif "5.1" in layout_clean:
            return f"{channels} channels (5.1 Surround)"
        elif "7.1" in layout_clean:
            return f"{channels} channels (7.1 Surround)"
        return f"{channels} channels ({layout})"

    channel_names = {
        1: "1 channel (Mono)",
        2: "2 channels (Stereo)",
        3: "3 channels (2.1)",
        6: "6 channels (5.1 Surround)",
        8: "8 channels (7.1 Surround)",
    }
    return channel_names.get(channels, f"{channels} channels")


def format_language(lang_code: str) -> str:
    """Chuyển mã ngôn ngữ sang tên hiển thị thân thiện."""
    if not lang_code:
        return "Unknown"
    code = lang_code.strip().lower()
    if not code or code in ("und", "unk", "unknown", "n/a"):
        return "Unknown"
    return LANGUAGE_CODE_MAP.get(code, lang_code)


def _fourcc_to_str(fourcc_int: int) -> str:
    """Giải mã mã nguyên FourCC của libvlc/OpenCV sang chuỗi 4 ký tự."""
    if not fourcc_int:
        return ""
    try:
        chars = struct.pack("<I", fourcc_int & 0xFFFFFFFF)
        return chars.decode("ascii", errors="ignore").strip("\x00").strip().lower()
    except Exception:
        return ""


def invalidate_metadata_cache(file_path: str = None):
    """Xóa cache metadata (dùng khi đổi tên hoặc xóa file)."""
    with _CACHE_LOCK:
        if file_path is None:
            _METADATA_CACHE.clear()
        else:
            norm = os.path.normcase(os.path.abspath(file_path))
            _METADATA_CACHE.pop(norm, None)


def _find_ffprobe() -> str | None:
    """Tìm kiếm ffprobe an toàn trên hệ thống (bỏ qua CWD chống hijacking)."""
    return find_safe_ffprobe()


def _extract_via_ffprobe(file_path: str, ffprobe_bin: str) -> dict | None:
    """Trích xuất metadata chi tiết bằng FFprobe với giới hạn thời gian và đầu ra."""
    try:
        data = run_ffprobe_safely(file_path, ffprobe_bin, timeout_sec=6.0)
        if not data:
            return None

        streams = data.get("streams", [])
        fmt = data.get("format", {})

        fmt_duration = float(fmt["duration"]) if "duration" in fmt else None
        fmt_bitrate = int(fmt["bit_rate"]) if "bit_rate" in fmt and str(fmt["bit_rate"]).isdigit() else None

        video_info = None
        audio_streams = []
        subtitle_streams = []

        for s in streams:
            codec_type = s.get("codec_type", "")
            tags = s.get("tags", {}) or {}
            disposition = s.get("disposition", {}) or {}

            if codec_type == "video" and video_info is None:
                # Bỏ qua ảnh bìa đính kèm (attached_pic) nếu có
                if disposition.get("attached_pic") == 1:
                    continue

                width = int(s.get("width", 0) or 0)
                height = int(s.get("height", 0) or 0)
                codec_raw = sanitize_metadata_text(s.get("codec_name"), max_len=60, default="").lower()
                profile = sanitize_metadata_text(s.get("profile"), max_len=60, default="")
                codec_display = VIDEO_CODEC_MAP.get(codec_raw, codec_raw.upper() if codec_raw else "Unavailable")
                if profile and profile.lower() not in ("unknown", "unavailable") and codec_raw:
                    codec_display = sanitize_metadata_text(f"{codec_display} ({profile})", max_len=120)

                # Tính FPS
                fps_val = None
                for fps_key in ("avg_frame_rate", "r_frame_rate"):
                    fps_str = s.get(fps_key, "")
                    if fps_str and "/" in fps_str:
                        num_s, den_s = fps_str.split("/", 1)
                        try:
                            num, den = float(num_s), float(den_s)
                            if den > 0 and num > 0:
                                fps_val = num / den
                                break
                        except ValueError:
                            pass

                fps_display = "Unavailable"
                if fps_val and fps_val > 0:
                    if abs(fps_val - round(fps_val)) < 0.01:
                        fps_display = f"{int(round(fps_val))} FPS"
                    else:
                        fps_display = f"{fps_val:.3f} FPS"

                # Bitrate video
                v_bitrate = s.get("bit_rate")
                if v_bitrate and str(v_bitrate).isdigit():
                    v_bitrate_val = int(v_bitrate)
                else:
                    # Kiểm tra tag BPS (thường có trong MKV)
                    bps_tag = tags.get("BPS") or tags.get("BPS-eng")
                    v_bitrate_val = int(bps_tag) if bps_tag and str(bps_tag).isdigit() else fmt_bitrate

                # Duration
                s_dur = s.get("duration")
                dur_val = float(s_dur) if s_dur else fmt_duration

                dar = sanitize_metadata_text(s.get("display_aspect_ratio"), max_len=40, default="") or None
                pix_fmt = sanitize_metadata_text(s.get("pix_fmt"), max_len=60, default="Unavailable")

                video_info = {
                    "resolution": f"{width} × {height}" if (width > 0 and height > 0) else "Unavailable",
                    "width": width,
                    "height": height,
                    "video_quality": classify_video_quality(width, height),
                    "frame_rate": fps_display,
                    "video_codec": sanitize_metadata_text(codec_display, max_len=120),
                    "bitrate": format_bitrate(v_bitrate_val),
                    "duration": format_duration(dur_val),
                    "aspect_ratio": sanitize_metadata_text(calculate_aspect_ratio(width, height, dar), max_len=60),
                    "pixel_format": pix_fmt,
                }

            elif codec_type == "audio":
                codec_raw = sanitize_metadata_text(s.get("codec_name"), max_len=60, default="").lower()
                codec_display = sanitize_metadata_text(
                    AUDIO_CODEC_MAP.get(codec_raw, codec_raw.upper() if codec_raw else "Unavailable"),
                    max_len=120,
                )

                a_bitrate = s.get("bit_rate")
                if a_bitrate and str(a_bitrate).isdigit():
                    a_bitrate_val = int(a_bitrate)
                else:
                    bps_tag = tags.get("BPS") or tags.get("BPS-eng")
                    a_bitrate_val = int(bps_tag) if bps_tag and str(bps_tag).isdigit() else None

                sample_rate = s.get("sample_rate")
                if sample_rate and str(sample_rate).isdigit():
                    sr_int = int(sample_rate)
                    sr_display = f"{sr_int:,} Hz ({sr_int / 1000.0:.1f} kHz)"
                else:
                    sr_display = "Unavailable"

                channels = int(s.get("channels", 0) or 0)
                channel_layout = sanitize_metadata_text(s.get("channel_layout"), max_len=40, default="") or None
                lang_raw = sanitize_metadata_text(tags.get("language") or tags.get("LANGUAGE"), max_len=32, default="")
                title_raw = sanitize_metadata_text(tags.get("title") or tags.get("TITLE"), max_len=120, default="")

                audio_streams.append({
                    "stream_index": len(audio_streams) + 1,
                    "codec": codec_display,
                    "bitrate": format_bitrate(a_bitrate_val),
                    "sample_rate": sr_display,
                    "channels": format_channels(channels, channel_layout),
                    "language": sanitize_metadata_text(format_language(lang_raw), max_len=80),
                    "title": title_raw if title_raw else "Default Audio Track" if disposition.get("default") else "Audio Stream",
                })

            elif codec_type == "subtitle":
                codec_raw = sanitize_metadata_text(s.get("codec_name"), max_len=60, default="").lower()
                codec_display = sanitize_metadata_text(
                    SUBTITLE_CODEC_MAP.get(codec_raw, codec_raw.upper() if codec_raw else "Unavailable"),
                    max_len=120,
                )
                lang_raw = sanitize_metadata_text(tags.get("language") or tags.get("LANGUAGE"), max_len=32, default="")
                title_raw = sanitize_metadata_text(tags.get("title") or tags.get("TITLE"), max_len=120, default="")
                flags = []
                if disposition.get("default"):
                    flags.append("Default")
                if disposition.get("forced"):
                    flags.append("Forced")
                flag_str = f" ({', '.join(flags)})" if flags else ""

                subtitle_streams.append({
                    "stream_index": len(subtitle_streams) + 1,
                    "codec": codec_display,
                    "language": sanitize_metadata_text(format_language(lang_raw), max_len=80),
                    "title": sanitize_metadata_text((title_raw + flag_str).strip(), max_len=140, default="") or f"Embedded Track #{len(subtitle_streams) + 1}{flag_str}",
                    "source": "Embedded",
                })

        return {
            "video": video_info,
            "audio_streams": audio_streams,
            "subtitle_streams": subtitle_streams,
            "engine": "FFprobe",
        }
    except Exception:
        return None


def _extract_via_vlc_and_opencv(file_path: str, file_size: int) -> dict:
    """
    Phương án dự phòng (Fallback) sử dụng libvlc + OpenCV đã tích hợp sẵn
    khi máy người dùng không có ffprobe.
    """
    width = 0
    height = 0
    fps_val = 0.0
    duration_sec = 0.0
    v_codec_str = ""
    v_bitrate_val = None
    dar_str = None

    audio_streams = []
    subtitle_streams = []

    # 1. Thử đọc qua libvlc Media tracks_get (offline hoàn toàn, tắt Lua)
    if HAS_VLC:
        inst = None
        media = None
        try:
            inst = vlc.Instance(get_safe_vlc_args())
            if inst:
                media = inst.media_new(file_path)
                media.parse_with_options(vlc.MediaParseFlag.local, 3000)
                # Chờ tối đa 1.5s cho libvlc parse xong header
                import time
                t0 = time.time()
                while media.get_parsed_status() not in (
                    vlc.MediaParsedStatus.done,
                    vlc.MediaParsedStatus.failed,
                    vlc.MediaParsedStatus.timeout,
                ) and (time.time() - t0) < 1.5:
                    time.sleep(0.05)

                dur_ms = media.get_duration()
                if dur_ms and dur_ms > 0:
                    duration_sec = dur_ms / 1000.0

                tracks = media.tracks_get()
                if tracks:
                    for t in tracks:
                        if not t:
                            continue
                        t_type = t.type
                        fourcc_int = t.original_fourcc or t.codec
                        codec_code = sanitize_metadata_text(_fourcc_to_str(fourcc_int), max_len=40, default="").lower()
                        lang = sanitize_metadata_text(t.language, max_len=32, default="")
                        desc = sanitize_metadata_text(t.description, max_len=120, default="")
                        br = t.bitrate if hasattr(t, "bitrate") and t.bitrate and t.bitrate > 0 else None

                        if t_type == vlc.TrackType.video and width == 0:
                            if t.u and t.u.video:
                                width = int(t.u.video.width or 0)
                                height = int(t.u.video.height or 0)
                                fn = int(t.u.video.frame_rate_num or 0)
                                fd = int(t.u.video.frame_rate_den or 0)
                                if fn > 0 and fd > 0:
                                    fps_val = fn / fd
                                sn = int(t.u.video.sar_num or 0)
                                sd = int(t.u.video.sar_den or 0)
                                if sn > 0 and sd > 0 and sn != sd and width > 0 and height > 0:
                                    dar_w = width * sn
                                    dar_h = height * sd
                                    g = math.gcd(dar_w, dar_h)
                                    dar_str = f"{dar_w // g}:{dar_h // g}"
                            v_codec_str = codec_code
                            v_bitrate_val = br

                        elif t_type == vlc.TrackType.audio:
                            ch = int(t.u.audio.channels or 0) if (t.u and t.u.audio) else 0
                            sr = int(t.u.audio.rate or 0) if (t.u and t.u.audio) else 0
                            sr_display = f"{sr:,} Hz ({sr / 1000.0:.1f} kHz)" if sr > 0 else "Unavailable"
                            c_disp = sanitize_metadata_text(
                                AUDIO_CODEC_MAP.get(codec_code, codec_code.upper() if codec_code else "Unavailable"),
                                max_len=120,
                            )
                            audio_streams.append({
                                "stream_index": len(audio_streams) + 1,
                                "codec": c_disp,
                                "bitrate": format_bitrate(br),
                                "sample_rate": sr_display,
                                "channels": format_channels(ch),
                                "language": sanitize_metadata_text(format_language(lang), max_len=80),
                                "title": desc if desc else f"Audio Track #{len(audio_streams) + 1}",
                            })

                        elif t_type == vlc.TrackType.text:
                            c_disp = sanitize_metadata_text(
                                SUBTITLE_CODEC_MAP.get(codec_code, codec_code.upper() if codec_code else "Subtitle"),
                                max_len=120,
                            )
                            subtitle_streams.append({
                                "stream_index": len(subtitle_streams) + 1,
                                "codec": c_disp,
                                "language": sanitize_metadata_text(format_language(lang), max_len=80),
                                "title": desc if desc else f"Embedded Track #{len(subtitle_streams) + 1}",
                                "source": "Embedded",
                            })
        except Exception:
            pass
        finally:
            if media is not None:
                try:
                    media.release()
                except Exception:
                    pass
            if inst is not None:
                try:
                    inst.release()
                except Exception:
                    pass

    # 2. Bổ sung thông số Video qua OpenCV nếu libvlc chưa lấy đủ
    if HAS_OPENCV and (width == 0 or height == 0 or fps_val <= 0 or duration_sec <= 0):
        cap = None
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                if width == 0:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                if height == 0:
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if fps_val <= 0:
                    fps_val = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                if duration_sec <= 0 and fps_val > 0:
                    frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                    if frame_count > 0:
                        duration_sec = frame_count / fps_val
                if not v_codec_str:
                    fcc = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
                    v_codec_str = sanitize_metadata_text(_fourcc_to_str(fcc), max_len=40, default="").lower()
                if not v_bitrate_val and hasattr(cv2, "CAP_PROP_BITRATE"):
                    br_kbps = float(cap.get(cv2.CAP_PROP_BITRATE) or 0.0)
                    if br_kbps > 0:
                        v_bitrate_val = int(br_kbps * 1000)
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    # Tính tổng bitrate ước tính từ kích thước file / thời lượng nếu stream không ghi riêng
    if not v_bitrate_val and duration_sec > 0 and file_size > 0:
        v_bitrate_val = int((file_size * 8) / duration_sec)

    fps_display = "Unavailable"
    if fps_val and fps_val > 0:
        if abs(fps_val - round(fps_val)) < 0.01:
            fps_display = f"{int(round(fps_val))} FPS"
        else:
            fps_display = f"{fps_val:.3f} FPS"

    codec_display = VIDEO_CODEC_MAP.get(v_codec_str, v_codec_str.upper() if v_codec_str else "Unavailable")

    video_info = {
        "resolution": f"{width} × {height}" if (width > 0 and height > 0) else "Unavailable",
        "width": width,
        "height": height,
        "video_quality": classify_video_quality(width, height),
        "frame_rate": fps_display,
        "video_codec": codec_display,
        "bitrate": format_bitrate(v_bitrate_val),
        "duration": format_duration(duration_sec),
        "aspect_ratio": calculate_aspect_ratio(width, height, dar_str),
        "pixel_format": "Unavailable",
    }

    return {
        "video": video_info,
        "audio_streams": audio_streams,
        "subtitle_streams": subtitle_streams,
        "engine": "LibVLC/OpenCV",
    }


def _detect_external_subtitles(file_path: str) -> list[dict]:
    """Tìm các tệp phụ đề rời (.srt, .ass, .ssa, .vtt) cùng tên với video trong thư mục."""
    external_subs = []
    try:
        folder = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        sub_exts = {
            ".srt": "SubRip (SRT - External)",
            ".ass": "Advanced SubStation Alpha (ASS - External)",
            ".ssa": "SubStation Alpha (SSA - External)",
            ".vtt": "WebVTT (External)",
        }
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                cand_sub = os.path.join(folder, fname)
                if not verify_contained_file(cand_sub, folder):
                    continue
                name_part, ext_part = os.path.splitext(fname)
                ext_lower = ext_part.lower()
                if ext_lower in sub_exts and name_part.lower().startswith(base_name):
                    # Kiểm tra hậu tố ngôn ngữ (ví dụ: movie.vi.srt hoặc movie.en.srt)
                    suffix = sanitize_metadata_text(name_part[len(base_name):].strip("._- "), max_len=24, default="")
                    lang = sanitize_metadata_text(format_language(suffix) if suffix else "Unknown", max_len=80)
                    external_subs.append({
                        "stream_index": 0,
                        "codec": sub_exts[ext_lower],
                        "language": lang,
                        "title": sanitize_metadata_text(fname, max_len=140, default="Subtitle"),
                        "source": "External File",
                    })
    except Exception:
        pass
    return external_subs


def _unavailable_metadata_result(abs_path: str, error_msg: str) -> dict:
    return {
        "exists": False,
        "error": error_msg,
        "general": {
            "file_name": sanitize_metadata_text(os.path.basename(abs_path), max_len=260),
            "file_type": "Unavailable",
            "file_location": sanitize_metadata_text(os.path.dirname(abs_path), max_len=260),
            "full_path": abs_path,
            "file_size": "Unavailable",
            "file_size_short": "Unavailable",
            "created_date": "Unavailable",
            "modified_date": "Unavailable",
            "accessed_date": "Unavailable",
        },
        "video": {
            "resolution": "Unavailable",
            "video_quality": "Unavailable",
            "frame_rate": "Unavailable",
            "video_codec": "Unavailable",
            "bitrate": "Unavailable",
            "duration": "Unavailable",
            "aspect_ratio": "Unavailable",
            "pixel_format": "Unavailable",
        },
        "audio_streams": [],
        "subtitle_streams": [],
    }


def extract_video_metadata(file_path: str) -> dict:
    """
    Trích xuất toàn diện thông tin General, Video, Audio và Subtitles của tệp video.
    Kiểm tra an toàn đầu vào và làm sạch chuỗi metadata trước khi đưa ra UI.
    """
    try:
        abs_path = validate_path(file_path)
    except FileSecurityError as exc:
        return _unavailable_metadata_result(str(file_path or ""), str(exc))

    norm_path = os.path.normcase(abs_path)

    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        return _unavailable_metadata_result(
            abs_path,
            "Tệp video không tồn tại hoặc đã bị di chuyển / xóa khỏi ổ đĩa.",
        )

    valid_media, invalid_reason = check_disguised_or_invalid_media(abs_path)
    if not valid_media:
        return _unavailable_metadata_result(abs_path, invalid_reason)

    try:
        st = os.stat(abs_path)
        file_size = st.st_size
        mtime = st.st_mtime
        ctime = st.st_ctime
        atime = getattr(st, "st_atime", None)
    except Exception as e:
        return _unavailable_metadata_result(abs_path, f"Không thể đọc thuộc tính tệp hệ thống: {e}")

    # Kiểm tra Cache
    with _CACHE_LOCK:
        cached = _METADATA_CACHE.get(norm_path)
        if cached and cached[0] == mtime and cached[1] == file_size:
            return cached[2]

    ext = os.path.splitext(abs_path)[1].lower()
    file_type_str = VIDEO_TYPE_MAP.get(ext, f"{ext.upper().lstrip('.')} Video ({ext})" if ext else "Video File")

    general_info = {
        "file_name": sanitize_metadata_text(os.path.basename(abs_path), max_len=260),
        "file_type": file_type_str,
        "file_location": sanitize_metadata_text(os.path.dirname(abs_path), max_len=260),
        "full_path": abs_path,
        "file_size": format_file_size(file_size),
        "file_size_short": format_file_size_short(file_size),
        "created_date": datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S") if ctime else "Unavailable",
        "modified_date": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "Unavailable",
        "accessed_date": datetime.fromtimestamp(atime).strftime("%Y-%m-%d %H:%M:%S") if atime else "Unavailable",
    }

    # Ưu tiên trích xuất bằng FFprobe, nếu không có thì dùng LibVLC + OpenCV
    ffprobe_bin = _find_ffprobe()
    parsed = None
    if ffprobe_bin:
        parsed = _extract_via_ffprobe(abs_path, ffprobe_bin)

    if not parsed or not parsed.get("video"):
        parsed = _extract_via_vlc_and_opencv(abs_path, file_size)

    video_info = parsed.get("video") or {
        "resolution": "Unavailable",
        "video_quality": "Unavailable",
        "frame_rate": "Unavailable",
        "video_codec": "Unavailable",
        "bitrate": "Unavailable",
        "duration": "Unavailable",
        "aspect_ratio": "Unavailable",
        "pixel_format": "Unavailable",
    }

    audio_streams = parsed.get("audio_streams") or []
    subtitle_streams = list(parsed.get("subtitle_streams") or [])

    # Quét thêm phụ đề rời cùng thư mục (nếu có)
    ext_subs = _detect_external_subtitles(abs_path)
    for es in ext_subs:
        es["stream_index"] = len(subtitle_streams) + 1
        subtitle_streams.append(es)

    result = {
        "exists": True,
        "error": None,
        "engine": parsed.get("engine", "Unknown"),
        "general": general_info,
        "video": video_info,
        "audio_streams": audio_streams,
        "subtitle_streams": subtitle_streams,
    }

    with _CACHE_LOCK:
        _METADATA_CACHE[norm_path] = (mtime, file_size, result)

    return result


class VideoMetadataWorker(QThread):
    """
    Worker chạy nền truy xuất Metadata của video để không bao giờ làm đơ giao diện.
    """
    metadata_ready = pyqtSignal(str, dict)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        data = extract_video_metadata(self.file_path)
        self.metadata_ready.emit(self.file_path, data)
