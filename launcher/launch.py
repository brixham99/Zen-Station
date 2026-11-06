"""Launch games / Kodi as subprocesses and return when they exit."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import GameEntry


def python_for_games() -> str:
    return os.environ.get("GAMESBOX_PYTHON", sys.executable)


def launch_game(game: GameEntry, games_dir: Path) -> int:
    path = game.path_under(games_dir)
    entry = path / game.entry
    if not entry.is_file():
        raise FileNotFoundError(f"Missing {entry}")
    env = os.environ.copy()
    # Let the game open its own display; clear dummy drivers if set by selftest
    env.pop("SDL_VIDEODRIVER", None)
    env.pop("SDL_AUDIODRIVER", None)
    proc = subprocess.run(
        [python_for_games(), game.entry],
        cwd=str(path),
        env=env,
        check=False,
    )
    return int(proc.returncode)


def kodi_available() -> bool:
    return shutil.which("kodi") is not None or shutil.which("kodi-standalone") is not None


def launch_kodi() -> int:
    cmd = shutil.which("kodi-standalone") or shutil.which("kodi")
    if not cmd:
        raise FileNotFoundError("Kodi is not installed")
    env = os.environ.copy()
    env.pop("SDL_VIDEODRIVER", None)
    env.pop("SDL_AUDIODRIVER", None)
    return int(subprocess.run([cmd], env=env, check=False).returncode)


def power_off() -> None:
    subprocess.run(["systemctl", "poweroff"], check=False)


def exit_to_desktop() -> None:
    """Caller should quit the pygame loop; this is a no-op helper."""
    return
