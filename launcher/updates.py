"""Background git fetch / pull for games and the launcher itself."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, GameEntry, ROOT


@dataclass
class UpdateStatus:
    available: dict[str, bool] = field(default_factory=dict)  # id -> bool
    launcher_available: bool = False
    last_check: float = 0.0
    last_error: str = ""
    busy: bool = False
    message: str = ""
    offline: bool = False
    updated: set[str] = field(default_factory=set)  # ids updated but not yet played


class UpdateService:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.status = UpdateStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._updated_file = self.config.settings.games_dir / ".zen_updated.json"
        try:
            self.status.updated = set(json.loads(self._updated_file.read_text()))
        except Exception:  # noqa: BLE001
            self.status.updated = set()

    def _save_updated(self) -> None:
        try:
            self._updated_file.parent.mkdir(parents=True, exist_ok=True)
            self._updated_file.write_text(json.dumps(sorted(self.status.updated)))
        except OSError:
            pass

    def mark_played(self, game_id: str) -> None:
        """Clear the green Updated badge once the game has been played."""
        with self._lock:
            if game_id in self.status.updated:
                self.status.updated.discard(game_id)
                self._save_updated()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="gb-updates", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # First check quickly
        self.check_all()
        interval = max(30, self.config.settings.update_interval_sec)
        while not self._stop.wait(interval):
            self.check_all()

    def check_all(self, force: bool = False) -> None:
        with self._lock:
            if self.status.busy and not force:
                return
        offline = False
        avail: dict[str, bool] = {}
        err = ""
        for g in self.config.games:
            if g.kind != "game" or not g.repo:
                continue
            path = g.path_under(self.config.settings.games_dir)
            try:
                avail[g.id] = self._has_update(path, g.branch)
            except OfflineError:
                offline = True
                avail[g.id] = False
            except Exception as e:  # noqa: BLE001
                err = str(e)
                avail[g.id] = False
        launcher_avail = False
        try:
            launcher_avail = self._has_update(ROOT, self.config.settings.launcher_branch)
        except OfflineError:
            offline = True
        except Exception as e:  # noqa: BLE001
            err = str(e)
        with self._lock:
            self.status.available = avail
            self.status.launcher_available = launcher_avail
            self.status.last_check = time.time()
            self.status.offline = offline
            if offline:
                self.status.last_error = "Offline"
                self.status.message = "Offline"
            elif err:
                self.status.last_error = err
            else:
                self.status.last_error = ""
                if not self.status.busy:
                    self.status.message = ""

    def pull_game(self, game: GameEntry) -> str:
        path = game.path_under(self.config.settings.games_dir)
        msg = self._pull(path, game.branch, label=game.name)
        if msg == "ok":
            with self._lock:
                self.status.available[game.id] = False
                self.status.updated.add(game.id)
                self._save_updated()
        elif msg == "current":
            # Nothing new: no green Updated badge, and no stale Update available.
            with self._lock:
                self.status.available[game.id] = False
        return msg

    def pull_launcher(self) -> str:
        return self._pull(ROOT, self.config.settings.launcher_branch, label="Zen Station")

    def ensure_cloned(self, game: GameEntry) -> str:
        """Clone a missing game repo. Returns a short status message."""
        path = game.path_under(self.config.settings.games_dir)
        if (path / ".git").exists() or (path / game.entry).exists():
            return "present"
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.status.busy = True
            self.status.message = f"Downloading {game.name}…"
        try:
            self._run(
                ["git", "clone", "--branch", game.branch, "--single-branch", game.repo, str(path)],
                cwd=path.parent,
                timeout=600,
            )
            self._pip_install(path)
            return "cloned"
        except OfflineError:
            with self._lock:
                self.status.offline = True
                self.status.message = "Offline"
            return "offline"
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self.status.message = f"Could not download {game.name}"
                self.status.last_error = str(e)
            return f"error: {e}"
        finally:
            with self._lock:
                self.status.busy = False

    def ensure_all_cloned(self) -> None:
        for g in self.config.games:
            if g.kind == "game" and g.repo:
                self.ensure_cloned(g)

    def _pull(self, path: Path, branch: str, label: str) -> str:
        with self._lock:
            self.status.busy = True
            self.status.message = f"Updating {label}…"
        try:
            if not (path / ".git").exists():
                return "not a git repo"
            req_before = self._req_hash(path)
            head_before = self._head(path)
            self._run(["git", "fetch", "origin", branch], cwd=path)
            self._run(["git", "pull", "--ff-only", "origin", branch], cwd=path)
            req_after = self._req_hash(path)
            if req_before != req_after:
                self._pip_install(path)
            changed = self._head(path) != head_before
            with self._lock:
                self.status.message = f"{label} updated" if changed else f"{label} up to date"
            return "ok" if changed else "current"
        except OfflineError:
            with self._lock:
                self.status.offline = True
                self.status.message = "Offline"
            return "offline"
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self.status.message = f"Update failed: {e}"
                self.status.last_error = str(e)
            return f"error: {e}"
        finally:
            with self._lock:
                self.status.busy = False

    def _head(self, path: Path) -> str:
        try:
            return self._run(["git", "rev-parse", "HEAD"], cwd=path, quiet=True).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""

    def _has_update(self, path: Path, branch: str) -> bool:
        if not (path / ".git").exists():
            return False
        self._run(["git", "fetch", "origin", branch], cwd=path, quiet=True)
        local = self._run(["git", "rev-parse", "HEAD"], cwd=path, quiet=True).stdout.strip()
        remote = self._run(
            ["git", "rev-parse", f"origin/{branch}"], cwd=path, quiet=True
        ).stdout.strip()
        return bool(local and remote and local != remote)

    def _pip_install(self, path: Path) -> None:
        req = path / "requirements.txt"
        if not req.is_file():
            return
        pip = os.environ.get("ZENSTATION_PIP", "")
        if not pip:
            # Prefer pip next to the running interpreter (venv)
            import sys
            cand = Path(sys.executable).with_name("pip")
            pip = str(cand) if cand.is_file() else "pip3"
        self._run([pip, "install", "-r", str(req)], cwd=path, timeout=600)

    @staticmethod
    def _req_hash(path: Path) -> str:
        req = path / "requirements.txt"
        if not req.is_file():
            return ""
        return hashlib.sha1(req.read_bytes()).hexdigest()

    def _run(
        self,
        cmd: list[str],
        cwd: Path,
        timeout: int = 120,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd),
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or str(e)).strip()
            low = err.lower()
            if any(
                s in low
                for s in (
                    "could not resolve",
                    "network is unreachable",
                    "temporary failure",
                    "failed to connect",
                    "no route to host",
                    "timed out",
                    "unable to access",
                )
            ):
                raise OfflineError(err) from e
            if quiet:
                raise
            raise RuntimeError(err or str(e)) from e
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise OfflineError(str(e)) from e


class OfflineError(Exception):
    pass
