"""Asynchronous sound effects from external WAV files in assets/sounds/.

Any file can be replaced with your own 16-bit PCM WAV recording without touching the code.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QSettings, QUrl
from PyQt6.QtMultimedia import QSoundEffect

SOUND_FILES = {
    "seek": "floppy_seek.wav",       # stepper motor grinding: pranks
    "read": "floppy_read.wav",       # sectors being read: progress bar, snoring motor
    "error": "win95_error.wav",      # error dialog chord
    "bsod": "bsod_beep.wav",         # PC speaker siren
    "eject": "floppy_eject.wav",     # metal click on exit
    "ding": "ding.wav",              # "job done" bell when a progress bar finishes
    "scared": "scared_beep.wav",     # panicked beep
    "clack": "shutter_clack.wav",    # shutter slamming on a click
    "boom": "mine_boom.wav",         # Minesweeper mine going off
    "spray": "spray_hiss.wav",       # spray can
    "pop": "clone_pop.wav",          # Ctrl+V: a copy pops into existence
    "trash": "recycle_bin.wav",      # something landed in the Recycle Bin
}
MUSIC_FILE = "chiptune_loop.wav"     # Media Player background music, looped

POOL_SIZE = 3                        # overlapping copies per sound (rapid clicks)
MUSIC_GAIN = 0.45
DEFAULT_VOLUME = 70


def assets_dir() -> Path:
    """Next to the .exe in a frozen build (so users can swap files), else in the project."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "assets")
    candidates.append(Path(__file__).resolve().parent.parent / "assets")
    return next((c for c in candidates if c.is_dir()), candidates[-1])


def sounds_dir() -> Path:
    return assets_dir() / "sounds"


class SoundBank(QObject):
    def __init__(self, settings: QSettings, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        self.enabled = str(settings.value("sound/enabled", "true")).lower() == "true"
        self.volume = int(settings.value("sound/volume", DEFAULT_VOLUME))
        self._pools: dict[str, list[QSoundEffect]] = {}
        self._next: dict[str, int] = {}

        folder = sounds_dir()
        for name, filename in SOUND_FILES.items():
            path = folder / filename
            if not path.exists():
                continue
            pool = []
            for _ in range(POOL_SIZE):
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(path)))  # preload: first play is instant
                pool.append(effect)
            self._pools[name] = pool
            self._next[name] = 0

        self._music: QSoundEffect | None = None
        self._music_users = 0
        music = folder / MUSIC_FILE
        if music.exists():
            self._music = QSoundEffect(self)
            self._music.setSource(QUrl.fromLocalFile(str(music)))
            self._music.setLoopCount(QSoundEffect.Loop.Infinite.value)

    def play(self, name: str, gain: float = 1.0) -> None:
        if not self.enabled or self.volume <= 0:
            return
        pool = self._pools.get(name)
        if not pool:
            return
        i = self._next[name]
        self._next[name] = (i + 1) % len(pool)
        effect = pool[i]
        effect.setVolume(max(0.0, min(1.0, self.volume / 100 * gain)))
        effect.play()

    # --- looping background music (several players may want it at once) -------

    def music_on(self) -> None:
        self._music_users += 1
        self._sync_music()

    def music_off(self) -> None:
        self._music_users = max(0, self._music_users - 1)
        self._sync_music()

    def _sync_music(self) -> None:
        m = self._music
        if m is None:
            return
        want = self._music_users > 0 and self.enabled and self.volume > 0
        m.setVolume(max(0.0, min(1.0, self.volume / 100 * MUSIC_GAIN)))
        if want and not m.isPlaying():
            m.play()
        elif not want and m.isPlaying():
            m.stop()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._settings.setValue("sound/enabled", "true" if enabled else "false")
        self._sync_music()

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, volume))
        self._settings.setValue("sound/volume", self.volume)
        self._sync_music()
