#!/usr/bin/env python3
"""Headless self-test and screenshot pass for Zen Station."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from launcher.config import load_config  # noqa: E402
from launcher.controllers import ACT_CONFIRM, ACT_RIGHT, ACT_UPDATE, ControllerHub  # noqa: E402
from launcher.main import main as launcher_main  # noqa: E402
from launcher.ui import HomeScreen  # noqa: E402
from launcher.updates import UpdateService  # noqa: E402


def shot_dir() -> Path:
    env = os.environ.get("ZENSTATION_SHOTS")
    if env:
        p = Path(env)
    elif Path("/workspace").is_dir():
        p = Path("/workspace/zenstation_shots")
    else:
        p = ROOT / "shots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def base_games(games_dir: Path) -> dict:
    raw = json.loads((ROOT / "games.json").read_text())
    raw["settings"]["games_dir"] = str(games_dir)
    return raw


def write_config(path: Path, games_dir: Path, *, extras: list | None = None, system: bool = False) -> None:
    """Write a games.json. Normal shots: 4 games only. system=True adds TV/Power/Exit via UI always —
    the UI always appends system tiles, so for '4 games only' screenshots we use a HomeScreen
    subclass... Actually UI always adds system tiles. For shots that should show only 4 game
    tiles, pass games and set env ZENSTATION_NO_SYSTEM=1 handled in ui.
    """
    raw = base_games(games_dir)
    if extras:
        raw["games"] = list(raw["games"]) + extras
    raw["settings"]["include_system_tiles"] = system
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def run_shot(name: str, cfg_path: Path, extra: list[str]) -> Path:
    dest = shot_dir() / name
    argv = [
        "--windowed",
        "--no-updates",
        "--config",
        str(cfg_path),
        "--screenshot",
        str(dest),
        *extra,
    ]
    rc = launcher_main(argv)
    assert rc == 0, f"launcher failed for {name}: {rc}"
    assert dest.is_file() and dest.stat().st_size > 1000, dest
    print("wrote", dest, dest.stat().st_size)
    return dest


def test_navigation(cfg_path: Path) -> None:
    if pygame.get_init():
        pygame.quit()
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((1280, 720))
    cfg = load_config(cfg_path)
    ui = HomeScreen(cfg)
    assert len(ui.tiles) >= 4, len(ui.tiles)
    start = ui.state.selected
    ui.move(1)
    assert ui.state.selected == start + 1
    ui.move(-1)
    assert ui.state.selected == start
    ui.state.selected = len(ui.tiles) - 1
    ui.move(1)
    assert ui.state.selected == 0
    hub = ControllerHub()
    hub.force_family("xbox")
    assert hub.hints.family == "xbox"
    assert "A" in hub.hints.confirm
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    assert ACT_RIGHT in hub.handle_event(ev)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_u)
    assert ACT_UPDATE in hub.handle_event(ev)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    assert ACT_CONFIRM in hub.handle_event(ev)
    print("navigation ok; tiles =", len(ui.tiles))
    pygame.quit()


def test_update_check_local(games_dir: Path) -> None:
    cfg = load_config(ROOT / "games.json")
    cfg.settings.games_dir = games_dir
    svc = UpdateService(cfg)
    svc.check_all()
    print(
        "update check:",
        "offline=" + str(svc.status.offline),
        "avail=" + str(svc.status.available),
        "msg=" + repr(svc.status.message),
    )


def main() -> int:
    out = shot_dir()
    print("shots ->", out)
    with tempfile.TemporaryDirectory(prefix="zenstation-") as tmp:
        tmp_path = Path(tmp)
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        for name, src in [
            ("Daleks-in-Hedges", Path("/workspace/Daleks-in-Hedges")),
            ("Haunted-Mansion", Path("/workspace/Haunted-Mansion")),
            ("Moon-Sweeper", Path("/tmp/ms-check")),
            ("Courtyard", Path("/tmp/ct-check")),
        ]:
            if src.is_dir():
                link = games_dir / name
                if not link.exists():
                    link.symlink_to(src)

        extras = [
            {"id": "robo-rally", "name": "Robo Rally", "repo": "", "branch": "main", "entry": "game.py", "folder": "Robo-Rally"},
            {"id": "hedgerow", "name": "Hedgerow Heroes", "repo": "", "branch": "main", "entry": "game.py", "folder": "Hedgerow"},
            {"id": "lantern", "name": "Lantern Run", "repo": "", "branch": "main", "entry": "game.py", "folder": "Lantern-Run"},
            {"id": "starferry", "name": "Star Ferry", "repo": "", "branch": "main", "entry": "game.py", "folder": "Star-Ferry"},
        ]

        # Normal: 4 games only, no system tiles (via settings flag)
        cfg_normal = tmp_path / "games_normal.json"
        write_config(cfg_normal, games_dir, system=False)

        # Many games
        cfg_many = tmp_path / "games_many.json"
        write_config(cfg_many, games_dir, extras=extras, system=False)

        # Full (with system tiles) for power-off
        cfg_full = tmp_path / "games_full.json"
        write_config(cfg_full, games_dir, system=True)

        run_shot("v2_01_home_daleks.png", cfg_normal, ["--select", "0"])
        run_shot(
            "v2_02_home_haunted_update.png",
            cfg_normal,
            ["--select", "1", "--fake-update", "haunted"],
        )
        # Power off is the first system tile after games when system=True:
        # indices: 0..3 games, 4 TV, 5 Power, 6 Exit
        run_shot("v2_03_power_confirm.png", cfg_full, ["--select", "5", "--confirm-power"])
        run_shot("v2_04_scroll_many_games.png", cfg_many, ["--select", "6"])
        run_shot(
            "v2_05_xbox_hints.png",
            cfg_normal,
            ["--select", "0", "--fake-pad", "xbox"],
        )

        test_navigation(cfg_many)
        test_update_check_local(games_dir)
    print("selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
