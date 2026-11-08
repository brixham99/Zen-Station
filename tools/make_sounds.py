"""Synthesise Zen Station's menu sounds into assets/sounds/*.wav (48 kHz, 16-bit).

Run:  python -m tools.make_sounds
Soft, bell-like tones on a pentatonic scale in D, so every sound sits together.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

RATE = 48000
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"

# D major pentatonic, octave 5 and up
N = {"D5": 587.33, "E5": 659.25, "F#5": 739.99, "A5": 880.0, "B5": 987.77,
     "D6": 1174.66, "E6": 1318.51, "F#6": 1479.98, "A6": 1760.0, "A4": 440.0,
     "D4": 293.66, "F#4": 369.99, "A3": 220.0, "D3": 146.83}


def t(sec: float) -> np.ndarray:
    return np.arange(int(RATE * sec)) / RATE


def bell(freq: float, sec: float, decay: float = 8.0, bright: float = 0.35) -> np.ndarray:
    x = t(sec)
    env = np.exp(-decay * x) * np.minimum(1.0, x / 0.003)  # 3 ms soft attack
    tone = (np.sin(2 * np.pi * freq * x)
            + bright * np.sin(2 * np.pi * freq * 2.0 * x) * np.exp(-decay * 2 * x)
            + 0.12 * np.sin(2 * np.pi * freq * 3.01 * x) * np.exp(-decay * 3 * x))
    return tone * env


def place(buf: np.ndarray, sig: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * RATE)
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def blank(sec: float) -> np.ndarray:
    return np.zeros(int(RATE * sec))


def write(name: str, mono: np.ndarray, peak: float = 0.5, width: float = 0.0) -> None:
    mono = mono / (np.max(np.abs(mono)) or 1.0) * peak
    fade = min(len(mono), int(0.01 * RATE))
    mono[-fade:] *= np.linspace(1, 0, fade)
    # gentle stereo: a 0.4 ms delay on one side when width > 0
    d = int(width * RATE)
    right = np.concatenate([np.zeros(d), mono[: len(mono) - d]]) if d else mono
    st = np.stack([mono, right], axis=1)
    data = (st * 32767).astype("<i2")
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def main() -> None:
    # move: a tiny soft tick
    write("move", bell(N["A5"], 0.09, decay=45, bright=0.2), peak=0.28)

    # select / confirm: two notes up
    b = blank(0.35)
    place(b, bell(N["D6"], 0.3, 14), 0.0)
    place(b, bell(N["A6"], 0.3, 12), 0.06, 0.8)
    write("select", b, peak=0.4, width=0.0004)

    # back / cancel: two notes down
    b = blank(0.35)
    place(b, bell(N["A5"], 0.3, 14), 0.0)
    place(b, bell(N["D5"], 0.3, 12), 0.07, 0.9)
    write("back", b, peak=0.35, width=0.0004)

    # launch: rising arpeggio with a soft shimmer tail
    b = blank(1.3)
    for k, n in enumerate(["D5", "F#5", "A5", "D6", "F#6", "A6"]):
        place(b, bell(N[n], 1.0, 5.5, 0.4), k * 0.07, 0.85)
    x = t(1.3)
    shimmer = np.sin(2 * np.pi * N["D6"] * x) * np.sin(2 * np.pi * 6 * x) * np.exp(-3 * x) * np.minimum(1, x / 0.3)
    place(b, shimmer, 0.0, 0.25)
    write("launch", b, peak=0.5, width=0.0004)

    # update started: a soft question-like blip
    b = blank(0.3)
    place(b, bell(N["E5"], 0.25, 16), 0.0)
    place(b, bell(N["A5"], 0.25, 16), 0.08, 0.7)
    write("update_start", b, peak=0.3)

    # updated: happy three-note chime
    b = blank(0.9)
    for k, n in enumerate(["D6", "F#6", "A6"]):
        place(b, bell(N[n], 0.8, 6.5), k * 0.11, 0.9)
    write("updated", b, peak=0.45, width=0.0004)

    # up to date: one calm bell with its fifth
    b = blank(0.8)
    place(b, bell(N["A5"], 0.8, 6.0), 0.0)
    place(b, bell(N["E6"], 0.8, 7.0), 0.0, 0.35)
    write("up_to_date", b, peak=0.38)

    # error / offline / not available: two low, dull notes
    b = blank(0.45)
    place(b, bell(N["A3"], 0.2, 18, 0.6), 0.0)
    place(b, bell(N["A3"], 0.2, 18, 0.6), 0.16)
    write("error", b, peak=0.4)

    # power-off question: a warm, lower two-note
    b = blank(0.6)
    place(b, bell(N["F#4"], 0.55, 7), 0.0)
    place(b, bell(N["D4"], 0.55, 7), 0.12, 0.9)
    write("power", b, peak=0.4)

    # start-up: slow soft chord bloom
    b = blank(2.0)
    for k, n in enumerate(["D4", "A4", "D5", "F#5", "A5"]):
        place(b, bell(N[n], 1.8, 2.6, 0.25), k * 0.12, 0.7)
    write("startup", b, peak=0.45, width=0.0004)

    print("Wrote", ", ".join(sorted(p.stem for p in OUT.glob("*.wav"))))


if __name__ == "__main__":
    main()
