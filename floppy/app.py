import signal
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDir, QEventLoop, QLockFile, QSettings, QStandardPaths, QTimer, QT_VERSION_STR
from PyQt6.QtWidgets import QApplication

from .character import FloppyWindow


def self_check(app: QApplication) -> int:
    """`Floppy.exe --self-check`: writes floppy_check.txt next to the executable and exits.

    Useful for verifying a frozen build (sounds found and decodable) without hearing anything.
    """
    from . import __version__, win32
    from .sound import SOUND_FILES, SoundBank, sounds_dir

    bank = SoundBank(QSettings("Floppy", "FloppySelfCheck"))
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)  # sound effects load asynchronously
    loop.exec()

    lines = [
        f"Floppy {__version__} self-check",
        f"Qt {QT_VERSION_STR}, frozen={getattr(sys, 'frozen', False)}",
        f"sounds dir: {sounds_dir()}",
    ]
    ok = True
    for name in SOUND_FILES:
        pool = bank._pools.get(name)
        status = pool[0].status().name if pool else "MISSING"
        ok &= status == "Ready"
        lines.append(f"  {name:7} {status}")
    music = bank._music.status().name if bank._music else "MISSING"
    ok &= music == "Ready"
    lines.append(f"  {'music':7} {music}")
    # Playback probe: start a long sound muted and check that the audio output actually runs.
    probe = bank._pools.get("bsod")
    playing = False
    if probe:
        probe[0].setMuted(True)
        probe[0].play()
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()
        playing = probe[0].isPlaying()
        probe[0].stop()
    ok &= playing
    lines.append(f"playback probe: {'playing' if playing else 'FAILED'}")
    lines.append(f"fullscreen app in front: {win32.foreground_fullscreen()}")
    lines.append("RESULT: OK" if ok else "RESULT: PROBLEM")

    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    (base / "floppy_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


def error_log_path() -> Path:
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "floppy_error.log"


def install_error_log() -> None:
    """Log unhandled exceptions instead of letting PyQt abort the app silently (windowed builds have no console)."""
    def hook(exc_type, exc, tb):
        try:
            with error_log_path().open("a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except OSError:
            pass
        if sys.stderr:
            traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # Ctrl+C in the console quits the app
    app = QApplication(sys.argv)
    app.setOrganizationName("Floppy")
    install_error_log()
    app.setApplicationName("Floppy")
    app.setQuitOnLastWindowClosed(False)

    if "--self-check" in sys.argv:
        return self_check(app)

    # Only one Floppy per desktop: a second launch quietly exits.
    lock = QLockFile(str(Path(QDir.tempPath()) / "floppy-v144.lock"))
    if not lock.tryLock(100):
        return 0

    settings = QSettings("Floppy", "Floppy")
    floppy = FloppyWindow(settings)
    floppy.show()
    return app.exec()
