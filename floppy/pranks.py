"""Prank arsenal: error windows, the "hydra", fake progress bars, tug of war, the defragmenter,
Minesweeper, videos hauled in from behind the screen, graffiti and the clone show."""

import random
from pathlib import Path
from typing import Callable

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPointF, QRectF, QSettings, QSizeF
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import QWidget

from . import config as cfg
from .actors import BinWindow, CloneWindow
from .browser import BrowserVideo
from .defrag import DefragDialog
from .dialogs import ErrorDialog, ProgressDialog, Win95Window
from .graffiti import PAINTS, GraffitiWindow
from .mediaplayer import MediaPlayerDialog, make_clips
from .messages import (BUTTON_SETS, DEFAULT_VIDEOS, FOLLOW_UPS, GRAFFITI, HYDRA_PAIRS, MESSAGES, MOON,
                       PROGRESS_JOKES, REACTIONS, TITLES)
from .minesweeper import MinesweeperDialog
from .skins import SKINS, Skin
from .sound import assets_dir
from .sprites import text_width
from .stunts import CloneShow, Haul

class ShuffleBag:
    """Hands out items in random order without repeats until every item has been used.

    The rest of the bag is stored in settings, so there are no repeats across restarts either.
    """

    def __init__(self, items, settings: QSettings | None, key: str):
        self._items = items
        self._settings = settings
        self._key = f"bags/{key}"
        self._last = -1
        self._remaining: list[int] | None = None

    def _load(self) -> list[int]:
        if self._settings is None:
            return []
        raw = str(self._settings.value(self._key, ""))
        return [int(i) for i in raw.split(",") if i.isdigit() and int(i) < len(self._items)]

    def draw(self):
        remaining = self._remaining if self._remaining is not None else self._load()
        if not remaining:
            remaining = list(range(len(self._items)))
            random.shuffle(remaining)
            if len(remaining) > 1 and remaining[-1] == self._last:
                remaining[0], remaining[-1] = remaining[-1], remaining[0]  # avoid a repeat across the bag boundary
        index = remaining.pop()
        self._remaining = remaining
        self._last = index
        if self._settings is not None:
            self._settings.setValue(self._key, ",".join(map(str, remaining)))
        return self._items[index]


class TugTarget:
    """A window Floppy is pushing. The brain reads it every frame."""

    def __init__(self, window: Win95Window):
        self.window = window
        self.released = False   # the user let go of the window
        self.closed = False

    def rect(self) -> QRectF:
        if sip.isdeleted(self.window):
            self.closed = True
            return QRectF()
        return self.window.frame_rect()

    @property
    def active(self) -> bool:
        if not self.closed and sip.isdeleted(self.window):
            self.closed = True  # the window was deleted while the brain still holds the target
        return not self.released and not self.closed


def videos_file() -> Path:
    """The user-editable list of YouTube links (created with defaults on first use)."""
    path = assets_dir() / "videos.txt"
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(DEFAULT_VIDEOS, encoding="utf-8")
        except OSError:
            pass
    return path


def _video_links() -> list[str]:
    try:
        lines = videos_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = DEFAULT_VIDEOS.splitlines()
    links = [line.split("#")[0].strip() for line in lines]
    return [link for link in links if link.startswith(("http://", "https://"))]


class PlayerTarget:
    """A haul target: Floppy's own Media Player window."""

    ready = True
    failed = False

    def __init__(self, window: MediaPlayerDialog):
        self.window = window

    def size(self) -> QSizeF:
        return QSizeF(self.window.width(), self.window.height())

    def alive(self) -> bool:
        return not sip.isdeleted(self.window) and self.window.isVisible()

    def place(self, left: float, top: float, _ref: QPointF) -> None:
        self.window.place(QPointF(left, top))

    def moved_by_user(self) -> bool:
        return self.window.dragging

    def show(self) -> None:
        self.window.show()

    def start(self) -> None:
        self.window.play()

    def cancel(self) -> None:
        self.window.close()


class HaulJob:
    """Keeps a window's edge in Floppy's hands while he drags it in from behind the screen edge."""

    EDGE_MARGIN = 20

    def __init__(self, floppy, stunt: Haul, target, fallback: Callable[[], "PlayerTarget"] | None = None):
        self.floppy = floppy
        self.stunt = stunt
        self.target = target
        self._fallback = fallback   # used if the real target never shows up (no browser window)
        self.done = False
        self._pulled = False
        self._parked = False
        self._started = False

    def _geometry(self) -> tuple[float, float, float, QPointF]:
        """(width, height, top, reference point) for the target on Floppy's screen."""
        f = self.floppy
        floor = f._world.floor
        size = self.target.size()
        return size.width(), size.height(), floor.y - size.height(), QPointF(f.x, floor.y - 10)

    def _left_at_hands(self, w: float) -> float:
        hands = self.stunt.hands_x
        return hands - w if self.stunt.side < 0 else hands

    def _final_left(self, w: float) -> float:
        floor = self.floppy._world.floor
        if self.stunt.side < 0:
            return floor.left + self.EDGE_MARGIN
        return floor.right - self.EDGE_MARGIN - w

    def tick(self) -> None:
        if self.done:
            return
        st, tg = self.stunt, self.target
        if tg.failed and self._fallback is not None and st.in_control and not self._pulled:
            self.target, self._fallback = self._fallback(), None
            return
        if tg.failed:
            if st.in_control:
                self.floppy.say("haul_fail", force=True)
            st.finish()
            self.done = True
            return
        if st.finished or not st.in_control:
            self._wrap_up()
            return
        if not self._pulled:
            if tg.ready and not self._parked:
                # Hide it behind the screen edge until he gets hold of it.
                w, _h, top, ref = self._geometry()
                floor = self.floppy._world.floor
                left = floor.left - w - 60 if st.side < 0 else floor.right + 60
                tg.place(left, top, ref)
                self._parked = True
            if st.ready and tg.ready:
                w, _h, top, ref = self._geometry()
                tg.place(self._left_at_hands(w), top, ref)
                tg.show()
                final_hands = self._final_left(w) + (w if st.side < 0 else 0)
                st.pull(abs(final_hands - st.hands_x))
                self._pulled = True
            return
        if not tg.alive() or tg.moved_by_user():
            st.abort()
            self._wrap_up()
            return
        w, _h, top, ref = self._geometry()
        tg.place(self._left_at_hands(w), top, ref)

    def _wrap_up(self) -> None:
        """The stunt is over: finished, interrupted or aborted."""
        st, tg = self.stunt, self.target
        self.done = True
        if self._pulled:
            if tg.alive():
                tg.start()
                w, h, top, _ref = self._geometry()
                left = self._left_at_hands(w) if st.phase == "dust" else self._final_left(w)
                self.floppy.look_at(QPointF(left + w / 2, top + h / 2), 12.0)
        elif tg.ready and isinstance(tg, BrowserVideo):
            # He let go before pulling: the window falls onto the screen by itself.
            w, _h, top, ref = self._geometry()
            tg.place(self._final_left(w), top, ref)
        else:
            tg.cancel()


class PrankManager(QObject):
    def __init__(self, floppy, settings: QSettings | None = None, parent: QObject | None = None,
                 play: Callable[..., None] | None = None, sounds=None,
                 skin: Callable[[], Skin] | None = None):
        super().__init__(parent)
        self.floppy = floppy
        self._settings = settings
        self._play = play or (lambda name, gain=1.0: None)
        self._sounds = sounds
        self._skin = skin or (lambda: SKINS["black"])
        self.youtube = False
        self._graffiti_texts = ShuffleBag(GRAFFITI, settings, "graffiti")
        self._clip_bag = ShuffleBag(list(range(4)), settings, "clips")
        self._haul: HaulJob | None = None
        self._spray: tuple | None = None
        self._graffiti: list[GraffitiWindow] = []
        self._show: CloneShow | None = None
        self._clone_win: CloneWindow | None = None
        self._bin_win: BinWindow | None = None
        self._messages = ShuffleBag(MESSAGES, settings, "messages")
        self._buttons = ShuffleBag(BUTTON_SETS, settings, "buttons")
        self._titles = ShuffleBag(TITLES, settings, "titles")
        self._progress_jokes = ShuffleBag(PROGRESS_JOKES, settings, "progress")
        self._hydra_pairs = ShuffleBag(HYDRA_PAIRS, settings, "hydra")
        self._windows: list[Win95Window] = []
        self._tug: TugTarget | None = None
        self._tug_travel = QPointF(0, 0)

    # --- creating windows ---------------------------------------------------

    def spawn(self, kind: str, near: QPointF) -> None:
        if kind == "video":
            self._start_video()
            return
        if kind == "graffiti":
            self._start_graffiti()
            return
        if kind == "clone":
            self._start_clone()
            return
        if len(self._windows) >= cfg.MAX_PRANK_WINDOWS:
            return
        if kind == "defrag":
            self._defrag(near)
        elif kind == "mines":
            self._mines(near)
        elif kind == "progress":
            task, punch = self._progress_jokes.draw()
            self._progress(task, punch, near)
        elif kind == "revenge":
            n = self.floppy.throw_count
            self._error(
                "Floppy.exe",
                f"You have thrown Floppy {n} times. Floppy wrote it all down on sector 0.",
                "warning", ["Apologize", "Throw again"], None, near,
            )
        else:
            buttons, runaway = self._buttons.draw()
            icon = random.choice(("error", "error", "warning", "info"))
            self._error(self._titles.draw(), self._messages.draw(), icon, list(buttons), runaway, near)

    def _error(self, title, message, icon, buttons, runaway, near, mini=False) -> ErrorDialog:
        win = ErrorDialog(title, message, icon, buttons, runaway, mini)
        win.button_clicked.connect(self._on_button)
        if not mini:
            win.closed_by_x.connect(lambda w=win: self._hydra(w))
        self._register(win, near)
        self._play("error", 0.6 if mini else 1.0)
        return win

    def _progress(self, task: str, punch: str, near: QPointF) -> ProgressDialog:
        win = ProgressDialog("Floppy Setup", task, punch)
        win.finished_joke.connect(self._progress_done)
        win.button_clicked.connect(self._on_button)
        self._register(win, near)
        self._play("read", 0.7)
        return win

    def _progress_done(self) -> None:
        self.floppy.laugh()
        self._play("ding")

    def _register(self, win: Win95Window, near: QPointF | None) -> None:
        win.resist = lambda delta, w=win: self._resist(w, delta)
        win.drag_started.connect(lambda w=win: self._on_drag_started(w))
        win.drag_moved.connect(lambda delta, w=win: self._on_drag_moved(w, delta))
        win.drag_finished.connect(lambda w=win: self._on_drag_finished(w))
        win.destroyed.connect(lambda _=None, w=win: self._drop(w))
        win.closed_by_x.connect(lambda w=win: self._forget(w))
        win.adjustSize()
        if near is not None:
            win.place(self._position(win, near))
            win.show()
        self._windows.append(win)

    def _position(self, win: Win95Window, near: QPointF) -> QPointF:
        """Above Floppy's head, cascaded, kept on screen."""
        screen = QGuiApplication.screenAt(near.toPoint()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        cascade = 24 * (len(self._windows) % 5)
        x = near.x() - win.width() / 2 + cascade
        y = near.y() - win.height() + cascade
        x = max(avail.left() + 4, min(x, avail.right() - win.width() - 4))
        y = max(avail.top() + 4, min(y, avail.bottom() - win.height() - 4))
        return QPointF(x, y)

    def _forget(self, win: Win95Window) -> None:
        """A window was closed by us or by the user: stop tracking it and delete it."""
        if win in self._windows:
            win.deleteLater()
        self._drop(win)

    def _drop(self, win: Win95Window) -> None:
        """Stop tracking without touching the object itself (Qt may have deleted it already)."""
        if win in self._windows:
            self._windows.remove(win)
        if self._tug and self._tug.window is win:
            self._tug.closed = True
            self._tug = None

    def close_all(self) -> None:
        for win in list(self._windows):
            win.close()
            self._forget(win)
        for win in list(self._graffiti):
            win.close()
        self._close_clone_windows()
        self._haul = None
        self._spray = None

    def _raise_floppy(self) -> None:
        """New overlay windows appear on top; Floppy himself should stay in front of them."""
        parent = self.parent()
        if isinstance(parent, QWidget):
            parent.raise_()

    def _watch(self, win: Win95Window, seconds: float) -> None:
        self.floppy.look_at(QPointF(win.frame_rect().center()), seconds)

    # --- the defragmenter and Minesweeper -------------------------------------

    def _defrag(self, near: QPointF) -> None:
        win = DefragDialog(self._skin().body)
        win.button_clicked.connect(self._on_button)
        win.finished_joke.connect(self._progress_done)
        win.oops.connect(lambda: self.floppy.react("defrag_oops", "scared"))
        self._register(win, near)
        self._play("read", 0.7)
        self._watch(win, 20.0)

    def _mines(self, near: QPointF) -> None:
        win = MinesweeperDialog()
        win.exploded.connect(self._on_explosion)
        win.won.connect(lambda by_floppy: self.floppy.react(
            "mines_floppy_won" if by_floppy else "mines_user_won", "happy" if by_floppy else "scared"))
        win.taken_over.connect(lambda: self.floppy.react("mines_taken", "smug"))
        self._register(win, near)
        self._watch(win, 25.0)

    def _on_explosion(self, where: QPointF) -> None:
        self._play("boom")
        self.floppy.blast(where)

    # --- a video hauled in from behind the screen edge --------------------------

    def _start_video(self) -> None:
        stunt = self.floppy.start_haul()
        if stunt is None:
            return
        target = self._browser_target() if self.youtube else None
        if target is None:
            self._haul = HaulJob(self.floppy, stunt, self._player_target())
        else:
            self._haul = HaulJob(self.floppy, stunt, target, fallback=self._player_target)

    def _player_target(self) -> PlayerTarget:
        """Floppy's own Media Player: used when real YouTube is off or no browser window turned up."""
        clip = make_clips(self._skin().body)[self._clip_bag.draw()]
        on = self._sounds.music_on if self._sounds else (lambda: None)
        off = self._sounds.music_off if self._sounds else (lambda: None)
        win = MediaPlayerDialog(clip, on, off)
        self._register(win, None)
        return PlayerTarget(win)

    def _browser_target(self) -> BrowserVideo | None:
        links = _video_links()
        if not links:
            return None
        url = ShuffleBag(links, self._settings, "videos").draw()
        floor = self.floppy._world.floor
        screen = QGuiApplication.screenAt(QPointF(self.floppy.x, floor.y - 10).toPoint())
        top = screen.availableGeometry().top() if screen else 0
        size = QSizeF(min(cfg.VIDEO_W, floor.right - floor.left - 300),
                      min(cfg.VIDEO_H, floor.y - top - 40))
        try:
            return BrowserVideo(url, size)
        except (RuntimeError, OSError):
            return None

    # --- graffiti -----------------------------------------------------------------

    def _start_graffiti(self) -> None:
        text = self._graffiti_texts.draw()
        room = self.floppy.spray_room()
        cell = 7
        while cell > 3 and text_width(text) * cell > room:
            cell -= 1
        if text_width(text) * cell > room:
            return
        color = QColor(random.choice(PAINTS))
        stunt = self.floppy.start_spray(text_width(text) * cell, color)
        if stunt is None:
            return
        bottom = self.floppy._world.floor.y - cfg.GRAFFITI_ABOVE_FLOOR
        win = GraffitiWindow(text, color, cell, stunt.left, bottom)
        win.wiped.connect(lambda: self.floppy.react("graffiti_wiped", "angry"))
        win.gone.connect(lambda w=win: self._graffiti_gone(w))
        win.show()
        self._raise_floppy()
        self._graffiti.append(win)
        self._spray = (stunt, win)
        while len(self._graffiti) > 3:
            self._graffiti[0].close()

    def _graffiti_gone(self, win: GraffitiWindow) -> None:
        if win in self._graffiti:
            self._graffiti.remove(win)
            win.deleteLater()
        if self._spray and self._spray[1] is win:
            self._spray = None

    def _tick_graffiti(self) -> None:
        stunt, win = self._spray
        if stunt.painting:
            win.spray_at(stunt.nozzle.x())
        elif stunt.finished or not stunt.in_control or stunt.phase == "admire":
            win.stop_painting()
            self._spray = None

    # --- the clone show -------------------------------------------------------------

    def _start_clone(self) -> None:
        show = self.floppy.stunt
        if not isinstance(show, CloneShow) or show is self._show:
            return
        self._close_clone_windows()
        mine = self._skin()
        skin = random.choice([s for s in SKINS.values() if s.key != mine.key])
        self._show = show
        self._clone_win = CloneWindow(skin, show.delete_clone)
        self._bin_win = BinWindow(skin.body)

    def _tick_clone(self) -> None:
        show = self._show
        if show.finished:
            self._close_clone_windows()
            return
        c = show.clone
        if c is not None and (c.visible or c.effects.active):
            self._clone_win.sync(c)
        elif self._clone_win.isVisible():
            self._clone_win.hide()
        if show.bin is not None:
            self._bin_win.sync(show.bin, self.floppy._now)
        elif self._bin_win.isVisible():
            self._bin_win.hide()

    def _close_clone_windows(self) -> None:
        for win in (self._clone_win, self._bin_win):
            if win is not None:
                win.close()
                win.deleteLater()
        self._clone_win = self._bin_win = None
        self._show = None

    # --- button reactions ---------------------------------------------------

    def _on_button(self, label: str) -> None:
        sender = self.sender()
        near = QPointF(sender.frame_rect().center()) if isinstance(sender, Win95Window) else QPointF(600, 400)
        if sender is not None:
            self._forget(sender)
        if label in REACTIONS:
            self.floppy.react(*REACTIONS[label])
        elif label == "Format the Moon":
            self._progress(MOON[0], MOON[1], near)
        elif label in FOLLOW_UPS:
            icon, text = FOLLOW_UPS[label]
            self._error("Message", text, icon, ["OK"], None, near)
        elif label == "Apologize":
            self.floppy.forgive_throws()
            self.floppy.react("apology_ok", "happy")

    def _hydra(self, win: Win95Window) -> None:
        """Closed with the X: with some chance, two tiny windows pop out."""
        if random.random() >= cfg.HYDRA_CHANCE:
            return
        center = QPointF(win.frame_rect().center())
        for i, text in enumerate(self._hydra_pairs.draw()):
            mini = self._error("VIRUS_DO_NOT_RUN.bat", text, "error", ["OK"], None,
                               center + QPointF(-110 + 220 * i, 40), mini=True)
            mini.place(mini.frame_rect().topLeft() + QPointF(0, 30 * i))

    # --- tug of war ---------------------------------------------------------

    def _on_drag_started(self, win: Win95Window) -> None:
        self._tug = TugTarget(win)
        self._tug_travel = QPointF(0, 0)

    def _on_drag_moved(self, win: Win95Window, delta: QPointF) -> None:
        tug = self._tug
        if tug is None or tug.window is not win or self.floppy.tugging(tug):
            return
        self._tug_travel += delta
        tx = self._tug_travel.x()
        if abs(tx) > 8:
            side = 1 if tx > 0 else -1          # stands in the window's way
        elif self._tug_travel.manhattanLength() > 14:
            side = 1 if self.floppy.x > win.frame_rect().center().x() else -1
        else:
            return
        if not self.floppy.start_tug(tug, side):
            self._tug = None

    def _on_drag_finished(self, win: Win95Window) -> None:
        if self._tug and self._tug.window is win:
            self._tug.released = True
            self._tug = None

    def _resist(self, win: Win95Window, delta: QPointF) -> QPointF:
        """While Floppy is pushing back, the window barely moves towards him."""
        tug = self._tug
        if tug and tug.window is win and self.floppy.pushing(tug):
            side = self.floppy.tug_side
            if delta.x() * side > 0:
                delta = QPointF(delta.x() * cfg.TUG_RESISTANCE, delta.y())
        return delta

    def tick(self, dt: float) -> None:
        if self._haul is not None:
            job = self._haul
            job.tick()
            if job.done:
                self._haul = None
                if isinstance(job.target, PlayerTarget) and not sip.isdeleted(job.target.window):
                    win = job.target.window
                    if not sip.isdeleted(win) and not win.isVisible():
                        self._forget(win)   # never made it onto the screen
        if self._spray is not None:
            self._tick_graffiti()
        if self._show is not None:
            self._tick_clone()
        tug = self._tug
        if tug and self.floppy.pushing(tug):
            # Floppy huffs and pushes the window away from himself.
            tug.window.nudge(-self.floppy.tug_side * cfg.TUG_PUSH_SPEED * dt)
