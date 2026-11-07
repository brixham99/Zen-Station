#!/usr/bin/env bash
# Idempotent Zen Station installer for Raspberry Pi OS Bookworm (64-bit).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
GAMES_DIR="${GAMES_DIR:-$HOME/games}"
VENV="$ROOT/.venv"
CONFIG="$ROOT/games.json"

echo "=== Zen Station installer ==="
echo "Launcher: $ROOT"
echo "Games:    $GAMES_DIR"

need_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Need root to run: $*" >&2
    return 1
  fi
}

echo "--- apt packages ---"
need_sudo apt-get update -y
need_sudo apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  libsdl2-2.0-0 \
  libsdl2-image-2.0-0 \
  libsdl2-mixer-2.0-0 \
  libsdl2-ttf-2.0-0 \
  libatlas3-base \
  || true

echo "--- Python venv ---"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip wheel
pip install -r "$ROOT/requirements.txt"

export ZENSTATION_PYTHON="$VENV/bin/python"
export ZENSTATION_PIP="$VENV/bin/pip"

echo "--- Clone / update games from games.json ---"
mkdir -p "$GAMES_DIR"
python3 - << PY
import json, os, subprocess, hashlib
from pathlib import Path

root = Path(r"$ROOT")
games_dir = Path(r"$GAMES_DIR")
cfg = json.loads((root / "games.json").read_text())
pip = r"$VENV/bin/pip"
py = r"$VENV/bin/python"

def run(cmd, cwd=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

for g in cfg.get("games", []):
    if g.get("kind", "game") != "game" or not g.get("repo"):
        continue
    folder = g.get("folder") or g["id"]
    path = games_dir / folder
    branch = g.get("branch", "main")
    if (path / ".git").exists():
        run(["git", "-C", str(path), "fetch", "origin", branch])
        run(["git", "-C", str(path), "checkout", branch])
        run(["git", "-C", str(path), "pull", "--ff-only", "origin", branch])
    elif path.exists() and any(path.iterdir()):
        print(f"Skipping {folder}: folder exists but is not a git repo")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", branch, "--single-branch", g["repo"], str(path)])
    req = path / "requirements.txt"
    if req.is_file():
        run([pip, "install", "-r", str(req)])
print("Games ready under", games_dir)
PY

# Convenience wrapper on PATH for this user
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
cat > "$BIN/zen-station" << WRAP
#!/usr/bin/env bash
export ZENSTATION_PYTHON="$VENV/bin/python"
export ZENSTATION_PIP="$VENV/bin/pip"
# start.sh pulls the latest Zen Station before starting it
exec "$ROOT/start.sh" "\$@"
WRAP
chmod +x "$BIN/zen-station"

echo "--- Steady HDMI sound ---"
bash "$ROOT/tools/hdmi_audio.sh" || true

echo "--- Autostart (desktop session) ---"
# Raspberry Pi OS Bookworm uses labwc (Wayland) or wayfire; both honour
# ~/.config/autostart/*.desktop via xdg / the desktop portal.
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
DESKTOP="$AUTOSTART_DIR/zen-station.desktop"
cat > "$DESKTOP" << DESK
[Desktop Entry]
Type=Application
Name=Zen Station
Comment=Controller-driven games home screen
Exec=$BIN/zen-station
Path=$ROOT
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
DESK
echo "Wrote $DESKTOP"

chmod +x "$ROOT/install.sh"

echo
echo "Done."
echo "Reboot to start Zen Station automatically on the desktop,"
echo "or run:  zen-station --windowed"
echo
echo "Optional TV apps:  sudo apt install kodi"
echo "Controller tip: plug in the wired Xbox pad before launching."
