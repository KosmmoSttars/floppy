"""Facial animation: blinking, expression blending, gaze and small idle fidgets."""

import math
import random
from dataclasses import replace

from PyQt6.QtCore import QPointF

from .expressions import EXPRESSIONS, Expression
from .render import Pose

BLINK_DURATION = 0.16
EXPRESSION_SPEED = 10.0     # expression blending speed, 1/s

_SMUG = EXPRESSIONS["smug"]
_SMUG_MIRROR = replace(_SMUG, brow_left=_SMUG.brow_right, brow_right=_SMUG.brow_left)


class Face:
    def __init__(self) -> None:
        self.base = "smug"                 # expression of the current state
        self.eyes_closed = False           # asleep
        self.look: QPointF | None = None   # forced gaze direction
        self.fidgets = True                # glances around and wiggles eyebrows when idle

        self._expression: Expression = EXPRESSIONS[self.base]
        self._override: str | None = None
        self._override_until = 0.0

        self._pupil = QPointF(0, 0)
        self._next_blink = random.uniform(1.5, 4.0)
        self._blink_start = -1.0

        self._next_fidget = random.uniform(4.0, 8.0)
        self._glance: QPointF | None = None
        self._glance_until = 0.0
        self._wiggle_until = 0.0

    def flash(self, name: str, duration: float, now: float) -> None:
        """Briefly show an expression on top of the state's expression."""
        self._override = name
        self._override_until = now + duration

    def update(self, now: float, dt: float, eyes: QPointF, cursor: QPointF, pose: Pose) -> None:
        if self.fidgets:
            self._update_fidgets(now)
        target = self._target_expression(now)
        self._expression = self._expression.blend(target, min(1.0, dt * EXPRESSION_SPEED))
        pose.expression = self._expression
        pose.blink = 1.0 if self.eyes_closed else self._blink(now)
        pose.pupil = self._pupils(now, dt, eyes, cursor)

    def _update_fidgets(self, now: float) -> None:
        if now < self._next_fidget:
            return
        if random.random() < 0.6:
            self._glance = QPointF(random.choice((-2, 2)), random.choice((-1, 0, 1)))
            self._glance_until = now + random.uniform(0.8, 1.5)
        else:
            self._wiggle_until = now + 0.75
        self._next_fidget = now + random.uniform(5.0, 11.0)

    def _target_expression(self, now: float) -> Expression:
        if self._override and now < self._override_until:
            return EXPRESSIONS[self._override]
        self._override = None
        if self.base == "smug" and now < self._wiggle_until:
            return _SMUG_MIRROR if int(now / 0.15) % 2 else _SMUG
        return EXPRESSIONS[self.base]

    def _blink(self, now: float) -> float:
        if self._blink_start < 0 and now >= self._next_blink:
            self._blink_start = now
        if self._blink_start < 0:
            return 0.0
        k = (now - self._blink_start) / BLINK_DURATION
        if k < 1.0:
            return 1.0 - abs(2 * k - 1)
        self._blink_start = -1.0
        # Sometimes blinks twice in a row.
        self._next_blink = now + (0.12 if random.random() < 0.2 else random.uniform(2.5, 6.0))
        return 0.0

    def _pupils(self, now: float, dt: float, eyes: QPointF, cursor: QPointF) -> tuple[int, int]:
        if self.look is not None:
            target = self.look
        elif self._glance is not None and now < self._glance_until:
            target = self._glance
        else:
            self._glance = None
            dx, dy = cursor.x() - eyes.x(), cursor.y() - eyes.y()
            dist = math.hypot(dx, dy)
            if dist < 1:
                target = QPointF(0, 0)
            else:
                reach = 2.0 * min(1.0, dist / 160)
                target = QPointF(dx / dist * reach, dy / dist * reach)
        self._pupil += (target - self._pupil) * min(1.0, dt * 12)
        return round(self._pupil.x()), round(self._pupil.y())
