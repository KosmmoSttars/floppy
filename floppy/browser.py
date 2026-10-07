"""Real YouTube for the video prank: opens a NEW window of the default browser and hands it to Floppy.

Only the window this prank opened is ever moved; the user's own browser windows are left alone.
If the default browser is unknown (so a new window can't be guaranteed), the prank falls back
to Floppy's own Media Player.
"""

import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSizeF

from . import win32

CHROMIUM = {"chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "launcher.exe", "vivaldi.exe",
            "browser.exe", "chromium.exe", "yandex.exe"}
FIREFOX = {"firefox.exe", "librewolf.exe", "waterfox.exe", "floorp.exe"}
FIND_TIMEOUT = 8.0          # then Floppy brings his own Media Player instead
MOVED_TOLERANCE = 8        # physical px: farther than this from where we put it = the user moved it


def default_browser() -> tuple[str, str] | None:
    """(executable, new-window flag) of the default browser, if it's one we know."""
    if not win32.IS_WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as key:
            prog_id = winreg.QueryValueEx(key, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + r"\shell\open\command") as key:
            command = str(winreg.QueryValueEx(key, "")[0]).strip()
    except OSError:
        return None
    if command.startswith('"'):
        exe = command[1:command.find('"', 1)]
    else:
        exe = command.split(" ")[0]
    name = Path(exe).name.lower()
    if not Path(exe).exists():
        return None
    if name in CHROMIUM:
        return exe, "--new-window"
    if name in FIREFOX:
        return exe, "-new-window"
    return None


class BrowserVideo:
    """A haul target: a fresh browser window with a video in it."""

    def __init__(self, url: str, size: QSizeF):
        info = default_browser()
        if info is None:
            raise RuntimeError("unknown default browser")
        exe, flag = info
        self._name = Path(exe).name.lower()
        self._folder = str(Path(exe).parent).lower()
        self._size = size
        self._before = set(win32.top_level_windows())
        self.hwnd: int | None = None
        self._placed: tuple[int, int, int, int] | None = None
        self._next_poll = 0.0
        subprocess.Popen([exe, flag, url], close_fds=True)
        self._started = time.monotonic()

    # --- finding the new window ---------------------------------------------------

    def _poll(self) -> None:
        now = time.monotonic()
        if self.hwnd is not None or now < self._next_poll:
            return
        self._next_poll = now + 0.15
        for hwnd in win32.top_level_windows():
            if hwnd in self._before:
                continue
            path = win32.process_path(hwnd).lower()
            if path and (Path(path).name == self._name or str(Path(path).parent) == self._folder):
                self.hwnd = hwnd
                win32.restore_window(hwnd)
                return

    @property
    def ready(self) -> bool:
        self._poll()
        return self.hwnd is not None

    @property
    def failed(self) -> bool:
        return self.hwnd is None and time.monotonic() - self._started > FIND_TIMEOUT

    # --- the haul target interface ----------------------------------------------------

    def size(self) -> QSizeF:
        return self._size

    def alive(self) -> bool:
        return self.hwnd is not None and win32.window_exists(self.hwnd)

    def place(self, left: float, top: float, ref: QPointF) -> None:
        frame = QRectF(QPointF(left, top), self._size)
        self._placed = win32.place_frame(self.hwnd, frame, ref)

    def moved_by_user(self) -> bool:
        if self._placed is None:
            return False
        now = win32.window_rect_physical(self.hwnd)
        if now is None:
            return True
        return any(abs(a - b) > MOVED_TOLERANCE for a, b in zip(now, self._placed))

    def show(self) -> None:
        pass   # it is a real window: already visible

    def start(self) -> None:
        pass   # YouTube autoplays

    def cancel(self) -> None:
        pass   # never close a browser window behind the user's back
