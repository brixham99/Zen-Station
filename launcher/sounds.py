"""Little menu sounds for the Zen Station home screen.

Sounds live in assets/sounds/*.wav (made by tools/make_sounds.py). Everything
here fails quietly: no audio device just means no sounds.
Background threads call queue(); the main loop calls pump() to play them.
"""
from __future__ import annotations

import os
import queue as _queue
from pathlib import Path

import pygame

from .config import ROOT

SOUND_DIR = ROOT / "assets" / "sounds"
NAMES = ("move", "select", "back", "launch", "update_start", "updated",
         "up_to_date", "error", "power", "startup")


class Sounds:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and not os.environ.get("ZENSTATION_NO_SOUND")
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._pending: _queue.SimpleQueue[str] = _queue.SimpleQueue()
        self.open()

    def open(self) -> None:
        if not self.enabled:
            return
        try:
            got = pygame.mixer.get_init()
            if got and got[0] != 48000:
                pygame.mixer.quit()  # pygame.init() opened it at 44.1 kHz
                got = None
            if not got:
                pygame.mixer.init(48000, -16, 2, 1024)
            for n in NAMES:
                p = SOUND_DIR / f"{n}.wav"
                if p.is_file():
                    self._sounds[n] = pygame.mixer.Sound(str(p))
        except pygame.error:
            self._sounds = {}

    def close(self) -> None:
        """Let go of the sound device so a game or Kodi can have it."""
        self._sounds = {}
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except pygame.error:
            pass

    def play(self, name: str) -> None:
        s = self._sounds.get(name)
        if s is not None:
            try:
                s.play()
            except pygame.error:
                pass

    def queue(self, name: str) -> None:
        self._pending.put(name)

    def pump(self) -> None:
        while True:
            try:
                self.play(self._pending.get_nowait())
            except _queue.Empty:
                return

    def busy(self) -> bool:
        try:
            return bool(pygame.mixer.get_init()) and pygame.mixer.get_busy()
        except pygame.error:
            return False
