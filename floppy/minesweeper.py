"""Minesweeper that Floppy plays himself, badly. The user can take over at any moment."""

import random
import time

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from .dialogs import BLACK, GRAY, LIGHT, SILVER, WHITE, Win95Window, _bevel

N = 9
MINES = 10
CELL = 16
HEADER = 36
PAD = 6
BOARD_W = 214
BOT_STEP = (0.45, 0.85)        # s between Floppy's moves
NUMBER_COLORS = {
    1: QColor("#0000FF"), 2: QColor("#008000"), 3: QColor("#FF0000"), 4: QColor("#000080"),
    5: QColor("#800000"), 6: QColor("#008080"), 7: QColor("#000000"), 8: QColor("#808080"),
}
SEGMENTS = {   # 7-segment digits: a b c d e f g
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g",
}


def _neighbors(c: int) -> list[int]:
    x, y = c % N, c // N
    return [ny * N + nx for ny in range(y - 1, y + 2) for nx in range(x - 1, x + 2)
            if (nx, ny) != (x, y) and 0 <= nx < N and 0 <= ny < N]


class _Board(QWidget):
    exploded = pyqtSignal(QPointF)     # global position of the mine
    won = pyqtSignal(bool)             # True = Floppy won, False = the user did
    taken_over = pyqtSignal()          # the user clicked while Floppy was playing

    def __init__(self):
        super().__init__()
        self.setFixedSize(BOARD_W, PAD * 3 + HEADER + N * CELL)
        self.setMouseTracking(True)
        self.bot = True
        self._pointer: QPointF | None = None
        self._pointer_from = QPointF(0, 0)
        self._pointer_to = QPointF(0, 0)
        self._pending: tuple[str, int] | None = None
        self._move_t = 0.0
        self._next_move = 0.0
        self._moves = 0
        self._blunder_at = random.randint(5, 11)
        self._pressing = False
        self.reset()

        self._clock = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    # --- game rules -----------------------------------------------------------

    def reset(self) -> None:
        self.mines: set[int] = set()
        self.revealed: set[int] = set()
        self.flags: set[int] = set()
        self.boom: int | None = None
        self.state = "ready"            # ready / playing / lost / won
        self.started = 0.0
        self.elapsed = 0

    def _place_mines(self, safe: int) -> None:
        keep_clear = set(_neighbors(safe)) | {safe}
        spots = [c for c in range(N * N) if c not in keep_clear]
        self.mines = set(random.sample(spots, MINES))
        self.state = "playing"
        self.started = time.monotonic()

    def count(self, c: int) -> int:
        return sum(1 for n in _neighbors(c) if n in self.mines)

    def reveal(self, c: int, by_bot: bool) -> None:
        if self.state in ("lost", "won") or c in self.flags or c in self.revealed:
            return
        if self.state == "ready":
            self._place_mines(c)
        if c in self.mines:
            self.boom = c
            self.state = "lost"
            self.revealed |= self.mines
            center = self.mapToGlobal(self.cell_rect(c).center())
            self.exploded.emit(QPointF(center))
            return
        stack = [c]
        while stack:
            cur = stack.pop()
            if cur in self.revealed or cur in self.flags:
                continue
            self.revealed.add(cur)
            if self.count(cur) == 0:
                stack.extend(n for n in _neighbors(cur) if n not in self.revealed)
        if len(self.revealed) == N * N - MINES:
            self.state = "won"
            self.flags = set(self.mines)
            self.won.emit(by_bot)

    def toggle_flag(self, c: int) -> None:
        if self.state in ("lost", "won") or c in self.revealed:
            return
        self.flags ^= {c}

    # --- Floppy's "strategy" --------------------------------------------------

    def _plan(self) -> tuple[str, int] | None:
        hidden = [c for c in range(N * N) if c not in self.revealed and c not in self.flags]
        if not hidden:
            return None
        if self.state == "ready":
            return "reveal", N * N // 2
        if self._moves >= self._blunder_at:
            risky = [c for c in hidden if c in self.mines]
            if risky:
                return "reveal", random.choice(risky)     # overconfidence
        for c in self.revealed:
            n = self.count(c)
            if n == 0:
                continue
            around = _neighbors(c)
            closed = [x for x in around if x not in self.revealed and x not in self.flags]
            flagged = sum(1 for x in around if x in self.flags)
            if closed and n - flagged == len(closed):
                return "flag", closed[0]
            if closed and n == flagged:
                return "reveal", closed[0]
        return "reveal", random.choice(hidden)          # a wild guess

    def _tick(self) -> None:
        now = time.monotonic()
        dt = now - self._clock
        self._clock = now
        if self.state == "playing":
            self.elapsed = min(999, int(now - self.started))
        if self.bot and self.state in ("ready", "playing"):
            self._bot_step(dt)
        self.update()

    def _bot_step(self, dt: float) -> None:
        if self._pending is None:
            self._next_move -= dt
            if self._next_move > 0:
                return
            self._pending = self._plan()
            if self._pending is None:
                return
            self._pointer_from = QPointF(self._pointer) if self._pointer else QPointF(self.width() / 2, self.height())
            self._pointer_to = QPointF(self.cell_rect(self._pending[1]).center()) + QPointF(1, 2)
            self._move_t = 0.0
            return
        self._move_t += dt
        k = min(1.0, self._move_t / 0.3)
        k = k * k * (3 - 2 * k)
        self._pointer = self._pointer_from + (self._pointer_to - self._pointer_from) * k
        self._pressing = 0.3 < self._move_t < 0.45
        if self._move_t >= 0.45:
            action, c = self._pending
            self._pending = None
            self._pressing = False
            self._moves += 1
            self._next_move = random.uniform(*BOT_STEP)
            if action == "flag":
                self.toggle_flag(c)
            else:
                self.reveal(c, by_bot=True)

    def stop_bot(self) -> None:
        if self.bot:
            self.bot = False
            self._pointer = None
            self._pending = None
            self._pressing = False
            self.taken_over.emit()

    # --- geometry -------------------------------------------------------------

    def grid_rect(self) -> QRect:
        return QRect((BOARD_W - N * CELL) // 2, PAD * 2 + HEADER, N * CELL, N * CELL)

    def cell_rect(self, c: int) -> QRect:
        g = self.grid_rect()
        return QRect(g.left() + (c % N) * CELL, g.top() + (c // N) * CELL, CELL, CELL)

    def smiley_rect(self) -> QRect:
        return QRect(self.width() // 2 - 13, PAD + (HEADER - 26) // 2, 26, 26)

    def cell_at(self, pos: QPointF) -> int | None:
        g = self.grid_rect()
        if not g.contains(pos.toPoint()):
            return None
        return int((pos.y() - g.top()) // CELL) * N + int((pos.x() - g.left()) // CELL)

    # --- the user's hands -------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if self.smiley_rect().contains(pos.toPoint()):
            self.stop_bot()
            self.reset()
            return
        c = self.cell_at(pos)
        if c is None:
            return
        self.stop_bot()
        if event.button() == Qt.MouseButton.RightButton:
            self.toggle_flag(c)
        elif event.button() == Qt.MouseButton.LeftButton:
            self._pressing = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressing and not self.bot:
            self._pressing = False
            c = self.cell_at(event.position())
            if c is not None:
                self.reveal(c, by_bot=False)

    # --- painting -------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), SILVER)
        header = QRect(PAD, PAD, self.width() - 2 * PAD, HEADER)
        _bevel(p, header, GRAY, WHITE, GRAY, WHITE)
        self._draw_counter(p, QPoint(header.left() + 5, header.top() + 6), MINES - len(self.flags))
        self._draw_counter(p, QPoint(header.right() - 5 - 39, header.top() + 6), self.elapsed)
        self._draw_smiley(p)
        g = self.grid_rect()
        _bevel(p, g.adjusted(-3, -3, 2, 2), GRAY, WHITE, GRAY, WHITE)
        for c in range(N * N):
            self._draw_cell(p, c)
        if self._pointer is not None:
            self._draw_pointer(p, self._pointer)
        p.end()

    def _draw_counter(self, p: QPainter, at: QPoint, value: int) -> None:
        box = QRect(at.x(), at.y(), 39, 23)
        p.fillRect(box, BLACK)
        text = f"{value:03d}" if value >= 0 else f"-{abs(value):02d}"
        for i, ch in enumerate(text[-3:]):
            x, y = box.left() + 2 + i * 12, box.top() + 2
            for seg in "abcdefg":
                on = seg in SEGMENTS.get(ch, "")
                p.fillRect(self._segment(seg, x, y), QColor("#FF0000") if on else QColor("#400000"))

    @staticmethod
    def _segment(seg: str, x: int, y: int) -> QRect:
        w, h, t = 9, 19, 2
        return {
            "a": QRect(x + 1, y, w - 2, t), "g": QRect(x + 1, y + h // 2 - 1, w - 2, t),
            "d": QRect(x + 1, y + h - t, w - 2, t), "f": QRect(x, y + 1, t, h // 2 - 1),
            "b": QRect(x + w - t, y + 1, t, h // 2 - 1), "e": QRect(x, y + h // 2 + 1, t, h // 2 - 2),
            "c": QRect(x + w - t, y + h // 2 + 1, t, h // 2 - 2),
        }[seg]

    def _draw_smiley(self, p: QPainter) -> None:
        r = self.smiley_rect()
        p.fillRect(r, SILVER)
        _bevel(p, r, WHITE, GRAY, LIGHT, GRAY)
        face = QRectF(r.left() + 5, r.top() + 5, 16, 16)
        p.setPen(QPen(BLACK, 1))
        p.setBrush(QColor("#FFFF00"))
        p.drawEllipse(face)
        cx, cy = face.center().x(), face.center().y()
        p.setBrush(BLACK)
        if self.state == "lost":
            p.setPen(QPen(BLACK, 1.2))
            for ex in (cx - 4, cx + 3):
                p.drawLine(QPointF(ex - 1.5, cy - 4), QPointF(ex + 1.5, cy - 1))
                p.drawLine(QPointF(ex + 1.5, cy - 4), QPointF(ex - 1.5, cy - 1))
            p.drawArc(QRectF(cx - 4, cy + 2, 8, 6), 0, 180 * 16)
        elif self.state == "won":
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(cx - 7, cy - 4, 14, 2))
            p.drawRect(QRectF(cx - 6, cy - 3, 5, 3))
            p.drawRect(QRectF(cx + 1, cy - 3, 5, 3))
            p.setPen(QPen(BLACK, 1))
            p.drawArc(QRectF(cx - 4, cy - 1, 8, 6), 200 * 16, 140 * 16)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(cx - 4, cy - 3, 2, 2))
            p.drawRect(QRectF(cx + 2, cy - 3, 2, 2))
            if self._pressing:
                p.drawEllipse(QRectF(cx - 2, cy + 1, 4, 4))   # "oh!"
            else:
                p.setPen(QPen(BLACK, 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(QRectF(cx - 4, cy - 1, 8, 6), 200 * 16, 140 * 16)

    def _draw_cell(self, p: QPainter, c: int) -> None:
        r = self.cell_rect(c)
        if c not in self.revealed:
            p.fillRect(r, SILVER)
            _bevel(p, r, WHITE, GRAY, LIGHT, GRAY)
            if c in self.flags:
                self._draw_flag(p, r)
                if self.state == "lost" and c not in self.mines:
                    p.setPen(QPen(QColor("#FF0000"), 1.5))
                    p.drawLine(r.topLeft() + QPoint(3, 3), r.bottomRight() - QPoint(3, 3))
                    p.drawLine(r.topRight() + QPoint(-3, 3), r.bottomLeft() + QPoint(3, -3))
            return
        p.fillRect(r, QColor("#FF0000") if c == self.boom else SILVER)
        p.setPen(GRAY)
        p.drawLine(r.topLeft(), r.topRight())
        p.drawLine(r.topLeft(), r.bottomLeft())
        if c in self.mines:
            if c in self.flags:
                self._draw_flag(p, r)
            else:
                self._draw_mine(p, r)
            return
        n = self.count(c)
        if n:
            font = QFont("MS Sans Serif")
            font.setPixelSize(12)
            font.setBold(True)
            p.setFont(font)
            p.setPen(NUMBER_COLORS[n])
            p.drawText(r.adjusted(1, 1, 0, 0), Qt.AlignmentFlag.AlignCenter, str(n))

    @staticmethod
    def _draw_mine(p: QPainter, r: QRect) -> None:
        c = QPointF(r.center()) + QPointF(0.5, 0.5)
        p.setPen(QPen(BLACK, 1.5))
        p.drawLine(c + QPointF(-6, 0), c + QPointF(6, 0))
        p.drawLine(c + QPointF(0, -6), c + QPointF(0, 6))
        p.drawLine(c + QPointF(-4, -4), c + QPointF(4, 4))
        p.drawLine(c + QPointF(-4, 4), c + QPointF(4, -4))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BLACK)
        p.drawEllipse(c, 4.5, 4.5)
        p.setBrush(WHITE)
        p.drawRect(QRectF(c.x() - 2.5, c.y() - 2.5, 2, 2))

    @staticmethod
    def _draw_flag(p: QPainter, r: QRect) -> None:
        x, y = r.left(), r.top()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FF0000"))
        p.drawPolygon(QPolygonF([QPointF(x + 9, y + 3), QPointF(x + 9, y + 9), QPointF(x + 4, y + 6)]))
        p.setBrush(BLACK)
        p.drawRect(QRectF(x + 8, y + 3, 1.5, 9))
        p.drawRect(QRectF(x + 5, y + 11, 7, 1.5))
        p.drawRect(QRectF(x + 4, y + 12, 9, 1.5))

    @staticmethod
    def _draw_pointer(p: QPainter, at: QPointF) -> None:
        """Floppy's mouse pointer: the classic arrow."""
        shape = [(0, 0), (0, 13), (3, 10), (6, 16), (8, 15), (5, 9), (9, 9)]
        path = QPainterPath()
        path.moveTo(at + QPointF(*shape[0]))
        for x, y in shape[1:]:
            path.lineTo(at + QPointF(x, y))
        path.closeSubpath()
        p.setPen(QPen(BLACK, 1))
        p.setBrush(WHITE)
        p.drawPath(path)


class MinesweeperDialog(Win95Window):
    exploded = pyqtSignal(QPointF)
    won = pyqtSignal(bool)
    taken_over = pyqtSignal()

    def __init__(self):
        super().__init__("Minesweeper: Floppy plays")
        self.board = _Board()
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.board)
        self.board.exploded.connect(self._on_exploded)
        self.board.won.connect(self.won)
        self.board.taken_over.connect(self._on_taken_over)
        self.adjustSize()
        self._shake_left = 0
        self._shake = QTimer(self)
        self._shake.timeout.connect(self._shake_step)
        self._shake_origin = QPointF(0, 0)

    def _on_taken_over(self) -> None:
        self.title = "Minesweeper"
        self.update()
        self.taken_over.emit()

    def _on_exploded(self, where: QPointF) -> None:
        self.exploded.emit(where)
        if not self.dragging:
            self._shake_origin = self.frame_rect().topLeft()
            self._shake_left = 14
            self._shake.start(30)

    def _shake_step(self) -> None:
        self._shake_left -= 1
        if self._shake_left <= 0 or self.dragging:
            self._shake.stop()
            self.place(self._shake_origin)
            return
        amp = self._shake_left * 0.6
        self.place(self._shake_origin + QPointF(random.uniform(-amp, amp), random.uniform(-amp, amp)))
