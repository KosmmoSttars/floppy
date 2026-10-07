"""Tiny pixel art shared by the prank windows: a mini Floppy and a 5x7 pixel font."""

from functools import lru_cache

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath

# --- mini Floppy --------------------------------------------------------------

MINI_PALETTE = {
    "K": QColor("#000000"),
    "B": QColor("#2D2D33"),   # body: replaced by the skin color
    "L": QColor("#F4EABB"),   # paper label
    "N": QColor("#000080"),   # label stripe
    "E": QColor("#FFFFFF"),   # eye white
    "S": QColor("#C0C0C0"),   # shutter
    "R": QColor("#B3141B"),   # boots
}

_MINI_BODY = (
    "KKKKKKKK..",
    "KNNNNNNBK.",
    "KLLLLLLBBK",
    "KBBBBBBBBK",
    "KBEEBBEEBK",
    "KBE{BBE{BK",   # { is the pupil, shifted by the gaze
    "KBBBBBBBBK",
    "KBBSSSSBBK",
    "KBBSKSSBBK",
    "KKKKKKKKKK",
)
_MINI_HAPPY_EYES = ("KBEEBBEEBK", "KBBBBBBBBK")   # squinting with joy
_MINI_LEGS = (
    ("..K....K..", ".RR....RR."),
    ("...K..K...", "..RR..RR.."),
    ("..K...K...", ".RR...RR.."),
)

MINI_W = 10
MINI_H = len(_MINI_BODY) + 2


@lru_cache(maxsize=64)
def mini_floppy_rows(frame: int = 0, look: int = 1, happy: bool = False) -> tuple[str, ...]:
    """frame: legs (0 = standing, 1/2 = walking). look: -1/0/1 pupils. happy: ^ ^ eyes."""
    rows = list(_MINI_BODY)
    if happy:
        rows[4], rows[5] = _MINI_HAPPY_EYES
    else:
        eye = "E{" if look >= 0 else "{E"
        rows[5] = f"KB{eye}BB{eye}BK".replace("{", "K")
    rows.extend(_MINI_LEGS[frame % len(_MINI_LEGS)])
    return tuple(rows)


def draw_sprite(p: QPainter, rows, x: float, y: float, scale: float = 1.0,
                palette: dict | None = None, mirror: bool = False) -> None:
    pal = palette or MINI_PALETTE
    p.setPen(Qt.PenStyle.NoPen)
    width = max(len(r) for r in rows)
    for cy, row in enumerate(rows):
        for cx, ch in enumerate(row):
            color = pal.get(ch)
            if color is None:
                continue
            col = width - 1 - cx if mirror else cx
            p.fillRect(QRectF(x + col * scale, y + cy * scale, scale, scale), color)


# --- 5x7 pixel font -----------------------------------------------------------

GLYPHS: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000",) * 7,
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    "<": ("00001", "00010", "00100", "01000", "00100", "00010", "00001"),
    "%": ("11001", "11001", "00010", "00100", "01000", "10011", "10011"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
}
GLYPH_W, GLYPH_H = 5, 7
ADVANCE = GLYPH_W + 1


def text_cells(text: str) -> list[tuple[int, int]]:
    """Pixel cells (col, row) of a line of text in the 5x7 font, one empty column between letters."""
    cells = []
    for i, ch in enumerate(text.upper()):
        glyph = GLYPHS.get(ch, GLYPHS["?"])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    cells.append((i * ADVANCE + col, row))
    return cells


def text_width(text: str) -> int:
    """Width in cells."""
    return max(0, len(text) * ADVANCE - 1)


@lru_cache(maxsize=256)
def _text_path(text: str, scale: float) -> QPainterPath:
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    for cx, cy in text_cells(text):
        path.addRect(QRectF(cx * scale, cy * scale, scale, scale))
    return path.simplified()


def draw_text(p: QPainter, text: str, x: float, y: float, scale: float, color: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(_text_path(text, scale).translated(x, y))
