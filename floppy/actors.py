"""Windows for the clone show's extras: the copy of Floppy and the Recycle Bin."""

import math
from typing import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .render import BODY_CENTER, BODY_W, BOOT, LEG_H, draw_floppy
from .skins import Skin
from .stunts import BIN_RIM, Puppet, RecycleBin

BLACK = QColor("#000000")
WHITE = QColor("#FFFFFF")

_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


class CloneWindow(QWidget):
    """Draws the puppet exactly like Floppy, plus the shortcut arrow every copy deserves."""

    WIN_W, WIN_H = 240, 275
    FEET = QPointF(120, 228)

    def __init__(self, skin: Skin, on_click: Callable[[], None]):
        super().__init__(None, _FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.WIN_W, self.WIN_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skin = skin
        self._on_click = on_click
        self.puppet: Puppet | None = None

    def sync(self, puppet: Puppet) -> None:
        self.puppet = puppet
        self.move(round(puppet.x - self.FEET.x()), round(puppet.y - self.FEET.y()))
        if not self.isVisible():
            self.show()
        self.update()

    def paintEvent(self, _event) -> None:
        c = self.puppet
        if c is None:
            return
        p = QPainter(self)
        p.translate(self.FEET + c.shake)
        if c.visible:
            draw_floppy(p, self.skin, c.pose)
            p.save()
            if abs(c.pose.tilt) > 0.1:
                p.translate(BODY_CENTER)
                p.rotate(c.pose.tilt)
                p.translate(-BODY_CENTER)
            _draw_shortcut_arrow(p, QPointF(-BODY_W / 2 + 3, -LEG_H - 19 + round(c.pose.sit * 7)))
            p.restore()
        c.effects.draw(p, self.skin.body)
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()


def _draw_shortcut_arrow(p: QPainter, at: QPointF) -> None:
    """The little white box with a curved black arrow from Windows shortcut icons."""
    box = QRectF(at.x(), at.y(), 15, 15)
    p.setPen(QPen(BLACK, 1.2))
    p.setBrush(WHITE)
    p.drawRect(box)
    arrow = QPainterPath(QPointF(box.left() + 3.5, box.bottom() - 2.5))
    arrow.cubicTo(QPointF(box.left() + 3.5, box.top() + 6), QPointF(box.left() + 6, box.top() + 5),
                  QPointF(box.right() - 5, box.top() + 5))
    pen = QPen(BLACK, 2.2)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(arrow)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BLACK)
    tip = QPointF(box.right() - 2, box.top() + 5)
    p.drawPolygon(QPolygonF([tip, tip + QPointF(-5, -3.5), tip + QPointF(-5, 3.5)]))


class BinWindow(QWidget):
    """A Windows 95 style wire wastebasket. When full, a pair of boots kicks out of it."""

    W, H = 110, 120
    BASE = QPointF(55, 116)    # bottom center of the basket inside the window

    def __init__(self, body: QColor):
        super().__init__(None, _FLAGS | Qt.WindowType.WindowTransparentForInput)
        self.body = QColor(body)
        self.body.setAlpha(255)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(self.W, self.H)
        self.bin: RecycleBin | None = None
        self._t = 0.0

    def sync(self, b: RecycleBin, now: float) -> None:
        self.bin = b
        self._t = now
        shake = math.sin(now * 55) * 2.5 if b.shake > 0 else 0.0
        self.move(round(b.x - self.BASE.x() + shake), round(b.y - self.BASE.y()))
        if not self.isVisible():
            self.show()
        self.update()

    def paintEvent(self, _event) -> None:
        b = self.bin
        if b is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.translate(self.BASE)
        top_w, bottom_w, h = 54.0, 40.0, float(BIN_RIM)

        if b.full:
            self._draw_boots(p, h)

        basket = QPolygonF([QPointF(-top_w / 2, -h), QPointF(top_w / 2, -h),
                            QPointF(bottom_w / 2, 0), QPointF(-bottom_w / 2, 0)])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#C0C0C0"))
        p.drawPolygon(basket)
        # Wire mesh: slats and bands, darker on the right like a Win95 icon.
        p.setPen(QPen(QColor("#808080"), 1.4))
        for i in range(1, 8):
            k = i / 8
            p.drawLine(QPointF(-top_w / 2 + top_w * k, -h + 4), QPointF(-bottom_w / 2 + bottom_w * k, -2))
        for y in (-h * 0.66, -h * 0.33):
            half = bottom_w / 2 + (top_w - bottom_w) / 2 * (-y / h)
            p.drawLine(QPointF(-half, y), QPointF(half, y))
        p.setPen(QPen(WHITE, 2))
        p.drawLine(QPointF(-top_w / 2 + 3, -h + 4), QPointF(-bottom_w / 2 + 3, -3))
        p.setPen(QPen(BLACK, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(basket)
        # Rim.
        rim = QRectF(-top_w / 2 - 3, -h - 5, top_w + 6, 7)
        p.setBrush(QColor("#A8A8A8"))
        p.drawRect(rim)
        p.setPen(QPen(QColor("#404040"), 1.2))
        p.drawLine(QPointF(rim.left() + 3, rim.bottom() - 2), QPointF(rim.right() - 3, rim.bottom() - 2))
        p.end()

    def _draw_boots(self, p: QPainter, h: float) -> None:
        """Upside-down Floppy inside: legs and red boots sticking out of the top, kicking."""
        for side in (-1, 1):
            kick = math.sin(self._t * 14 + side) * 4
            x = side * 12
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(BLACK)
            p.drawRect(QRectF(x - 1.75, -h - 16 - kick, 3.5, 16 + kick))
            boot = QRectF(x - 7 - side * 2, -h - 24 - kick, 14, 8)
            path = QPainterPath()
            path.addRoundedRect(boot, 3.5, 3.5)
            p.setBrush(BOOT)
            p.drawPath(path)
            p.setBrush(WHITE)
            p.drawRect(QRectF(boot.left(), boot.top(), boot.width(), 2.4))   # soles face up
            p.setPen(QPen(BLACK, 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        # The bottom edge of the floppy body peeks out between the boots.
        p.setPen(QPen(BLACK, 1.6))
        p.setBrush(self.body)
        p.drawRect(QRectF(-22, -h - 4, 44, 6))
