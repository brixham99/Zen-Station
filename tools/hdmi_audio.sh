#!/usr/bin/env bash
# Keep HDMI sound steady on the Pi: never let PipeWire put the TV's audio
# output to sleep when idle, and keep the output at one fixed rate (48 kHz)
# so the TV never has to re-sync when a game opens audio at another rate.
# Safe to run at every start; only restarts the sound service if a file changed.
set -u
[[ "$(uname -s)" == "Linux" ]] || exit 0
command -v pipewire >/dev/null 2>&1 || exit 0

changed=0
write() {  # write <path> <content>, set changed=1 if it differs
  local path="$1" content="$2"
  mkdir -p "$(dirname "$path")"
  if [[ ! -f "$path" || "$(cat "$path")" != "$content" ]]; then
    printf '%s\n' "$content" > "$path"
    changed=1
  fi
}

CFG="${XDG_CONFIG_HOME:-$HOME/.config}"

write "$CFG/pipewire/pipewire.conf.d/50-zenstation.conf" 'context.properties = {
    default.clock.rate          = 48000
    default.clock.allowed-rates = [ 48000 ]
}'

# WirePlumber 0.5 (.conf)
write "$CFG/wireplumber/wireplumber.conf.d/50-zenstation-no-suspend.conf" 'monitor.alsa.rules = [
  {
    matches = [ { node.name = "~alsa_output.*" } ]
    actions = { update-props = { session.suspend-timeout-seconds = 0 } }
  }
]'

# WirePlumber 0.4 (Lua), for older images
write "$CFG/wireplumber/main.lua.d/51-zenstation-no-suspend.lua" 'table.insert(alsa_monitor.rules, {
  matches = { { { "node.name", "matches", "alsa_output.*" } } },
  apply_properties = { ["session.suspend-timeout-seconds"] = 0 },
})'

if [[ "$changed" == 1 ]]; then
  echo "Zen Station: applying steady HDMI sound settings" >&2
  systemctl --user restart wireplumber pipewire pipewire-pulse >/dev/null 2>&1 || true
  sleep 2
fi
exit 0
