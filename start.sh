#!/usr/bin/env bash
# Zen Station start-up: pull the latest launcher (if online), then run it.
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
export ZENSTATION_PYTHON="${ZENSTATION_PYTHON:-$VENV/bin/python}"
export ZENSTATION_PIP="${ZENSTATION_PIP:-$VENV/bin/pip}"
cd "$ROOT" || exit 1

pull_latest() {
  [[ -z "${ZENSTATION_NO_PULL:-}" && -d .git ]] || return 0
  # Wi-Fi can take a few seconds after boot; wait up to ~20 s for GitHub
  for _ in $(seq 1 10); do
    git ls-remote --heads origin >/dev/null 2>&1 && break
    sleep 2
  done
  local req_before
  req_before="$(sha1sum requirements.txt 2>/dev/null)"
  if GIT_TERMINAL_PROMPT=0 timeout 60 git pull --ff-only --quiet; then
    if [[ "$(sha1sum requirements.txt 2>/dev/null)" != "$req_before" ]]; then
      "$ZENSTATION_PIP" install -q -r requirements.txt || true
    fi
  else
    echo "Zen Station: could not update (offline?), starting anyway" >&2
  fi
}

# Exit code 75 from the launcher (hold X + B) means: pull again and restart.
while true; do
  pull_latest
  # Steady HDMI sound (no sleeping output, fixed 48 kHz); no-op if already set
  bash "$ROOT/tools/hdmi_audio.sh" || true
  bash "$ROOT/tools/hdmi_boot.sh" || true
  "$ZENSTATION_PYTHON" -m launcher "$@"
  rc=$?
  [[ "$rc" -eq 75 ]] || exit "$rc"
done
