"""A joke Blue Screen of Death on every monitor."""

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QGuiApplication, QPainter
from PyQt6.QtWidgets import QWidget

from .config import BSOD_TIMEOUT

BLUE = QColor("#0000AA")
GRAY = QColor("#AAAAAA")
WHITE = QColor("#FFFFFF")

TITLE = " Floppy "
LINES = (
    "*** STOP: 0x00000035 (STATUS_FLOPPY_OVERHEAT)",
    "Floppy (v1.44) has executed an illegal instruction in BRAIN.SYS.",
    "The current thread tried to allocate 2.88 MB on a 1.44 MB disk.",
    "",
    "* Press SPACE to forgive Floppy and continue.",
    "* Press ESC if your boss is approaching.",
)


def _mono_font(pixel_size: int) -> QFont:
    families = QFontDatabase.families()
    family = next((f for f in ("Lucida Console", "Consolas", "Courier New") if f in families), "")
    font = QFont(family)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(pixel_size)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)  # blocky letters, like VGA text mode
    return font


class _Screen(QWidget):
    dismissed = pyqtSignal(bool)  # True = Floppy was forgiven

    def __init__(self, geometry):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setGeometry(geometry)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._cursor_on = True
        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle_cursor)
        self._blink.start(500)

    def _toggle_cursor(self) -> None:
        self._cursor_on = not self._cursor_on
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), BLUE)

        font = _mono_font(max(14, self.height() // 36))
        fm = QFontMetricsF(font)
        p.setFont(font)
        line_h = fm.height() * 1.25
        block_w = max(fm.horizontalAdvance(line) for line in LINES)
        left = (self.width() - block_w) / 2
        top = (self.height() - line_h * (len(LINES) + 3)) / 2

        title_w = fm.horizontalAdvance(TITLE)
        title_rect = QRectF((self.width() - title_w) / 2, top, title_w, fm.height())
        p.fillRect(title_rect, GRAY)
        p.setPen(BLUE)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, TITLE)

        p.setPen(WHITE)
        y = top + line_h * 2
        for line in LINES:
            p.drawText(QPointF(left, y + fm.ascent()), line)
            y += line_h

        if self._cursor_on:
            p.fillRect(QRectF(left, y + fm.ascent() - 2, fm.horizontalAdvance("_"), 3), WHITE)
        p.end()

    def keyPressEvent(self, event) -> None:
        self.dismissed.emit(event.key() != Qt.Key.Key_Escape)

    def mousePressEvent(self, _event) -> None:
        self.dismissed.emit(True)


class Bsod(QObject):
    """Shows the BSOD on every monitor and closes them all at once."""

    finished = pyqtSignal(bool)  # True = forgiven (space, click, timeout), False = Esc

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._screens: list[_Screen] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._close(True))

    @property
    def active(self) -> bool:
        return bool(self._screens)

    def show(self) -> None:
        if self._screens:
            return
        primary = QGuiApplication.primaryScreen()
        for screen in QGuiApplication.screens():
            win = _Screen(screen.geometry())
            win.dismissed.connect(self._close)
            win.show()
            win.raise_()
            if screen is primary:
                win.activateWindow()
                win.setFocus()
            self._screens.append(win)
        self._timer.start(int(BSOD_TIMEOUT * 1000))

    def _close(self, forgiven: bool) -> None:
        if not self._screens:
            return
        self._timer.stop()
        for win in self._screens:
            win.close()
            win.deleteLater()
        self._screens.clear()
        self.finished.emit(forgiven)
