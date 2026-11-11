"""Load games.json and resolve paths."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "games.json"


@dataclass
class GameEntry:
    id: str
    name: str
    repo: str
    branch: str = "main"
    entry: str = "game.py"
    folder: str = ""
    thumbnail: str | None = None
    kind: str = "game"  # game | action | tv
    # Optional one-off preparation after a clone or update, run with the games'
    # Python in the game folder (e.g. Hide and Seek pre-builds its room images).
    setup: list[str] = field(default_factory=list)

    def path_under(self, games_dir: Path) -> Path:
        folder = self.folder or self.id
        return games_dir / folder


@dataclass
class Settings:
    games_dir: Path
    update_interval_sec: int = 180
    width: int = 1280
    height: int = 720
    launcher_repo: str = ""
    launcher_branch: str = "main"
    include_system_tiles: bool = True


@dataclass
class Config:
    settings: Settings
    games: list[GameEntry] = field(default_factory=list)
    path: Path = DEFAULT_CONFIG


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _setup_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return v.split()
    return [str(x) for x in v]


def load_config(path: Path | None = None) -> Config:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    s = raw.get("settings", {})
    settings = Settings(
        games_dir=_expand(s.get("games_dir", "~/games")),
        update_interval_sec=int(s.get("update_interval_sec", 180)),
        width=int(s.get("width", 1280)),
        height=int(s.get("height", 720)),
        launcher_repo=str(s.get("launcher_repo", "")),
        launcher_branch=str(s.get("launcher_branch", "main")),
        include_system_tiles=bool(s.get("include_system_tiles", True)),
    )
    games: list[GameEntry] = []
    for g in raw.get("games", []):
        games.append(
            GameEntry(
                id=g["id"],
                name=g["name"],
                repo=g.get("repo", ""),
                branch=g.get("branch", "main"),
                entry=g.get("entry", "game.py"),
                folder=g.get("folder", g["id"]),
                thumbnail=g.get("thumbnail"),
                kind=g.get("kind", "game"),
                setup=_setup_list(g.get("setup")),
            )
        )
    return Config(settings=settings, games=games, path=cfg_path)


def bundled_thumbnail(rel: str | None) -> Path | None:
    if not rel:
        return None
    p = ROOT / rel
    return p if p.is_file() else None
