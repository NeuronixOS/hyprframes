#!/bin/bash
# Arm hyprframes for the *next* Hyprland start. Does not load the plugin now.
# Do not run hyprctl plugin load or hyprctl reload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SO="$ROOT/build/libhyprframes.so"
USER_DEST="${HOME}/.local/lib/hyprland/plugins/libhyprframes.so"
SYS_DEST="/usr/local/lib/hyprland/plugins/libhyprframes.so"
PNG_SHARE="${HOME}/.local/share/hyprframes"
SETTINGS="${HOME}/.config/hypr/hyprframes.conf"
CONF="${HOME}/.config/hypr/hyprland.conf"

if [ ! -f "$SO" ]; then
  echo "missing $SO — run ./debug.sh first" >&2
  exit 1
fi

mkdir -p "$(dirname "$USER_DEST")" "$PNG_SHARE" "$(dirname "$SETTINGS")"
cp -f "$SO" "$USER_DEST"
cp -f "$ROOT/example.png" "$PNG_SHARE/example.png"
if [ ! -f "$SETTINGS" ]; then
  sed -E "s|^[[:space:]]*image[[:space:]]*=.*|image = ${PNG_SHARE}/example.png|" \
    "$ROOT/hyprframes.conf.example" >"$SETTINGS"
fi

PLUGIN_LINE="plugin = ${USER_DEST}"
if [ -w "$(dirname "$SYS_DEST")" ] 2>/dev/null || mkdir -p "$(dirname "$SYS_DEST")" 2>/dev/null; then
  if cp -f "$SO" "$SYS_DEST" 2>/dev/null; then
    PLUGIN_LINE="plugin = ${SYS_DEST}"
    echo "installed $SYS_DEST"
  fi
fi

if [ -f "$CONF" ] && ! grep -qE '^[[:space:]]*plugin = .*/libhyprframes\.so' "$CONF"; then
  python3 - "$CONF" "$PLUGIN_LINE" <<'PY'
from pathlib import Path
import re
import sys

conf, line = Path(sys.argv[1]), sys.argv[2]
text = conf.read_text()
block = (
    "# hyprframes at compositor start (before titlebar plugins).\n"
    "# Settings: ~/.config/hypr/hyprframes.conf\n"
    "# Do not hyprctl plugin load / reload after hyprbars is up.\n"
    f"{line}\n"
)
m = re.search(r"(?m)^exec-once = .*hyprbars", text)
if m:
    text = text[: m.start()] + block + text[m.start() :]
else:
    text = block + text
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
    r"(?m)^[[:space:]]*plugin = .*/libhyprframes\.so\s*$",
    line,
    text,
    count=1,
)
if n:
    conf.write_text(text2)
    print(f"refreshed plugin= in {conf}")
PY
fi

echo "armed $USER_DEST"
echo "conf line: $PLUGIN_LINE"
echo "settings $SETTINGS"
echo "Log out / new Hyprland session. Do not hyprctl plugin load / reload."
echo "Live texture reload after login: hyprctl dispatch hyprframesreload"
echo "If login fails: $ROOT/disable-hyprframes.sh"
