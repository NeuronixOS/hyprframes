#!/bin/bash
# Arm image borders for the *next* Hyprland start. Does not load the plugin now.
# Do not run hyprctl plugin load or hyprctl reload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SO="$ROOT/build/libimgborders.so"
DEST="${HOME}/.local/lib/hyprland/plugins/libimgborders.so"
CONF="${HOME}/.config/hypr/hyprland.conf"
SETTINGS="${HOME}/.config/hypr/imgborders.conf"
LINE="plugin = ${DEST}"

if [ ! -f "$SO" ]; then
  echo "missing $SO — run ./debug.sh first" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")" "$(dirname "$SETTINGS")"
cp -f "$SO" "$DEST"
if [ ! -f "$SETTINGS" ]; then
  cp -f "$ROOT/imgborders.conf.example" "$SETTINGS"
fi

if [ -f "$CONF" ] && ! grep -qF 'libimgborders.so' "$CONF"; then
  python3 - "$CONF" "$LINE" <<'PY'
from pathlib import Path
import sys
conf, line = Path(sys.argv[1]), sys.argv[2]
text = conf.read_text()
needle = "exec-once = neuronix-ensure-hyprbars"
block = (
    "# Image borders: compositor-start only. Settings: ~/.config/hypr/imgborders.conf\n"
    "# Do not hyprctl plugin load / reload after hyprbars is up.\n"
    f"{line}\n"
    + needle
)
if needle in text:
    text = text.replace(needle, block, 1)
else:
    text = line + "\n" + text
# Strip any old plugin { imgborders { ... } } block — those Hyprland values crash.
import re
text = re.sub(r"\n    imgborders \{.*?\n    \}\n", "\n", text, count=1, flags=re.S)
conf.write_text(text)
print(f"updated {conf}")
PY
fi

echo "armed $DEST"
echo "settings $SETTINGS"
echo "Log out of Hyprland (new session). Do not hyprctl plugin load. Do not hyprctl reload."
echo "If login fails, run: $ROOT/disable-imgborders.sh  then try the greeter again."
