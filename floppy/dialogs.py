"""Windows 95 style windows: an error with a runaway button and a fake progress bar."""

import random

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

SILVER = QColor("#C0C0C0")
LIGHT = QColor("#DFDFDF")
WHITE = QColor("#FFFFFF")
GRAY = QColor("#808080")
BLACK = QColor("#000000")
NAVY = QColor("#000080")

TITLE_H = 18
FRAME = 4

BUTTON_QSS = """
QPushButton {
    background: #C0C0C0;
    color: #000000;
    font-family: "MS Sans Serif", "Tahoma";
    font-size: 8pt;
    border-style: solid;
    border-width: 2px;
    border-top-color: #FFFFFF;
    border-left-color: #FFFFFF;
    border-right-color: #000000;
    border-bottom-color: #000000;
    padding: 3px 10px;
    min-width: 62px;
    min-height: 16px;
}
QPushButton:pressed {
    border-top-color: #000000;
    border-left-color: #000000;
    border-right-color: #FFFFFF;
    border-bottom-color: #FFFFFF;
    padding: 4px 9px 2px 11px;
}
QLabel {
    color: #000000;
    font-family: "MS Sans Serif", "Tahoma";
    font-size: 8pt;
}
"""


def _ui_font(bold: bool = False, size: int = 8) -> QFont:
    font = QFont("MS Sans Serif")
    font.setPointSize(size)
    font.setBold(bold)
    return font


def icon_pixmap(kind: str) -> QPixmap:
    """Win95 icons: red cross, yellow triangle, blue "i"."""
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setPen(QPen(BLACK, 1))
    if kind == "error":
        p.setBrush(QColor("#FF0000"))
        p.drawEllipse(QRect(2, 2, 27, 27))
        p.setPen(QPen(WHITE, 4))
        p.drawLine(10, 10, 21, 21)
        p.drawLine(21, 10, 10, 21)
    elif kind == "warning":
        p.setBrush(QColor("#FFFF00"))
        p.drawPolygon(QPolygonF([QPointF(15.5, 2), QPointF(29, 28), QPointF(2, 28)]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BLACK)
        p.drawRect(14, 10, 4, 10)
        p.drawRect(14, 22, 4, 3)
    else:
        p.setBrush(WHITE)
        p.drawEllipse(QRect(2, 2, 27, 27))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0000FF"))
        p.drawRect(14, 7, 4, 4)
        p.drawRect(14, 13, 4, 12)
        p.drawRect(12, 13, 2, 2)
        p.drawRect(12, 23, 8, 2)
    p.end()
    return pm


def _bevel(p: QPainter, r: QRect, outer_light: QColor, outer_dark: QColor,
           inner_light: QColor, inner_dark: QColor) -> None:
    """Double Win95 bevel around rect r (inclusive)."""
    for (tl, br), inset in (((outer_light, outer_dark), 0), ((inner_light, inner_dark), 1)):
        x0, y0, x1, y1 = r.left() + inset, r.top() + inset, r.right() - inset, r.bottom() - inset
        p.setPen(tl)
        p.drawLine(x0, y0, x1 - 1, y0)
        p.drawLine(x0, y0, x0, y1 - 1)
        p.setPen(br)
        p.drawLine(x0, y1, x1, y1)
        p.drawLine(x1, y0, x1, y1)


class _CloseButton(QAbstractButton):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(16, 14)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def sizeHint(self) -> QSize:
        return QSize(16, 14)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, SILVER)
        down = self.isDown()
        if down:
            _bevel(p, r, BLACK, WHITE, GRAY, LIGHT)
        else:
            _bevel(p, r, LIGHT, BLACK, WHITE, GRAY)
        # Pixel X glyph.
        o = 1 if down else 0
        p.setPen(BLACK)
        for i in range(6):
            for dx in (0, 1):
                p.drawPoint(4 + i + dx + o, 3 + i + o)
                p.drawPoint(9 - i + dx + o, 3 + i + o)
        p.end()


class Win95Window(QWidget):
    """Frameless window drawn like a Windows 95 window. Dragged by its title bar."""

    closed_by_x = pyqtSignal()
    drag_started = pyqtSignal()
    drag_moved = pyqtSignal(QPointF)
    drag_finished = pyqtSignal()

    def __init__(self, title: str, mini: bool = False):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setStyleSheet(BUTTON_QSS)
        self.title = title
        self.mini = mini
        # Replaced by the prank manager: this is how Floppy resists dragging.
        self.resist = lambda delta: delta

        self._drag_last: QPointF | None = None
        self._fpos = QPointF(0, 0)

        self.body = QWidget(self)
        self.body.setMouseTracking(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(FRAME, FRAME + TITLE_H + 2, FRAME, FRAME)
        outer.addWidget(self.body)

        self._close = _CloseButton(self)
        self._close.clicked.connect(self._on_close_clicked)

    # --- sub-pixel position: both the mouse and Floppy move the window ------

    def place(self, pos: QPointF) -> None:
        self._fpos = QPointF(pos)
        self.move(round(pos.x()), round(pos.y()))

    def nudge(self, dx: float, dy: float = 0.0) -> None:
        self.place(self._fpos + QPointF(dx, dy))

    def frame_rect(self) -> QRectF:
        return QRectF(self._fpos, QPointF(self._fpos.x() + self.width(), self._fpos.y() + self.height()))

    @property
    def dragging(self) -> bool:
        return self._drag_last is not None

    # --- painting -----------------------------------------------------------

    def resizeEvent(self, _event) -> None:
        self._close.move(self.width() - FRAME - 16 - 2, FRAME + 2)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, SILVER)
        _bevel(p, r.adjusted(0, 0, -1, -1), LIGHT, BLACK, WHITE, GRAY)
        title = QRect(FRAME - 1, FRAME - 1, self.width() - 2 * FRAME + 2, TITLE_H)
        p.fillRect(title, NAVY)
        p.setFont(_ui_font(bold=True, size=7 if self.mini else 8))
        p.setPen(WHITE)
        p.drawText(title.adjusted(5, 0, -22, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.title)
        p.end()

    def _on_close_clicked(self) -> None:
        self.closed_by_x.emit()
        self.close()

    # --- dragging by the title bar ------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < FRAME + TITLE_H:
            self._drag_last = event.globalPosition()
            self.drag_started.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_last is None:
            self.hover(event.position())
            return
        delta = event.globalPosition() - self._drag_last
        self._drag_last = event.globalPosition()
        delta = self.resist(delta)
        self.nudge(delta.x(), delta.y())
        self.drag_moved.emit(delta)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_last is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_last = None
            self.drag_finished.emit()

    def hover(self, pos: QPointF) -> None:
        """The cursor is moving over the window (not over a button)."""


class ErrorDialog(Win95Window):
    """Error message. runaway is the label of the button that runs away from the cursor."""

    button_clicked = pyqtSignal(str)

    ESCAPE_DISTANCE = 26
    MAX_ESCAPES = 7

    def __init__(self, title: str, message: str, icon: str, buttons: list[str],
                 runaway: str | None = None, mini: bool = False):
        super().__init__(title, mini)
        self._runaway_label = runaway
        self._escapes = 0

        content = QHBoxLayout()
        content.setSpacing(12)
        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap(icon))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        text = QLabel(message)
        text.setWordWrap(True)
        text.setFixedWidth(150 if mini else 250)
        if mini:
            text.setStyleSheet("font-size: 7pt;")
        content.addWidget(icon_label)
        content.addWidget(text)
        content.addStretch(1)  # in a wide window the text stays next to the icon

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addStretch()
        self._buttons: list[QPushButton] = []
        for label in buttons:
            btn = QPushButton(label)
            btn.setMouseTracking(True)
            btn.installEventFilter(self)
            btn.clicked.connect(lambda _=False, b=btn: self._on_button(b))
            row.addWidget(btn)
            self._buttons.append(btn)
        row.addStretch()

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(10, 10, 10, 6)
        lay.setSpacing(12)
        lay.addLayout(content)
        lay.addLayout(row)

        # Equal widths, like Win95, so labels still fit after the runaway button swaps them.
        # Measured after insertion into the window: only then is the Win95 style applied.
        for btn in self._buttons:
            btn.ensurePolished()
        width = max(b.sizeHint().width() for b in self._buttons) + 4
        for btn in self._buttons:
            btn.setFixedWidth(width)
        self.adjustSize()

    def _on_button(self, btn: QPushButton) -> None:
        self.button_clicked.emit(btn.text())
        self.close()

    def _runaway_button(self) -> QPushButton | None:
        if self._runaway_label is None or self._escapes >= self.MAX_ESCAPES:
            return None
        return next((b for b in self._buttons if b.text() == self._runaway_label), None)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Enter and obj is self._runaway_button():
            self._escape(obj)
        return False

    def hover(self, pos: QPointF) -> None:
        btn = self._runaway_button()
        if btn is None:
            return
        rect = QRectF(btn.geometry()).translated(QPointF(self.body.pos()))
        dx = max(rect.left() - pos.x(), 0, pos.x() - rect.right())
        dy = max(rect.top() - pos.y(), 0, pos.y() - rect.bottom())
        if (dx * dx + dy * dy) ** 0.5 < self.ESCAPE_DISTANCE:
            self._escape(btn)

    def _escape(self, btn: QPushButton) -> None:
        """The button swaps labels with a neighbor ("Panic"), so the cursor is no longer on it."""
        others = [b for b in self._buttons if b is not btn]
        if not others:
            return
        other = random.choice(others)
        text = btn.text()
        btn.setText(other.text())
        other.setText(text)
        self._escapes += 1


class _ProgressBar(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(20)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, SILVER)
        _bevel(p, r.adjusted(0, 0, -1, -1), GRAY, WHITE, BLACK, LIGHT)
        inner = r.adjusted(3, 3, -3, -3)
        filled = int(inner.width() * self.value / 100)
        x = inner.left()
        while x + 8 <= inner.left() + filled:
            p.fillRect(QRect(x, inner.top(), 8, inner.height()), NAVY)
            x += 10
        p.end()


class ProgressDialog(Win95Window):
    """'Removing gravity...': reaches 99%, hangs, then turns out to be a joke."""

    finished_joke = pyqtSignal()
    button_clicked = pyqtSignal(str)

    def __init__(self, title: str, task: str, punchline: str):
        super().__init__(title)
        self._punchline = punchline
        self._t = 0.0

        self._label = QLabel(task)
        self._label.setWordWrap(True)
        self._label.setFixedWidth(280)
        self._bar = _ProgressBar()
        self._percent = QLabel("0%")
        self._ok = QPushButton("OK")
        self._ok.hide()
        self._ok.clicked.connect(lambda: (self.button_clicked.emit("OK"), self.close()))

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(8)
        lay.addWidget(self._label)
        lay.addWidget(self._bar)
        lay.addWidget(self._percent)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._ok)
        row.addStretch()
        lay.addLayout(row)
        self.adjustSize()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self) -> None:
        self._t += 0.05
        t = self._t
        if t < 2.6:
            value = 99 * (1 - (1 - t / 2.6) ** 2)   # speeds along briskly...
        elif t < 4.6:
            value = 99                               # ...then hangs at 99% for good
        else:
            value = 100
        self._bar.value = value
        self._percent.setText(f"{int(value)}%")
        self._bar.update()
        if value >= 100:
            self._timer.stop()
            self._label.setText(self._punchline)
            self._ok.show()
            self.adjustSize()
            self.finished_joke.emit()
