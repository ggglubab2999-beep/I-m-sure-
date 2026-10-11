# CX Downloader v2.2 - RED ALERT

Python/Kivy Android downloader (yt-dlp engine) with a GitHub Actions APK build.

## What's new in v2.2
- Files now save to the public **Downloads/CX_Downloader** folder (visible in Files/Gallery/Music apps).
- FILES screen lists saved files with **OPEN** and **DELETE** buttons; history is kept after restart.
- **CANCEL** button during a download; accurate progress, speed, ETA and size.
- New RED ALERT design: bottom navigation, cards, custom buttons and progress bar.
- Many bug fixes (see CHANGELOG below).

## Repository layout
Upload the **contents of this folder** to the repository root (no extra wrapper folder):

```text
main.py
core.py
android_utils.py
buildozer.spec
requirements.txt
icon.png
README.md
.gitignore
tests/
.github/workflows/build.yml
```

## Build on GitHub
1. Push the files to the `main` branch.
2. Open **Actions** -> **Build Android APK** (or use **Run workflow**).
3. When it finishes, download the artifact `cx-downloader-red-alert-debug-apk`.
   The first build takes a long time (downloads the Android SDK/NDK); later builds use a cache.

The workflow runs the unit tests first, so a logic mistake is caught before the long APK build.

## Run locally (desktop)
```bash
pip install -r requirements.txt
python main.py
python tests/test_core.py && python tests/test_flow.py   # tests
```
On desktop, files go to `~/Downloads/CX_Downloader`. If FFmpeg is installed, merging and MP3 conversion work.

## Important limits (please read)
- **No FFmpeg on Android.** The app therefore downloads *single-file* formats. On some sites
  (notably YouTube) these top out around 360p-720p, and audio is saved as M4A/WebM instead of MP3.
  FFmpeg is detected automatically on desktop, where all quality options and MP3 work.
- **YouTube:** yt-dlp now needs an external JavaScript runtime for full YouTube support, which an
  Android build does not have. YouTube links may fail or offer fewer formats; many other sites work.
  Site support changes often - rebuild periodically to pick up the newest yt-dlp.
- Keep the app open while downloading (it survives switching apps briefly, but Android may stop it
  if the system is short on memory).
- Bengali/Hindi/Arabic/CJK titles use a system font if one is found. To force a font, put a `.ttf`
  such as `NotoSansBengali-Regular.ttf` in a `fonts/` folder next to `main.py`.
- Download only media you are authorized to save. The app does not bypass DRM, logins or paywalls.

## CHANGELOG (v2.1 -> v2.2)
- Fixed: literal `\n` shown in texts and in the file list (wrong escaping).
- Fixed: files were hidden inside private app storage; "OPEN DOWNLOAD FOLDER" only refreshed.
- Fixed: `ffmpeg` requirement (no usable binary, can break the build); app no longer asks yt-dlp for
  formats that need merging when FFmpeg is missing.
- Fixed: HTTPS certificate errors on Android (certifi bundle).
- Fixed: UI properties were changed from the download thread (unsafe).
- Fixed: "CLEAR HISTORY" could allow two downloads at once.
- Fixed: long non-English titles could exceed the filename limit (limit is in bytes).
- Fixed: tabs could be un-selected, text alignment ignored, blue default button style, symbols
  that Android's default font cannot draw.
- Fixed: progress went back to 0% for every stream; speed/ETA text could contain control codes.
- Added: pinned python-for-android version, SDK license auto-accept, build cache, tests.
