"""Win32 API wrappers via ctypes.

Win32 works in physical pixels while Qt works in logical ones (scaled per monitor).
ScreenMap converts between them.
"""

import ctypes
import os
import sys
import time
from ctypes import wintypes

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QGuiApplication

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _dwmapi = ctypes.windll.dwmapi
    _user32.WindowFromPoint.argtypes = [wintypes.POINT]
    _user32.WindowFromPoint.restype = wintypes.HWND
    _user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetAncestor.restype = wintypes.HWND
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = wintypes.HMONITOR

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GA_ROOT = 2
MONITOR_DEFAULTTONEAREST = 2

# The desktop, taskbar, Start menu and other system surfaces are not platforms.
_SYSTEM_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow", "NotifyIconOverflowWindow",
}

_OWN_PID = os.getpid()


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


if IS_WINDOWS:
    _user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MONITORINFOEX)]


def get_idle_seconds() -> float:
    """Seconds since the user last touched the mouse or keyboard."""
    if not IS_WINDOWS:
        return 0.0
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not _user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    millis = (_kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
    return millis / 1000.0


# --- coordinates ------------------------------------------------------------

class ScreenMap:
    """Maps physical monitor rectangles to Qt screens."""

    REFRESH = 2.0

    def __init__(self) -> None:
        self._entries: list[tuple[tuple[int, int, int, int], object]] = []
        self._stamp = -1e9

    def _refresh(self) -> None:
        if time.monotonic() - self._stamp < self.REFRESH:
            return
        self._stamp = time.monotonic()
        native: dict[str, tuple[int, int, int, int]] = {}

        def callback(hmon, _hdc, _rect, _lparam):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(_MONITORINFOEX)
            if _user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcMonitor
                native[info.szDevice] = (r.left, r.top, r.right, r.bottom)
            return 1

        proto = ctypes.WINFUNCTYPE(
            ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
        )
        _user32.EnumDisplayMonitors(None, None, proto(callback), 0)
        self._entries = [
            (native[s.name()], s) for s in QGuiApplication.screens() if s.name() in native
        ]

    def to_logical(self, x: float, y: float) -> QPointF:
        self._refresh()
        for (left, top, right, bottom), screen in self._entries:
            if left <= x < right and top <= y < bottom:
                g, dpr = screen.geometry(), screen.devicePixelRatio()
                return QPointF(g.left() + (x - left) / dpr, g.top() + (y - top) / dpr)
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        return QPointF(x / dpr, y / dpr)

    def to_physical_via(self, p: QPointF, ref: QPointF) -> tuple[int, int]:
        """Like to_physical, but always through the monitor containing `ref`, extrapolating past its edges.

        Used for windows that hang partly off-screen: both corners map consistently.
        """
        self._refresh()
        for (left, top, _r, _b), screen in self._entries:
            g = screen.geometry()
            if g.left() <= ref.x() < g.left() + g.width() and g.top() <= ref.y() < g.top() + g.height():
                dpr = screen.devicePixelRatio()
                return round(left + (p.x() - g.left()) * dpr), round(top + (p.y() - g.top()) * dpr)
        return self.to_physical(p)

    def to_physical(self, p: QPointF) -> tuple[int, int]:
        self._refresh()
        for (left, top, _r, _b), screen in self._entries:
            g = screen.geometry()
            if g.left() <= p.x() < g.left() + g.width() and g.top() <= p.y() < g.top() + g.height():
                dpr = screen.devicePixelRatio()
                return round(left + (p.x() - g.left()) * dpr), round(top + (p.y() - g.top()) * dpr)
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        return round(p.x() * dpr), round(p.y() * dpr)


SCREENS = ScreenMap()


# --- windows ----------------------------------------------------------------

def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(128)
    _user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _cloaked(hwnd: int) -> bool:
    value = wintypes.DWORD()
    res = _dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
    )
    return res == 0 and value.value != 0


def window_alive(hwnd: int) -> bool:
    """The window exists, is visible on screen and is not minimized."""
    if not IS_WINDOWS or not hwnd:
        return False
    return bool(
        _user32.IsWindow(hwnd)
        and _user32.IsWindowVisible(hwnd)
        and not _user32.IsIconic(hwnd)
        and not _cloaked(hwnd)
    )


def window_frame(hwnd: int) -> QRectF | None:
    """Visible window frame in Qt logical coordinates.

    On Windows 10 GetWindowRect includes invisible DWM borders (~7 px),
    so DWMWA_EXTENDED_FRAME_BOUNDS is used instead.
    """
    rect = wintypes.RECT()
    res = _dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
    )
    if res != 0 and not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    tl = SCREENS.to_logical(rect.left, rect.top)
    br = SCREENS.to_logical(rect.right, rect.bottom)
    return QRectF(tl, br)


def foreground_window() -> int | None:
    """The user's active window, if Floppy can jump onto it."""
    if not IS_WINDOWS:
        return None
    hwnd = _user32.GetForegroundWindow()
    if not hwnd or not window_alive(hwnd):
        return None
    if _pid(hwnd) == _OWN_PID or _class_name(hwnd) in _SYSTEM_CLASSES:
        return None
    return hwnd


def top_edge_clear(hwnd: int, x: float, y: float) -> bool:
    """The window's top edge at (x, y) is not covered by another window."""
    px, py = SCREENS.to_physical(QPointF(x, y + 6))  # just below the edge, inside the title bar
    hit = _user32.WindowFromPoint(wintypes.POINT(px, py))
    if not hit:
        return False
    root = _user32.GetAncestor(hit, GA_ROOT)
    return root == hwnd or _pid(root) == _OWN_PID


def foreground_fullscreen() -> bool:
    """A non-system window covers its whole monitor (a game, a video, a presentation)."""
    if not IS_WINDOWS:
        return False
    hwnd = _user32.GetForegroundWindow()
    if not hwnd or _pid(hwnd) == _OWN_PID or _class_name(hwnd) in _SYSTEM_CLASSES:
        return False
    rect = wintypes.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    info = _MONITORINFOEX()
    info.cbSize = ctypes.sizeof(_MONITORINFOEX)
    monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor or not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    m = info.rcMonitor
    return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom


# --- moving other programs' windows (the YouTube prank) -----------------------

SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

if IS_WINDOWS:
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                     ctypes.POINTER(wintypes.DWORD)]


def top_level_windows() -> list[int]:
    """Visible, titled top-level windows of other processes."""
    if not IS_WINDOWS:
        return []
    found: list[int] = []

    def callback(hwnd, _lparam):
        if _user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd) > 0 and _pid(hwnd) != _OWN_PID:
            found.append(hwnd)
        return 1

    proto = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows(proto(callback), 0)
    return found


def process_path(hwnd: int) -> str:
    """Full path of the executable that owns the window ('' if unknown)."""
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, _pid(hwnd))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        _kernel32.CloseHandle(handle)


def window_exists(hwnd: int) -> bool:
    """Still open and not minimized (it may be off-screen)."""
    return bool(IS_WINDOWS and hwnd and _user32.IsWindow(hwnd) and _user32.IsWindowVisible(hwnd)
                and not _user32.IsIconic(hwnd))


def restore_window(hwnd: int) -> None:
    """Un-maximizes a window so it can be moved and resized."""
    if _user32.IsZoomed(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)


def window_rect_physical(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wintypes.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def place_frame(hwnd: int, frame: QRectF, ref: QPointF) -> tuple[int, int, int, int] | None:
    """Moves a window so its visible frame covers `frame` (logical px, may hang off-screen).

    `ref` is a point on the monitor whose scale is used. Returns the physical window rect set.
    """
    outer = window_rect_physical(hwnd)
    visible = wintypes.RECT()
    res = _dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(visible), ctypes.sizeof(visible)
    )
    if outer is None:
        return None
    if res == 0:
        ml, mt = visible.left - outer[0], visible.top - outer[1]
        mr, mb = outer[2] - visible.right, outer[3] - visible.bottom
    else:
        ml = mt = mr = mb = 0
    left, top = SCREENS.to_physical_via(frame.topLeft(), ref)
    right, bottom = SCREENS.to_physical_via(frame.bottomRight(), ref)
    x, y = left - ml, top - mt
    w, h = right - left + ml + mr, bottom - top + mt + mb
    _user32.SetWindowPos(hwnd, None, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE)
    return x, y, x + w, y + h
