"""Long pranks where Floppy acts in person: hauling a window in, spraying graffiti, fighting a clone.

Like the brain, these know nothing about Qt windows. A stunt drives Floppy while the brain is in
State.STUNT and exposes what the window side needs (where his hands are, where the paint goes,
where the clone and the Recycle Bin are). A stunt may outlive its control over Floppy: after an
interruption or once it lets him go, it keeps animating its own leftovers until `finished`.
"""

import math
import random
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF

from . import config as cfg
from .effects import Effects
from .face import Face
from .render import BODY_W, EYES_CENTER, TOTAL_H, Pose, hand_offset

STEP_LENGTH = 7.0


def _pose_hand_x(arms: float, lift: float) -> float:
    pose = Pose(arms=arms, arm_lift=lift, arm_side=1)
    return hand_offset(pose).x()


HAUL_HANDS = _pose_hand_x(1.0, 0.0)      # hands from the center while pulling, px
SPRAY_HAND = _pose_hand_x(1.0, 0.75)     # spray can from the center while painting, px
SPRAY_NOZZLE_UP = 18                      # the nozzle is this far above the hand


class Stunt:
    kind = ""

    def __init__(self, floppy) -> None:
        self.f = floppy
        self.t = 0.0
        self.phase = ""
        self.phase_t = 0.0
        self.in_control = True     # drives Floppy (the brain stays in State.STUNT)
        self.finished = False      # nothing left to animate: the brain forgets the stunt

    def set_phase(self, name: str) -> None:
        self.phase = name
        self.phase_t = 0.0

    def update(self, dt: float, in_control: bool) -> None:
        if self.in_control and not in_control:
            self.in_control = False
            self.interrupted()     # grabbed, clicked, blown up...
        self.t += dt
        self.phase_t += dt
        self.tick(dt)

    def release(self) -> None:
        """Lets Floppy go back to his usual life; the stunt may still animate leftovers."""
        self.in_control = False

    def finish(self) -> None:
        self.in_control = False
        self.finished = True

    def interrupted(self) -> None:
        self.finished = True

    def tick(self, dt: float) -> None:
        raise NotImplementedError

    # --- small helpers for Floppy's body ------------------------------------

    def arms(self, extent: float, side: int, lift: float = 0.0, wiggle: float = 0.0,
             spray=None) -> None:
        f = self.f
        f.arms_target = extent
        f.pose.arm_side = side
        f.pose.arm_lift = lift
        f.pose.arm_wiggle = wiggle
        f.pose.spray = spray

    def lean(self, angle: float, dt: float, speed: float = 8.0) -> None:
        pose = self.f.pose
        pose.tilt += (angle - pose.tilt) * min(1.0, dt * speed)


# --- hauling a window in from behind the screen edge ------------------------

class Haul(Stunt):
    """Walks to the screen edge, rummages behind it and drags a window onto the screen.

    The window side waits until `ready`, places the window so its edge is in his hands
    and calls `pull(distance)`. Every frame it keeps the window edge at `hands_x`.
    """

    kind = "haul"

    def __init__(self, floppy, side: int, stand_x: float) -> None:
        super().__init__(floppy)
        self.side = side            # -1 = the left screen edge, 1 = the right one
        self.stand_x = stand_x
        self.distance = 0.0
        self.start_x = 0.0
        self.set_phase("walk")

    @property
    def hands_x(self) -> float:
        return self.f.x + self.side * HAUL_HANDS

    @property
    def ready(self) -> bool:
        return self.in_control and self.phase == "reach" and self.phase_t >= cfg.HAUL_MIN_REACH

    @property
    def pulling(self) -> bool:
        return self.in_control and self.phase == "pull"

    def pull(self, distance: float) -> None:
        if self.phase != "reach" or not self.in_control:
            return
        self.distance = distance
        self.start_x = self.f.x
        self.set_phase("pull")
        self.f.say("haul_pull", force=True)
        self.f.on_sound("seek")

    def abort(self) -> None:
        """The window got away (closed, or the user grabbed it)."""
        if self.in_control and self.phase in ("reach", "pull"):
            self.f.say("haul_lost", force=True)
            self.f.face.flash("angry", 1.2, self.f._now)
        self.finish()

    def tick(self, dt: float) -> None:
        if not self.in_control:
            return
        f = self.f
        if self.phase == "walk":
            f.face.base = "sneaky"
            f.face.look = QPointF(math.copysign(2, self.stand_x - f.x), 0)
            if f.step_towards(self.stand_x, cfg.WALK_SPEED * 1.5, dt):
                self.set_phase("reach")
                f.say("haul_reach", force=True)
                f.on_sound("seek", 0.6)
        elif self.phase == "reach":
            # Up to the elbows behind the screen edge, feeling around.
            self.arms(1.0, self.side, 0.0, math.sin(self.t * 9))
            self.lean(self.side * 9, dt)
            f.face.base = "smug"
            f.face.look = QPointF(self.side * 2, 0)
            f.shutter_at_least(0.12)
            if self.phase_t > cfg.HAUL_REACH_TIMEOUT:
                f.say("haul_fail", force=True)
                f.face.flash("neutral", 1.2, f._now)
                self.finish()
        elif self.phase == "pull":
            lo, hi = f.floor_span()
            target = max(lo, min(hi, self.start_x - self.side * self.distance))
            arrived = f.step_towards(target, cfg.HAUL_SPEED, dt)
            self.arms(1.0, self.side, 0.0, 0.0)
            self.lean(-self.side * 12, dt)          # leans back with all his weight
            f.face.base = "angry"
            f.face.look = QPointF(self.side * 2, 0)
            f.shutter_at_least(0.25)                # gritted teeth
            if random.random() < dt * 4:
                f.effects.sweat(-self.side * 30, -TOTAL_H + 10, -self.side)
            if arrived:
                self.set_phase("dust")
                f.face.flash("happy", 1.6, f._now)
                f.say("haul_done", force=True)
                f.clack()
        elif self.phase == "dust":
            # Dusts off his hands.
            self.arms(0.55, self.side, 0.35, math.sin(self.t * 32))
            self.lean(0.0, dt)
            if self.phase_t > 0.6:
                self.finish()


# --- graffiti ---------------------------------------------------------------

class Spray(Stunt):
    """Walks along the wall with a spray can held up and paints letters between `left` and `right`."""

    kind = "spray"

    def __init__(self, floppy, left: float, right: float, direction: int, color) -> None:
        super().__init__(floppy)
        self.left, self.right = left, right
        self.direction = direction
        self.color = color
        # The can is in the trailing hand: fresh paint appears behind him, never under his body.
        start = left if direction > 0 else right
        end = right if direction > 0 else left
        self.start_x = start + direction * SPRAY_HAND
        self.end_x = end + direction * SPRAY_HAND
        self._next_hiss = 0.0
        self.set_phase("walk")

    @property
    def painting(self) -> bool:
        return self.in_control and self.phase == "paint"

    @property
    def nozzle(self) -> QPointF:
        """World point the paint comes out of."""
        f = self.f
        return QPointF(f.x - self.direction * SPRAY_HAND, f.y + hand_offset(f.pose).y() - SPRAY_NOZZLE_UP)

    def tick(self, dt: float) -> None:
        if not self.in_control:
            return
        f = self.f
        if self.phase == "walk":
            f.face.base = "sneaky"
            f.face.look = QPointF(math.copysign(2, self.start_x - f.x), 0)
            if f.step_towards(self.start_x, cfg.WALK_SPEED * 1.4, dt):
                self.set_phase("shake")
                f.say("graffiti_start", force=True)
        elif self.phase == "shake":
            # Shakes the can: rattle-rattle.
            self.arms(1.0, -self.direction, 0.75, math.sin(self.t * 45), self.color)
            f.face.base = "happy"
            if self.phase_t > 0.7:
                self.set_phase("paint")
        elif self.phase == "paint":
            self.arms(1.0, -self.direction, 0.75, 0.0, self.color)
            f.face.base = "smug"
            f.face.look = QPointF(-self.direction * 2, -1)   # keeps an eye on his lettering
            f.step_towards(self.end_x, cfg.SPRAY_SPEED, dt)
            if random.random() < dt * 40:
                hand = hand_offset(f.pose)
                f.effects.mist(hand.x(), hand.y() - SPRAY_NOZZLE_UP, self.color)
            if self.t >= self._next_hiss:
                self._next_hiss = self.t + 1.3
                f.on_sound("spray", 0.5)
            if abs(f.x - self.end_x) < 0.5:
                self.set_phase("admire")
                f.say("graffiti_done", force=True)
                f.face.flash("happy", 2.0, f._now)
        elif self.phase == "admire":
            self.arms(0.0, -self.direction, 0.75, 0.0, self.color)
            self.lean(self.direction * 6, dt)
            f.face.look = QPointF(-self.direction * 2, -1)   # admires his art
            if self.phase_t > 1.4:
                self.lean(0.0, 1.0)
                self.finish()


# --- the clone and the Recycle Bin ------------------------------------------

@dataclass
class Puppet:
    """The clone: rendered like Floppy, moved by the show's script."""

    x: float
    y: float
    pose: Pose = field(default_factory=Pose)
    face: Face = field(default_factory=Face)
    effects: Effects = field(default_factory=Effects)
    visible: bool = True
    vx: float = 0.0
    vy: float = 0.0
    spin: float = 0.0
    airborne: bool = False
    walk_phase: float = 0.0
    shake: QPointF = field(default_factory=lambda: QPointF(0, 0))

    def step_towards(self, target: float, speed: float, dt: float) -> bool:
        dist = target - self.x
        step = speed * dt
        if abs(dist) <= step:
            self.x = target
            self.pose.step = 0.0
            return True
        self.x += math.copysign(step, dist)
        self.walk_phase += step / STEP_LENGTH * math.pi / 2
        self.pose.step = math.sin(self.walk_phase)
        self.pose.lift = round(abs(math.sin(self.walk_phase)) * 2)
        return False


BIN_RIM = 58        # height of the wastebasket's rim above the floor


@dataclass
class RecycleBin:
    x: float
    y: float            # floor
    target_x: float
    home_x: float       # off-screen parking spot
    full: bool = False  # a pair of boots sticks out
    shake: float = 0.0  # seconds of wobbling left
    leaving: bool = False

    @property
    def rim_y(self) -> float:
        return self.y - BIN_RIM


class CloneShow(Stunt):
    """Ctrl+C, Ctrl+V: a copy appears, they shove, and the copy goes into the Recycle Bin."""

    kind = "clone"
    TOUCH = BODY_W - 6      # centers this far apart: bodies pressed together

    def __init__(self, floppy, side: int) -> None:
        super().__init__(floppy)
        self.side = side
        self.clone: Puppet | None = None
        self.bin: RecycleBin | None = None
        self._mid = 0.0
        self._sway = random.choice((-1, 1))
        self._flight_t = 0.0
        self._flight_time = 1.0
        self._flight_turn = 0.0
        self.set_phase("copy")
        floppy.say("clone_copy", force=True)
        floppy.face.base = "happy"
        floppy.face.fidgets = False

    # --- user actions ---------------------------------------------------------

    def delete_clone(self) -> None:
        """The user clicked the clone: it is deleted on the spot."""
        c = self.clone
        if c is None or not c.visible or self.phase in ("flight", "binned", "bin_out", "end"):
            return
        self._poof()
        f = self.f
        if self.in_control:
            f.say("clone_deleted", force=True)
            f.face.flash("happy", 1.5, f._now)
            self.release()
            f.pose.arms = 0.0
        self._leave()

    def interrupted(self) -> None:
        if self.clone is not None and self.clone.visible and self.phase not in ("flight", "binned"):
            self._poof()
        if self.phase not in ("binned", "bin_out", "end"):
            self._leave()

    def _poof(self) -> None:
        c = self.clone
        c.visible = False
        c.effects.pixels(0, -TOTAL_H / 2, 14)
        self.f.on_sound("pop")

    def _leave(self) -> None:
        if self.bin is not None:
            self.bin.leaving = True
            self.set_phase("bin_out")
        else:
            self.set_phase("end")

    # --- the script -------------------------------------------------------------

    def tick(self, dt: float) -> None:
        f = self.f
        now = f._now
        c = self.clone

        if self.phase == "copy":
            hop = self.phase_t % 0.65
            if hop < 0.2:
                f.shake = QPointF(0, -round(7 * math.sin(hop / 0.2 * math.pi)))
            if 0.3 <= self.phase_t < 0.3 + dt * 1.5 or 0.95 <= self.phase_t < 0.95 + dt * 1.5:
                f.clack()
                f.on_sound("clack", 0.5)
            if self.phase_t > 1.4:
                self._paste()
        elif self.phase == "paste":
            c.pose.sit = max(0.0, 1.0 - self.phase_t * 3)     # pops up out of nothing
            c.face.look = QPointF(-self.side * 2, 0)
            f.face.look = QPointF(self.side * 2, 0)
            if self.phase_t > 0.6:
                c.face.base = "angry"
            if 0.7 <= self.phase_t < 0.7 + dt * 1.5:
                f.say("clone_argue", force=True)
                f.face.base = "angry"
            if self.phase_t > 1.9:
                self._mid = (f.x + c.x) / 2
                self.set_phase("approach")
        elif self.phase == "approach":
            a = f.step_towards(self._mid - self.side * self.TOUCH / 2, cfg.WALK_SPEED * 1.6, dt)
            b = c.step_towards(self._mid + self.side * self.TOUCH / 2, cfg.WALK_SPEED * 1.6, dt)
            if a and b:
                self.set_phase("shove")
                f.on_sound("seek", 0.5)
        elif self.phase == "shove":
            self._shove(dt)
            if self.phase_t > 1.2 and self.bin is None:
                self._call_bin()
            if self.phase_t > 3.0 and self.bin is not None and self.bin.x == self.bin.target_x:
                self._kick()
        elif self.phase == "flight":
            self._fly(dt)
            f.pose.step += (0.0 - f.pose.step) * min(1.0, dt * 6)
            self.lean(0.0, dt)
        elif self.phase == "binned":
            self.arms(0.0, self.side)
            if 0.3 <= self.phase_t < 0.3 + dt * 1.5:
                f.clack()
            if self.phase_t > 1.8:
                self.release()
                self.bin.leaving = True
                self.set_phase("bin_out")
        elif self.phase == "bin_out":
            if self.bin is None or self.bin.x == self.bin.home_x:
                self.bin = None
                self.set_phase("end")
        elif self.phase == "end":
            if c is None or not c.effects.active:
                self.finish()

        self._update_bin(dt)
        if c is not None:
            self._update_puppet(c, now, dt)

    def _paste(self) -> None:
        f = self.f
        lo, hi = f.floor_span()
        x = max(lo, min(hi, f.x + self.side * cfg.CLONE_GAP))
        if abs(x - f.x) < self.TOUCH + 10:          # no room on that side: paste on the other
            self.side = -self.side
            x = max(lo, min(hi, f.x + self.side * cfg.CLONE_GAP))
        c = Puppet(x, f.y)
        c.pose.sit = 1.0
        c.face.base = "smug"
        c.face.fidgets = False
        for _ in range(10):
            c.effects.spark(random.uniform(-40, 40), -TOTAL_H * random.uniform(0.2, 1.0))
        self.clone = c
        self.set_phase("paste")
        f.say("clone_paste", force=True)
        f.on_sound("pop")

    def _shove(self, dt: float) -> None:
        f, c = self.f, self.clone
        t = self.phase_t
        lo, hi = f.floor_span()
        mid = self._mid + math.sin(t * 2.6) * 26 * self._sway
        mid = max(lo + self.TOUCH / 2, min(hi - self.TOUCH / 2, mid))
        f.x = mid - self.side * self.TOUCH / 2
        c.x = mid + self.side * self.TOUCH / 2
        wiggle = math.sin(t * 17)
        self.arms(0.55, self.side, 0.1, wiggle)
        c.pose.arms = 0.55
        c.pose.arm_side = -self.side
        c.pose.arm_lift = 0.1
        c.pose.arm_wiggle = -wiggle
        self.lean(self.side * 12, dt)
        c.pose.tilt += (-self.side * 12 - c.pose.tilt) * min(1.0, dt * 8)
        f.pose.step = math.sin(f._now * 30)
        c.pose.step = math.sin(f._now * 30 + 1.5)
        f.face.base = "angry"
        c.face.base = "angry"
        f.face.look = QPointF(self.side * 2, 0)
        c.face.look = QPointF(-self.side * 2, 0)
        f.shutter_at_least(0.25)
        f.shake = QPointF(round(random.uniform(-1, 1)), 0)
        c.shake = QPointF(round(random.uniform(-1, 1)), 0)
        if random.random() < dt * 14:
            f.effects.dust(-self.side * 14, 0, 0.5)
        if random.random() < dt * 10:
            f.effects.spark(self.side * BODY_W / 2, -TOTAL_H * random.uniform(0.3, 0.8))
        if random.random() < dt * 3:
            f.effects.sweat(-self.side * 30, -TOTAL_H + 10, -self.side)

    def _call_bin(self) -> None:
        f, c = self.f, self.clone
        w = f._world
        floor = w.floor
        home = floor.right + 80 if self.side > 0 else floor.left - 80
        target = c.x + self.side * 170
        target = max(floor.left + 60, min(floor.right - 60, target))
        if abs(target - c.x) < 100:                # pinned against the edge: the bin comes from behind Floppy
            target = c.x + self.side * 100
        self.bin = RecycleBin(x=home, y=floor.y, target_x=target, home_x=home)
        f.on_sound("seek", 0.4)

    def _kick(self) -> None:
        f, c, b = self.f, self.clone, self.bin
        f.say("clone_bin", force=True)
        f.face.base = "smug"
        f.pose.step = self.side            # the kicking boot goes up
        f.shake = QPointF(self.side * 3, 0)
        f.on_sound("clack")
        # Ballistic arc into the bin, head first: he turns upside down on the way.
        gravity = cfg.GRAVITY
        tx, ty = b.x, b.rim_y + 26
        apex = min(c.y, ty) - 110
        vy = -math.sqrt(2 * gravity * (c.y - apex))
        t = -vy / gravity + math.sqrt(2 * (ty - apex) / gravity)
        c.vx, c.vy = (tx - c.x) / t, vy
        c.airborne = True
        c.pose.arms = 0.0
        c.face.base = "panic"
        c.face.look = None
        self._flight_t = 0.0
        self._flight_time = t
        self._flight_turn = self.side * 180 - c.pose.tilt
        self.set_phase("flight")

    def _fly(self, dt: float) -> None:
        c = self.clone
        self._flight_t += dt
        c.vy += cfg.GRAVITY * dt
        c.x += c.vx * dt
        c.y += c.vy * dt
        c.pose.tilt += self._flight_turn * dt / self._flight_time
        c.pose.step = math.sin(self.f._now * 14) * 0.8       # kicks his legs in the air
        if self._flight_t >= self._flight_time:
            c.visible = False
            c.airborne = False
            self.bin.full = True
            self.bin.shake = 0.7
            self.f.on_sound("trash")
            self.f.say("clone_binned", force=True)
            self.f.face.flash("happy", 2.0, self.f._now)
            self.set_phase("binned")

    def _update_bin(self, dt: float) -> None:
        b = self.bin
        if b is None:
            return
        goal = b.home_x if b.leaving else b.target_x
        step = cfg.BIN_SPEED * dt
        b.x = goal if abs(goal - b.x) <= step else b.x + math.copysign(step, goal - b.x)
        b.shake = max(0.0, b.shake - dt)

    def _update_puppet(self, c: Puppet, now: float, dt: float) -> None:
        c.shake = QPointF(0, 0) if self.phase != "shove" else c.shake
        if not c.airborne:
            c.y = self.f._world.floor.y
            if self.phase != "shove":
                c.pose.tilt *= math.exp(-dt * 10)
            breath = math.sin(now * 2 * math.pi / 3.2)
            if c.pose.step == 0.0:
                c.pose.lift = round((breath + 1) / 2 * 2)
        c.pose.grounded = not c.airborne
        c.pose.anim_t = now
        eyes = QPointF(c.x, c.y + EYES_CENTER.y())
        c.face.update(now, dt, eyes, self.f._world.cursor, c.pose)
        c.effects.update(dt)
