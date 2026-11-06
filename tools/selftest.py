#!/usr/bin/env python3
"""Headless self-test and screenshot pass for Games Box."""
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
from launcher.controllers import ACT_CONFIRM, ACT_LEFT, ACT_RIGHT, ACT_UPDATE, ControllerHub  # noqa: E402
from launcher.main import main as launcher_main  # noqa: E402
from launcher.ui import HomeScreen  # noqa: E402
from launcher.updates import UpdateService  # noqa: E402


def shot_dir() -> Path:
    env = os.environ.get("GAMESBOX_SHOTS")
    if env:
        p = Path(env)
    elif Path("/workspace").is_dir():
        p = Path("/workspace/gamesbox_shots")
    else:
        p = ROOT / "shots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_extended_config(path: Path, games_dir: Path) -> None:
    """Real four games + four fake entries to exercise scrolling."""
    base = json.loads((ROOT / "games.json").read_text())
    base["settings"]["games_dir"] = str(games_dir)
    extras = [
        {"id": "robo-rally", "name": "Robo Rally", "repo": "", "branch": "main", "entry": "game.py", "folder": "Robo-Rally"},
        {"id": "hedgerow", "name": "Hedgerow Heroes", "repo": "", "branch": "main", "entry": "game.py", "folder": "Hedgerow"},
        {"id": "lantern", "name": "Lantern Run", "repo": "", "branch": "main", "entry": "game.py", "folder": "Lantern-Run"},
        {"id": "starferry", "name": "Star Ferry", "repo": "", "branch": "main", "entry": "game.py", "folder": "Star-Ferry"},
    ]
    base["games"] = list(base["games"]) + extras
    path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def run_shots(cfg_path: Path) -> list[Path]:
    out = shot_dir()
    shots: list[Path] = []

    def run(name: str, extra: list[str]) -> Path:
        dest = out / name
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
        shots.append(dest)
        print("wrote", dest, dest.stat().st_size)
        return dest

    run("01_home_daleks.png", ["--select", "0"])
    run(
        "02_home_haunted_update.png",
        ["--select", "1", "--fake-update", "haunted"],
    )
    run("03_power_confirm.png", ["--select", "0", "--confirm-power"])
    # Many games: select a far tile so scroll + dots are visible
    run("04_scroll_many_games.png", ["--select", "6"])
    return shots


def test_navigation(cfg_path: Path) -> None:
    if pygame.get_init():
        pygame.quit()
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((1280, 720))
    cfg = load_config(cfg_path)
    ui = HomeScreen(cfg)
    assert len(ui.tiles) >= 8, len(ui.tiles)
    start = ui.state.selected
    ui.move(1)
    assert ui.state.selected == start + 1
    ui.move(-1)
    assert ui.state.selected == start
    # wrap
    ui.state.selected = len(ui.tiles) - 1
    ui.move(1)
    assert ui.state.selected == 0
    hub = ControllerHub()
    assert hub.hints.family in ("keyboard", "xbox", "playstation", "generic")
    # Simulate key events
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    assert ACT_RIGHT in hub.handle_event(ev)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_u)
    assert ACT_UPDATE in hub.handle_event(ev)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    assert ACT_CONFIRM in hub.handle_event(ev)
    print("navigation ok; tiles =", len(ui.tiles))
    pygame.quit()


def test_update_check_local(games_dir: Path) -> None:
    """Point at local clones under /workspace if present; expect quiet result."""
    cfg = load_config(ROOT / "games.json")
    cfg.settings.games_dir = games_dir
    svc = UpdateService(cfg)
    # Should not raise; offline or clean both fine
    try:
        svc.check_all()
    except Exception as e:  # noqa: BLE001
        raise AssertionError(e) from e
    print(
        "update check:",
        "offline=" + str(svc.status.offline),
        "avail=" + str(svc.status.available),
        "msg=" + repr(svc.status.message),
    )


def main() -> int:
    shots = shot_dir()
    print("shots ->", shots)
    with tempfile.TemporaryDirectory(prefix="gamesbox-") as tmp:
        tmp_path = Path(tmp)
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        # Symlink real local repos when available so thumbnails resolve
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

        cfg_path = tmp_path / "games.json"
        write_extended_config(cfg_path, games_dir)
        run_shots(cfg_path)
        test_navigation(cfg_path)
        # Update check against workspace /tmp clones
        test_update_check_local(games_dir)
    print("selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
