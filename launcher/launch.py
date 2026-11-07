"""Launch games / Kodi as subprocesses and return when they exit."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import GameEntry


def python_for_games() -> str:
    return os.environ.get("ZENSTATION_PYTHON", sys.executable)


def _run(cmd, cwd=None, env=None, while_waiting=None) -> int:
    """Run a child process; call while_waiting() about 10x a second until it exits."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env)
    while True:
        try:
            return int(proc.wait(timeout=0.1))
        except subprocess.TimeoutExpired:
            if while_waiting:
                while_waiting()


def launch_game(game: GameEntry, games_dir: Path, while_waiting=None) -> int:
    path = game.path_under(games_dir)
    entry = path / game.entry
    if not entry.is_file():
        raise FileNotFoundError(f"Missing {entry}")
    env = os.environ.copy()
    # Let the game open its own display; clear dummy drivers if set by selftest
    env.pop("SDL_VIDEODRIVER", None)
    env.pop("SDL_AUDIODRIVER", None)
    env["ZENSTATION"] = "1"  # games run full screen and controller-friendly
    return _run([python_for_games(), game.entry], cwd=str(path), env=env,
                while_waiting=while_waiting)


def kodi_available() -> bool:
    return shutil.which("kodi") is not None or shutil.which("kodi-standalone") is not None


def launch_kodi(while_waiting=None) -> int:
    # Inside the kiosk display server Kodi runs as a normal window; on the
    # desktop, kodi-standalone is fine too.
    if os.environ.get("ZENSTATION_KIOSK"):
        cmd = shutil.which("kodi") or shutil.which("kodi-standalone")
    else:
        cmd = shutil.which("kodi-standalone") or shutil.which("kodi")
    if not cmd:
        raise FileNotFoundError("Kodi is not installed")
    env = os.environ.copy()
    env.pop("SDL_VIDEODRIVER", None)
    env.pop("SDL_AUDIODRIVER", None)
    return _run([cmd], env=env, while_waiting=while_waiting)


def power_off() -> None:
    subprocess.run(["systemctl", "poweroff"], check=False)


def exit_to_desktop() -> None:
    """Caller should quit the pygame loop; this is a no-op helper."""
    return
