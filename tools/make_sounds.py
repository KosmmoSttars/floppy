"""Synthesizes Floppy's retro sound effects into assets/sounds/.

All sounds are generated from scratch (no samples), so they are free to ship.
Run again any time to restore the defaults:

    python tools/make_sounds.py [--force]

Any WAV file can be replaced with your own recording (16-bit PCM WAV) without changing code.
"""

import math
import random
import struct
import sys
import wave
from pathlib import Path

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


# --- building blocks --------------------------------------------------------

def silence(seconds: float) -> list[float]:
    return [0.0] * int(seconds * SR)


def mix_into(buf: list[float], part: list[float], at: float, gain: float = 1.0) -> None:
    start = int(at * SR)
    if start + len(part) > len(buf):
        buf.extend([0.0] * (start + len(part) - len(buf)))
    for i, v in enumerate(part):
        buf[start + i] += v * gain


def damped(freq: float, seconds: float, tau: float, phase: float = 0.0) -> list[float]:
    """A decaying sine: the basic 'ping' of a struck piece of metal."""
    n = int(seconds * SR)
    return [math.sin(2 * math.pi * freq * i / SR + phase) * math.exp(-i / SR / tau) for i in range(n)]


def noise_burst(seconds: float, tau: float, smooth: float = 0.0) -> list[float]:
    """Decaying noise; smooth (0..1) is a one-pole low-pass amount."""
    out, prev = [], 0.0
    for i in range(int(seconds * SR)):
        v = random.uniform(-1, 1)
        prev = prev * smooth + v * (1 - smooth)
        out.append(prev * math.exp(-i / SR / tau))
    return out


def square(freq_at, seconds: float, duty: float = 0.5) -> list[float]:
    """PC-speaker style square wave; freq_at(t) returns the frequency at time t."""
    out, phase = [], 0.0
    for i in range(int(seconds * SR)):
        phase = (phase + freq_at(i / SR) / SR) % 1.0
        out.append(1.0 if phase < duty else -1.0)
    return out


def fade(buf: list[float], fade_in: float = 0.004, fade_out: float = 0.01) -> list[float]:
    n_in, n_out = int(fade_in * SR), int(fade_out * SR)
    for i in range(min(n_in, len(buf))):
        buf[i] *= i / n_in
    for i in range(min(n_out, len(buf))):
        buf[-1 - i] *= i / n_out
    return buf


def save(name: str, buf: list[float], peak: float = 0.89) -> None:
    top = max(1e-9, max(abs(v) for v in buf))
    data = b"".join(struct.pack("<h", int(v / top * peak * 32767)) for v in buf)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)


# --- the sounds -------------------------------------------------------------

def floppy_seek() -> list[float]:
    """Stepper motor grinding across tracks: 'brrrt... brrrrt... brt'."""
    buf = silence(0.95)
    t = 0.02
    for burst_len, rate in ((0.24, 260), (0.34, 330), (0.12, 220)):
        end = t + burst_len
        while t < end:
            click = damped(1150, 0.006, 0.0014)
            ring = damped(2350, 0.004, 0.0008, 1.0)
            grit = noise_burst(0.003, 0.0008)
            mix_into(buf, click, t, 0.7)
            mix_into(buf, ring, t, 0.35)
            mix_into(buf, grit, t, 0.25)
            t += 1 / rate * random.uniform(0.9, 1.1)
        # Motor hum under the burst.
        hum = square(lambda _t: 150, burst_len)
        mix_into(buf, [v * 0.05 for v in hum], end - burst_len)
        t = end + random.uniform(0.06, 0.09)
    return fade(buf)


def floppy_read() -> list[float]:
    """Spindle whine plus the crackle of sectors being read."""
    seconds = 1.4
    buf = []
    for i in range(int(seconds * SR)):
        tt = i / SR
        f = 300 * (1 + 0.004 * math.sin(2 * math.pi * 5 * tt))
        whine = sum(math.sin(2 * math.pi * f * k * tt) / k for k in (1, 2, 3, 5))
        buf.append(whine * 0.10)
    t = 0.05
    while t < seconds - 0.05:
        mix_into(buf, noise_burst(0.0012, 0.0004), t, random.uniform(0.15, 0.35))
        t += random.expovariate(70)
    for k in range(int(seconds / 0.19)):
        mix_into(buf, damped(1300, 0.006, 0.0015), 0.1 + k * 0.19, 0.5)
    return fade(buf, 0.08, 0.15)


def win95_error() -> list[float]:
    """An original dissonant 'something went wrong' chord (not the real Windows sound)."""
    seconds = 0.75
    notes = ((440.0, 1.0), (622.25, 0.8), (164.81, 0.6))   # A4 + D#5 tritone over E3
    buf = []
    for i in range(int(seconds * SR)):
        tt = i / SR
        env = (1 - math.exp(-tt / 0.004)) * math.exp(-tt / 0.28)
        vib = 1 + 0.003 * math.sin(2 * math.pi * 6 * tt)
        s = 0.0
        for f, g in notes:
            s += g * (math.sin(2 * math.pi * f * vib * tt) + 0.3 * math.sin(4 * math.pi * f * vib * tt))
        buf.append(s * env)
    return fade(buf)


def bsod_beep() -> list[float]:
    """Long, low PC-speaker beep."""
    return fade([v * 0.5 for v in square(lambda _t: 196, 1.25)], 0.01, 0.02)


def floppy_eject() -> list[float]:
    """Latch click, spring 'boing', and the clunk of the disk popping out."""
    buf = silence(0.45)
    mix_into(buf, noise_burst(0.006, 0.0015), 0.0, 0.8)
    mix_into(buf, damped(2700, 0.03, 0.008), 0.0, 0.6)
    spring = []
    for i in range(int(0.08 * SR)):
        tt = i / SR
        f = 520 - 1800 * tt
        spring.append(math.sin(2 * math.pi * f * tt) * math.exp(-tt / 0.03))
    mix_into(buf, spring, 0.06, 0.5)
    mix_into(buf, damped(110, 0.08, 0.035), 0.12, 0.9)
    mix_into(buf, noise_burst(0.05, 0.015, 0.85), 0.12, 0.6)
    return fade(buf)


def ding() -> list[float]:
    """A bright 'job done' bell."""
    f = 1568.0
    buf = []
    for i in range(int(0.9 * SR)):
        tt = i / SR
        s = (math.sin(2 * math.pi * f * tt) * math.exp(-tt / 0.35)
             + 0.5 * math.sin(2 * math.pi * 2.0 * f * tt) * math.exp(-tt / 0.18)
             + 0.25 * math.sin(2 * math.pi * 2.76 * f * tt) * math.exp(-tt / 0.08))
        buf.append(s * (1 - math.exp(-tt / 0.002)))
    return fade(buf)


def scared_beep() -> list[float]:
    """Two panicky upward chirps from the PC speaker."""
    buf = silence(0.36)
    mix_into(buf, square(lambda t: 700 + 1200 * t / 0.14, 0.14), 0.0, 0.35)
    mix_into(buf, square(lambda t: 900 + 1400 * t / 0.14, 0.14), 0.18, 0.35)
    return fade(buf)


def shutter_clack() -> list[float]:
    """Short metal snap of the shutter slamming shut."""
    buf = silence(0.09)
    mix_into(buf, noise_burst(0.003, 0.0008), 0.0, 0.7)
    mix_into(buf, damped(3200, 0.05, 0.012), 0.0, 0.6)
    mix_into(buf, damped(5100, 0.03, 0.006, 0.7), 0.0, 0.3)
    return fade(buf, 0.0005, 0.01)


def mine_boom() -> list[float]:
    """A crunchy 8-bit explosion: a falling thump plus rumbling noise."""
    seconds = 1.1
    buf = []
    lp = 0.0
    phase = 0.0
    for i in range(int(seconds * SR)):
        tt = i / SR
        phase += (40 + 140 * math.exp(-tt / 0.06)) / SR
        thump = math.sin(2 * math.pi * phase) * math.exp(-tt / 0.25)
        lp = lp * 0.93 + random.uniform(-1, 1) * 0.07
        rumble = lp * 5 * math.exp(-tt / 0.35)
        crackle = random.uniform(-1, 1) * math.exp(-tt / 0.04) * 0.6
        buf.append(thump + rumble + crackle)
    # Bit-crush for that cheap sound card feel.
    return fade([round(v * 12) / 12 for v in buf], 0.001, 0.1)


def spray_hiss() -> list[float]:
    """Spray can: 'pssshhhh' (high-passed noise with a little flutter)."""
    seconds = 1.2
    buf, prev = [], 0.0
    for i in range(int(seconds * SR)):
        tt = i / SR
        v = random.uniform(-1, 1)
        hp = v - prev
        prev = v
        env = min(1.0, tt / 0.04) * (1 - max(0.0, tt - 0.9) / 0.3)
        flutter = 1 + 0.15 * math.sin(2 * math.pi * 11 * tt)
        buf.append(hp * env * flutter * 0.5)
    return fade(buf, 0.005, 0.05)


def clone_pop() -> list[float]:
    """Ctrl+V: a bright rising 'bloop' with a click."""
    buf = silence(0.22)
    blip, phase = [], 0.0
    for i in range(int(0.14 * SR)):
        tt = i / SR
        phase += (320 + 2400 * tt) / SR
        blip.append(math.sin(2 * math.pi * phase) * math.exp(-tt / 0.06))
    mix_into(buf, blip, 0.0, 0.8)
    mix_into(buf, noise_burst(0.004, 0.001), 0.0, 0.4)
    mix_into(buf, damped(1760, 0.12, 0.04), 0.05, 0.3)
    return fade(buf)


def recycle_bin() -> list[float]:
    """Something crumples into a wire wastebasket: rustle, then a hollow metal 'dunk'."""
    buf = silence(0.7)
    t = 0.0
    while t < 0.3:
        mix_into(buf, noise_burst(random.uniform(0.004, 0.012), 0.003, 0.3), t, random.uniform(0.3, 0.8))
        t += random.uniform(0.012, 0.035)
    mix_into(buf, damped(196, 0.4, 0.12), 0.28, 0.9)
    mix_into(buf, damped(467, 0.3, 0.07), 0.28, 0.5)
    mix_into(buf, damped(1210, 0.15, 0.03), 0.28, 0.3)
    return fade(buf)


def chiptune_loop() -> list[float]:
    """An original 8-second chiptune loop (120 bpm): Am - F - C - G, square lead, bass and drums."""
    bpm = 120
    beat = 60 / bpm
    bars = 4
    seconds = bars * 4 * beat
    buf = [0.0] * int(seconds * SR)

    def note_freq(n: int) -> float:
        return 440.0 * 2 ** ((n - 69) / 12)

    def tone(freq: float, length: float, duty: float, gain: float, at: float, decay: float = 0.25) -> None:
        part, phase = [], 0.0
        for i in range(int(length * SR)):
            tt = i / SR
            phase = (phase + freq / SR) % 1.0
            env = min(1.0, tt / 0.004) * math.exp(-tt / decay) * min(1.0, (length - tt) / 0.01)
            part.append((1.0 if phase < duty else -1.0) * env)
        mix_into(buf, part, at, gain)

    chords = ((57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62))      # Am F C G
    lead = (
        (76, 0, 1), (74, 1, 0.5), (72, 1.5, 0.5), (74, 2, 1), (76, 3, 1),
        (77, 4, 1), (76, 5, 0.5), (74, 5.5, 0.5), (72, 6, 2),
        (72, 8, 1), (74, 9, 0.5), (76, 9.5, 0.5), (79, 10, 1), (76, 11, 1),
        (74, 12, 1.5), (72, 13.5, 0.5), (71, 14, 1), (74, 15, 1),
    )
    for bar, chord in enumerate(chords):
        start = bar * 4 * beat
        for k in range(8):   # bass on eighths, root and fifth
            n = chord[0] - 12 + (7 if k % 4 == 2 else 0)
            tone(note_freq(n), beat / 2 * 0.9, 0.5, 0.22, start + k * beat / 2, 0.15)
        for k in range(16):  # arpeggio on sixteenths
            n = chord[k % 3] + 12
            tone(note_freq(n), beat / 4 * 0.8, 0.125, 0.06, start + k * beat / 4, 0.05)
        for k in range(4):   # kick on beats, hi-hat on off-beats, snare on 2 and 4
            mix_into(buf, damped(55, 0.12, 0.05), start + k * beat, 0.5)
            mix_into(buf, noise_burst(0.03, 0.008), start + k * beat + beat / 2, 0.12)
            if k % 2:
                mix_into(buf, noise_burst(0.12, 0.04, 0.4), start + k * beat, 0.25)
    for n, at, length in lead:
        tone(note_freq(n), length * beat * 0.92, 0.25, 0.16, at * beat, 0.6)
    return buf[:int(seconds * SR)]   # exact length so the loop is seamless


SOUNDS = {
    "floppy_seek.wav": floppy_seek,
    "floppy_read.wav": floppy_read,
    "win95_error.wav": win95_error,
    "bsod_beep.wav": bsod_beep,
    "floppy_eject.wav": floppy_eject,
    "ding.wav": ding,
    "scared_beep.wav": scared_beep,
    "shutter_clack.wav": shutter_clack,
    "mine_boom.wav": mine_boom,
    "spray_hiss.wav": spray_hiss,
    "clone_pop.wav": clone_pop,
    "recycle_bin.wav": recycle_bin,
    "chiptune_loop.wav": chiptune_loop,
}


def main() -> None:
    force = "--force" in sys.argv
    random.seed(144)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        if (OUT / name).exists() and not force:
            print(f"keep   {name} (exists; use --force to regenerate)")
            continue
        save(name, make())
        print(f"wrote  {name}")


if __name__ == "__main__":
    main()
