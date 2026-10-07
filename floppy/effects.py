"""Pixel particles: rage sparks, landing dust and sleepy "Z z z".

Coordinates are relative to the point between the boots, as in render.py.
"""

import random
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath

SPARK_COLORS = (QColor("#FFFF00"), QColor("#FFA500"), QColor("#FF3B00"), QColor("#FFFFFF"))
SPARK_GRAVITY = 260.0
SWEAT_COLOR = QColor("#6FD3FF")
DUST_COLORS = (QColor("#C0C0C0"), QColor("#A8A8A8"), QColor("#E0E0E0"))

Z_GLYPH = ("11111", "00010", "00100", "01000", "11111")
Z_CELLS = frozenset(
    (cx, cy) for cy, row in enumerate(Z_GLYPH) for cx, bit in enumerate(row) if bit == "1"
)
Z_OUTLINE = frozenset(
    {(cx + dx, cy + dy) for cx, cy in Z_CELLS for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    | Z_CELLS
)


@dataclass
class _Particle:
    kind: str
    pos: QPointF
    vel: QPointF
    life: float
    age: float = 0.0
    color: QColor | None = None


class Effects:
    def __init__(self) -> None:
        self._particles: list[_Particle] = []

    @property
    def active(self) -> bool:
        return bool(self._particles)

    @property
    def fast(self) -> bool:
        """Fast particles (sparks, dust, sweat, pixels) need 60 fps; floating "Z"s are fine at 20."""
        return any(part.kind != "z" for part in self._particles)

    def spark(self, x: float, y: float) -> None:
        self._particles.append(_Particle(
            kind="spark",
            pos=QPointF(x, y),
            vel=QPointF(random.uniform(-70, 70), random.uniform(-150, -70)),
            life=random.uniform(0.45, 0.75),
            color=random.choice(SPARK_COLORS),
        ))

    def snore(self, x: float, y: float) -> None:
        self._particles.append(_Particle(
            kind="z",
            pos=QPointF(x, y),
            vel=QPointF(random.uniform(8, 16), -18),
            life=2.4,
        ))

    def dust(self, x: float, y: float, strength: float = 1.0) -> None:
        """Dust puffs from under the boots on landing."""
        for _ in range(int(4 + 6 * strength)):
            side = random.choice((-1, 1))
            self._particles.append(_Particle(
                kind="dust",
                pos=QPointF(x + side * random.uniform(8, 30), y - random.uniform(0, 4)),
                vel=QPointF(side * random.uniform(30, 90) * strength, random.uniform(-25, -5)),
                life=random.uniform(0.35, 0.6),
                color=random.choice(DUST_COLORS),
            ))

    def sweat(self, x: float, y: float, side: int) -> None:
        """A sweat drop flies off his head while he huffs and pushes a window."""
        self._particles.append(_Particle(
            kind="sweat",
            pos=QPointF(x, y),
            vel=QPointF(side * random.uniform(40, 90), random.uniform(-110, -60)),
            life=0.7,
            color=SWEAT_COLOR,
        ))

    def pixels(self, x: float, y: float, count: int) -> None:
        """Pixels of plastic falling off in a panic (drawn in the skin's body color)."""
        for _ in range(count):
            self._particles.append(_Particle(
                kind="pixel",
                pos=QPointF(x + random.uniform(-6, 6), y + random.uniform(-6, 6)),
                vel=QPointF(random.uniform(-90, 90), random.uniform(-160, -40)),
                life=random.uniform(0.6, 0.9),
            ))

    def mist(self, x: float, y: float, color: QColor) -> None:
        """A puff of spray paint from the can's nozzle."""
        self._particles.append(_Particle(
            kind="mist",
            pos=QPointF(x + random.uniform(-2, 2), y + random.uniform(-2, 2)),
            vel=QPointF(random.uniform(-35, 35), random.uniform(-45, 5)),
            life=random.uniform(0.25, 0.45),
            color=color,
        ))

    def update(self, dt: float) -> None:
        alive = []
        for part in self._particles:
            part.age += dt
            if part.age >= part.life:
                continue
            if part.kind in ("spark", "sweat", "pixel"):
                part.vel.setY(part.vel.y() + SPARK_GRAVITY * dt)
            elif part.kind in ("dust", "mist"):
                part.vel *= max(0.0, 1.0 - 4.0 * dt)
            part.pos += part.vel * dt
            alive.append(part)
        self._particles = alive

    def draw(self, p: QPainter, body_color: QColor | None = None) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for part in self._particles:
            k = part.age / part.life
            if part.kind == "spark":
                color = QColor(part.color)
                color.setAlphaF(1.0 - k * k)
                p.setBrush(color)
                p.drawRect(QRectF(round(part.pos.x()), round(part.pos.y()), 3, 3))
            elif part.kind == "pixel":
                x, y = round(part.pos.x()), round(part.pos.y())
                outline = QColor(0, 0, 0)
                outline.setAlphaF(1.0 - k * k)
                fill = QColor(body_color or QColor("#2D2D33"))
                fill.setAlphaF(1.0 - k * k)
                p.setBrush(outline)
                p.drawRect(QRectF(x - 1, y - 1, 5, 5))
                p.setBrush(fill)
                p.drawRect(QRectF(x, y, 3, 3))
            elif part.kind == "sweat":
                color = QColor(part.color)
                color.setAlphaF(1.0 - k)
                p.setBrush(color)
                x, y = round(part.pos.x()), round(part.pos.y())
                p.drawRect(QRectF(x, y, 2, 2))
                p.drawRect(QRectF(x - 1, y + 2, 4, 3))
            elif part.kind == "mist":
                color = QColor(part.color)
                color.setAlphaF(0.8 * (1.0 - k))
                p.setBrush(color)
                size = 2 + round(k * 2)
                p.drawRect(QRectF(round(part.pos.x()), round(part.pos.y()), size, size))
            elif part.kind == "dust":
                color = QColor(part.color)
                color.setAlphaF(0.85 * (1.0 - k))
                p.setBrush(color)
                size = 3 + k * 4
                p.drawRect(QRectF(round(part.pos.x() - size / 2), round(part.pos.y() - size / 2), size, size))
            else:
                self._draw_z(p, part, k)

    @staticmethod
    def _draw_z(p: QPainter, part: _Particle, k: float) -> None:
        cell = 1.5 + k * 1.5          # the letter grows as it floats away
        alpha = 1.0 - max(0.0, k - 0.6) / 0.4
        origin = QPointF(round(part.pos.x()), round(part.pos.y()))
        for cells, color in ((Z_OUTLINE, QColor(0, 0, 0)), (Z_CELLS, QColor(255, 255, 255))):
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            for cx, cy in cells:
                path.addRect(QRectF(origin.x() + cx * cell, origin.y() + cy * cell, cell, cell))
            color.setAlphaF(alpha)
            p.setBrush(color)
            p.drawPath(path)
