"""'Media Player': a Win95 player showing tiny procedural pixel cartoons (no video files needed)."""

import math
import random
from typing import Callable

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .dialogs import BLACK, GRAY, LIGHT, SILVER, WHITE, Win95Window, _bevel
from .sprites import ADVANCE, MINI_PALETTE, draw_sprite, draw_text, mini_floppy_rows, text_width

CANVAS_W, CANVAS_H = 80, 50
SCALE = 4
FPS = 15


def _px(p: QPainter, x: float, y: float, w: float = 1, h: float = 1, color: QColor | str = BLACK) -> None:
    p.fillRect(QRectF(round(x), round(y), w, h), QColor(color))


def _centered_text(p: QPainter, text: str, y: float, color, x_center: float = CANVAS_W / 2) -> None:
    draw_text(p, text, round(x_center - text_width(text) / 2), y, 1, QColor(color))


def _marquee(p: QPainter, text: str, y: float, t: float, color, speed: float = 18) -> None:
    width = text_width(text)
    x = CANVAS_W - (t * speed) % (width + CANVAS_W)
    draw_text(p, text, round(x), y, 1, QColor(color))


# --- the cartoons -------------------------------------------------------------

class Clip:
    name = ""
    duration = 20.0
    music = True

    def draw(self, p: QPainter, t: float) -> None:
        raise NotImplementedError


class FloppyDance(Clip):
    name = "floppy_dance.avi"
    duration = 24.0
    TILES = ("#FF00FF", "#00FFFF", "#FFFF00", "#00FF00")

    def __init__(self, body: QColor):
        self.palette = dict(MINI_PALETTE, B=body)

    def draw(self, p: QPainter, t: float) -> None:
        beat = int(t * 2)
        p.fillRect(QRect(0, 0, CANVAS_W, CANVAS_H), QColor("#1A0033"))
        # Light spots sweeping the walls.
        for k in range(6):
            a = t * 1.3 + k * math.tau / 6
            _px(p, 40 + math.cos(a) * 34, 18 + math.sin(a * 1.7) * 12, 2, 2, self.TILES[k % 4])
        # Disco ball.
        for dy in range(-4, 5):
            half = int(math.sqrt(max(0, 20 - dy * dy)))
            for dx in range(-half, half + 1):
                bright = (dx + dy + int(t * 8)) % 3 == 0
                _px(p, 40 + dx, 6 + dy, 1, 1, "#FFFFFF" if bright else "#9090A0")
        _px(p, 40, 0, 1, 2, "#C0C0C0")
        # Dance floor.
        for j in range(3):
            for i in range(10):
                lit = (i + j + beat) % 4
                color = QColor(self.TILES[lit])
                if (i + j) % 2:
                    color = color.darker(260)
                _px(p, i * 8, 38 + j * 4, 8, 4, color)
        # The star of the show.
        hop = abs(math.sin(t * math.pi * 2)) * 4
        mirror = beat % 2 == 1
        frame = 1 + beat % 2
        rows = mini_floppy_rows(frame, -1 if mirror else 1, happy=beat % 4 == 3)
        draw_sprite(p, rows, 35, 26 - hop, 1, self.palette, mirror)
        if t > self.duration - 3:
            _centered_text(p, "FIN", 14, "#FFFFFF")


class HamsterWheel(Clip):
    name = "hamster_wheel.mpg"
    duration = 20.0
    CENTER = QPointF(40, 24)
    R = 17

    def draw(self, p: QPainter, t: float) -> None:
        p.fillRect(QRect(0, 0, CANVAS_W, CANVAS_H), QColor("#EFE4C8"))
        p.fillRect(QRect(0, 43, CANVAS_W, 7), QColor("#B88A4A"))
        for i in range(0, CANVAS_W, 3):
            _px(p, i + (i * 7) % 2, 43 + (i * 5) % 4, 1, 1, "#8A6030")
        speed = 2.0 + t * 0.55
        angle = speed * t * 0.5
        c, r = self.CENTER, self.R
        # Stand.
        _px(p, c.x() - 1, c.y(), 2, 43 - c.y(), "#606060")
        _px(p, c.x() - 8, 42, 16, 2, "#606060")
        # Spokes and rim.
        for k in range(6):
            a = angle + k * math.tau / 6
            for s in range(2, r):
                _px(p, c.x() + math.cos(a) * s, c.y() + math.sin(a) * s, 1, 1, "#A0A0B0")
        for k in range(90):
            a = k * math.tau / 90
            _px(p, c.x() + math.cos(a) * r, c.y() + math.sin(a) * r, 1, 1, "#404050")
        _px(p, c.x() - 1, c.y() - 1, 3, 3, "#404050")

        fling = 14.0
        if t < fling:
            self._hamster(p, c.x() - 4, c.y() + r - 7, t, speed)
        elif t < fling + 1.6:
            a = math.pi / 2 - (t - fling) * speed * 1.4       # loops around with the wheel
            hx = c.x() + math.cos(a) * (r - 5) - 4
            hy = c.y() + math.sin(a) * (r - 5) - 3
            self._hamster(p, hx, hy, t, speed)
        else:
            k = t - fling - 1.6
            hx = 52 + k * 40
            hy = 4 + k * k * 30 - k * 10
            if hx < CANVAS_W:
                self._hamster(p, hx, hy, t, speed)
            _centered_text(p, "WHEEE!", 2, "#C00000", 22)
        if t > self.duration - 2.5:
            _centered_text(p, "HAMSTER OK", 2, "#000080")

    @staticmethod
    def _hamster(p: QPainter, x: float, y: float, t: float, speed: float) -> None:
        _px(p, x, y + 1, 9, 5, "#E08A2C")
        _px(p, x + 1, y, 6, 1, "#E08A2C")
        _px(p, x + 2, y + 4, 5, 2, "#FFF0D8")
        _px(p, x + 7, y, 2, 1, "#F0A0A0")
        _px(p, x + 7, y + 2, 1, 1, BLACK)
        _px(p, x + 9, y + 3, 1, 1, "#F0A0A0")
        leg = int(t * speed * 3) % 2
        _px(p, x + 1 + leg, y + 6, 1, 1, "#F0A0A0")
        _px(p, x + 6 - leg, y + 6, 1, 1, "#F0A0A0")


class CatKeyboard(Clip):
    name = "cat_on_keyboard.avi"
    duration = 18.0

    def __init__(self) -> None:
        rnd = random.Random(7)
        self.typed = "".join(rnd.choice("ASDFGHJKL;QWERTYUIOP") for _ in range(120))
        self.keys = [(8 + col * 6 + row * 2, 31 + row * 5) for row in range(3) for col in range(10)]
        self.hits = [rnd.randrange(len(self.keys)) for _ in range(400)]

    def draw(self, p: QPainter, t: float) -> None:
        p.fillRect(QRect(0, 0, CANVAS_W, CANVAS_H), QColor("#C8D8E8"))
        # Monitor.
        p.fillRect(QRect(14, 1, 52, 24), QColor("#D8D0B8"))
        p.fillRect(QRect(17, 3, 46, 18), QColor("#002000"))
        if t < self.duration - 4:
            n = int(t * 7)
            line = self.typed[max(0, n - 7):n]
            draw_text(p, line, 19, 6, 1, QColor("#30FF30"))
            if int(t * 3) % 2:
                _px(p, 19 + len(line) * ADVANCE, 6, 4, 7, "#30FF30")
        else:
            draw_text(p, "CAT.EXE", 19, 4, 1, QColor("#FF4040"))
            draw_text(p, "HALTED", 21, 12, 1, QColor("#FF4040"))
        # Keyboard.
        p.fillRect(QRect(5, 29, 70, 17), QColor("#A0A0A0"))
        beat = int(t * 6)
        hit = self.keys[self.hits[beat % len(self.hits)]]
        for k in self.keys:
            _px(p, k[0], k[1], 5, 4, "#FFFFFF" if k == hit else "#E0E0E0")
            _px(p, k[0], k[1] + 3, 5, 1, "#707070")
        # The cat, paws alternating.
        cx = 50 + math.sin(t * 2) * 2
        _px(p, cx, 19, 16, 10, "#F08C20")
        _px(p, cx + 1, 17, 3, 2, "#F08C20")
        _px(p, cx + 12, 17, 3, 2, "#F08C20")
        _px(p, cx + 3, 22, 2, 2, "#108010")
        _px(p, cx + 10, 22, 2, 2, "#108010")
        _px(p, cx + 7, 25, 2, 1, "#FF80A0")
        for i in range(0, 16, 4):
            _px(p, cx + i, 20, 2, 1, "#C06010")
        paw = hit if beat % 2 else (hit[0] + 8, hit[1])
        _px(p, paw[0], paw[1] - 2, 5, 3, "#FFFFFF")
        _px(p, cx + 2 if beat % 2 else cx + 11, 28, 3, 3, "#FFFFFF")


class Buffering(Clip):
    name = "buffering.avi"
    duration = 30.0
    music = False

    def draw(self, p: QPainter, t: float) -> None:
        p.fillRect(QRect(0, 0, CANVAS_W, CANVAS_H), BLACK)
        head = int(t * 10) % 8
        for k in range(8):
            a = k * math.tau / 8 - math.pi / 2
            age = (head - k) % 8
            level = max(40, 255 - age * 45)
            _px(p, 39 + math.cos(a) * 8, 18 + math.sin(a) * 8, 2, 2, QColor(level, level, level))
        if t < 10:
            _centered_text(p, "BUFFERING", 31, "#FFFFFF")
            _centered_text(p, "99%", 40, "#FFFF00")
        else:
            _marquee(p, "THE HAMSTER WHO RUNS THE SERVER IS ON A COFFEE BREAK. PLEASE HOLD. "
                        "YOUR CALL IS IMPORTANT TO US.", 33, t - 10, "#FFFF00")


def make_clips(body: QColor) -> list[Clip]:
    return [FloppyDance(body), HamsterWheel(), CatKeyboard(), Buffering()]


# --- the player window --------------------------------------------------------

def _glyph_icon(kind: str) -> QIcon:
    pm = QPixmap(12, 12)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BLACK)
    if kind == "play":
        p.drawPolygon(QPolygonF([QPointF(3, 1), QPointF(10, 6), QPointF(3, 11)]))
    elif kind == "pause":
        p.drawRect(2, 1, 3, 10)
        p.drawRect(7, 1, 3, 10)
    else:
        p.drawRect(2, 2, 8, 8)
    p.end()
    return QIcon(pm)


class _Screen(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(CANVAS_W * SCALE + 4, CANVAS_H * SCALE + 4)
        self.image = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_RGB32)
        self.image.fill(BLACK)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        _bevel(p, r.adjusted(0, 0, -1, -1), GRAY, WHITE, BLACK, LIGHT)
        p.drawImage(QRect(2, 2, CANVAS_W * SCALE, CANVAS_H * SCALE), self.image)
        p.end()


class _SeekBar(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(16)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        groove = QRect(4, r.height() // 2 - 2, r.width() - 8, 4)
        _bevel(p, groove, GRAY, WHITE, BLACK, LIGHT)
        x = groove.left() + int((groove.width() - 10) * self.value)
        thumb = QRect(x, 1, 10, r.height() - 2)
        p.fillRect(thumb, SILVER)
        _bevel(p, thumb, WHITE, BLACK, LIGHT, GRAY)
        p.end()


class MediaPlayerDialog(Win95Window):
    """Plays one cartoon. music_on/music_off start and stop the background chiptune."""

    def __init__(self, clip: Clip, music_on: Callable[[], None], music_off: Callable[[], None]):
        super().__init__(f"Media Player - {clip.name}")
        self.clip = clip
        self._music_on, self._music_off = music_on, music_off
        self._t = 0.0
        self._playing = False
        self._music = False

        self.screen = _Screen()
        self._seek = _SeekBar()
        self._time = QLabel()
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for kind, slot in (("play", self.play), ("pause", self.pause), ("stop", self.stop)):
            btn = QPushButton()
            btn.setIcon(_glyph_icon(kind))
            btn.setIconSize(QSize(12, 12))
            btn.setStyleSheet("min-width: 24px; padding: 2px 4px;")
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        buttons.addSpacing(8)
        buttons.addWidget(self._time)
        buttons.addStretch()

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addWidget(self.screen)
        lay.addWidget(self._seek)
        lay.addLayout(buttons)
        self.adjustSize()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._render()

    # --- transport --------------------------------------------------------------

    def play(self) -> None:
        if self._t >= self.clip.duration:
            self._t = 0.0
        self._playing = True
        self._timer.start(1000 // FPS)
        self._set_music(self.clip.music)

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()
        self._set_music(False)

    def stop(self) -> None:
        self.pause()
        self._t = 0.0
        self._render()

    def _set_music(self, on: bool) -> None:
        if on != self._music:
            self._music = on
            (self._music_on if on else self._music_off)()

    def _step(self) -> None:
        self._t += 1.0 / FPS
        if self._t >= self.clip.duration:
            self._t = self.clip.duration
            self.pause()
        self._render()

    def _render(self) -> None:
        img = self.screen.image
        p = QPainter(img)
        if self._t >= self.clip.duration:
            p.fillRect(QRect(0, 0, CANVAS_W, CANVAS_H), BLACK)
            _centered_text(p, "THE END", 17, "#FFFFFF")
            _centered_text(p, "REWIND?", 28, "#808080")
        else:
            self.clip.draw(p, self._t)
        p.end()
        self.screen.update()
        self._seek.value = min(1.0, self._t / self.clip.duration)
        self._seek.update()
        total = int(self.clip.duration)
        now = int(self._t)
        self._time.setText(f"{now // 60}:{now % 60:02d} / {total // 60}:{total % 60:02d}")

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self._set_music(False)
        super().closeEvent(event)
