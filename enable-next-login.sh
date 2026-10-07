#!/bin/bash
# Arm image borders for the *next* Hyprland start. Does not load the plugin now.
# Do not run hyprctl plugin load or hyprctl reload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SO="$ROOT/build/libimgborders.so"
USER_DEST="${HOME}/.local/lib/hyprland/plugins/libimgborders.so"
SYS_DEST="/usr/local/lib/hyprland/plugins/libimgborders.so"
PNG_SHARE="${HOME}/.local/share/neuronix/imgborders"
SETTINGS="${HOME}/.config/hypr/imgborders.conf"
CONF="${HOME}/.config/hypr/hyprland.conf"

if [ ! -f "$SO" ]; then
  echo "missing $SO — run ./debug.sh first" >&2
  exit 1
fi

mkdir -p "$(dirname "$USER_DEST")" "$PNG_SHARE" "$(dirname "$SETTINGS")"
cp -f "$SO" "$USER_DEST"
cp -f "$ROOT/example.png" "$PNG_SHARE/example.png"
if [ ! -f "$SETTINGS" ]; then
  cp -f "$ROOT/imgborders.conf.example" "$SETTINGS"
fi

PLUGIN_LINE="plugin = ${USER_DEST}"
if [ -w "$(dirname "$SYS_DEST")" ] 2>/dev/null || mkdir -p "$(dirname "$SYS_DEST")" 2>/dev/null; then
  if cp -f "$SO" "$SYS_DEST" 2>/dev/null; then
    PLUGIN_LINE="plugin = ${SYS_DEST}"
    echo "installed $SYS_DEST"
  fi
fi

if [ -f "$CONF" ] && ! grep -qE '^[[:space:]]*plugin = .*/libimgborders\.so' "$CONF"; then
  python3 - "$CONF" "$PLUGIN_LINE" <<'PY'
from pathlib import Path
import sys
conf, line = Path(sys.argv[1]), sys.argv[2]
text = conf.read_text()
needle = "exec-once = neuronix-ensure-hyprbars"
block = (
    "# Image borders at compositor start, before hyprbars.\n"
    "# Settings: ~/.config/hypr/imgborders.conf\n"
    "# Do not hyprctl plugin load / reload after hyprbars is up.\n"
    f"{line}\n"
    + needle
)
if needle in text:
    text = text.replace(needle, block, 1)
else:
    text = line + "\n" + text
conf.write_text(text)
print(f"updated {conf}")
PY
elif [ -f "$CONF" ]; then
  # Keep existing plugin= path in sync with what we just installed.
  python3 - "$CONF" "$PLUGIN_LINE" <<'PY'
from pathlib import Path
import re, sys
conf, line = Path(sys.argv[1]), sys.argv[2]
text = conf.read_text()
text2, n = re.subn(
    r"(?m)^[[:space:]]*plugin = .*/libimgborders\.so\s*$",
    line,
    text,
    count=1,
)
if n:
    conf.write_text(text2)
    print(f"refreshed plugin= in {conf}")
PY
fi

LOG="${IMGBORDERS_LOG:-$HOME/.cache/hyprland/imgborders.log}"
mkdir -p "$(dirname "$LOG")"
{
  echo ""
  echo "======== armed $(date '+%Y-%m-%d %H:%M:%S') ========"
  echo "so=$USER_DEST"
  echo "plugin_line=$PLUGIN_LINE"
  echo "settings=$SETTINGS"
} >>"$LOG"

echo "armed $USER_DEST"
echo "conf line: $PLUGIN_LINE"
echo "settings $SETTINGS"
echo "error log: $LOG"
echo "Log out / new Hyprland session. Do not hyprctl plugin load / reload."
echo "Live texture reload after login: hyprctl dispatch imgbordersreload"
echo "If login fails: $ROOT/disable-imgborders.sh"
echo "After a crash:  tail -100 $LOG"
