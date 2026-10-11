[app]
title = CX Downloader
package.name = cxdownloader
package.domain = org.cxdownloader
source.dir = .
source.include_exts = py,png,jpg,kv,txt,ttf,otf
source.exclude_dirs = tests,.github,bin,.buildozer,__pycache__
version = 2.2.0
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# ffmpeg is NOT listed: python-for-android's "ffmpeg" recipe builds libraries
# only (no ffmpeg executable), so yt-dlp could never call it, and it often
# breaks the build. Without it the app downloads single-file formats.
requirements = python3,kivy==2.3.0,sqlite3,openssl,certifi,yt-dlp,android,pyjnius

# INTERNET for downloading. WRITE_EXTERNAL_STORAGE is only needed (and only
# requested) on Android 9 and below; newer Android saves through MediaStore.
android.permissions = INTERNET,(name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# Pinned so the build does not break when python-for-android changes.
# v2024.01.21 = Kivy 2.3.0, Python 3.11, NDK 25b.
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
