"""Spray-paint graffiti on the screen. It appears behind Floppy's spray can and can be wiped off with the mouse."""

import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

from . import config as cfg
from .sprites import GLYPH_H, text_cells, text_width

PAINTS = ("#FF2BD6", "#39FF14", "#00E5FF", "#FFE600", "#FF7A00")
PAD = 6
DRIP_MAX = 26
WIPE_RADIUS = 16


class GraffitiWindow(QWidget):
    wiped = pyqtSignal()        # the user scrubbed it all off
    gone = pyqtSignal()         # closed: faded away or wiped

    def __init__(self, text: str, color: QColor, cell: int, left: float, bottom: float):
        """left/bottom: where the lettering starts and where its baseline is, in desktop coordinates."""
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text = text
        self.color = QColor(color)
        self.cell = cell
        self._dark = self.color.darker(330)
        w = text_width(text) * cell
        h = GLYPH_H * cell
        self.setFixedSize(w + 2 * PAD, h + PAD + DRIP_MAX)
        self.move(round(left - PAD), round(bottom - h - PAD))
        self._origin_x = left

        cells = text_cells(text)
        self._cells = set(cells)
        self._revealed: set[tuple[int, int]] = set()
        self._erased: set[tuple[int, int]] = set()
        # Drips run down from some cells that have nothing below them.
        bottoms = [c for c in cells if (c[0], c[1] + 1) not in self._cells]
        self._drips = {c: random.uniform(6, DRIP_MAX - 4) for c in random.sample(bottoms, len(bottoms) // 5)}
        self._drip_start: dict[tuple[int, int], float] = {}
        self._speckles = {c: [(random.randrange(cell), random.randrange(cell)) for _ in range(2)] for c in cells}
        self._lo = self._hi = None
        self._age = 0.0
        self._alpha = 1.0
        self._painting = True

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)

    # --- painting by Floppy ---------------------------------------------------

    def spray_at(self, x: float) -> None:
        """The nozzle is at desktop x: everything it has passed over gets paint."""
        self._lo = x if self._lo is None else min(self._lo, x)
        self._hi = x if self._hi is None else max(self._hi, x)
        new = {c for c in self._cells - self._revealed
               if self._lo <= self._origin_x + (c[0] + 0.5) * self.cell <= self._hi}
        if new:
            for c in new:
                if c in self._drips:
                    self._drip_start[c] = self._age
            self._revealed |= new
            self.update()

    def stop_painting(self) -> None:
        self._painting = False
        if not self._revealed:
            self.close()
        elif self._revealed <= self._erased:
            self.wiped.emit()   # scrubbed off while he was still painting
            self.close()

    # --- life cycle -------------------------------------------------------------

    def _tick(self) -> None:
        self._age += 0.1
        fade_at = cfg.GRAFFITI_LIFETIME
        if self._age > fade_at:
            self._alpha = max(0.0, 1.0 - (self._age - fade_at) / cfg.GRAFFITI_FADE)
            if self._alpha <= 0.0:
                self.close()
                return
            self.update()
        elif any(self._age - start < 3.0 for start in self._drip_start.values()):
            self.update()   # drips are still running

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.gone.emit()
        super().closeEvent(event)

    # --- wiping with the mouse ---------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._wipe(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._wipe(event.position())

    def _wipe(self, pos: QPointF) -> None:
        c = self.cell
        hit = {
            cell for cell in self._revealed - self._erased
            if (PAD + (cell[0] + 0.5) * c - pos.x()) ** 2 + (PAD + (cell[1] + 0.5) * c - pos.y()) ** 2
            < WIPE_RADIUS ** 2
        }
        if not hit:
            return
        self._erased |= hit
        self.update()
        if not self._painting and self._revealed <= self._erased:
            self.wiped.emit()
            self.close()

    # --- drawing ----------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        visible = self._revealed - self._erased
        if not visible:
            return
        p = QPainter(self)
        p.setOpacity(self._alpha)
        c = self.cell

        def rect(cell, grow=0.0) -> QRectF:
            return QRectF(PAD + cell[0] * c - grow, PAD + cell[1] * c - grow, c + 2 * grow, c + 2 * grow)

        outline = QPainterPath()
        outline.setFillRule(Qt.FillRule.WindingFill)
        fill = QPainterPath()
        fill.setFillRule(Qt.FillRule.WindingFill)
        for cell in visible:
            outline.addRect(rect(cell, 2))
            fill.addRect(rect(cell))
            if cell in self._drip_start:
                k = min(1.0, (self._age - self._drip_start[cell]) / 3.0)
                length = self._drips[cell] * k
                drip = QRectF(PAD + cell[0] * c + c * 0.3, PAD + (cell[1] + 1) * c, c * 0.4, length)
                fill.addRect(drip)
                outline.addRect(drip.adjusted(-1.5, 0, 1.5, 1.5))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._dark)
        p.drawPath(outline.simplified())
        p.setBrush(self.color)
        p.drawPath(fill.simplified())
        # Speckles of over-spray and a highlight on top of each stroke.
        light = QColor(255, 255, 255, 150)
        for cell in visible:
            for sx, sy in self._speckles[cell]:
                p.fillRect(QRectF(PAD + cell[0] * c + sx, PAD + cell[1] * c + sy, 1.5, 1.5), light)
            if (cell[0], cell[1] - 1) not in visible:
                p.fillRect(QRectF(PAD + cell[0] * c + 1, PAD + cell[1] * c + 1, c - 2, 1.5), light)
        p.end()
