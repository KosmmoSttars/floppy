"""'Defragmenting Drive A:': a tiny Floppy runs around the disk map and carries the blocks by hand."""

import math
import random

from PyQt6.QtCore import QPointF, QRect, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .dialogs import BLACK, GRAY, LIGHT, WHITE, Win95Window, _bevel, _ProgressBar
from .sprites import MINI_H, MINI_PALETTE, MINI_W, draw_sprite, mini_floppy_rows

COLS, ROWS = 22, 8
CELL = 15
WORKER_SCALE = 2
FREE, USED, DONE, BAD = 0, 1, 2, 3
COLORS = {
    FREE: QColor("#FFFFFF"),
    USED: QColor("#00A8F0"),     # fragmented data
    DONE: QColor("#0000A8"),     # optimized data
    BAD: QColor("#E00000"),
}
READ = QColor("#00E000")         # the block he's holding
TRIP_SLOW, TRIP_FAST = 0.7, 0.22  # seconds per trip: he gets the hang of it
FPS = 30


class _DiskMap(QWidget):
    """The cluster map with the little worker on top of it."""

    def __init__(self, body_color: QColor):
        super().__init__()
        self.setFixedSize(COLS * CELL + 4, ROWS * CELL + 4)
        self._palette = dict(MINI_PALETTE, B=body_color)
        self.cells: list[int] = []
        self.worker = QPointF(0, 0)      # mini Floppy's feet, in cell units
        self.carrying: int | None = None
        self.frame = 0
        self.happy = False
        self.hop = 0.0
        self.flying: list[tuple[QPointF, QPointF, int]] = []
        self.fly_k = 0.0
        self.scramble()

    def scramble(self) -> None:
        n = COLS * ROWS
        self.cells = [USED if random.random() < 0.42 else FREE for _ in range(n)]
        for i in random.sample(range(n), 4):
            self.cells[i] = BAD

    def cell_center(self, i: int) -> QPointF:
        return QPointF(i % COLS + 0.5, i // COLS + 0.5)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, WHITE)
        _bevel(p, r.adjusted(0, 0, -1, -1), GRAY, WHITE, BLACK, LIGHT)
        for i, state in enumerate(self.cells):
            x, y = 2 + (i % COLS) * CELL, 2 + (i // COLS) * CELL
            cell = QRect(x + 1, y + 1, CELL - 2, CELL - 2)
            p.fillRect(cell, COLORS[state])
            if state != FREE:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1))
                p.drawLine(cell.topLeft(), cell.topRight())
            if state == BAD:
                p.setPen(QPen(WHITE, 1.5))
                p.drawLine(cell.topLeft() + QPointF(2, 2).toPoint(), cell.bottomRight() - QPointF(2, 2).toPoint())
                p.drawLine(cell.topRight() + QPointF(-2, 2).toPoint(), cell.bottomLeft() + QPointF(2, -2).toPoint())
        # Blocks flying around after the sneeze.
        for start, end, state in self.flying:
            k = self.fly_k
            pos = start + (end - start) * k - QPointF(0, math.sin(k * math.pi) * 3)
            p.fillRect(QRectF(2 + pos.x() * CELL - CELL / 2 + 1, 2 + pos.y() * CELL - CELL / 2 + 1,
                              CELL - 2, CELL - 2), COLORS[state])
        # The worker: feet at the bottom of his current cell.
        scale = WORKER_SCALE
        x = 2 + self.worker.x() * CELL - MINI_W * scale / 2
        y = 2 + self.worker.y() * CELL + CELL / 2 - MINI_H * scale - self.hop
        rows = mini_floppy_rows(self.frame, 1, self.happy)
        draw_sprite(p, rows, round(x), round(y), scale, self._palette)
        if self.carrying is not None:
            block = QRectF(round(x) + (MINI_W * scale - CELL + 2) / 2, round(y) - CELL + 1, CELL - 2, CELL - 2)
            p.fillRect(block, READ)
            p.setPen(QPen(BLACK, 1))
            p.drawRect(block)
        p.end()


class DefragDialog(Win95Window):
    finished_joke = pyqtSignal()       # 100%: Floppy is proud
    oops = pyqtSignal()                # ...and then he sneezes
    button_clicked = pyqtSignal(str)

    def __init__(self, body_color: QColor):
        super().__init__("Defragmenting Drive A:")
        self.map = _DiskMap(body_color)
        self._status = QLabel()
        self._status.setFixedWidth(self.map.width())
        self._hint_width = self.map.width()
        self._bar = _ProgressBar()
        self._hint = QLabel()
        self._hint.setStyleSheet("color: #000080;")
        self._hint.setFixedWidth(self.map.width())

        self._stop = QPushButton("Stop")
        self._pause = QPushButton("Pause")
        self._stop.clicked.connect(self._on_stop)
        self._pause.clicked.connect(self._on_pause)

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        lay.addWidget(self.map)
        lay.addWidget(self._status)
        lay.addWidget(self._bar)
        lay.addWidget(self._hint)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._stop)
        row.addWidget(self._pause)
        row.addStretch()
        lay.addLayout(row)
        self.adjustSize()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._restart()
        self.adjustSize()
        self._timer.start(1000 // FPS)

    # --- the job ------------------------------------------------------------

    def _restart(self) -> None:
        m = self.map
        m.happy = False
        m.carrying = None
        m.flying = []
        self._paused = False
        self._phase = "plan"
        self._t = 0.0
        self._trips = 0
        self._cursor = 0
        self._trip: tuple[QPointF, QPointF, float] | None = None
        self._total = sum(1 for c in m.cells if c == USED)
        self._stop.setText("Stop")
        self._pause.setText("Pause")
        self._pause.show()
        self._hint.setText("Floppy is moving your files by hand.")
        self._update_status()

    def _progress(self) -> float:
        done = sum(1 for c in self.map.cells if c == DONE)
        return 100.0 * done / max(1, self._total)

    def _update_status(self) -> None:
        value = self._progress()
        self._bar.value = value
        self._bar.update()
        self._status.setText(f"Drive A: {int(value)}% complete")

    def _next_job(self) -> tuple[int, int] | None:
        """Moves blocks into the first free slots from the end of the disk: (from, to)."""
        cells = self.map.cells
        while self._cursor < len(cells):
            i = self._cursor
            if cells[i] == USED:
                cells[i] = DONE                 # already in place
                self._cursor += 1
            elif cells[i] in (DONE, BAD):
                self._cursor += 1
            else:
                for j in range(len(cells) - 1, i, -1):
                    if cells[j] == USED:
                        return j, i
                return None
        return None

    def _walk(self, dt: float, start: QPointF, end: QPointF, duration: float) -> bool:
        m = self.map
        self._t += dt
        k = min(1.0, self._t / duration)
        m.worker = start + (end - start) * k
        m.frame = 1 + int(self._t * 12) % 2 if k < 1.0 else 0
        return k >= 1.0

    def _step(self) -> None:
        dt = 1.0 / FPS
        if self._paused:
            return
        m = self.map
        if self._phase == "plan":
            job = self._next_job()
            if job is None:
                self._finish()
            else:
                src, dst = job
                speed = TRIP_SLOW - (TRIP_SLOW - TRIP_FAST) * min(1.0, self._trips / 25)
                self._trip = (QPointF(m.worker), m.cell_center(src), speed)
                self._dst = dst
                self._src = src
                self._t = 0.0
                self._phase = "fetch"
        elif self._phase == "fetch":
            start, end, speed = self._trip
            if self._walk(dt, start, end, speed):
                m.cells[self._src] = FREE
                m.carrying = USED
                self._trip = (QPointF(m.worker), m.cell_center(self._dst), speed)
                self._t = 0.0
                self._phase = "carry"
        elif self._phase == "carry":
            start, end, speed = self._trip
            if self._walk(dt, start, end, speed):
                m.cells[self._dst] = DONE
                m.carrying = None
                self._trips += 1
                self._cursor = self._dst + 1
                self._phase = "plan"
                self._update_status()
        elif self._phase == "proud":
            self._t += dt
            m.hop = abs(math.sin(self._t * 9)) * 4 if self._t < 1.4 else 0.0
            if self._t > 2.2:
                self._phase = "sneeze"
                self._t = 0.0
                m.happy = False
                self._hint.setText("Ah... ah...")
        elif self._phase == "sneeze":
            self._t += dt
            if self._t > 1.0:
                self._hint.setText("ACHOO!")
                self._scatter()
        elif self._phase == "scatter":
            self._t += dt
            m.fly_k = min(1.0, self._t / 0.8)
            if m.fly_k >= 1.0:
                for _start, end, state in m.flying:
                    m.cells[int(end.y()) * COLS + int(end.x())] = state
                m.flying = []
                self._phase = "oops"
                self._status.setText("Drive A: fragmented again. Oops.")
                self._hint.setText("Floppy is very sorry. Floppy is not sorry.")
                self._stop.setText("OK")
                self._pause.setText("Again!")
                self._pause.show()
                self.oops.emit()
        m.update()

    def _finish(self) -> None:
        self._phase = "proud"
        self._t = 0.0
        self.map.happy = True
        self.map.frame = 0
        self._bar.value = 100
        self._bar.update()
        self._status.setText("Defragmentation complete. Drive A: is now 0.0001% faster.")
        self._hint.setText("You're welcome.")
        self._pause.hide()
        self.finished_joke.emit()

    def _scatter(self) -> None:
        m = self.map
        blocks = [(i, c) for i, c in enumerate(m.cells) if c == DONE]
        free = [i for i, c in enumerate(m.cells) if c != BAD]
        targets = random.sample(free, len(blocks))
        m.flying = []
        for (i, _c), j in zip(blocks, targets):
            m.cells[i] = FREE
            m.flying.append((m.cell_center(i), m.cell_center(j), USED))
        for j in targets:
            m.cells[j] = FREE
        m.fly_k = 0.0
        self._phase = "scatter"
        self._t = 0.0

    # --- buttons --------------------------------------------------------------

    def _on_stop(self) -> None:
        self.button_clicked.emit("Stop" if self._phase not in ("oops", "proud", "sneeze") else "OK")
        self.close()

    def _on_pause(self) -> None:
        if self._phase == "oops":
            self._restart()
            return
        self._paused = not self._paused
        self._pause.setText("Resume" if self._paused else "Pause")
        self._hint.setText("Floppy is having a snack." if self._paused
                           else "Floppy is moving your files by hand.")
