#!/usr/bin/env bash
# Steadier HDMI link on the Pi 5 (needs one reboot after it first changes anything):
#  - vc4.force_hotplug=1      : keep HDMI 0 "connected" through the TV's signal blips
#  - video=HDMI-A-1:1920x1080@60 : 1080p60 instead of 4K, far less demanding on the cable
#  - hdmi_ignore_cec_init=1   : don't send the TV the "switch to me" message at boot
# Uses passwordless sudo if available and never prompts. Backs files up once.
set -u
BOOT="${ZS_BOOT_DIR:-/boot/firmware}"
CMD="$BOOT/cmdline.txt"
CFG="$BOOT/config.txt"
[[ -f "$CMD" && -f "$CFG" ]] || exit 0
SUDO="${ZS_SUDO-sudo -n}"

changed=0
cmd="$(tr -d '\n' < "$CMD")"
for opt in vc4.force_hotplug=1 video=HDMI-A-1:1920x1080@60; do
  key="${opt%%=*}"; [[ "$key" == video ]] && key="video=HDMI-A-1"
  [[ " $cmd " == *" $key"* ]] || { cmd="$cmd $opt"; changed=1; }
done
if [[ "$changed" == 1 ]]; then
  $SUDO cp -n "$CMD" "$CMD.zen-backup" 2>/dev/null
  printf '%s\n' "$cmd" | $SUDO tee "$CMD" >/dev/null || exit 0
fi

if ! grep -q '^hdmi_ignore_cec_init=1' "$CFG"; then
  $SUDO cp -n "$CFG" "$CFG.zen-backup" 2>/dev/null
  printf '\n# Zen Station: steadier HDMI\n[all]\nhdmi_ignore_cec_init=1\n' | $SUDO tee -a "$CFG" >/dev/null || exit 0
  changed=1
fi

if [[ "$changed" == 1 ]]; then
  echo "Zen Station: HDMI boot settings updated, reboot once to apply" >&2
  mkdir -p "$HOME/.cache" && touch "$HOME/.cache/zenstation-reboot-needed"
fi
exit 0
