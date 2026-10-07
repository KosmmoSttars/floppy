"""Floppy plastic palettes.

The body is drawn like a Windows 95 icon: flat fill, hard bevels
(body_light top-left, body_dark bottom-right) and dithering instead of gradients.
"""

from dataclasses import dataclass

from PyQt6.QtGui import QColor


def _c(hex_color: str, alpha: int = 255) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


@dataclass(frozen=True)
class Skin:
    key: str
    title: str
    body: QColor
    body_light: QColor
    body_dark: QColor
    brow: QColor          # eyebrows and closed eyes; must read well on the body
    translucent: bool = False


SKINS: dict[str, Skin] = {
    s.key: s
    for s in (
        Skin(
            key="black",
            title="Classic Stealth Black",
            body=_c("#2D2D33"),
            body_light=_c("#6B6B76"),
            body_dark=_c("#000000"),
            brow=_c("#F0F0F0"),  # eyebrows drawn on with correction fluid
        ),
        Skin(
            key="beige",
            title="IBM Vintage Beige",
            body=_c("#D5CAA2"),
            body_light=_c("#F6F0DA"),
            body_dark=_c("#8C7E55"),
            brow=_c("#2A2418"),
        ),
        Skin(
            key="neon_blue",
            title="Cyber Neon: Atomic Blue",
            body=_c("#1E7BFF", 150),
            body_light=_c("#B8DCFF", 210),
            body_dark=_c("#04205E", 190),
            brow=_c("#04164A"),
            translucent=True,
        ),
        Skin(
            key="neon_purple",
            title="Cyber Neon: Purple Haze",
            body=_c("#A23BFF", 150),
            body_light=_c("#E6C4FF", 210),
            body_dark=_c("#2E0566", 190),
            brow=_c("#240450"),
            translucent=True,
        ),
    )
}

DEFAULT_SKIN = "black"
