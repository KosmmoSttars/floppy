"""Builds dist/Floppy/Floppy.exe with PyInstaller and zips it for sharing.

    python tools/build.py

The sounds are copied next to the .exe (dist/Floppy/assets/sounds), not baked in,
so anyone can swap a WAV without rebuilding.
"""

import io
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ICON = ROOT / "assets" / "floppy.ico"
DIST = ROOT / "dist"
APP_DIR = DIST / "Floppy"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Parts of Qt that Floppy never uses (relative to dist/Floppy/_internal). Saves ~55 MB.
# The self-check at the end verifies sound still loads and plays without them.
TRIM = (
    "PyQt6/Qt6/bin/opengl32sw.dll",            # software OpenGL; widgets are raster-painted
    "PyQt6/Qt6/bin/Qt6Pdf.dll",
    "PyQt6/Qt6/plugins/imageformats/qpdf.dll",
    "PyQt6/Qt6/bin/av*.dll",                   # FFmpeg: QSoundEffect decodes WAV itself
    "PyQt6/Qt6/bin/sw*.dll",
    "PyQt6/Qt6/plugins/multimedia/ffmpegmediaplugin.dll",
    "PyQt6/Qt6/translations",                  # Qt's own UI translations; Floppy is English-only
    "PyQt6/Qt6/plugins/tls/qopensslbackend.dll",  # no networking
    "libcrypto-3-x64.dll",                     # OpenSSL for Qt (Python's own libcrypto-3.dll stays)
    "libssl-3-x64.dll",
)


def render_icon() -> None:
    """Draws Floppy at every icon size and packs the PNGs into a multi-size .ico."""
    from PyQt6.QtCore import QBuffer, QIODevice
    from PyQt6.QtGui import QColor, QImage, QPainter
    from PyQt6.QtWidgets import QApplication

    from floppy.render import BODY_W, TOTAL_H, Pose, draw_floppy
    from floppy.skins import SKINS

    app = QApplication.instance() or QApplication([])
    images = []
    for size in ICON_SIZES:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        scale = size / (max(BODY_W, TOTAL_H) + 8)
        p.translate(size / 2, size - 3 * scale)
        p.scale(scale, scale)
        draw_floppy(p, SKINS["black"], Pose(grounded=False))
        p.end()
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        images.append((size, bytes(buf.data())))
    del app

    # ICO container: header, one directory entry per size, then the PNG blobs.
    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for size, data in images:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        out.write(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    for _, data in images:
        out.write(data)
    ICON.parent.mkdir(parents=True, exist_ok=True)
    ICON.write_bytes(out.getvalue())
    print(f"icon   {ICON.relative_to(ROOT)} ({len(images)} sizes)")


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_sounds.py")], check=True)
    render_icon()

    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "Floppy",
        "--icon", str(ICON),
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--exclude-module", "tkinter",
        str(ROOT / "main.py"),
    ], check=True, cwd=ROOT)

    trim()

    sounds = APP_DIR / "assets" / "sounds"
    if sounds.exists():
        shutil.rmtree(sounds)
    shutil.copytree(ROOT / "assets" / "sounds", sounds)
    shutil.copy2(ROOT / "assets" / "videos.txt", APP_DIR / "assets" / "videos.txt")  # editable link list
    shutil.copy2(ROOT / "README.md", APP_DIR / "README.md")
    print(f"sounds {sounds.relative_to(ROOT)}")

    check = subprocess.run([str(APP_DIR / "Floppy.exe"), "--self-check"])
    report = APP_DIR / "floppy_check.txt"
    print(report.read_text(encoding="utf-8"))
    report.unlink()
    if check.returncode != 0:
        raise SystemExit("self-check failed: see the report above")

    archive = shutil.make_archive(str(DIST / "Floppy-v1.44"), "zip", DIST, "Floppy")
    print(f"zip    {Path(archive).relative_to(ROOT)}")
    print(f"done   {(APP_DIR / 'Floppy.exe').relative_to(ROOT)}")


def trim() -> None:
    internal = APP_DIR / "_internal"
    saved = 0
    for pattern in TRIM:
        for path in internal.glob(pattern):
            if path.is_dir():
                saved += sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                shutil.rmtree(path)
            else:
                saved += path.stat().st_size
                path.unlink()
    print(f"trim   removed {saved / 2**20:.1f} MB of unused Qt parts")


if __name__ == "__main__":
    main()
