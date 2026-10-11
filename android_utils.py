"""Android integration for CX Downloader.

Every function is defensive: if anything fails (different Android version,
missing permission, odd device) it returns a failure value instead of
raising, so the app itself never crashes because of storage problems.

On non-Android systems (desktop testing) the functions fall back to simple
file-system operations.
"""
import os
import shutil
import subprocess
import sys

try:
    from kivy.utils import platform as _platform
except Exception:  # pragma: no cover - kivy missing
    _platform = sys.platform

ON_ANDROID = _platform == "android"

SUBFOLDER = "CX_Downloader"
_CHUNK = 256 * 1024


def _log(msg):
    try:
        from kivy.logger import Logger
        Logger.info("CX: " + msg)
    except Exception:
        print("CX:", msg)


# --------------------------------------------------------------------------
# Android helpers
# --------------------------------------------------------------------------
def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def sdk_int():
    if not ON_ANDROID:
        return 0
    try:
        from jnius import autoclass
        return int(autoclass("android.os.Build$VERSION").SDK_INT)
    except Exception:
        return 0


def public_folder_label():
    if ON_ANDROID:
        return "Downloads/" + SUBFOLDER
    return os.path.join(os.path.expanduser("~"), "Downloads", SUBFOLDER)


def request_storage_permission():
    """Only Android 9 and below need a runtime storage permission."""
    if not ON_ANDROID:
        return
    try:
        if 0 < sdk_int() <= 28:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE])
    except Exception as exc:
        _log(f"permission request failed: {exc}")


def _legacy_has_permission():
    try:
        from android.permissions import Permission, check_permission
        return bool(check_permission(Permission.WRITE_EXTERNAL_STORAGE))
    except Exception:
        return False


# --------------------------------------------------------------------------
# Export a finished download to the public Downloads folder
# --------------------------------------------------------------------------
def export_to_public(src_path, display_name, mime):
    """Copy *src_path* to the public Downloads/CX_Downloader folder.

    Returns a dict ``{"uri": str, "path": str}`` on success (one of the two
    may be empty) or ``None`` on failure. The caller keeps the private copy
    when this returns None.
    """
    if not ON_ANDROID:
        return _export_desktop(src_path, display_name)
    try:
        if sdk_int() >= 29:
            return _export_mediastore(src_path, display_name, mime)
        return _export_legacy(src_path, display_name)
    except Exception as exc:
        _log(f"export failed: {exc!r}")
        return None


def _export_desktop(src_path, display_name):
    try:
        dest_dir = os.path.join(os.path.expanduser("~"), "Downloads", SUBFOLDER)
        os.makedirs(dest_dir, exist_ok=True)
        dest = _unique_path(os.path.join(dest_dir, display_name))
        shutil.copyfile(src_path, dest)
        return {"uri": "", "path": dest}
    except OSError as exc:
        _log(f"desktop export failed: {exc!r}")
        return None


def _unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def _export_mediastore(src_path, display_name, mime):
    """Android 10+ (API 29+): scoped-storage safe, needs no permission."""
    from jnius import autoclass

    activity = _activity()
    resolver = activity.getContentResolver()
    ContentValues = autoclass("android.content.ContentValues")
    Downloads = autoclass("android.provider.MediaStore$Downloads")
    Columns = autoclass("android.provider.MediaStore$MediaColumns")
    Environment = autoclass("android.os.Environment")

    values = ContentValues()
    values.put(Columns.DISPLAY_NAME, display_name)
    values.put(Columns.MIME_TYPE, mime)
    values.put(Columns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + SUBFOLDER)

    uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        return None
    try:
        out = resolver.openOutputStream(uri)
        if out is None:
            raise RuntimeError("openOutputStream returned null")
        try:
            with open(src_path, "rb") as fh:
                while True:
                    chunk = fh.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            out.flush()
        finally:
            out.close()
    except Exception:
        try:
            resolver.delete(uri, None, None)
        except Exception:
            pass
        raise
    return {"uri": str(uri.toString()), "path": ""}


def _export_legacy(src_path, display_name):
    """Android 9 and below: write straight into the public Downloads folder."""
    if not _legacy_has_permission():
        _log("legacy export skipped: no storage permission")
        return None
    from jnius import autoclass

    Environment = autoclass("android.os.Environment")
    public = Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_DOWNLOADS
    ).getAbsolutePath()
    dest_dir = os.path.join(public, SUBFOLDER)
    os.makedirs(dest_dir, exist_ok=True)
    dest = _unique_path(os.path.join(dest_dir, display_name))
    shutil.copyfile(src_path, dest)
    try:  # make the file show up in Gallery / Music apps
        MediaScanner = autoclass("android.media.MediaScannerConnection")
        MediaScanner.scanFile(_activity(), [dest], None, None)
    except Exception as exc:
        _log(f"media scan failed: {exc!r}")
    return {"uri": "", "path": dest}


# --------------------------------------------------------------------------
# Open / delete
# --------------------------------------------------------------------------
def open_media(uri, path, mime):
    """Open a saved file with an external player. Returns True on success."""
    if not ON_ANDROID:
        return _open_desktop(path)
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        activity = _activity()

        if uri:
            target = Uri.parse(uri)
        elif path and os.path.exists(path):
            _allow_file_uri()
            File = autoclass("java.io.File")
            target = Uri.fromFile(File(path))
        else:
            return False

        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(target, mime or "*/*")
        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK
        )
        activity.startActivity(intent)
        return True
    except Exception as exc:
        _log(f"open failed: {exc!r}")
        return False


def _allow_file_uri():
    """Android 7+ blocks file:// URIs unless this check is relaxed."""
    try:
        from jnius import autoclass
        StrictMode = autoclass("android.os.StrictMode")
        StrictMode.disableDeathOnFileUriExposure()
    except Exception:
        pass


def _open_desktop(path):
    try:
        if not path or not os.path.exists(path):
            return False
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception as exc:
        _log(f"desktop open failed: {exc!r}")
        return False


def delete_media(uri, path):
    """Delete a saved file. Returns True if it is gone afterwards."""
    ok = True
    if uri and ON_ANDROID:
        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            _activity().getContentResolver().delete(Uri.parse(uri), None, None)
        except Exception as exc:
            _log(f"mediastore delete failed: {exc!r}")
            ok = False
    if path:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            _log(f"file delete failed: {exc!r}")
            ok = False
    return ok


def media_exists(uri, path):
    """Best-effort check that a saved file still exists."""
    if path:
        return os.path.exists(path)
    if uri and ON_ANDROID:
        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            resolver = _activity().getContentResolver()
            cursor = resolver.query(Uri.parse(uri), None, None, None, None)
            if cursor is None:
                return False
            try:
                return bool(cursor.getCount() > 0)
            finally:
                cursor.close()
        except Exception:
            return True  # unknown -> keep showing it
    return bool(uri)
