"""Procedural rendering of Floppy with QPainter, in the style of Windows 95 icons.

The origin is the point between the boots (bottom of the character) and the Y axis points down,
so the whole body lives in negative Y.
"""

import math
from dataclasses import dataclass, field
from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from .expressions import EXPRESSIONS, Expression
from .skins import Skin

BODY_W = 92
BODY_H = 110
LEG_H = 12
CUT = 14            # clipped top-right corner
RADIUS = 4
OUTLINE_W = 2.5

PIXEL = 3           # size of one eye "pixel"
EYE_CELLS = 9
EYE_SPACING = 18    # eye center offset from the axis
EYE_Y = 61          # eye center, measured from the top of the body

SHUTTER_W = 44
SHUTTER_H = 27
SHUTTER_TRAVEL = 16
CAVITY_W = 15
CAVITY_H = 18

SIT_DROP = 7

LABEL_TEXT = ("VIRUS_DO_NOT_", "RUN.bat")
LABEL_TILT = -2.2   # the label is stuck on crooked

# Windows 95 palette.
BLACK = QColor("#000000")
WHITE = QColor("#FFFFFF")
SILVER = QColor("#C0C0C0")
GRAY = QColor("#808080")
NAVY = QColor("#000080")
RED = QColor("#C00000")
PAPER = QColor("#F4EABB")
MEDIA = QColor("#6B4423")
BOOT = QColor("#B3141B")

TOTAL_H = BODY_H + LEG_H
EYES_CENTER = QPointF(0, -TOTAL_H + EYE_Y)
BODY_CENTER = QPointF(0, -TOTAL_H / 2)


@dataclass
class Pose:
    lift: int = 0                # 0..2 px of stepped "breathing", like a sprite
    blink: float = 0.0           # 0 = open, 1 = closed
    pupil: tuple[int, int] = (0, 0)  # pupil offset in eye pixels, -2..2
    shutter: float = 0.0         # 0 = shutter closed, 1 = mouth open
    step: float = 0.0            # -1..1, which leg is lifted (walking)
    sit: float = 0.0             # 0 = standing, 1 = sitting (sleep)
    rage: float = 0.0            # 0..1, how red he has turned
    tilt: float = 0.0            # tilt/rotation in degrees around the body center
    grounded: bool = True        # standing on something: draw the shadow
    chute: float = 0.0           # 0..1 parachute deployment
    chute_phase: float = 0.0     # flight time, makes the canopy flutter
    dizzy: float = 0.0           # 0..1 stars above the head
    anim_t: float = 0.0          # clock for frame-based effects (spirals, stars)
    arms: float = 0.0            # 0 = arms tucked away, 1 = fully stretched out
    arm_side: int = 1            # which side the arms reach to
    arm_lift: float = 0.0        # 0 = straight out sideways, 1 = raised above the head
    arm_wiggle: float = 0.0      # -1..1 vertical hand offset (rummaging, shoving)
    spray: QColor | None = None  # holding a spray can of this color
    expression: Expression = field(default_factory=lambda: EXPRESSIONS["smug"])


def draw_floppy(p: QPainter, skin: Skin, pose: Pose) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if pose.grounded:
        _draw_ground_shadow(p)

    p.save()
    if abs(pose.tilt) > 0.1:
        p.translate(BODY_CENTER)
        p.rotate(pose.tilt)
        p.translate(-BODY_CENTER)
    _draw_legs(p, pose)

    drop = round(pose.sit * SIT_DROP)
    r = QRectF(-BODY_W / 2, -TOTAL_H - pose.lift + drop, BODY_W, BODY_H + pose.lift)
    body = _body_path(r)
    if pose.arms > 0.05:
        _draw_arms(p, r, pose)  # behind the body: they stick out from its side

    if skin.translucent:
        _draw_inner_disk(p, body, r)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(skin.body)
    p.drawPath(body)
    if pose.rage > 0.01:
        p.setBrush(QColor(230, 16, 16, int(170 * pose.rage)))
        p.drawPath(body)

    p.save()
    p.setClipPath(body)
    _draw_shading(p, skin, r)
    _draw_label(p, r)
    _draw_face(p, skin, r, pose)
    _draw_shutter(p, skin, r, pose)
    p.restore()

    # Outline last: it also traces the see-through write-protect hole.
    pen = QPen(BLACK, OUTLINE_W)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(body)

    if pose.dizzy > 0.05:
        _draw_stars(p, r, pose)
    if pose.chute > 0.1:  # a nearly folded canopy is skipped, it would just be a blob
        _draw_parachute(p, r, pose.chute, pose.chute_phase)
    p.restore()


# --- shared helpers ---------------------------------------------------------

@lru_cache(maxsize=32)
def _dither_brush(rgba: int, cell: int = 2) -> QBrush:
    """Checkerboard dithering, like 16-color VGA graphics."""
    img = QImage(cell * 2, cell * 2, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    color = QColor.fromRgba(rgba)
    for x, y in ((0, 0), (cell, cell)):
        for dx in range(cell):
            for dy in range(cell):
                img.setPixelColor(x + dx, y + dy, color)
    return QBrush(img)


def _dither(color: QColor, alpha: int | None = None) -> QBrush:
    c = QColor(color)
    if alpha is not None:
        c.setAlpha(alpha)
    return _dither_brush(c.rgba())


def _line_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen


# --- body -------------------------------------------------------------------

def _write_protect_rect(r: QRectF) -> QRectF:
    return QRectF(r.left() + 7, r.bottom() - 16, 8, 9)


def _body_path(r: QRectF) -> QPainterPath:
    x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
    k = RADIUS
    path = QPainterPath()
    path.moveTo(x0 + k, y0)
    path.lineTo(x1 - CUT, y0)
    path.lineTo(x1, y0 + CUT)
    path.lineTo(x1, y1 - k)
    path.quadTo(x1, y1, x1 - k, y1)
    path.lineTo(x0 + k, y1)
    path.quadTo(x0, y1, x0, y1 - k)
    path.lineTo(x0, y0 + k)
    path.quadTo(x0, y0, x0 + k, y0)
    path.closeSubpath()

    # See-through write-protect hole: the desktop shows through it.
    hole = QPainterPath()
    hole.addRect(_write_protect_rect(r))
    return path.subtracted(hole)


def _draw_ground_shadow(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_dither(BLACK, 130))
    p.setBrushOrigin(0, 0)
    p.drawEllipse(QPointF(0, -1.5), 31, 3.5)


def _draw_inner_disk(p: QPainter, body: QPainterPath, r: QRectF) -> None:
    """The magnetic disk showing through translucent plastic."""
    p.save()
    p.setClipPath(body)
    center = QPointF(r.center().x(), r.top() + 63)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(MEDIA.red(), MEDIA.green(), MEDIA.blue(), 210))
    p.drawEllipse(center, 41, 41)
    p.setBrush(_dither(BLACK, 90))
    p.drawEllipse(center, 41, 41)
    p.setBrush(QColor(200, 205, 212, 230))
    p.drawEllipse(center, 11, 11)
    p.setBrush(QColor(80, 85, 90, 230))
    p.drawRect(QRectF(center.x() - 3, center.y() - 3, 6, 6))
    p.restore()


def _draw_shading(p: QPainter, skin: Skin, r: QRectF) -> None:
    """Volume without gradients: dithering along the bottom and right edges plus hard bevels."""
    x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()

    band = QPainterPath()
    band.addRect(QRectF(x1 - 11, y0, 11, r.height()))
    band.addRect(QRectF(x0, y1 - 13, r.width(), 13))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_dither(skin.body_dark))
    p.setBrushOrigin(QPointF(x0, y1))
    p.drawPath(band.simplified())

    inset = 3.2
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_line_pen(skin.body_light, 2.4))
    highlight = QPainterPath(QPointF(x0 + inset, y1 - 18))
    highlight.lineTo(x0 + inset, y0 + inset)
    highlight.lineTo(x1 - CUT - 1, y0 + inset)
    highlight.lineTo(x1 - inset, y0 + CUT + 1)
    p.drawPath(highlight)

    p.setPen(_line_pen(skin.body_dark, 2.4))
    shadow = QPainterPath(QPointF(x1 - inset, y0 + CUT + 3))
    shadow.lineTo(x1 - inset, y1 - inset)
    shadow.lineTo(x0 + 18, y1 - inset)
    p.drawPath(shadow)


# --- label ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _label_font() -> QFont:
    families = QFontDatabase.families()
    family = next((f for f in ("Segoe Print", "Comic Sans MS") if f in families), "")
    font = QFont(family)
    font.setPixelSize(10)
    font.setBold(True)
    return font


def _draw_label(p: QPainter, r: QRectF) -> None:
    lab = QRectF(r.left() + 8, r.top() + 6, BODY_W - 8 - CUT - 6, 23)

    p.save()
    p.translate(lab.center())
    p.rotate(LABEL_TILT)
    p.translate(-lab.center())

    paper = QPainterPath()
    paper.addRect(lab)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(PAPER)
    p.drawPath(paper)

    p.save()
    p.setClipPath(paper, Qt.ClipOperation.IntersectClip)
    p.setBrush(NAVY)
    p.drawRect(QRectF(lab.left(), lab.top(), lab.width(), 4))
    p.setPen(QPen(QColor(0, 0, 128, 45), 0.8))
    for dy in (13.5, 21.5):
        p.drawLine(QPointF(lab.left() + 2, lab.top() + dy), QPointF(lab.right() - 2, lab.top() + dy))
    p.restore()

    # Handwritten marker text.
    font = _label_font()
    fm = QFontMetricsF(font)
    area_w = lab.width() - 6
    p.setFont(font)
    p.setPen(NAVY)
    for text, baseline in zip(LABEL_TEXT, (13.0, 21.5)):
        width = fm.horizontalAdvance(text)
        p.save()
        p.translate(lab.left() + 3, lab.top() + baseline)
        if width > area_w:
            p.scale(area_w / width, 1)
        p.drawText(QPointF(0, 0), text)
        p.restore()

    # Red underline under RUN.
    run_w = min(fm.horizontalAdvance("RUN"), area_w)
    pen = QPen(RED, 1.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    y = lab.top() + 23
    wave = QPainterPath(QPointF(lab.left() + 3, y))
    for i in range(1, 7):
        wave.lineTo(QPointF(lab.left() + 3 + run_w * i / 6, y + (1.2 if i % 2 else -0.2)))
    p.drawPath(wave)

    p.setPen(QPen(BLACK, 1.3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(paper)
    p.restore()


# --- face -------------------------------------------------------------------

_LAST = EYE_CELLS - 1
_MID = EYE_CELLS // 2
_EYE_CORNERS = {
    (0, 0), (1, 0), (0, 1),
    (_LAST, 0), (_LAST - 1, 0), (_LAST, 1),
    (0, _LAST), (1, _LAST), (0, _LAST - 1),
    (_LAST, _LAST), (_LAST - 1, _LAST), (_LAST, _LAST - 1),
}
_EYE_SHAPE = frozenset(
    (cx, cy) for cx in range(EYE_CELLS) for cy in range(EYE_CELLS) if (cx, cy) not in _EYE_CORNERS
)


@lru_cache(maxsize=1024)
def _cells_shape(cells: frozenset[tuple[int, int]]) -> QPainterPath:
    """Merges grid cells into one outline once; the face reuses a handful of shapes over and over."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    for cx, cy in cells:
        path.addRect(QRectF(cx * PIXEL, cy * PIXEL, PIXEL, PIXEL))
    return path.simplified()


def _cells_path(cells, origin: QPointF) -> QPainterPath:
    return _cells_shape(frozenset(cells)).translated(origin)


def _expand(cells) -> set[tuple[int, int]]:
    out = set(cells)
    for cx, cy in cells:
        out.update({(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)})
    return out


def _inner(cx: int, side: int, half: float) -> float:
    """-1 at the outer edge of the eye, +1 at the inner edge (towards the nose)."""
    return -side * (cx - _MID) / half


def _eye_cells(expr: Expression, blink: float, side: int):
    """Returns (eye white, closed-eye line) for one eye."""
    if blink > 0.85:
        return set(), {(cx, _MID + 1) for cx in range(2, _LAST - 1)} | {(1, _MID), (_LAST - 1, _MID)}

    if expr.happy or expr.dizzy:
        if expr.dizzy:
            return set(_EYE_SHAPE), set()
        arc = set()
        for cx in range(1, _LAST):
            y = 2 + abs(cx - _MID)
            arc.update({(cx, y), (cx, y + 1)})
        return arc, set()

    visible = set()
    for cx, cy in _EYE_SHAPE:
        top = expr.lid + expr.slant * 0.5 * _inner(cx, side, _MID)
        top += blink * (_MID + 1.5 - top)
        if cy + 0.5 > top and cy + 0.5 < EYE_CELLS - expr.lid_bottom:
            visible.add((cx, cy))
    if not visible:
        return set(), {(cx, _MID + 1) for cx in range(2, _LAST - 1)}
    return visible, set()


_SPIRAL = (
    "1111111",
    "0000001",
    "0111101",
    "0100101",
    "0101101",
    "0100001",
    "0111111",
)


@lru_cache(maxsize=2)
def _spiral_cells(mirror: bool) -> frozenset[tuple[int, int]]:
    cells = set()
    for cy, row in enumerate(_SPIRAL):
        for cx, bit in enumerate(row):
            if bit == "1":
                cells.add((7 - cx if mirror else cx + 1, cy + 1))
    return frozenset(cells)


def _brow_cells(expr: Expression, side: int) -> set[tuple[int, int]]:
    raise_ = expr.brow_left if side < 0 else expr.brow_right
    cells = set()
    for cx in range(1, _LAST):
        y = round(-3 - raise_ + expr.brow_tilt * 0.5 * _inner(cx, side, _MID - 1))
        cells.update({(cx, y), (cx, y - 1)})
    return cells


def _draw_face(p: QPainter, skin: Skin, r: QRectF, pose: Pose) -> None:
    expr = pose.expression
    n = expr.pupil
    start = _MID - (n - 1) // 2 if n % 2 else _MID - n // 2 + 1
    # Under a heavy lid the pupil can't go up, or the eye would look empty.
    min_dy = max(-2, math.ceil(expr.lid - 0.5) - start)
    max_dy = min(2, math.floor(EYE_CELLS - expr.lid_bottom - 0.5 - 1e-6) - (start + n - 1))
    dx = max(-2, min(2, pose.pupil[0]))
    dy = max(min_dy, min(max_dy, pose.pupil[1]))

    p.setPen(Qt.PenStyle.NoPen)
    for side in (-1, 1):
        center_x = r.center().x() + side * EYE_SPACING
        origin = QPointF(center_x - EYE_CELLS * PIXEL / 2, r.top() + EYE_Y - EYE_CELLS * PIXEL / 2)

        p.setBrush(skin.brow)
        p.drawPath(_cells_path(_brow_cells(expr, side), origin))

        white, closed = _eye_cells(expr, pose.blink, side)
        if closed:
            p.setBrush(skin.brow)
            p.drawPath(_cells_path(closed, origin))
            continue

        p.setBrush(BLACK)
        p.drawPath(_cells_path(_expand(white), origin))
        p.setBrush(WHITE)
        p.drawPath(_cells_path(white, origin))
        if expr.happy:
            continue
        if expr.dizzy:
            # Spirals spin in opposite directions: frames alternate and the right eye is mirrored.
            frame = int(pose.anim_t * 8) % 2
            mirror = (frame == 1) != (side > 0)
            p.setBrush(BLACK)
            p.drawPath(_cells_path(_spiral_cells(mirror), origin))
            continue

        pupil = {
            (cx, cy)
            for cx in range(start + dx, start + dx + n)
            for cy in range(start + dy, start + dy + n)
        } & white
        if n >= 3:
            pupil -= {(start + dx, start + dy)}  # highlight
        p.setBrush(BLACK)
        p.drawPath(_cells_path(pupil, origin))


STAR = ((0, 1), (1, 0), (1, 1), (1, 2), (2, 1))
STAR_COLOR = QColor("#FFE000")


def _draw_stars(p: QPainter, r: QRectF, pose: Pose) -> None:
    """Three pixel stars circling above the head."""
    cell = 2.0
    center = QPointF(0, r.top() - 6)
    for k in range(3):
        angle = pose.anim_t * 4 + k * 2 * math.pi / 3
        pos = center + QPointF(math.cos(angle) * 40, math.sin(angle) * 8)
        origin = QPointF(round(pos.x()) - 1.5 * cell, round(pos.y()) - 1.5 * cell)
        color = QColor(STAR_COLOR)
        color.setAlphaF(min(1.0, pose.dizzy))
        outline = QColor(BLACK)
        outline.setAlphaF(min(1.0, pose.dizzy))
        p.setPen(Qt.PenStyle.NoPen)
        for cells, c in ((_expand(STAR), outline), (STAR, color)):
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            for cx, cy in cells:
                path.addRect(QRectF(origin.x() + cx * cell, origin.y() + cy * cell, cell, cell))
            p.setBrush(c)
            p.drawPath(path)


# --- shutter mouth ----------------------------------------------------------

def _bevel(p: QPainter, rect: QRectF, light: QColor, dark: QColor, width: float = 1.5) -> None:
    """Win95 bevel: light top-left, shadow bottom-right (reversed for sunken)."""
    h = width / 2
    p.setPen(_line_pen(light, width))
    p.drawLine(QPointF(rect.left() + h, rect.bottom() - h), QPointF(rect.left() + h, rect.top() + h))
    p.drawLine(QPointF(rect.left() + h, rect.top() + h), QPointF(rect.right() - h, rect.top() + h))
    p.setPen(_line_pen(dark, width))
    p.drawLine(QPointF(rect.right() - h, rect.top() + h), QPointF(rect.right() - h, rect.bottom() - h))
    p.drawLine(QPointF(rect.right() - h, rect.bottom() - h), QPointF(rect.left() + h, rect.bottom() - h))


def _draw_shutter(p: QPainter, skin: Skin, r: QRectF, pose: Pose) -> None:
    top = r.bottom() - SHUTTER_H
    closed_left = -SHUTTER_W / 2
    open_left = closed_left + SHUTTER_TRAVEL

    # Groove the shutter slides in. It's the same plastic inside, so a closed mouth
    # reads as closed rather than as a hole.
    track = QRectF(closed_left - 1.5, top - 1.5, SHUTTER_W + SHUTTER_TRAVEL + 3, SHUTTER_H + 6)
    p.setPen(QPen(skin.body_dark, 1.2))
    p.setBrush(skin.body)
    p.drawRect(track)

    # The "mouth": darkness, pixel teeth on top, magnetic disk tongue below.
    cavity = QRectF(0, top + 4, CAVITY_W, CAVITY_H)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BLACK)
    p.drawRect(cavity)
    p.setBrush(MEDIA)
    p.drawRect(QRectF(cavity.left(), cavity.bottom() - 8, cavity.width(), 8))
    p.setBrush(_dither(BLACK, 110))
    p.drawRect(QRectF(cavity.left(), cavity.bottom() - 8, cavity.width(), 8))
    p.setBrush(WHITE)
    for i in range(4):
        p.drawRect(QRectF(cavity.left() + 0.5 + i * 3.6, cavity.top(), 3, 3.5))

    # Metal shutter: a raised Win95 button with a sunken window.
    plate_left = closed_left + pose.shutter * SHUTTER_TRAVEL
    plate = QRectF(plate_left, top, SHUTTER_W, SHUTTER_H + 4)
    slot = QRectF(plate_left + (cavity.left() - open_left), cavity.top(), CAVITY_W, CAVITY_H)
    plate_path = QPainterPath()
    plate_path.addRect(plate)
    slot_path = QPainterPath()
    slot_path.addRect(slot)
    plate_path = plate_path.subtracted(slot_path)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(SILVER)
    p.drawPath(plate_path)

    p.save()
    p.setClipPath(plate_path, Qt.ClipOperation.IntersectClip)
    p.setBrush(Qt.BrushStyle.NoBrush)
    _bevel(p, plate.adjusted(0.6, 0.6, -0.6, 0), WHITE, GRAY, 2)
    _bevel(p, slot.adjusted(-2, -2, 2, 2), GRAY, WHITE, 1.6)
    p.restore()

    p.setPen(QPen(BLACK, 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(plate_path)


# --- legs -------------------------------------------------------------------

def _draw_legs(p: QPainter, pose: Pose) -> None:
    for side in (-1, 1):
        lx = side * (18 + pose.sit * 20)  # boots spread apart when sitting
        lift = max(0.0, side * pose.step) * 4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BLACK)
        p.drawRect(QRectF(lx - 1.75, -LEG_H - 2, 3.5, LEG_H - 4 - lift))

        boot = QRectF(lx - 7 + side * 2, -8.5 - lift, 14, 8)
        sole = QRectF(boot.left(), boot.bottom() - 2.4, boot.width(), 2.4)
        path = QPainterPath()
        path.addRoundedRect(boot, 3.5, 3.5)
        p.setBrush(BOOT)
        p.drawPath(path)
        p.save()
        p.setClipPath(path, Qt.ClipOperation.IntersectClip)
        p.setBrush(WHITE)
        p.drawRect(sole)
        toe = QRectF(boot.right() - 5 if side > 0 else boot.left(), boot.top(), 5, boot.height())
        p.drawRect(toe)
        p.restore()
        p.setPen(QPen(BLACK, 1.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


# --- arms -------------------------------------------------------------------

ARM_LEN = 32
ARM_W = 3.6
HAND = 9.0
SPRAY_CAN = QColor("#E8E8E8")


def hand_offset(pose: Pose, lower: bool = False) -> QPointF:
    """Where a hand is, relative to the point between the boots (used for stunts too)."""
    side = pose.arm_side
    shoulder = QPointF(side * (BODY_W / 2 - 4), -TOTAL_H - pose.lift + round(pose.sit * SIT_DROP) + 64)
    if lower:
        shoulder += QPointF(0, 10)
    angle = math.radians(pose.arm_lift * 80)
    length = (ARM_LEN - (4 if lower else 0)) * pose.arms
    return shoulder + QPointF(side * math.cos(angle) * (length + 4),
                              -math.sin(angle) * length + pose.arm_wiggle * 3 * (-1 if lower else 1))


def _draw_arms(p: QPainter, r: QRectF, pose: Pose) -> None:
    """Stick arms with white cartoon mittens, both on one side (pulling, shoving, spraying)."""
    side = pose.arm_side
    arms = (False,) if pose.spray is not None else (True, False)  # the lower arm first: it's behind
    for lower in arms:
        shoulder = QPointF(side * (BODY_W / 2 - 4), r.top() + 64 + (10 if lower else 0))
        hand = hand_offset(pose, lower)
        pen = QPen(BLACK, ARM_W)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(shoulder, hand)
        if pose.spray is not None:
            _draw_spray_can(p, hand, side, pose.spray)
        p.setPen(QPen(BLACK, 1.3))
        p.setBrush(WHITE)
        p.drawRoundedRect(QRectF(hand.x() - HAND / 2, hand.y() - HAND / 2, HAND, HAND), 2.5, 2.5)


def _draw_spray_can(p: QPainter, hand: QPointF, side: int, color: QColor) -> None:
    can = QRectF(hand.x() - 3.5, hand.y() - 14, 7, 13)
    p.setPen(QPen(BLACK, 1.2))
    p.setBrush(color)
    p.drawRect(can)
    p.setBrush(SPRAY_CAN)
    p.drawRect(QRectF(can.left() + 1, can.top() - 3, 5, 3))
    p.setBrush(BLACK)
    p.drawRect(QRectF(can.center().x() + (1 if side > 0 else -3), can.top() - 5, 2, 2))


# --- parachute --------------------------------------------------------------

CHUTE_W = 112
CHUTE_H = 46
CHUTE_GAP = 34      # from the top of the body to the canopy hem
AIRMAIL_BLUE = QColor("#1F3FA8")
# Canopy gores in airmail envelope colors; the center one carries a stamp.
CHUTE_GORES = (RED, PAPER, AIRMAIL_BLUE, QColor("#FBF7EC"), AIRMAIL_BLUE, PAPER, RED)


def _ease_out_back(t: float) -> float:
    """Overshooting deployment: the canopy pops open and settles."""
    c = 1.9
    t -= 1
    return 1 + (c + 1) * t ** 3 + c * t ** 2


def _draw_parachute(p: QPainter, r: QRectF, chute: float, phase: float) -> None:
    n = len(CHUTE_GORES)
    sx = max(0.05, _ease_out_back(chute))
    sy = chute ** 0.6
    hem_y = r.top() - CHUTE_GAP * chute
    half = CHUTE_W / 2 * sx
    height = CHUTE_H * sy * (1 + 0.03 * math.sin(phase * 3))  # the canopy "breathes"
    apex = QPointF(0, hem_y - height)
    hem = [QPointF(-half + i * 2 * half / n, hem_y) for i in range(n + 1)]

    # Suspension lines fan out from the hem to two points at the body's corners.
    left_anchor = QPointF(r.left() + 10, r.top() + 1)
    right_anchor = QPointF(r.right() - CUT - 2, r.top() + 1)
    p.setPen(QPen(QColor("#202020"), 0.9))
    for i, point in enumerate(hem):
        p.drawLine(point, left_anchor if i <= n // 2 else right_anchor)
    p.setPen(QPen(BLACK, 2.2))
    for anchor in (left_anchor, right_anchor):
        p.drawLine(anchor, anchor + QPointF(0, -4))  # risers

    def seam_ctrl(x: float) -> QPointF:
        return QPointF(x, hem_y - height * 1.02)

    def scallop_ctrl(i: int) -> QPointF:
        # The hem between lines bows upward and flutters in the wind.
        depth = (4 + 1.6 * math.sin(phase * 7 + i * 1.3)) * sy
        mid = (hem[i].x() + hem[i + 1].x()) / 2
        return QPointF(mid, hem_y - 2 * depth)

    dome = QPainterPath(hem[0])
    dome.cubicTo(QPointF(-half, hem_y - height * 4 / 3), QPointF(half, hem_y - height * 4 / 3), hem[-1])
    for i in range(n - 1, -1, -1):
        dome.quadTo(scallop_ctrl(i), hem[i])
    dome.closeSubpath()

    p.save()
    p.setClipPath(dome, Qt.ClipOperation.IntersectClip)
    p.setPen(Qt.PenStyle.NoPen)
    for i, color in enumerate(CHUTE_GORES):
        gore = QPainterPath(hem[i])
        gore.quadTo(seam_ctrl(hem[i].x()), apex)
        gore.quadTo(seam_ctrl(hem[i + 1].x()), hem[i + 1])
        gore.quadTo(scallop_ctrl(i), hem[i])
        p.setBrush(color)
        p.drawPath(gore)

    # Win95-style volume: dithering on the right side, a hard highlight on the left.
    p.setBrush(_dither(BLACK, 120))
    p.setBrushOrigin(0, 0)
    p.drawRect(QRectF(half * 0.45, apex.y() - 2, half, height + 4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    highlight = QPainterPath(QPointF(-half + 6, hem_y - 6))
    highlight.cubicTo(QPointF(-half + 5, hem_y - height * 1.05), QPointF(-half * 0.25, hem_y - height * 1.12),
                      QPointF(-half * 0.05, apex.y() + 4))
    p.setPen(_line_pen(WHITE, 2))
    p.drawPath(highlight)

    # Seams between gores.
    p.setPen(QPen(BLACK, 0.9))
    for point in hem[1:-1]:
        seam = QPainterPath(point)
        seam.quadTo(seam_ctrl(point.x()), apex)
        p.drawPath(seam)

    # Stamp on the center gore.
    if chute > 0.6:
        stamp = QRectF(-4.5 * sx, hem_y - height * 0.62, 9 * sx, 10 * sy)
        p.setPen(QPen(WHITE, 1.2, Qt.PenStyle.DotLine))
        p.setBrush(RED)
        p.drawRect(stamp)
    p.restore()

    p.setPen(QPen(BLACK, 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(dome)
    # Vent cap at the apex.
    p.setBrush(PAPER)
    p.drawEllipse(apex + QPointF(0, 1.5), 5 * sx, 2.5 * sy)
