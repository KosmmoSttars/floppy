"""Floppy's state machine and physics. Knows nothing about Qt windows: takes a world, returns a pose.

Position (x, y) is the point between the boots in logical desktop coordinates.
Floppy stands on a support: the floor (top of the taskbar, key=0) or a window's top edge (key=hwnd).
"""

import math
import random
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol

from PyQt6.QtCore import QPointF, QRectF

from . import config as cfg
from .config import ChaosLevel
from .effects import Effects
from .face import Face
from .render import BODY_W, EYES_CENTER, TOTAL_H, Pose
from .speech import LINES, READ_PER_CHAR, READ_TIME, TYPE_SPEED
from .stunts import CloneShow, Haul, Spray, Stunt

BREATH_PERIOD = 3.2
SLEEP_BREATH_PERIOD = 5.0
CLACK_DURATION = 0.35
STEP_LENGTH = 7.0           # px traveled per half step
HALF_W = BODY_W / 2

FLOOR_EDGE = 50             # keeps at least this far from the screen edge
WINDOW_EDGE = 28            # and from a window edge


class State(Enum):
    IDLE = "idle"
    WALK = "walk"
    RAGE = "rage"
    BSOD = "bsod"
    SLEEP = "sleep"
    MISCHIEF = "mischief"   # hops and pulls a prank
    DIZZY = "dizzy"         # head spinning after throws and shaking
    JUMP = "jump"           # crouching before a jump
    AIR = "air"             # flying: a jump, a throw or simply dropped
    FALL = "fall"           # gliding on the parachute
    DRAG = "drag"           # held by the user's mouse
    PUSH = "push"           # pushing back on an error window the user is dragging
    SNEAK = "sneak"         # tiptoes towards a frozen cursor
    SCARED = "scared"       # the cursor came alive: panics, spins his wheels, runs away
    STUNT = "stunt"         # a long prank in person: hauling a window, graffiti, the clone


GROUNDED = {
    State.IDLE, State.WALK, State.RAGE, State.BSOD, State.SLEEP,
    State.MISCHIEF, State.DIZZY, State.JUMP, State.SNEAK, State.SCARED, State.STUNT,
}

WINDOW_PRANKS = {"error", "progress", "defrag", "mines"}   # a hop and a window pops up
BUSY = {State.BSOD, State.DRAG, State.PUSH, State.SLEEP, State.STUNT}


@dataclass
class Surface:
    key: int          # 0 = floor, otherwise the window's hwnd
    left: float
    right: float
    y: float


@dataclass
class World:
    floor: Surface                  # top of the taskbar on Floppy's screen
    platform: Surface | None        # top of the active window, if he can stand on it
    support: Surface | None         # supporting window; None = closed or minimized
    bounds: QRectF                  # walls for flight: the whole virtual desktop
    cursor: QPointF
    user_idle: float                # seconds without mouse or keyboard input
    is_clear: Callable[[Surface, float], bool]  # whether a window edge is uncovered at x
    fullscreen: bool = False        # a fullscreen app is in front: no pranks


class TugTarget(Protocol):
    """A window the user is dragging and Floppy refuses to give up."""

    @property
    def active(self) -> bool: ...
    @property
    def released(self) -> bool: ...
    def rect(self) -> QRectF: ...


@dataclass
class Speech:
    text: str
    start: float

    @property
    def typing_time(self) -> float:
        return len(self.text) / TYPE_SPEED

    @property
    def end(self) -> float:
        return self.start + self.typing_time + READ_TIME + READ_PER_CHAR * len(self.text)


def _is_night() -> bool:
    return datetime.now().hour in cfg.NIGHT_HOURS


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _norm_angle(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


class Floppy:
    def __init__(self, x: float, y: float, chaos: ChaosLevel):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.support = 0
        self.chaos = chaos
        self.pose = Pose()
        self.face = Face()
        self.effects = Effects()
        self.state = State.IDLE
        self.shake = QPointF(0, 0)
        self.speech: Speech | None = None
        self.on_bsod: Callable[[], None] = lambda: None
        self.on_prank: Callable[[str], None] = lambda kind: None
        self.on_sound: Callable[..., None] = lambda name, gain=1.0: None

        self._now = 0.0
        self._world: World | None = None
        self._anger = 0.0
        self._rage_warned = False
        self._last_click = -10.0
        self._clack_start = -1.0
        self._state_shutter = 0.0
        self._support_left = 0.0
        self._last_say = -10.0
        self._walk_speed = cfg.WALK_SPEED

        # Cursor stillness: SNEAK starts once it hasn't moved for a while.
        self._cursor_anchor: QPointF | None = None
        self._cursor_still_since = 0.0
        self._sneak_anchor = QPointF(0, 0)
        self._sneak_start = 0.0
        self._sneak_cooldown_until = 0.0
        self._next_look = 0.0
        self._scared_start = 0.0
        self._scared_from = 0.0
        self._snore_count = 0

        self._walk_target = x
        self._walk_then: Callable[[], None] | None = None
        self._walk_phase = 0.0

        self._jump_v = (0.0, 0.0)
        self._jump_at = 0.0
        self._air_reason = ""
        self._bounces = 0
        self._spin = 0.0
        self._fall_start = 0.0

        # The user's hands: grabbing, shaking, throwing and grudges.
        self._grab_offset = QPointF(0, 0)
        self._drag_samples: deque[tuple[float, QPointF]] = deque()
        self._drag_start = 0.0
        self._drag_vx = 0.0
        self._still_since = 0.0
        self._held_said = False
        self._shake_dir = 0
        self._reversals: deque[float] = deque()
        self._dizziness = 0.0
        self._dizzy_until = 0.0
        self._throws: deque[float] = deque()
        self._last_revenge = -1e9
        self.total_throws = 0

        self._tug: TugTarget | None = None
        self.tug_side = 1
        self._push_start = 0.0

        self._mischief_start = 0.0
        self._mischief_kind = ""
        self._mischief_done = False

        self.stunt: Stunt | None = None
        self.arms_target = 0.0
        self.enabled_pranks: set[str] = set(cfg.PRANKS)
        self._pending_prank: str | None = None
        self._watch: QPointF | None = None
        self._watch_until = 0.0

        self._sleep_until = math.inf
        self._sleep_reason = ""
        self._next_z = 0.0
        self._next_walk = math.inf
        self._next_nap = math.inf
        self._next_prank = math.inf

        self._schedule_nap()
        self._schedule_prank()
        self._enter_idle()

    @property
    def asleep(self) -> bool:
        return self.state is State.SLEEP

    @property
    def airborne(self) -> bool:
        return self.state not in GROUNDED

    @property
    def throw_count(self) -> int:
        return self.total_throws

    # --- speech -------------------------------------------------------------

    def say(self, key: str, chance: float = 1.0, force: bool = False) -> None:
        if not force and (self._now - self._last_say < cfg.SPEECH_COOLDOWN or random.random() > chance):
            return
        self.speech = Speech(random.choice(LINES[key]), self._now)
        self._last_say = self._now

    def visible_speech(self) -> tuple[str, int] | None:
        """The text and how many characters have been "typed" so far."""
        s = self.speech
        if s is None:
            return None
        return s.text, min(len(s.text), int((self._now - s.start) * TYPE_SPEED) + 1)

    def react(self, key: str, expression: str) -> None:
        """Reaction to the user's choice in a prank: a line and an expression."""
        self.say(key, force=True)
        self.face.flash(expression, 1.5, self._now)

    def laugh(self) -> None:
        self.face.flash("happy", 1.5, self._now)
        self._clack_start = self._now

    def forgive_throws(self) -> None:
        self._throws.clear()

    # --- external commands --------------------------------------------------

    def click(self, now: float) -> None:
        if self.state is State.BSOD or self.airborne:
            return
        if self.state is State.SLEEP:
            self.wake(startled=True)
            return

        self._anger = min(1.0, self._anger + cfg.RAGE_PER_CLICK)
        self._last_click = now
        self._clack_start = now
        self.on_sound("clack", 0.6)
        if self.state is not State.RAGE:
            self._stop_walking()
            self.state = State.RAGE
            self._rage_warned = False
            self.face.base = "angry"
            self.face.fidgets = False
        if self._anger >= 0.6 and not self._rage_warned:
            self._rage_warned = True
            self.say("rage_warn", force=True)
        if self._anger >= 1.0 - 1e-6:
            self.trigger_bsod()

    def grab(self, now: float, cursor: QPointF) -> bool:
        """The user grabbed Floppy. Returns False if that isn't allowed right now."""
        if self.state is State.BSOD:
            return False
        caught = self.state in (State.AIR, State.FALL)
        self._stop_walking()
        self._pending_prank = None
        self._anger = 0.0
        self.state = State.DRAG
        self.support = 0
        self.vx = self.vy = self._spin = 0.0
        self._grab_offset = cursor - QPointF(self.x, self.y)
        self._drag_samples = deque([(now, QPointF(cursor))])
        self._drag_start = self._still_since = now
        self._drag_vx = 0.0
        self._held_said = False
        self._shake_dir = 0
        self._reversals.clear()
        self.face.eyes_closed = False
        self.face.base = "scared"
        self.face.fidgets = False
        self.face.look = None
        self.say("caught" if caught else "grab", chance=0.8 if caught else 0.6, force=caught)
        return True

    def release(self, now: float) -> None:
        """Released: thrown with the mouse velocity over the last ~0.1 s."""
        if self.state is not State.DRAG:
            return
        samples = self._drag_samples
        velocity = QPointF(0, 0)
        if len(samples) >= 2 and samples[-1][0] > samples[0][0]:
            (t0, p0), (t1, p1) = samples[0], samples[-1]
            velocity = (p1 - p0) / (t1 - t0)
        speed = math.hypot(velocity.x(), velocity.y())
        if speed > cfg.MAX_THROW_SPEED:
            velocity *= cfg.MAX_THROW_SPEED / speed
            speed = cfg.MAX_THROW_SPEED

        height = self._world.floor.y - self.y if self._world else 0.0
        if speed < cfg.THROW_MIN_SPEED and height > cfg.DROP_CHUTE_HEIGHT:
            self._start_fall()
            self.say("chute", chance=0.5)
        elif speed >= cfg.THROW_MIN_SPEED:
            self._throws.append(now)
            self.total_throws += 1
            self._launch(velocity.x(), velocity.y(), "throw")
            if speed > 900:
                self.say("throw", chance=0.6, force=True)
        else:
            self._launch(velocity.x(), velocity.y(), "drop")

    def perform(self, kind: str | None = None) -> None:
        """'Put on a show' from the menu: a given prank, or a random prank or BSOD."""
        if self.state in (State.BSOD, State.DRAG, State.PUSH, State.STUNT) or self.airborne:
            return
        if self.state is State.SLEEP:
            self.wake()
        if kind == "bsod" or (kind is None and random.random() < cfg.PERFORMANCE_BSOD_CHANCE):
            self.trigger_bsod()
            return
        kind = kind or self._random_prank(anywhere=True)
        if kind is None or (kind not in WINDOW_PRANKS and self.stunt is not None):
            return  # the previous stunt is still clearing up
        if cfg.PRANKS[kind][2] and self.support:
            self._pending_prank = kind      # floor-only prank: hop down first
            self._jump_down()
            return
        self._start_prank(kind)

    def look_at(self, point: QPointF, duration: float) -> None:
        """Keeps an eye on something (a game he is playing, a video he brought) while idle."""
        self._watch = QPointF(point)
        self._watch_until = self._now + duration

    def blast(self, source: QPointF) -> None:
        """A mine went off at `source`: throws him away from it, spinning."""
        if self.state in (State.BSOD, State.DRAG) or self.airborne:
            return
        dist = math.hypot(source.x() - self.x, source.y() - (self.y - TOTAL_H / 2))
        if dist > cfg.BLAST_RADIUS:
            self.face.flash("scared", 1.2, self._now)
            self.say("blast_far", force=True)
            return
        if self.state is State.SLEEP:
            self.face.eyes_closed = False
        power = 1.0 - 0.5 * dist / cfg.BLAST_RADIUS
        direction = 1 if self.x >= source.x() else -1
        self._launch(direction * random.uniform(420, 700) * power, -random.uniform(950, 1250) * power, "blast")
        self._spin = direction * 820
        self._dizziness = cfg.DIZZY_THRESHOLD
        self.effects.pixels(0, -TOTAL_H / 2, 8)
        self.say("blast", force=True)

    # --- stunts (driven by stunts.py, set up by the window side) ---------------

    def _can_stunt(self) -> bool:
        return (self._world is not None and self.stunt is None and self.state not in BUSY
                and not self.airborne and self.support == 0)

    def _start_stunt(self, stunt: Stunt) -> Stunt:
        self._stop_walking()
        self._anger = 0.0
        self.state = State.STUNT
        self.stunt = stunt
        self.face.fidgets = False
        self.face.eyes_closed = False
        return stunt

    def start_haul(self) -> Haul | None:
        """Goes to the screen edge to drag a window in from behind it."""
        if not self._can_stunt():
            return None
        w = self._world
        lo, hi = self._bounds()
        left_open = w.floor.left <= w.bounds.left() + 1     # a real edge, not another monitor
        right_open = w.floor.right >= w.bounds.right() - 1
        if left_open != right_open:
            side = -1 if left_open else 1
        else:
            side = -1 if self.x - lo < hi - self.x else 1
        return self._start_stunt(Haul(self, side, lo if side < 0 else hi))

    def spray_room(self) -> float:
        """How wide a graffiti fits on the floor he stands on."""
        lo, hi = self._bounds()
        return max(0.0, hi - lo - 140)

    def start_spray(self, width: float, color) -> Spray | None:
        """Paints graffiti `width` px wide on the wall near him."""
        if not self._can_stunt():
            return None
        lo, hi = self._bounds()
        lo, hi = lo + 70, hi - 70
        width = min(width, hi - lo)
        left = _clamp(self.x - width / 2, lo, hi - width)
        right = left + width
        direction = 1 if abs(self.x - left) < abs(self.x - right) else -1
        return self._start_stunt(Spray(self, left, right, direction, color))

    def _start_clone(self) -> None:
        if not self._can_stunt():
            return
        lo, hi = self._bounds()
        side = 1 if hi - self.x > self.x - lo else -1
        self._start_stunt(CloneShow(self, side))

    # Small helpers the stunts use to move his body.

    def floor_span(self) -> tuple[float, float]:
        return self._bounds()

    def step_towards(self, target: float, speed: float, dt: float) -> bool:
        """Walks towards x = target with stepping legs. Returns True once there."""
        dist = target - self.x
        step = speed * dt
        if abs(dist) <= step:
            self.x = target
            self.pose.step = 0.0
            return True
        self.x += math.copysign(step, dist)
        self._walk_phase += step / STEP_LENGTH * math.pi / 2
        self.pose.step = math.sin(self._walk_phase)
        self.pose.lift = round(abs(math.sin(self._walk_phase)) * 2)
        self.shutter_at_least(0.08 * abs(math.sin(self._walk_phase * 2)))  # the shutter rattles
        return False

    def shutter_at_least(self, amount: float) -> None:
        self._state_shutter = max(self._state_shutter, amount)

    def clack(self) -> None:
        self._clack_start = self._now

    def sleep(self, duration: float = cfg.MANUAL_SLEEP) -> None:
        if self.state is State.BSOD or self.airborne:
            return
        self._anger = 0.0
        self._go_sleep(duration, "manual")

    def wake(self, startled: bool = False) -> None:
        if self.state is not State.SLEEP:
            return
        self.face.eyes_closed = False
        if startled:
            self.face.flash("scared", 0.8, self._now)
            self.say("wake", chance=0.7)
        self._schedule_nap()
        self._enter_idle()

    def trigger_bsod(self) -> None:
        if self.state is State.BSOD or self.airborne:
            return
        self._stop_walking()
        self.state = State.BSOD
        self._anger = 0.0
        self.speech = None
        self.face.eyes_closed = False
        self.face.base = "happy"
        self.on_sound("bsod")
        self.on_bsod()

    def bsod_finished(self, forgiven: bool) -> None:
        self._enter_idle()
        self.face.flash("happy" if forgiven else "neutral", 2.5, self._now)
        self.say("forgiven" if forgiven else "boss", force=True)

    def set_chaos(self, level: ChaosLevel) -> None:
        self.chaos = level
        self._schedule_nap()
        self._schedule_prank()
        if self.state is State.IDLE:
            self._schedule_walk()
        elif self.state is State.SLEEP and self._sleep_reason == "lazy" and level.percent > 0:
            self.wake()

    # --- tug of war ---------------------------------------------------------

    def start_tug(self, target: TugTarget, side: int) -> bool:
        """The user started dragging an error window: Floppy jumps over and pushes against its side."""
        if self.state in (State.BSOD, State.SLEEP, State.DRAG, State.PUSH):
            return False
        self._tug = target
        self.tug_side = side
        tx, ty = self._tug_point()
        apex = min(self.y, ty) - cfg.JUMP_CLEARANCE
        self._launch(0.0, -math.sqrt(2 * cfg.GRAVITY * max(1.0, self.y - apex)), "tug")
        self.say("tug", chance=0.8, force=True)
        return True

    def tugging(self, target: TugTarget) -> bool:
        """Already heading to this window or pushing it."""
        return self._tug is target and (self.state is State.PUSH or self._air_reason == "tug")

    def pushing(self, target: TugTarget) -> bool:
        return self.state is State.PUSH and self._tug is target

    def _tug_point(self) -> tuple[float, float]:
        r = self._tug.rect()
        x = r.right() + HALF_W - 4 if self.tug_side > 0 else r.left() - HALF_W + 4
        y = min(r.bottom(), self._world.floor.y) if self._world else r.bottom()
        return x, y

    # --- frame --------------------------------------------------------------

    def update(self, now: float, dt: float, world: World) -> None:
        self._now = now
        self._world = world
        self.shake = QPointF(0, 0)
        self._state_shutter = 0.0
        self.arms_target = 0.0
        self.pose.spray = None
        self._track_cursor(now, world.cursor)

        if self.state in GROUNDED:
            self._follow_support()  # may switch to FALL/AIR; the handler is looked up afterwards

        {
            State.IDLE: self._idle,
            State.WALK: self._walk,
            State.RAGE: self._rage,
            State.BSOD: self._bsod,
            State.SLEEP: self._sleep,
            State.MISCHIEF: self._mischief,
            State.DIZZY: self._dizzy,
            State.JUMP: self._jump,
            State.AIR: self._air,
            State.FALL: self._fall,
            State.DRAG: self._drag,
            State.PUSH: self._push,
            State.SNEAK: self._sneak,
            State.SCARED: self._scared,
            State.STUNT: lambda _dt: None,   # the stunt below drives him
        }[self.state](dt)

        stunt = self.stunt
        if stunt is not None:
            stunt.update(dt, self.state is State.STUNT)
            if self.state is State.STUNT and not stunt.in_control:
                self._enter_idle()
            if stunt.finished:
                self.stunt = None

        pose = self.pose
        grounded = self.state in GROUNDED
        pose.grounded = grounded
        pose.anim_t = now
        sit_target = {State.SLEEP: 1.0, State.JUMP: 0.6, State.SNEAK: 0.5}.get(self.state, 0.0)
        pose.sit += (sit_target - pose.sit) * min(1.0, dt * (14 if self.state is State.JUMP else 4))
        pose.arms += (self.arms_target - pose.arms) * min(1.0, dt * 9)
        if grounded and self.state not in (State.DIZZY, State.STUNT):
            pose.tilt = _norm_angle(pose.tilt) * math.exp(-dt * 14)
            self._dizziness = max(0.0, self._dizziness - dt * 0.5)
        chute_target = 1.0 if self.state is State.FALL else 0.0
        pose.chute += (chute_target - pose.chute) * min(1.0, dt * (5 if chute_target else 10))
        dizzy_target = 1.0 if self.state is State.DIZZY else 0.0
        pose.dizzy += (dizzy_target - pose.dizzy) * min(1.0, dt * 6)
        pose.rage += (self._anger - pose.rage) * min(1.0, dt * 10)

        if self.speech and now > self.speech.end:
            self.speech = None
        talking = self.speech is not None and now < self.speech.start + self.speech.typing_time
        if talking:
            self._state_shutter = max(self._state_shutter, abs(math.sin(now * 22)) * 0.75)  # shutter mouth
        pose.shutter = max(self._state_shutter, self._clack(now))

        eyes = QPointF(self.x, self.y + EYES_CENTER.y())
        self.face.update(now, dt, eyes, world.cursor, pose)
        self.effects.update(dt)

    def _breathe(self, period: float) -> None:
        breath = math.sin(self._now * 2 * math.pi / period)
        self.pose.lift = round((breath + 1) / 2 * 2)  # one-pixel steps, like a sprite

    def _clack(self, now: float) -> float:
        if self._clack_start < 0:
            return 0.0
        k = (now - self._clack_start) / CLACK_DURATION
        if k >= 1.0:
            self._clack_start = -1.0
            return 0.0
        return math.sin(math.pi * k)

    # --- support ------------------------------------------------------------

    def _surface(self) -> Surface:
        w = self._world
        if self.support and w.support:
            return w.support
        return w.floor

    def _bounds(self) -> tuple[float, float]:
        s = self._surface()
        edge = WINDOW_EDGE if self.support else FLOOR_EDGE
        lo, hi = s.left + edge, s.right - edge
        if lo > hi:
            lo = hi = (s.left + s.right) / 2
        return lo, hi

    def _follow_support(self) -> None:
        """Stands on the floor or rides along with a window; falls if the support is gone."""
        w = self._world
        if not self.support:
            self.y = w.floor.y
            self.x = _clamp(self.x, w.floor.left + HALF_W, w.floor.right - HALF_W)
            return
        s = w.support
        if s is None or s.key != self.support:
            self._start_fall()  # the window was minimized or closed
            self.say("window_gone", chance=0.8)
            return
        self.x += s.left - self._support_left  # rides along with the window
        self._support_left = s.left
        self.y = s.y
        if not s.left + 4 <= self.x <= s.right - 4:
            self._launch(0.0, 0.0, "drop")  # the window was narrowed out from under him
        elif not w.is_clear(s, self.x):
            self._start_fall()  # another window now covers the edge under his feet

    # --- IDLE ---------------------------------------------------------------

    def _enter_idle(self) -> None:
        self.state = State.IDLE
        self.face.base = "smug"
        self.face.eyes_closed = False
        self.face.fidgets = True
        self.face.look = None
        self._schedule_walk()

    def _schedule_walk(self) -> None:
        every = self.chaos.walk_every
        self._next_walk = self._now + random.uniform(*every) if every else math.inf

    def _schedule_nap(self) -> None:
        every = cfg.NIGHT_NAP_EVERY if _is_night() and self.chaos.percent else self.chaos.nap_every
        self._next_nap = self._now + random.uniform(*every)

    def _schedule_prank(self) -> None:
        every = self.chaos.prank_every
        self._next_prank = self._now + random.uniform(*every) if every else math.inf

    def _idle(self, dt: float) -> None:
        self._breathe(BREATH_PERIOD)
        world = self._world
        self._watch_something()

        if self._pending_prank and not self.support:
            kind, self._pending_prank = self._pending_prank, None
            self._start_prank(kind)
        elif world.user_idle > cfg.AWAY_SLEEP_AFTER:
            self._go_sleep(None, "away")
        elif self._now >= self._next_nap:
            if self.chaos.percent == 0:
                self._go_sleep(None, "lazy")
            else:
                span = cfg.NIGHT_NAP_DURATION if _is_night() else cfg.NAP_DURATION
                self._go_sleep(random.uniform(*span), "nap")
        elif self._should_sneak():
            self._start_sneak()
        elif self._now >= self._next_prank and not world.fullscreen:
            kind = self._random_prank()
            if kind:
                self._start_prank(kind)
            else:
                self._schedule_prank()
        elif self._now >= self._next_walk:
            self._choose_outing()
        elif self.chaos.rare_bsod and world.user_idle < 60 and not world.fullscreen:
            if random.random() < dt / cfg.RARE_BSOD_MEAN:
                self.trigger_bsod()

    def _choose_outing(self) -> None:
        """A walk, a jump onto the active window, or a jump down."""
        p = self._world.platform
        if p and p.key != self.support and self._can_jump_to(p) and random.random() < cfg.JUMP_CHANCE:
            self._plan_jump(p)
        elif self.support and random.random() < cfg.JUMP_DOWN_CHANCE:
            self._jump_down()
        else:
            self._walk_to(self._random_destination())

    def _random_destination(self) -> float:
        lo, hi = self._bounds()
        for _ in range(10):
            target = random.uniform(lo, hi)
            if abs(target - self.x) > 80:
                return target
        return lo if self.x - lo > hi - self.x else hi

    # --- MISCHIEF -----------------------------------------------------------

    def _watch_something(self) -> None:
        if self._watch is None:
            return
        if self._now >= self._watch_until:
            self._watch = None
            self.face.look = None
            return
        dx = self._watch.x() - self.x
        dy = self._watch.y() - (self.y + EYES_CENTER.y())
        self.face.look = QPointF(_clamp(dx / 120, -2, 2), _clamp(dy / 120, -2, 2))

    def _random_prank(self, anywhere: bool = False) -> str | None:
        """A random allowed prank. anywhere=True: floor-only pranks too (he hops down for them)."""
        kinds = [
            k for k in cfg.PRANKS
            if k in self.enabled_pranks
            and (k in WINDOW_PRANKS or self.stunt is None)
            and (anywhere or not cfg.PRANKS[k][2] or not self.support)
        ]
        if not kinds:
            return None
        return random.choices(kinds, weights=[cfg.PRANKS[k][1] for k in kinds])[0]

    def _start_prank(self, kind: str) -> None:
        self._schedule_prank()
        if kind in WINDOW_PRANKS:
            self._start_mischief(kind)
        elif kind == "clone":
            self._start_clone()
            self.on_prank(kind)
        else:
            self.on_prank(kind)   # the window side sets up the stunt (start_haul / start_spray)

    def _start_mischief(self, kind: str) -> None:
        self._stop_walking()
        self.state = State.MISCHIEF
        self._mischief_start = self._now
        self._mischief_kind = kind
        self._mischief_done = False
        self.face.base = "happy"
        self.face.fidgets = False
        self.face.eyes_closed = False

    def _mischief(self, dt: float) -> None:
        t = self._now - self._mischief_start
        if t < 0.66:
            self.shake = QPointF(0, -round(9 * abs(math.sin(t * math.pi * 3))))  # two hops
        if t >= 0.55 and not self._mischief_done:
            self._mischief_done = True
            self._clack_start = self._now
            self.on_sound("seek")
            self.on_prank(self._mischief_kind)
            self.say("mischief", chance=0.7)
            self.face.base = "smug"
            self.face.look = QPointF(0, -2)  # admires his handiwork
        if t >= 1.2:
            self._schedule_prank()
            self._enter_idle()

    # --- WALK ---------------------------------------------------------------

    def _walk_to(self, target: float, then: Callable[[], None] | None = None,
                 speed: float = cfg.WALK_SPEED, mood: str = "smug") -> None:
        self.state = State.WALK
        self._walk_target = target
        self._walk_then = then
        self._walk_speed = speed
        self.face.base = mood
        self.face.fidgets = False
        self.face.look = QPointF(math.copysign(2, target - self.x), 0)

    def _stop_walking(self) -> None:
        self._walk_then = None
        self.pose.step = 0.0
        self.face.look = None

    def _walk(self, dt: float) -> None:
        lo, hi = self._bounds()
        target = _clamp(self._walk_target, lo, hi)  # the window may have been narrowed mid-walk
        if self.step_towards(target, self._walk_speed, dt):
            then = self._walk_then
            self._stop_walking()
            if then:
                then()
            else:
                self._enter_idle()
            return
        if self._walk_speed > cfg.WALK_SPEED and random.random() < dt * 8:
            # Running in panic: sheds pixels as he goes.
            self.effects.pixels(random.uniform(-40, 40), -TOTAL_H * random.uniform(0.2, 0.8), 1)

    # --- JUMP ---------------------------------------------------------------

    def _can_jump_to(self, p: Surface) -> bool:
        w = self._world
        if p.right - p.left < 140:
            return False
        if self.y - p.y > cfg.JUMP_MAX_HEIGHT:
            return False
        if p.y - TOTAL_H - cfg.JUMP_CLEARANCE < w.bounds.top():
            return False  # no room above the window for the jump
        return True

    def _jump_x(self, p: Surface) -> float:
        return _clamp(self.x, p.left + WINDOW_EDGE + 10, p.right - WINDOW_EDGE - 10)

    def _plan_jump(self, p: Surface) -> None:
        tx = self._jump_x(p)
        dx = tx - self.x
        if abs(dx) <= cfg.JUMP_MAX_DX:
            self._start_jump(tx, p.y)
            return
        # Too far: walk closer first.
        lo, hi = self._bounds()
        approach = _clamp(tx - math.copysign(cfg.JUMP_MAX_DX * 0.7, dx), lo, hi)
        key = p.key
        self._walk_to(approach, then=lambda: self._retry_jump(key))

    def _retry_jump(self, key: int) -> None:
        p = self._world.platform
        if p and p.key == key and self._can_jump_to(p):
            tx = self._jump_x(p)
            if abs(tx - self.x) <= cfg.JUMP_MAX_DX * 1.3:
                self._start_jump(tx, p.y)
                return
        self._enter_idle()

    def _jump_down(self) -> None:
        f = self._world.floor
        tx = self.x + random.choice((-1, 1)) * random.uniform(60, 160)
        tx = _clamp(tx, f.left + FLOOR_EDGE, f.right - FLOOR_EDGE)
        self._start_jump(tx, f.y)

    def _start_jump(self, tx: float, ty: float) -> None:
        # Ballistics: the arc apex is JUMP_CLEARANCE above both start and target.
        apex = min(self.y, ty) - cfg.JUMP_CLEARANCE
        vy = -math.sqrt(2 * cfg.GRAVITY * (self.y - apex))
        t = -vy / cfg.GRAVITY + math.sqrt(2 * (ty - apex) / cfg.GRAVITY)
        self._jump_v = ((tx - self.x) / t, vy)
        self._jump_at = self._now + 0.18
        self.state = State.JUMP
        self.face.base = "smug"
        self.face.fidgets = False
        self.face.look = QPointF(math.copysign(2, tx - self.x) if abs(tx - self.x) > 5 else 0, -2)

    def _jump(self, dt: float) -> None:
        if self._now >= self._jump_at:
            self._launch(*self._jump_v, "jump")

    # --- AIR: ballistics ----------------------------------------------------

    def _launch(self, vx: float, vy: float, reason: str) -> None:
        self._stop_walking()
        self.state = State.AIR
        self.support = 0
        self.vx, self.vy = vx, vy
        self._air_reason = reason
        self._bounces = 0
        self._spin = _clamp(vx * 0.35, -900, 900) if reason == "throw" else 0.0
        self.face.eyes_closed = False
        self.face.fidgets = False
        self.face.look = None
        self.face.base = {"jump": "smug", "tug": "angry", "blast": "panic"}.get(reason, "scared")

    def _move_in_air(self, dt: float) -> tuple[float, float]:
        """Moves, respecting walls and ceiling. Returns the previous (x, y)."""
        b = self._world.bounds
        px, py = self.x, self.y
        nx, ny = px + self.vx * dt, py + self.vy * dt
        lo_x, hi_x = b.left() + HALF_W, b.right() - HALF_W
        if nx < lo_x:
            nx, self.vx, self._spin = lo_x, abs(self.vx) * cfg.WALL_BOUNCE, -self._spin * 0.6
        elif nx > hi_x:
            nx, self.vx, self._spin = hi_x, -abs(self.vx) * cfg.WALL_BOUNCE, -self._spin * 0.6
        ceiling = b.top() + TOTAL_H
        if ny < ceiling:
            ny, self.vy = ceiling, abs(self.vy) * 0.5
        self.x, self.y = nx, ny
        return px, py

    def _landing_surface(self, py: float) -> Surface | None:
        """Platforms are one-way (from above only); the floor is solid."""
        if self.vy <= 0:
            return None
        w = self._world
        p = w.platform
        if p and py <= p.y <= self.y and p.left <= self.x <= p.right and w.is_clear(p, self.x):
            return p
        if self.y >= w.floor.y:
            return w.floor
        return None

    def _air(self, dt: float) -> None:
        self.vy += cfg.GRAVITY * dt
        self.vx *= max(0.0, 1.0 - cfg.AIR_DRAG * dt)

        if self._air_reason == "tug":
            if self._tug is None or not self._tug.active:
                self._air_reason = "drop"  # the window was released mid-flight
            else:
                # Homes in on the window's side while it moves.
                tx, ty = self._tug_point()
                self.x += (tx - self.x) * min(1.0, dt * 7)
                if self.vy > 0 and self.y + self.vy * dt >= ty:
                    self.x, self.y = tx, ty
                    self._enter_push()
                    return

        _, py = self._move_in_air(dt)

        self.pose.tilt += self._spin * dt
        self._dizziness += abs(self._spin) * dt / 720  # one full spin = half a dizziness
        self._spin *= max(0.0, 1.0 - 0.6 * dt)
        if self._air_reason not in ("jump", "tug"):
            self.pose.step = math.sin(self._now * 14) * 0.7  # dangles his legs

        surface = self._landing_surface(py)
        if surface:
            self._land(surface)

    def _land(self, s: Surface) -> None:
        impact = self.vy
        self.y = s.y
        if impact > cfg.BOUNCE_SPEED and self._bounces < 2 and self._air_reason not in ("jump", "tug"):
            self._bounces += 1
            self.vy = -impact * cfg.BOUNCE_KEEP
            self.vx *= 0.7
            self.pose.sit = min(1.0, impact / 1600)
            self.effects.dust(0, 0, min(1.5, impact / 1000))
            return

        reason = self._air_reason
        self.support = s.key
        self._support_left = s.left
        self.vx = self.vy = self._spin = 0.0
        self.pose.step = 0.0
        self.pose.sit = max(self.pose.sit, min(1.0, impact / 1400))  # squats from the impact
        if impact > 450:
            self.effects.dust(0, 0, min(1.5, impact / 1000))
        self._enter_idle()
        self._react_to_landing(reason, impact, s)

    def _react_to_landing(self, reason: str, impact: float, s: Surface) -> None:
        now = self._now
        while self._throws and now - self._throws[0] > cfg.ANNOY_WINDOW:
            self._throws.popleft()
        hard = impact > cfg.HARD_LANDING

        if self._dizziness >= cfg.DIZZY_THRESHOLD:
            self._enter_dizzy()
            self.say("blast_land" if reason == "blast" else "land_hard" if hard else "dizzy", force=True)
        elif reason == "throw" and len(self._throws) >= cfg.ANNOY_THROWS:
            self.face.flash("angry", 2.0, now)
            self.say("annoyed", force=True)
            if now - self._last_revenge > cfg.REVENGE_COOLDOWN and random.random() < cfg.REVENGE_CHANCE:
                self._last_revenge = now
                self._start_mischief("revenge")
        elif hard:
            self.face.flash("angry", 1.2, now)    # hurt himself
            self.say("land_hard", chance=0.8)
        elif reason == "throw" and s.key:
            self.face.flash("happy", 1.0, now)
            self.say("land_window", chance=0.8)
        elif reason == "jump" and s.key:
            self.face.flash("happy", 0.8, now)    # made it onto a window
        elif reason == "throw":
            self.face.flash("happy", 0.8, now)
            self.say("land_fun", chance=0.5)
        elif reason == "drop":
            self.face.flash("scared", 0.5, now)

    # --- DIZZY --------------------------------------------------------------

    def _enter_dizzy(self) -> None:
        self.state = State.DIZZY
        self._dizzy_until = self._now + cfg.DIZZY_DURATION
        self._dizziness = 0.0
        self.face.base = "dizzy"
        self.face.fidgets = False

    def _dizzy(self, dt: float) -> None:
        t = self._now
        self.pose.tilt = math.sin(t * 4.5) * 7      # wobbles
        self.pose.step = math.sin(t * 4.5) * 0.4
        if t >= self._dizzy_until:
            self.pose.step = 0.0
            self._enter_idle()

    # --- FALL: parachute ----------------------------------------------------

    def _start_fall(self) -> None:
        self._stop_walking()
        self.state = State.FALL
        self.support = 0
        self.vx = self.vy = self._spin = 0.0
        self._air_reason = "chute"
        self._bounces = 2
        self._fall_start = self._now
        self.face.eyes_closed = False
        self.face.fidgets = False
        self.face.base = "smug"
        self.face.look = QPointF(0, 2)

    def _fall(self, dt: float) -> None:
        t = self._now - self._fall_start
        self.vy += (cfg.CHUTE_SPEED - self.vy) * min(1.0, dt * 3)
        self.vx = math.sin(t * 1.7) * 28        # sways on the lines
        _, py = self._move_in_air(dt)
        self.pose.tilt = math.cos(t * 1.7) * 8
        self.pose.step = math.sin(t * 3) * 0.3
        self.pose.chute_phase = t

        surface = self._landing_surface(py)
        if surface:
            self._land(surface)

    # --- DRAG ---------------------------------------------------------------

    def _drag(self, dt: float) -> None:
        w = self._world
        now = self._now
        cursor = w.cursor
        self._drag_samples.append((now, QPointF(cursor)))
        while len(self._drag_samples) > 2 and now - self._drag_samples[0][0] > 0.1:
            self._drag_samples.popleft()

        b = w.bounds
        target = cursor - self._grab_offset
        nx = _clamp(target.x(), b.left() + HALF_W, b.right() - HALF_W)
        ny = _clamp(target.y(), b.top() + TOTAL_H, b.bottom())
        vx = (nx - self.x) / dt if dt > 0 else 0.0
        vy = (ny - self.y) / dt if dt > 0 else 0.0
        self.x, self.y = nx, ny
        self._drag_vx += (vx - self._drag_vx) * min(1.0, dt * 20)
        speed = math.hypot(vx, vy)

        # Hanging in the hand: lags behind like a pendulum and kicks his legs.
        tilt_target = _clamp(-self._drag_vx * 0.015, -40, 40)
        self.pose.tilt += (tilt_target - self.pose.tilt) * min(1.0, dt * 10)
        self.pose.step = math.sin(now * 16) * 0.8

        self._detect_shaking(now, dt)
        if speed > cfg.FAST_DRAG_SPEED:
            self.say("fast_drag", chance=0.03)
        if speed > 40:
            self._still_since = now
        elif not self._held_said and now - self._still_since > cfg.HELD_LONG:
            self._held_said = True
            self.face.flash("angry", 1.0, now)
            self.say("held_long", force=True)

    def _detect_shaking(self, now: float, dt: float) -> None:
        """Shaking = frequent horizontal direction changes."""
        if abs(self._drag_vx) > cfg.SHAKE_SPEED:
            direction = 1 if self._drag_vx > 0 else -1
            if self._shake_dir and direction != self._shake_dir:
                self._reversals.append(now)
            self._shake_dir = direction
        while self._reversals and now - self._reversals[0] > 1.2:
            self._reversals.popleft()
        if len(self._reversals) >= 3:
            self._dizziness += dt * 1.5
            self.face.flash("dizzy", 0.4, now)
            self.say("shake", chance=0.05)

    # --- PUSH: tug of war ---------------------------------------------------

    def _enter_push(self) -> None:
        self.state = State.PUSH
        self._push_start = self._now
        self.vx = self.vy = 0.0
        self.face.base = "angry"
        self.face.look = QPointF(-self.tug_side * 2, 0)

    def _push(self, dt: float) -> None:
        tug = self._tug
        if tug is None or not tug.active:
            if tug is not None and tug.released:
                self.say("tug_win", chance=0.8, force=True)
                self.face.flash("happy", 1.2, self._now)
            self._tug = None
            self._launch(0.0, 0.0, "drop")
            return
        if self._now - self._push_start > cfg.TUG_TIRED_AFTER:
            self._tug = None
            self.say("tug_tired", force=True)
            self._launch(self.tug_side * 120, -250, "drop")  # hops away, exhausted
            return

        self.x, self.y = self._tug_point()
        self._breathe(0.5)
        self.pose.tilt = -self.tug_side * 16                 # leans into the window
        self.pose.step = math.sin(self._now * 22)            # feet spinning in place
        self._state_shutter = 0.25                            # gritted teeth
        if random.random() < dt * 4:
            self.effects.sweat(self.tug_side * 30, -TOTAL_H + 10, self.tug_side)

    # --- RAGE ---------------------------------------------------------------

    def _rage(self, dt: float) -> None:
        self._breathe(BREATH_PERIOD / 3)
        if self._now - self._last_click > cfg.RAGE_COOLDOWN_DELAY:
            self._anger -= cfg.RAGE_COOLDOWN_RATE * dt
        if self._anger <= 0:
            self._anger = 0.0
            self._enter_idle()
            self.face.flash("neutral", 0.6, self._now)  # exhales
            return

        amp = 0.6 + self._anger * 2.4
        self.shake = QPointF(round(random.uniform(-amp, amp)), round(random.uniform(-amp, amp) / 2))
        if self._anger > 0.25 and random.random() < self._anger * dt * 30:
            self.effects.spark(random.uniform(-40, 40), -TOTAL_H + random.uniform(0, 10))
        if self._anger > 0.5:
            self._state_shutter = 0.2 + 0.2 * abs(math.sin(self._now * 40))  # grinds his teeth

    # --- SNEAK / SCARED ---------------------------------------------------------

    def _track_cursor(self, now: float, cursor: QPointF) -> None:
        """Remembers since when the cursor has stayed within a few pixels of one spot."""
        a = self._cursor_anchor
        if a is None or math.hypot(cursor.x() - a.x(), cursor.y() - a.y()) > cfg.CURSOR_STILL_RADIUS:
            self._cursor_anchor = QPointF(cursor)
            self._cursor_still_since = now

    def _should_sneak(self) -> bool:
        return (self._cursor_anchor is not None
                and self._now - self._cursor_still_since > cfg.MOUSE_FROZEN
                and self._now >= self._sneak_cooldown_until)

    def _start_sneak(self) -> None:
        self.state = State.SNEAK
        self._sneak_start = self._now
        self._sneak_anchor = QPointF(self._cursor_anchor)
        self._next_look = self._now + 0.6
        self.face.base = "sneaky"
        self.face.fidgets = False
        self.face.look = None
        self.say("sneak", chance=0.5)

    def _sneak_target(self) -> float:
        lo, hi = self._bounds()
        cx = self._sneak_anchor.x()
        side = 1 if cx > self.x else -1
        return _clamp(cx - side * cfg.SNEAK_STOP_DISTANCE, lo, hi)

    def _sneak(self, dt: float) -> None:
        w = self._world
        cursor = w.cursor
        jerk = math.hypot(cursor.x() - self._sneak_anchor.x(), cursor.y() - self._sneak_anchor.y())
        if jerk > cfg.SCARE_JERK:
            near = math.hypot(cursor.x() - self.x, cursor.y() - (self.y - TOTAL_H / 2)) < cfg.SCARE_RADIUS
            self._sneak_cooldown_until = self._now + cfg.SNEAK_COOLDOWN
            if near:
                self._start_scared(cursor.x())
            else:
                self._enter_idle()
            return
        if w.user_idle > cfg.AWAY_SLEEP_AFTER:
            self._go_sleep(None, "away")
            return
        if self._now - self._sneak_start > cfg.SNEAK_BORED_AFTER:
            self._sneak_cooldown_until = self._now + cfg.SNEAK_COOLDOWN
            self._enter_idle()
            self.face.flash("neutral", 0.8, self._now)   # loses interest
            return

        target = self._sneak_target()
        dist = target - self.x
        step = cfg.SNEAK_SPEED * dt
        if abs(dist) > step:
            # Tiptoes: slow, small steps, glancing left and right.
            self.x += math.copysign(step, dist)
            self._walk_phase += step / STEP_LENGTH * math.pi / 2
            self.pose.step = math.sin(self._walk_phase) * 0.5
            if self._now >= self._next_look:
                self.face.look = QPointF(random.choice((-2, 2)), 0) if self.face.look is None else None
                self._next_look = self._now + random.uniform(0.5, 1.0)
        else:
            # In position: freezes right under the cursor and stares at it.
            self.x = target
            self.pose.step = 0.0
            self.face.look = None
            self._breathe(BREATH_PERIOD * 1.5)

    def _start_scared(self, cursor_x: float) -> None:
        self._stop_walking()
        self.state = State.SCARED
        self._scared_start = self._now
        self._scared_from = cursor_x
        self.face.base = "panic"
        self.face.fidgets = False
        self.face.look = None
        self.on_sound("scared")
        self.say("scared", chance=0.9, force=True)
        self.effects.pixels(0, -TOTAL_H / 2, 6)

    def _scared(self, dt: float) -> None:
        t = self._now - self._scared_start
        away = -1 if self._scared_from > self.x else 1
        self.face.look = QPointF(-away * 2, -1)          # can't take his eyes off the mouse
        if t < 0.15:
            self.shake = QPointF(0, -round(12 * math.sin(t / 0.15 * math.pi)))  # startled jump
        elif t < 0.6:
            # Wheels spinning in place before he gets traction.
            self.pose.step = math.sin(self._now * 45)
            self.shake = QPointF(round(random.uniform(-1, 1)), 0)
            if random.random() < dt * 20:
                self.effects.dust(-away * 14, 0, 0.6)
            if random.random() < dt * 6:
                self.effects.pixels(random.uniform(-40, 40), -TOTAL_H * random.uniform(0.2, 0.8), 1)
        else:
            lo, hi = self._bounds()
            safe = hi - random.uniform(0, 60) if away > 0 else lo + random.uniform(0, 60)
            self._walk_to(safe, then=self._calm_down, speed=cfg.SCARED_RUN_SPEED, mood="panic")

    def _calm_down(self) -> None:
        self._enter_idle()
        self.face.flash("scared", 0.8, self._now)

    # --- BSOD ---------------------------------------------------------------

    def _bsod(self, dt: float) -> None:
        self._breathe(BREATH_PERIOD)

    # --- SLEEP --------------------------------------------------------------

    def _go_sleep(self, duration: float | None, reason: str) -> None:
        """Walks to the nearest corner of his support and falls asleep. duration=None = until woken."""
        lo, hi = self._bounds()
        corner = lo if self.x - lo < hi - self.x else hi
        if abs(corner - self.x) > 4:
            self._walk_to(corner, then=lambda: self._enter_sleep(duration, reason))
        else:
            self._enter_sleep(duration, reason)

    def _enter_sleep(self, duration: float | None, reason: str) -> None:
        self.state = State.SLEEP
        self._sleep_until = self._now + duration if duration else math.inf
        self._sleep_reason = reason
        self._next_z = self._now + 1.0
        self.face.base = "sleepy"
        self.face.eyes_closed = True
        self.face.fidgets = False
        self.face.look = None

    def _sleep(self, dt: float) -> None:
        if self._now >= self._sleep_until:
            self.wake()
            return
        if self._sleep_reason == "away" and self._world.user_idle < 1.0:
            self.wake(startled=True)  # the user is back
            return

        self._breathe(SLEEP_BREATH_PERIOD)
        phase = self._now * 2 * math.pi / SLEEP_BREATH_PERIOD
        self._state_shutter = 0.22 * max(0.0, math.sin(phase))  # snores through the shutter
        if self._now >= self._next_z:
            self.effects.snore(24, -TOTAL_H + 4)
            self._snore_count += 1
            if self._snore_count % 2 == 0:
                self.on_sound("read", 0.12)  # quiet motor purr
            self._next_z = self._now + 1.4
