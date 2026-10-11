"""CX Downloader - RED ALERT edition (v2.2).

Kivy front-end for yt-dlp. Pure helper logic lives in core.py and Android
storage integration lives in android_utils.py.
"""
import glob
import os
import shutil
import threading
import time

# TLS certificates: Android's Python has no system CA bundle. This MUST be set
# before yt-dlp (or anything else) creates an SSL context.
try:
    import certifi

    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
except Exception:  # pragma: no cover
    pass

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget

import android_utils as droid
import core

try:
    import yt_dlp
except Exception:  # pragma: no cover
    yt_dlp = None

APP_VERSION = "2.2.0"
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [
    os.path.join(HERE, "fonts"),
    "/system/fonts",
    "/system/font",
    "/product/fonts",
]
MAX_RECORDS = 200

BG = (0.035, 0.016, 0.024, 1)

KV = r"""
#:import dp kivy.metrics.dp
#:import FadeTransition kivy.uix.screenmanager.FadeTransition

#:set C_BG (.035, .016, .024, 1)
#:set C_CARD (.075, .035, .048, 1)
#:set C_FIELD (.115, .052, .068, 1)
#:set C_BORDER (.34, .07, .095, 1)
#:set C_RED (.90, .09, .12, 1)
#:set C_RED_D (.60, .04, .07, 1)
#:set C_RED_L (1, .40, .40, 1)
#:set C_TEXT (.96, .93, .93, 1)
#:set C_MUTED (.68, .60, .62, 1)
#:set C_OK (.38, .86, .52, 1)

# ---------------------------------------------------------------- basics
<Card>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: C_CARD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
        Color:
            rgba: C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(14))
            width: dp(1)

<Caption>:
    color: C_RED_L
    font_size: "11sp"
    bold: True
    halign: "left"
    valign: "middle"
    text_size: self.width, None
    size_hint_y: None
    height: dp(18)

<Body>:
    color: C_TEXT
    font_size: "14sp"
    halign: "left"
    valign: "top"
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1] + dp(2)

<Muted>:
    color: C_MUTED
    font_size: "12sp"

<RedProgress>:
    size_hint_y: None
    height: dp(16)
    canvas:
        Color:
            rgba: C_FIELD
        RoundedRectangle:
            pos: self.x, self.center_y - dp(5)
            size: self.width, dp(10)
            radius: [dp(5)]
        Color:
            rgba: C_RED
        RoundedRectangle:
            pos: self.x, self.center_y - dp(5)
            size: max(self.width * self.value / 100.0, dp(10) if self.value > 0 else 0), dp(10)
            radius: [dp(5)]

# ---------------------------------------------------------------- buttons
<RedButton>:
    background_normal: ""
    background_down: ""
    background_disabled_normal: ""
    background_color: 0, 0, 0, 0
    color: 1, 1, 1, 1
    disabled_color: .6, .5, .52, 1
    bold: True
    font_size: "16sp"
    canvas.before:
        Color:
            rgba: (.28, .05, .07, 1) if self.alt else (C_RED_D if self.state == "down" else C_RED)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: C_RED if self.alt else (0, 0, 0, 0)
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(12))
            width: dp(1.4)

<GhostButton>:
    background_normal: ""
    background_down: ""
    background_disabled_normal: ""
    background_color: 0, 0, 0, 0
    color: C_TEXT
    disabled_color: .45, .38, .40, 1
    bold: True
    font_size: "12sp"
    canvas.before:
        Color:
            rgba: (.20, .08, .10, 1) if self.state == "down" else C_FIELD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(10))
            width: dp(1)

<Chip>:
    allow_no_selection: False
    background_normal: ""
    background_down: ""
    background_disabled_normal: ""
    background_disabled_down: ""
    background_color: 0, 0, 0, 0
    color: (1, 1, 1, 1) if self.state == "down" else C_MUTED
    disabled_color: .42, .35, .37, 1
    bold: True
    font_size: "13sp"
    canvas.before:
        Color:
            rgba: (.10, .05, .06, 1) if self.disabled else (C_RED if self.state == "down" else C_FIELD)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(10))
            width: dp(1)

<NavTab>:
    group: "nav"
    allow_no_selection: False
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    color: C_RED_L if self.state == "down" else C_MUTED
    bold: True
    font_size: "11sp"
    canvas.before:
        Color:
            rgba: C_RED if self.state == "down" else (0, 0, 0, 0)
        RoundedRectangle:
            pos: self.x + dp(16), self.top - dp(3)
            size: self.width - dp(32), dp(3)
            radius: [dp(2)]

<UrlInput>:
    multiline: False
    write_tab: False
    input_type: "url"
    background_normal: ""
    background_active: ""
    background_disabled_normal: ""
    background_color: 0, 0, 0, 0
    foreground_color: 1, 1, 1, 1
    hint_text_color: .55, .46, .49, 1
    cursor_color: C_RED
    selection_color: .90, .09, .12, .35
    font_size: "15sp"
    size_hint_y: None
    height: dp(52)
    padding: [dp(14), (self.height - self.line_height) / 2, dp(14), 0]
    canvas.before:
        Color:
            rgba: C_FIELD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: C_RED if self.focus else C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(10))
            width: dp(1.3) if self.focus else dp(1)

# ---------------------------------------------------------------- list rows
<FileRow>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(110)
    padding: dp(12)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: C_CARD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(12))
            width: dp(1)
    Label:
        text: root.title
        font_name: root.title_font
        color: C_TEXT
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        max_lines: 2
        shorten: True
        shorten_from: "right"
        text_size: self.width, self.height
        size_hint_y: None
        height: dp(40)
    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(8)
        Muted:
            text: root.meta
            size_hint_y: 1
            valign: "middle"
            text_size: self.width, self.height
        GhostButton:
            text: "OPEN"
            size_hint_x: None
            width: dp(70)
            on_release: app.ui.open_record(root.rid)
        GhostButton:
            text: "DELETE"
            size_hint_x: None
            width: dp(76)
            on_release: app.ui.ask_delete(root.rid)

<HistoryRow>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(74)
    padding: dp(12), dp(8)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: C_CARD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: C_BORDER
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(12))
            width: dp(1)
    Label:
        text: root.title
        font_name: root.title_font
        color: C_TEXT
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        max_lines: 1
        shorten: True
        shorten_from: "right"
        text_size: self.width, self.height
    Muted:
        text: root.meta
        size_hint_y: 1
        valign: "middle"
        text_size: self.width, self.height

<InfoRow>:
    size_hint_y: None
    height: max(dp(30), val.texture_size[1] + dp(10))
    spacing: dp(10)
    Caption:
        text: root.key
        size_hint_x: None
        width: dp(84)
        pos_hint: {"top": 1}
    Body:
        id: val
        text: root.value
        pos_hint: {"top": 1}

# ---------------------------------------------------------------- screens
<RootUI>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: C_BG
        Rectangle:
            pos: self.pos
            size: self.size

    # ---- header
    BoxLayout:
        size_hint_y: None
        height: dp(68)
        padding: dp(12), dp(8)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: C_CARD
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: C_RED_D
            Rectangle:
                pos: self.x, self.y
                size: self.width, dp(2)
        Image:
            source: "icon.png"
            size_hint: None, None
            size: dp(48), dp(48)
            pos_hint: {"center_y": .5}
            fit_mode: "contain"
        BoxLayout:
            orientation: "vertical"
            Label:
                text: "CX DOWNLOADER"
                bold: True
                font_size: "19sp"
                color: 1, 1, 1, 1
                halign: "left"
                valign: "bottom"
                text_size: self.size
            Label:
                text: "RED ALERT EDITION"
                font_size: "10sp"
                color: C_RED_L
                halign: "left"
                valign: "top"
                text_size: self.size
        Label:
            text: "BUSY" if root.busy else "READY"
            size_hint: None, None
            size: dp(86), dp(28)
            pos_hint: {"center_y": .5}
            bold: True
            font_size: "11sp"
            color: C_TEXT
            padding: [dp(14), 0]
            canvas.before:
                Color:
                    rgba: C_RED_D if root.busy else C_FIELD
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(14)]
                Color:
                    rgba: C_RED if root.busy else C_OK
                Ellipse:
                    pos: self.x + dp(11), self.center_y - dp(3)
                    size: dp(6), dp(6)

    # ---- pages
    ScreenManager:
        id: pages
        transition: FadeTransition(duration=0.12)

        # ======================= HOME
        Screen:
            name: "home"
            ScrollView:
                do_scroll_x: False
                bar_width: dp(3)
                bar_color: C_RED
                GridLayout:
                    cols: 1
                    spacing: dp(10)
                    padding: [dp(14), dp(12), dp(14), dp(16)]
                    size_hint_y: None
                    height: self.minimum_height

                    Caption:
                        text: "PASTE LINK"
                    Card:
                        size_hint_y: None
                        height: self.minimum_height
                        UrlInput:
                            id: url
                            hint_text: "Paste video / media link here..."
                            on_text_validate: root.start_download()
                        BoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            spacing: dp(10)
                            GhostButton:
                                text: "PASTE"
                                on_release: root.paste_url()
                            GhostButton:
                                text: "CLEAR"
                                on_release: root.clear_url()

                    Caption:
                        text: "TYPE"
                    BoxLayout:
                        size_hint_y: None
                        height: dp(46)
                        spacing: dp(10)
                        Chip:
                            text: "VIDEO"
                            group: "type"
                            state: "down"
                            on_release: root.media_type = "video"
                        Chip:
                            text: "AUDIO"
                            group: "type"
                            on_release: root.media_type = "audio"

                    Caption:
                        text: "QUALITY"
                    BoxLayout:
                        size_hint_y: None
                        height: dp(44)
                        spacing: dp(6)
                        disabled: root.media_type == "audio"
                        Chip:
                            text: "1080P"
                            group: "quality"
                            on_release: root.set_quality("1080p")
                        Chip:
                            text: "720P"
                            group: "quality"
                            state: "down"
                            on_release: root.set_quality("720p")
                        Chip:
                            text: "480P"
                            group: "quality"
                            on_release: root.set_quality("480p")
                        Chip:
                            text: "360P"
                            group: "quality"
                            on_release: root.set_quality("360p")
                        Chip:
                            text: "BEST"
                            group: "quality"
                            on_release: root.set_quality("Best available")

                    Muted:
                        text: root.mode_hint

                    RedButton:
                        text: "CANCEL DOWNLOAD" if root.busy else "DOWNLOAD NOW"
                        alt: root.busy
                        size_hint_y: None
                        height: dp(58)
                        on_release: root.toggle_download()

                    Card:
                        size_hint_y: None
                        height: self.minimum_height
                        Body:
                            text: root.status
                            color: C_RED_L if root.status_kind == "error" else (C_OK if root.status_kind == "ok" else C_TEXT)
                        BoxLayout:
                            size_hint_y: None
                            height: dp(20)
                            spacing: dp(8)
                            RedProgress:
                                value: root.progress
                            Label:
                                text: "%d%%" % root.progress
                                size_hint_x: None
                                width: dp(44)
                                bold: True
                                font_size: "12sp"
                                color: C_TEXT
                        GridLayout:
                            cols: 3
                            size_hint_y: None
                            height: dp(42)
                            BoxLayout:
                                orientation: "vertical"
                                Caption:
                                    text: "SPEED"
                                Muted:
                                    text: root.speed_text
                            BoxLayout:
                                orientation: "vertical"
                                Caption:
                                    text: "ETA"
                                Muted:
                                    text: root.eta_text
                            BoxLayout:
                                orientation: "vertical"
                                Caption:
                                    text: "SIZE"
                                Muted:
                                    text: root.size_text

                    Card:
                        size_hint_y: None
                        height: self.minimum_height
                        Caption:
                            text: "SAVE LOCATION"
                        Muted:
                            text: root.storage_label

        # ======================= DOWNLOADS
        Screen:
            name: "downloads"
            BoxLayout:
                orientation: "vertical"
                padding: [dp(14), dp(12), dp(14), dp(8)]
                spacing: dp(8)
                BoxLayout:
                    size_hint_y: None
                    height: dp(22)
                    Caption:
                        text: "DOWNLOADED FILES"
                    Caption:
                        text: root.files_count_text
                        halign: "right"
                Muted:
                    text: root.files_msg
                    color: C_RED_L
                ScrollView:
                    do_scroll_x: False
                    bar_width: dp(3)
                    bar_color: C_RED
                    GridLayout:
                        id: files_box
                        cols: 1
                        spacing: dp(8)
                        size_hint_y: None
                        height: self.minimum_height

        # ======================= HISTORY
        Screen:
            name: "history"
            BoxLayout:
                orientation: "vertical"
                padding: [dp(14), dp(12), dp(14), dp(8)]
                spacing: dp(8)
                BoxLayout:
                    size_hint_y: None
                    height: dp(22)
                    Caption:
                        text: "DOWNLOAD HISTORY"
                    Caption:
                        text: root.history_count_text
                        halign: "right"
                ScrollView:
                    do_scroll_x: False
                    bar_width: dp(3)
                    bar_color: C_RED
                    GridLayout:
                        id: history_box
                        cols: 1
                        spacing: dp(8)
                        size_hint_y: None
                        height: self.minimum_height
                GhostButton:
                    text: "CLEAR HISTORY"
                    size_hint_y: None
                    height: dp(46)
                    on_release: root.ask_clear_history()

        # ======================= SETTINGS
        Screen:
            name: "settings"
            ScrollView:
                do_scroll_x: False
                bar_width: dp(3)
                bar_color: C_RED
                GridLayout:
                    cols: 1
                    spacing: dp(10)
                    padding: [dp(14), dp(12), dp(14), dp(16)]
                    size_hint_y: None
                    height: self.minimum_height
                    Caption:
                        text: "SETTINGS"
                    Card:
                        id: settings_card
                        size_hint_y: None
                        height: self.minimum_height
                    GhostButton:
                        text: "RESET STATUS"
                        size_hint_y: None
                        height: dp(46)
                        on_release: root.reset_status()
                    Muted:
                        text: "Download only media you own or have permission to save. This app does not bypass DRM, logins or paywalls."

    # ---- bottom navigation
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        canvas.before:
            Color:
                rgba: C_CARD
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: C_BORDER
            Rectangle:
                pos: self.x, self.top - dp(1)
                size: self.width, dp(1)
        NavTab:
            id: nav_home
            text: "HOME"
            state: "down"
            on_release: root.show_page("home")
        NavTab:
            id: nav_downloads
            text: "FILES"
            on_release: root.show_page("downloads")
        NavTab:
            id: nav_history
            text: "HISTORY"
            on_release: root.show_page("history")
        NavTab:
            id: nav_settings
            text: "SETTINGS"
            on_release: root.show_page("settings")
"""


# ---------------------------------------------------------------------------
# Small widget classes (styled in the KV above)
# ---------------------------------------------------------------------------
class Card(BoxLayout):
    pass


class Caption(Label):
    pass


class Body(Label):
    pass


class Muted(Body):
    pass


class RedProgress(Widget):
    value = NumericProperty(0)


class RedButton(Button):
    alt = BooleanProperty(False)


class GhostButton(Button):
    pass


class Chip(ToggleButton):
    pass


class NavTab(ToggleButton):
    pass


class UrlInput(TextInput):
    pass


class FileRow(BoxLayout):
    rid = StringProperty("")
    title = StringProperty("")
    title_font = StringProperty("Roboto")
    meta = StringProperty("")


class HistoryRow(BoxLayout):
    title = StringProperty("")
    title_font = StringProperty("Roboto")
    meta = StringProperty("")


class InfoRow(BoxLayout):
    key = StringProperty("")
    value = StringProperty("")


class DownloadCancelled(Exception):
    pass


class _YDLLogger:
    """Keeps yt-dlp quiet but remembers its warnings/errors."""

    def __init__(self):
        self.messages = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.messages.append(core.strip_ansi(msg))

    def error(self, msg):
        self.messages.append(core.strip_ansi(msg))


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------
class RootUI(BoxLayout):
    status = StringProperty("Ready. Paste a link to begin.")
    status_kind = StringProperty("idle")  # idle | busy | ok | error
    progress = NumericProperty(0)
    speed_text = StringProperty("-- /s")
    eta_text = StringProperty("--:--")
    size_text = StringProperty("--")
    media_type = StringProperty("video")
    quality = StringProperty("720p")
    busy = BooleanProperty(False)
    mode_hint = StringProperty("")
    storage_label = StringProperty("")
    files_msg = StringProperty("")
    files_count_text = StringProperty("")
    history_count_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.library = []
        self.history = []
        self._cancel = threading.Event()
        self._ffmpeg = core.has_ffmpeg()
        self._ready = False
        self._popup = None

    # -- paths -------------------------------------------------------------
    @property
    def data_dir(self):
        return App.get_running_app().user_data_dir

    @property
    def work_dir(self):
        return os.path.join(self.data_dir, "work")

    @property
    def private_dir(self):
        return os.path.join(self.data_dir, "CX_Downloads")

    # -- setup -------------------------------------------------------------
    def setup(self):
        if self._ready:
            return
        self._ready = True
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.private_dir, exist_ok=True)
        self._purge_dir(self.work_dir)  # leftovers of an interrupted download
        self.library = core.load_json(os.path.join(self.data_dir, "library.json"), [])
        self.history = core.load_json(os.path.join(self.data_dir, "history.json"), [])
        self.storage_label = droid.public_folder_label()
        self._update_hint()
        self.refresh_downloads()
        self.refresh_history()
        self.refresh_settings()
        if yt_dlp is None:
            self._set_status("error", "yt-dlp is not installed in this build.")

    def on_resume(self):
        if self._ready:
            self.refresh_downloads()

    @staticmethod
    def _purge_dir(folder):
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
        except OSError:
            pass

    # -- navigation ----------------------------------------------------------
    def show_page(self, page):
        self.ids.pages.current = page
        nav = self.ids.get("nav_" + page)
        if nav is not None and nav.state != "down":
            nav.state = "down"
        if page == "downloads":
            self.files_msg = ""
            self.refresh_downloads()
        elif page == "history":
            self.refresh_history()
        elif page == "settings":
            self.refresh_settings()

    # -- simple UI actions -----------------------------------------------------
    def set_quality(self, q):
        self.quality = q

    def on_media_type(self, *_):
        self._update_hint()

    def _update_hint(self):
        if self.media_type == "audio":
            if self._ffmpeg:
                self.mode_hint = "Audio will be converted to MP3 (192 kbps)."
            else:
                self.mode_hint = ("Audio is saved in its original format (usually M4A). "
                                  "MP3 conversion needs FFmpeg.")
        elif self._ffmpeg:
            self.mode_hint = "FFmpeg found: the selected quality will be used."
        else:
            self.mode_hint = ("Single-file mode: if the exact quality is not offered as one "
                              "file, the best single-file format is used.")

    def paste_url(self):
        try:
            text = Clipboard.paste() or ""
        except Exception:
            text = ""
        url = core.extract_url(text)
        if url:
            self.ids.url.text = url
            if not self.busy:
                self._set_status("idle", "Link pasted. Press DOWNLOAD NOW.")
        else:
            self._set_status("error", "No link found in the clipboard.")

    def clear_url(self):
        self.ids.url.text = ""

    def reset_status(self):
        if self.busy:
            return
        self.progress = 0
        self.speed_text = "-- /s"
        self.eta_text = "--:--"
        self.size_text = "--"
        self._set_status("idle", "Ready. Paste a link to begin.")

    def _set_status(self, kind, text):
        self.status_kind = kind
        self.status = text

    # -- confirm dialog -----------------------------------------------------------
    def confirm(self, title, message, yes_text, on_yes):
        if self._popup is not None:
            self._popup.dismiss()
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
        label = Body(text=message)
        label.size_hint_y = 1
        box.add_widget(label)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        no_btn = GhostButton(text="CANCEL")
        yes_btn = RedButton(text=yes_text)
        yes_btn.font_size = "13sp"
        row.add_widget(no_btn)
        row.add_widget(yes_btn)
        box.add_widget(row)
        popup = Popup(
            title=title,
            content=box,
            size_hint=(0.88, None),
            height=dp(210),
            background="",
            background_color=(0.09, 0.04, 0.055, 1),
            separator_color=(0.9, 0.09, 0.12, 1),
            title_color=(1, 1, 1, 1),
        )
        no_btn.bind(on_release=lambda *_: popup.dismiss())

        def _yes(*_):
            popup.dismiss()
            on_yes()

        yes_btn.bind(on_release=_yes)
        popup.bind(on_dismiss=lambda *_: setattr(self, "_popup", None))
        self._popup = popup
        popup.open()

    # -- download control -------------------------------------------------------------
    def toggle_download(self):
        if self.busy:
            self.cancel_download()
        else:
            self.start_download()

    def cancel_download(self):
        self._cancel.set()
        self._set_status("busy", "Cancelling...")

    def start_download(self):
        if self.busy:
            return
        if yt_dlp is None:
            self._set_status("error", "yt-dlp is not installed in this build.")
            return
        url = core.extract_url(self.ids.url.text)
        if not url:
            self._set_status("error", "Paste a valid http(s) link first.")
            return
        self.ids.url.text = url
        self.ids.url.focus = False

        self._cancel = threading.Event()
        self.busy = True
        self.progress = 0
        self.speed_text = "-- /s"
        self.eta_text = "--:--"
        self.size_text = "--"
        self._set_status("busy", "Connecting... reading media info.")
        threading.Thread(
            target=self._worker,
            args=(url, self.quality, self.media_type, self._cancel, self._ffmpeg,
                  self.work_dir, self.private_dir),
            daemon=True,
        ).start()

    # -- worker thread (never touch widgets directly in here) ----------------------------
    @staticmethod
    def _ui(fn, *args):
        Clock.schedule_once(lambda dt: fn(*args), 0)

    def _make_hook(self, cancel, state):
        last = [0.0]

        def hook(d):
            if cancel.is_set():
                raise DownloadCancelled("cancelled")
            status = d.get("status")
            info = d.get("info_dict") or {}
            streams = len(info.get("requested_formats") or []) or 1
            if status == "finished":
                state["done"] += 1
                if state["done"] >= streams:
                    self._ui(self._on_processing)
                return
            if status != "downloading":
                return
            now = time.monotonic()
            if now - last[0] < 0.2:
                return
            last[0] = now

            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            frac = None
            if total:
                frac = min(done / float(total), 1.0)
            elif d.get("fragment_count"):
                frac = min((d.get("fragment_index") or 0) / float(d["fragment_count"]), 1.0)
            pct = None
            if frac is not None:
                pct = min((state["done"] + frac) / streams * 100.0, 100.0)
            size = core.human_size(done)
            if total:
                size += " / " + core.human_size(total)
            self._ui(self._on_progress, pct, core.human_speed(d.get("speed")),
                     core.human_eta(d.get("eta")), size)

        return hook

    def _worker(self, url, quality, media_type, cancel, has_ffmpeg, work_dir, private_dir):
        prefix = "cx%d" % int(time.time() * 1000)
        logger = _YDLLogger()
        state = {"done": 0}
        try:
            opts = {
                "outtmpl": os.path.join(work_dir, prefix + "_%(id).50s.%(ext)s"),
                "format": core.format_selector(quality, media_type, has_ffmpeg),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "logger": logger,
                "progress_hooks": [self._make_hook(cancel, state)],
                "cachedir": False,
                "socket_timeout": 30,
                "retries": 5,
                "fragment_retries": 5,
                "extractor_retries": 3,
                "concurrent_fragment_downloads": 4,
                "windowsfilenames": True,
                "continuedl": True,
            }
            if has_ffmpeg:
                if media_type == "audio":
                    opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]
                else:
                    opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            if cancel.is_set():
                raise DownloadCancelled("cancelled")
            if not info:
                raise RuntimeError("No media information returned.")
            if info.get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                if not entries:
                    raise RuntimeError("No downloadable media found at this link.")
                info = entries[0]

            src = self._find_output(info, work_dir, prefix)
            if not src:
                raise RuntimeError("Download finished but the file was not found.")

            self._ui(self._on_saving)
            record = self._store_file(src, info, media_type, private_dir)
            self._ui(self._on_success, record)
        except Exception as exc:  # includes DownloadCancelled
            if cancel.is_set() or isinstance(exc, DownloadCancelled):
                self._cleanup(work_dir, prefix)
                self._ui(self._on_cancelled)
            else:
                msg = core.clean_error(exc)
                if msg == "Unknown error." and logger.messages:
                    msg = core.clean_error(logger.messages[-1])
                if droid.ON_ANDROID and core.is_youtube(url):
                    msg += (" Note: recent YouTube support needs a JavaScript runtime that "
                            "this Android build does not include. Other sites usually work.")
                self._cleanup(work_dir, prefix)
                self._ui(self._on_error, msg)
        else:
            self._cleanup(work_dir, prefix)

    @staticmethod
    def _find_output(info, work_dir, prefix):
        for item in reversed(info.get("requested_downloads") or []):
            path = item.get("filepath") or item.get("_filename")
            if path and os.path.isfile(path):
                return path
        path = info.get("filepath")
        if path and os.path.isfile(path):
            return path
        pattern = glob.escape(os.path.join(work_dir, prefix)) + "_*"
        files = [p for p in glob.glob(pattern)
                 if os.path.isfile(p) and not p.endswith((".part", ".ytdl", ".temp"))]
        return max(files, key=os.path.getmtime) if files else None

    @staticmethod
    def _cleanup(work_dir, prefix):
        try:
            for path in glob.glob(glob.escape(os.path.join(work_dir, prefix)) + "*"):
                try:
                    os.remove(path)
                except OSError:
                    pass
        except Exception:
            pass

    def _store_file(self, src, info, media_type, private_dir):
        title = info.get("title") or "media"
        ext = os.path.splitext(src)[1]
        name = core.safe_filename(title, ext)
        mime = core.guess_mime(name, media_type)
        size = os.path.getsize(src)

        result = droid.export_to_public(src, name, mime)
        record = {
            "id": str(int(time.time() * 1000)),
            "title": title,
            "name": name,
            "mime": mime,
            "size": size,
            "ts": time.time(),
            "kind": media_type,
            "height": int(info.get("height") or 0),
            "uri": "",
            "path": "",
            "private": False,
        }
        if result:
            record["uri"] = result.get("uri", "")
            record["path"] = result.get("path", "")
            try:
                os.remove(src)
            except OSError:
                pass
        else:  # keep the file inside the app so nothing is lost
            os.makedirs(private_dir, exist_ok=True)
            dest = os.path.join(private_dir, name)
            if os.path.exists(dest):
                base, e = os.path.splitext(dest)
                dest = "%s_%d%s" % (base, int(time.time()), e)
            shutil.move(src, dest)
            record["path"] = dest
            record["private"] = True
        return record

    # -- worker -> UI callbacks (main thread) ---------------------------------------------
    def _on_progress(self, pct, speed, eta, size):
        if not self.busy:
            return
        if pct is not None:
            self.progress = pct
            self._set_status("busy", "Downloading... %d%%" % pct)
        else:
            self._set_status("busy", "Downloading...")
        self.speed_text = speed
        self.eta_text = eta
        self.size_text = size

    def _on_processing(self):
        if self.busy:
            self.progress = 100
            self.eta_text = "--:--"
            self._set_status("busy", "Finalizing file...")

    def _on_saving(self):
        if self.busy:
            self._set_status("busy", "Saving to your device...")

    def _end_busy(self):
        self.busy = False
        self._cancel = threading.Event()

    def _on_success(self, record):
        self._end_busy()
        self.progress = 100
        self.speed_text = "-- /s"
        self.eta_text = "done"
        self.size_text = core.human_size(record["size"])
        self.library.insert(0, record)
        self.history.insert(0, {
            "id": record["id"], "title": record["title"], "ts": record["ts"],
            "kind": record["kind"], "height": record["height"], "size": record["size"],
        })
        del self.library[MAX_RECORDS:]
        del self.history[MAX_RECORDS:]
        self._save_state()
        if record["private"]:
            where = "Saved inside the app (could not copy to Downloads)."
        else:
            where = "Saved to " + self.storage_label
        quality = ""
        if record["kind"] == "video" and record["height"]:
            quality = " (%dp)" % record["height"]
        self._set_status("ok", "Download complete%s. %s" % (quality, where))
        self.refresh_downloads()
        self.refresh_history()

    def _on_error(self, message):
        self._end_busy()
        self.speed_text = "-- /s"
        self.eta_text = "--:--"
        self._set_status("error", message)

    def _on_cancelled(self):
        self._end_busy()
        self.progress = 0
        self.speed_text = "-- /s"
        self.eta_text = "--:--"
        self.size_text = "--"
        self._set_status("idle", "Download cancelled.")

    def _save_state(self):
        try:
            core.save_json(os.path.join(self.data_dir, "library.json"), self.library)
            core.save_json(os.path.join(self.data_dir, "history.json"), self.history)
        except OSError:
            pass

    # -- downloads page ----------------------------------------------------------------------
    def _record(self, rid):
        for rec in self.library:
            if rec.get("id") == rid:
                return rec
        return None

    def refresh_downloads(self):
        if not self._ready:
            return
        alive = [r for r in self.library
                 if droid.media_exists(r.get("uri", ""), r.get("path", ""))]
        if len(alive) != len(self.library):  # files deleted outside the app
            self.library = alive
            self._save_state()
        box = self.ids.files_box
        box.clear_widgets()
        if not alive:
            empty = Muted(text="No downloaded files yet.")
            empty.halign = "center"
            box.add_widget(empty)
        for rec in alive:
            title = rec.get("title") or rec.get("name") or "media"
            meta = "%s  |  %s" % (core.human_size(rec.get("size")),
                                  core.human_date(rec.get("ts")))
            if rec.get("private"):
                meta += "  |  app storage"
            box.add_widget(FileRow(
                rid=rec["id"], title=title, meta=meta,
                title_font=core.pick_font(title, FONT_DIRS),
            ))
        self.files_count_text = "%d" % len(alive)

    def open_record(self, rid):
        rec = self._record(rid)
        if not rec:
            return
        ok = droid.open_media(rec.get("uri", ""), rec.get("path", ""), rec.get("mime", ""))
        if ok:
            self.files_msg = ""
        elif rec.get("private"):
            self.files_msg = "Cannot open from app storage. File: " + rec.get("path", "")
        else:
            self.files_msg = "No app found to open this file. Look in " + self.storage_label

    def ask_delete(self, rid):
        rec = self._record(rid)
        if not rec:
            return
        self.confirm(
            "Delete file?",
            "This permanently deletes the file from your device:\n" + (rec.get("name") or ""),
            "DELETE",
            lambda: self._delete_record(rid),
        )

    def _delete_record(self, rid):
        rec = self._record(rid)
        if not rec:
            return
        ok = droid.delete_media(rec.get("uri", ""), rec.get("path", ""))
        if ok:
            self.library = [r for r in self.library if r.get("id") != rid]
            self._save_state()
            self.files_msg = ""
        else:
            self.files_msg = "Could not delete the file."
        self.refresh_downloads()

    # -- history page ------------------------------------------------------------------------
    def refresh_history(self):
        if not self._ready:
            return
        box = self.ids.history_box
        box.clear_widgets()
        if not self.history:
            empty = Muted(text="No downloads yet.")
            empty.halign = "center"
            box.add_widget(empty)
        for item in self.history:
            title = item.get("title") or "media"
            kind = "Audio" if item.get("kind") == "audio" else "Video"
            if kind == "Video" and item.get("height"):
                kind += " %dp" % int(item["height"])
            meta = "%s  |  %s  |  %s" % (kind, core.human_size(item.get("size")),
                                          core.human_date(item.get("ts")))
            box.add_widget(HistoryRow(
                title=title, meta=meta, title_font=core.pick_font(title, FONT_DIRS)))
        self.history_count_text = "%d" % len(self.history)

    def ask_clear_history(self):
        if not self.history:
            return
        self.confirm(
            "Clear history?",
            "The list will be cleared. Your downloaded files are NOT deleted.",
            "CLEAR",
            self._clear_history,
        )

    def _clear_history(self):
        self.history = []
        self._save_state()
        self.refresh_history()

    # -- settings page -------------------------------------------------------------------------
    def refresh_settings(self):
        if not self._ready:
            return
        try:
            engine = ("yt-dlp " + yt_dlp.version.__version__) if yt_dlp else "not installed"
        except Exception:
            engine = "yt-dlp" if yt_dlp else "not installed"
        mode = ("Merge enabled (FFmpeg found)" if self._ffmpeg
                else "Single-file formats (no FFmpeg)")
        rows = [
            ("Theme", "RED ALERT"),
            ("Engine", engine),
            ("Mode", mode),
            ("Save to", self.storage_label),
            ("DRM", "Not bypassed"),
            ("Version", APP_VERSION),
        ]
        card = self.ids.settings_card
        card.clear_widgets()
        for key, value in rows:
            card.add_widget(InfoRow(key=key, value=value))


class CXDownloaderApp(App):
    title = "CX Downloader"
    icon = "icon.png"

    def build(self):
        Window.clearcolor = BG
        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass
        Builder.load_string(KV)
        self.ui = RootUI()
        Window.bind(on_keyboard=self._on_key)
        return self.ui

    def on_start(self):
        droid.request_storage_permission()
        self.ui.setup()

    def on_pause(self):
        return True  # keep the app (and a running download) alive in background

    def on_resume(self):
        self.ui.on_resume()

    def _on_key(self, window, key, *args):
        if key == 27:  # Android back button / Esc
            if self.ui.ids.pages.current != "home":
                self.ui.show_page("home")
                return True
            return False
        return False


if __name__ == "__main__":
    CXDownloaderApp().run()
