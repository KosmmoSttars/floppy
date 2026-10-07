"""Transparent character window on top of the desktop."""

import math
import os

from PyQt6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, QSettings, Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

from . import win32
from .brain import Floppy, State, Surface, World
from .bsod import Bsod
from .config import CHAOS_LEVELS, DEFAULT_CHAOS, PRANKS
from .menu import build_menu
from .pranks import PrankManager, videos_file
from .render import TOTAL_H, draw_floppy
from .skins import DEFAULT_SKIN, SKINS
from .sound import SoundBank
from .speech import SpeechBubble

FPS = 60
CALM_FPS = 20
DRAG_THRESHOLD = 5      # px: farther is a drag, closer is a click
MIN_PLATFORM_W = 140
CALM_STATES = {State.IDLE, State.SLEEP, State.BSOD}


class FloppyWindow(QWidget):
    # Room around the character for mid-air spins, the parachute, sparks and "Z z z".
    WIN_W = 240
    WIN_H = 275
    FEET = QPointF(120, 228)

    def __init__(self, settings: QSettings):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keep out of the taskbar and Alt+Tab
            | Qt.WindowType.WindowDoesNotAcceptFocus,  # don't steal focus from the user's windows
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.WIN_W, self.WIN_H)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self.settings = settings
        self.skin = SKINS.get(str(settings.value("skin", DEFAULT_SKIN)), SKINS[DEFAULT_SKIN])
        self.chaos_index = min(int(settings.value("chaos", DEFAULT_CHAOS)), len(CHAOS_LEVELS) - 1)
        self.sounds = SoundBank(settings, self)

        avail = QGuiApplication.primaryScreen().availableGeometry()
        self.floppy = Floppy(avail.right() - 200, avail.bottom(), CHAOS_LEVELS[self.chaos_index])
        self.floppy.on_bsod = self._show_bsod
        self.floppy.on_prank = self._spawn_prank
        self.floppy.on_sound = self.sounds.play
        self.bsod = Bsod(self)
        self.bsod.finished.connect(self.floppy.bsod_finished)
        disabled = str(settings.value("pranks/disabled", "")).split(",")
        self.floppy.enabled_pranks = {k for k in PRANKS if k not in disabled}
        self.pranks = PrankManager(self.floppy, settings, self, play=self.sounds.play,
                                   sounds=self.sounds, skin=lambda: self.skin)
        self.pranks.youtube = str(settings.value("pranks/youtube", "true")).lower() == "true"
        self.bubble = SpeechBubble()

        self._press_pos: QPointF | None = None
        self._dragging = False
        self._hidden = False
        self._last_preview = 0.0
        self._last_signature: tuple | None = None

        self._clock = QElapsedTimer()
        self._clock.start()
        self._last = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // FPS)
        self._tick()

    def _now(self) -> float:
        return self._clock.elapsed() / 1000.0

    # --- world --------------------------------------------------------------

    @staticmethod
    def _window_surface(hwnd: int) -> Surface | None:
        rect = win32.window_frame(hwnd)
        if rect is None or rect.width() < MIN_PLATFORM_W:
            return None
        return Surface(hwnd, rect.left(), rect.right(), rect.top())

    @staticmethod
    def _edge_clear(surface: Surface, x: float) -> bool:
        return surface.key == 0 or win32.top_edge_clear(surface.key, x, surface.y)

    def _world(self) -> World:
        f = self.floppy
        probe = QPoint(round(f.x), round(f.y) - 10)
        screen = QGuiApplication.screenAt(probe) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        floor = Surface(0, avail.left(), avail.right() + 1, avail.bottom() + 1)

        platform = None
        hwnd = win32.foreground_window()
        if hwnd:
            platform = self._window_surface(hwnd)

        support = None
        if f.support and win32.window_alive(f.support):
            support = self._window_surface(f.support)

        return World(
            floor=floor,
            platform=platform,
            support=support,
            bounds=QRectF(screen.virtualGeometry()),
            cursor=QPointF(QCursor.pos()),
            user_idle=win32.get_idle_seconds(),
            is_clear=self._edge_clear,
            fullscreen=win32.foreground_fullscreen(),
        )

    # --- frame --------------------------------------------------------------

    def _tick(self) -> None:
        now = self._now()
        dt = min(now - self._last, 0.1)
        self._last = now

        world = self._world()
        self.floppy.update(now, dt, world)
        self.pranks.tick(dt)
        self.move(round(self.floppy.x - self.FEET.x()), round(self.floppy.y - self.FEET.y()))
        # Step aside while a game, video or presentation runs fullscreen.
        self._hidden = world.fullscreen and not self._dragging
        if self.isVisible() == self._hidden:
            self.setVisible(not self._hidden)
        # Repaint only when something visible changed: idle frames are mostly identical.
        signature = self._frame_signature()
        if signature != self._last_signature or self.floppy.effects.active:
            self._last_signature = signature
            self.update()
        self._update_bubble()
        self._adapt_frame_rate()

    def _adapt_frame_rate(self) -> None:
        """60 fps while anything moves, 20 fps while he just stands, sleeps or waits."""
        f = self.floppy
        calm = (f.state in CALM_STATES and not f.effects.fast and not self._dragging and f.stunt is None
                and f.visible_speech() is None and f.pose.rage < 0.01 and f.pose.arms < 0.01)
        interval = 1000 // CALM_FPS if calm else 1000 // FPS
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    def _frame_signature(self) -> tuple:
        pose, f = self.floppy.pose, self.floppy
        e = pose.expression
        animated = e.dizzy or pose.dizzy > 0.05 or pose.chute > 0.1
        return (
            self.skin.key, pose.lift, round(pose.blink * 8), pose.pupil, round(pose.shutter * 16),
            round(pose.step * 8), round(pose.sit * 14), round(pose.rage * 30), round(pose.tilt * 2),
            pose.grounded, round(pose.chute * 30), round(pose.dizzy * 10),
            round(pose.anim_t * 30) if animated else 0,
            round(e.lid * 4), round(e.slant * 4), round(e.lid_bottom * 4), round(e.brow_left * 4),
            round(e.brow_right * 4), round(e.brow_tilt * 4), e.pupil, e.happy, e.dizzy,
            round(f.shake.x()), round(f.shake.y()),
            round(pose.arms * 20), pose.arm_side, round(pose.arm_lift * 10), round(pose.arm_wiggle * 4),
            pose.spray is not None,
        )

    def _update_bubble(self) -> None:
        f = self.floppy
        speech = f.visible_speech()
        if speech is None or self.bsod.active or self._hidden:
            if self.bubble.isVisible():
                self.bubble.hide()
            return
        head = TOTAL_H + 10 + (75 if f.pose.chute > 0.5 else 0)  # above the parachute, if open
        self.bubble.show_text(speech[0], speech[1], QPointF(f.x, f.y - head) + f.shake)

    def _spawn_prank(self, kind: str) -> None:
        f = self.floppy
        self.pranks.spawn(kind, QPointF(f.x, f.y - TOTAL_H - 30))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.translate(self.FEET + self.floppy.shake)
        draw_floppy(p, self.skin, self.floppy.pose)
        self.floppy.effects.draw(p, self.skin.body)
        p.end()

    def _show_bsod(self) -> None:
        self.bsod.show()
        self.raise_()

    # --- mouse: click = rage, drag = throw ----------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition()
            self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # The second click of a double-click arrives here; for rage it's still a click.
        self.mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is None or self._dragging:
            return
        delta = event.globalPosition() - self._press_pos
        if math.hypot(delta.x(), delta.y()) > DRAG_THRESHOLD:
            self._dragging = self.floppy.grab(self._now(), QPointF(QCursor.pos()))
            if self._dragging:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            return
        if self._dragging:
            self.floppy.release(self._now())
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.floppy.click(self._now())
        self._press_pos = None
        self._dragging = False

    def contextMenuEvent(self, event) -> None:
        menu = build_menu(
            self,
            chaos_index=self.chaos_index,
            skin_key=self.skin.key,
            asleep=self.floppy.asleep,
            on_chaos=self.set_chaos,
            on_skin=self.set_skin,
            on_sleep=self.floppy.sleep,
            on_wake=self.floppy.wake,
            on_performance=self.floppy.perform,
            sound_enabled=self.sounds.enabled,
            volume=self.sounds.volume,
            enabled_pranks=self.floppy.enabled_pranks,
            youtube=self.pranks.youtube,
            on_prank_toggle=self._toggle_prank,
            on_youtube=self._set_youtube,
            on_edit_videos=self._edit_videos,
            on_sound_toggle=self.sounds.set_enabled,
            on_volume=self._set_volume,
            on_eject=self.eject,
        )
        menu.exec(event.globalPos())

    def eject(self) -> None:
        self.sounds.play("eject")
        self.pranks.close_all()
        self.bubble.close()
        self.hide()
        QTimer.singleShot(600, QApplication.quit)  # let the eject click finish playing

    def _toggle_prank(self, kind: str, on: bool) -> None:
        enabled = self.floppy.enabled_pranks
        if on:
            enabled.add(kind)
        else:
            enabled.discard(kind)
        self.settings.setValue("pranks/disabled", ",".join(k for k in PRANKS if k not in enabled))

    def _set_youtube(self, on: bool) -> None:
        self.pranks.youtube = on
        self.settings.setValue("pranks/youtube", "true" if on else "false")

    @staticmethod
    def _edit_videos() -> None:
        try:
            os.startfile(str(videos_file()))  # opens in Notepad (or whatever edits .txt)
        except OSError:
            pass

    def _set_volume(self, volume: int) -> None:
        self.sounds.set_volume(volume)
        now = self._now()
        if now - self._last_preview > 0.15:  # audible preview while dragging the slider
            self._last_preview = now
            self.sounds.play("clack")

    def set_skin(self, key: str) -> None:
        self.skin = SKINS[key]
        self.settings.setValue("skin", key)

    def set_chaos(self, index: int) -> None:
        self.chaos_index = index
        self.settings.setValue("chaos", index)
        self.floppy.set_chaos(CHAOS_LEVELS[index])
