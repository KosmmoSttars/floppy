"""Floppy's expressions: eyelids, eyebrows and pupils, measured in eye-grid pixels."""

from dataclasses import dataclass


def _mix(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


@dataclass(frozen=True)
class Expression:
    lid: float = 0.0          # rows covered by the upper eyelid at the eye's center
    slant: float = 0.0        # >0: inner corners lower (angry), <0: higher (sad)
    lid_bottom: float = 0.0   # squint from below
    brow_left: float = 0.0    # left eyebrow raise, in rows
    brow_right: float = 0.0
    brow_tilt: float = 0.0    # >0: inner ends of the eyebrows lowered
    pupil: int = 3            # pupil size: 3 normal, 2 scared
    happy: bool = False       # arc eyes ^ ^
    dizzy: bool = False       # spiral eyes @ @

    def blend(self, other: "Expression", k: float) -> "Expression":
        return Expression(
            lid=_mix(self.lid, other.lid, k),
            slant=_mix(self.slant, other.slant, k),
            lid_bottom=_mix(self.lid_bottom, other.lid_bottom, k),
            brow_left=_mix(self.brow_left, other.brow_left, k),
            brow_right=_mix(self.brow_right, other.brow_right, k),
            brow_tilt=_mix(self.brow_tilt, other.brow_tilt, k),
            # Discrete features switch instantly, like a sprite frame change:
            # blending moves in small steps per frame, so a k > 0.5 threshold would never trigger.
            pupil=other.pupil,
            happy=other.happy,
            dizzy=other.dizzy,
        )


EXPRESSIONS: dict[str, Expression] = {
    "neutral": Expression(),
    # Default cheeky state: half-closed eyes, one eyebrow raised.
    "smug": Expression(lid=2.6, slant=-0.4, brow_left=1.1, brow_right=-0.6, brow_tilt=0.6),
    "angry": Expression(lid=2.2, slant=2.6, lid_bottom=0.6, brow_left=-1, brow_right=-1, brow_tilt=2.6),
    "scared": Expression(brow_left=2.2, brow_right=2.2, brow_tilt=-1.6, pupil=2),
    "happy": Expression(happy=True, brow_left=1.2, brow_right=1.2, brow_tilt=-0.4),
    "dizzy": Expression(dizzy=True, brow_left=1.4, brow_right=-0.4, brow_tilt=-1.0),
    "sneaky": Expression(lid=3.0, slant=0.9, brow_left=0.6, brow_right=-0.8, brow_tilt=1.2),
    # Eyes popping out: wide open with tiny pupils (O_O).
    "panic": Expression(brow_left=2.8, brow_right=2.8, brow_tilt=-2.2, pupil=1),
    "sleepy": Expression(lid=4.3, slant=-0.6, brow_left=-0.4, brow_right=-0.4, brow_tilt=-0.6),
}
