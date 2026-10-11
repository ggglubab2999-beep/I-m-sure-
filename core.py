"""CX Downloader - pure helper logic (no Kivy / Android imports).

Everything here is plain Python so it can be unit-tested on a desktop.
"""
import glob
import json
import mimetypes
import os
import re
import shutil
import tempfile
import time

# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"^(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:[/?#]\S*)?$", re.IGNORECASE
)
_BAD_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def strip_ansi(text):
    """Remove terminal colour codes that yt-dlp puts in error messages."""
    return _ANSI_RE.sub("", str(text))


def extract_url(text):
    """Return the first usable URL in *text*, or '' if there is none.

    Handles pasted text such as "Watch this https://example.com/v/1 now"
    and bare domains such as "example.com/video".
    """
    text = (text or "").strip()
    if not text:
        return ""
    m = _URL_RE.search(text)
    if m:
        return m.group(0).rstrip(").,;]}")
    first = text.split()[0]
    if _BARE_DOMAIN_RE.match(first):
        return "https://" + first
    return ""


def clean_error(err, limit=240):
    """Make a yt-dlp / network error short and readable."""
    msg = strip_ansi(err).strip()
    for prefix in ("ERROR:", "DownloadError:", "ExtractorError:"):
        if msg.startswith(prefix):
            msg = msg[len(prefix):].strip()
    msg = re.sub(r"\s+", " ", msg)
    low = msg.lower()
    if "unsupported url" in low:
        return "This link is not supported."
    if "certificate verify failed" in low:
        return "Secure connection failed (certificate error). Check phone date/time."
    if ("unable to download" in low or "name or service not known" in low
            or "network is unreachable" in low or "timed out" in low
            or "temporary failure" in low):
        return "Network problem. Check your internet connection and try again."
    if "ffmpeg" in low and ("not installed" in low or "not found" in low):
        return "This format needs FFmpeg, which is not available on this device."
    if "sign in" in low or "login" in low or "private video" in low:
        return "This media needs a login or is private. It cannot be downloaded."
    if len(msg) > limit:
        msg = msg[: limit - 3].rstrip() + "..."
    return msg or "Unknown error."


def truncate_utf8(text, max_bytes):
    """Cut *text* so its UTF-8 encoding is <= max_bytes (never splits a char)."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", "ignore").rstrip()


def safe_filename(title, ext, max_bytes=120):
    """Build a filesystem-safe '<title>.<ext>' name.

    The byte limit matters: Bengali/Hindi/Arabic characters use 3 bytes each,
    so a 100-character title can exceed the 255-byte filename limit.
    """
    ext = (ext or "").lstrip(".")
    title = _BAD_FILENAME_CHARS.sub(" ", title or "")
    title = re.sub(r"\s+", " ", title).strip(" .")
    if not title:
        title = "media"
    title = truncate_utf8(title, max_bytes).strip(" .") or "media"
    return f"{title}.{ext}" if ext else title


_EXTRA_MIME = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp4": "video/mp4",
    ".3gp": "video/3gpp",
    ".mov": "video/quicktime",
}


def guess_mime(filename, media_type="video"):
    ext = os.path.splitext(filename)[1].lower()
    if ext in _EXTRA_MIME:
        mime = _EXTRA_MIME[ext]
        if media_type == "audio" and mime == "video/webm":
            return "audio/webm"
        return mime
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        return mime
    return "audio/*" if media_type == "audio" else "video/*"


# --------------------------------------------------------------------------
# Number formatting
# --------------------------------------------------------------------------
def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "--"
    if n < 0:
        return "--"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return "--"


def human_speed(bps):
    if not bps:
        return "-- /s"
    return human_size(bps) + "/s"


def human_eta(seconds):
    if seconds is None:
        return "--:--"
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "--:--"
    if seconds < 0:
        return "--:--"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def human_date(ts):
    try:
        return time.strftime("%d %b %Y, %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


# --------------------------------------------------------------------------
# Format selection
# --------------------------------------------------------------------------
QUALITY_HEIGHT = {"1080p": 1080, "720p": 720, "480p": 480, "360p": 360}


def format_selector(quality, media_type, has_ffmpeg):
    """Return a yt-dlp format string.

    Without FFmpeg we cannot merge separate video+audio streams, so we ask
    only for single-file ("progressive") formats. With FFmpeg we can use the
    higher-quality separate streams.
    """
    h = QUALITY_HEIGHT.get(quality)

    if media_type == "audio":
        return "ba/b" if has_ffmpeg else "ba[ext=m4a]/ba/b"

    if has_ffmpeg:
        if h is None:
            return "bv*+ba/b"
        return (
            f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/"
            f"b[height<={h}]/bv*+ba/b"
        )

    if h is None:
        return "b"
    return f"b[height<={h}]/b"


# --------------------------------------------------------------------------
# JSON storage (atomic writes so a crash never corrupts the file)
# --------------------------------------------------------------------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, type(default)):
            return data
    except (OSError, ValueError):
        pass
    return default


def save_json(path, data):
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None


# --------------------------------------------------------------------------
# Fonts: Kivy's default font (Roboto) has no Bengali/Hindi/Arabic/CJK glyphs,
# so titles in those scripts would show as empty boxes.
# --------------------------------------------------------------------------
_SCRIPTS = [
    # (name, [(lo, hi), ...], [file patterns])
    ("bengali", [(0x0980, 0x09FF)],
     ["NotoSansBengali*.ttf", "NotoSerifBengali*.ttf", "Lohit-Bengali*.ttf"]),
    ("devanagari", [(0x0900, 0x097F)],
     ["NotoSansDevanagari*.ttf", "Lohit-Devanagari*.ttf"]),
    ("arabic", [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
     ["NotoNaskhArabic*.ttf", "NotoSansArabic*.ttf"]),
    ("cjk", [(0x2E80, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF)],
     ["NotoSansCJK*.ttc", "NotoSansCJK*.otf", "NotoSansSC*.otf", "NotoSansSC*.ttf",
      "DroidSansFallback*.ttf"]),
]
_FALLBACK_PATTERNS = ["DroidSansFallback*.ttf", "NotoSansSymbols*.ttf"]
_FONT_CACHE = {}


def _script_of(text):
    for ch in text:
        cp = ord(ch)
        if cp <= 0x024F or 0x2000 <= cp <= 0x206F:  # Latin + general punctuation
            continue
        for name, ranges, _ in _SCRIPTS:
            if any(lo <= cp <= hi for lo, hi in ranges):
                return name
        if cp >= 0x2190:  # symbols / emoji / misc
            continue
        return "other"
    return None


def pick_font(text, search_dirs, default="Roboto"):
    """Return a font file able to draw *text*, or *default* (Roboto)."""
    script = _script_of(text or "")
    if script is None:
        return default
    key = (script, tuple(search_dirs))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    patterns = _FALLBACK_PATTERNS
    for name, _, pats in _SCRIPTS:
        if name == script:
            patterns = pats
            break
    result = default
    for folder in search_dirs:
        for pat in patterns:
            hits = sorted(glob.glob(os.path.join(glob.escape(folder), pat)))
            if hits:
                result = hits[0]
                break
        if result != default:
            break
    _FONT_CACHE[key] = result
    return result


def is_youtube(url):
    return bool(re.match(r"https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/",
                         url or "", re.IGNORECASE))
