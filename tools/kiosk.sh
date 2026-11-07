#!/usr/bin/env bash
# Zen Station boot mode.
#   tools/kiosk.sh on   : boot to the console (no desktop), log in automatically
#                         and start Zen Station straight away in "cage", a tiny
#                         full-screen display server. Wi-Fi and sound still work.
#   tools/kiosk.sh off  : back to the normal desktop with Zen Station autostarting.
# Reboot afterwards.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="$HOME/.bash_profile"
BEGIN="# >>> zen-station kiosk >>>"
END="# <<< zen-station kiosk <<<"
AUTOSTART="$HOME/.config/autostart/zen-station.desktop"

strip_block() {
  [[ -f "$PROFILE" ]] || return 0
  awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1;next} $0==e{skip=0;next} !skip' "$PROFILE" > "$PROFILE.tmp"
  mv "$PROFILE.tmp" "$PROFILE"
}

case "${1:-}" in
  on)
    sudo apt-get install -y cage xwayland
    strip_block
    [[ -f "$PROFILE" ]] || printf '[[ -f ~/.bashrc ]] && . ~/.bashrc\n' > "$PROFILE"
    cat >> "$PROFILE" << BLOCK
$BEGIN
# Start Zen Station on the TV when logging in on the first console.
if [[ -z "\${WAYLAND_DISPLAY:-}\${DISPLAY:-}" && "\$(tty)" == /dev/tty1 && -z "\${ZEN_NO_KIOSK:-}" ]]; then
  export ZENSTATION_KIOSK=1
  cage -d -s -- "$HOME/.local/bin/zen-station"
  clear
  echo "Zen Station has closed."
  echo "  zen-station-tv   start it again"
  echo "  zen-desktop      open the normal desktop (this time only)"
  echo "  sudo reboot      restart the Pi"
fi
$END
BLOCK
    mkdir -p "$HOME/.local/bin"
    printf '#!/usr/bin/env bash\nexport ZENSTATION_KIOSK=1\nexec cage -d -s -- "%s/.local/bin/zen-station"\n' "$HOME" > "$HOME/.local/bin/zen-station-tv"
    printf '#!/usr/bin/env bash\nexec sudo systemctl start lightdm\n' > "$HOME/.local/bin/zen-desktop"
    chmod +x "$HOME/.local/bin/zen-station-tv" "$HOME/.local/bin/zen-desktop"
    # Stop the desktop starting a second copy if someone opens it with zen-desktop
    [[ -f "$AUTOSTART" ]] && mv "$AUTOSTART" "$AUTOSTART.off"
    sudo raspi-config nonint do_boot_behaviour B2   # console, auto login
    echo "Kiosk mode on. Reboot to start straight into Zen Station."
    ;;
  off)
    strip_block
    [[ -f "$AUTOSTART.off" ]] && mv "$AUTOSTART.off" "$AUTOSTART"
    sudo raspi-config nonint do_boot_behaviour B4   # desktop, auto login
    echo "Desktop mode on. Reboot to start the desktop with Zen Station."
    ;;
  *)
    echo "Usage: $0 on|off" >&2; exit 2 ;;
esac
