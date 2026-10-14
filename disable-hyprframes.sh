#!/bin/bash
# Stop image borders from loading. Safe to run while Hyprland is down.
set -euo pipefail
DEST="${HOME}/.local/lib/hyprland/plugins/libhyprframes.so"
CONF="${HOME}/.config/hypr/hyprland.conf"
rm -f "$DEST"
if [ -f "$CONF" ]; then
  python3 - "$CONF" <<'PY'
from pathlib import Path
import re
import sys
p = Path(sys.argv[1])
t = p.read_text()
t2 = re.sub(r"(?m)^# Image borders:.*\n", "", t)
t2 = re.sub(r"(?m)^plugin = .*/libhyprframes\.so\n", "", t2)
t2 = re.sub(r"\n    hyprframes \{.*?\n    \}\n", "\n", t2, count=1, flags=re.S)
if t2 != t:
    p.write_text(t2)
    print(f"cleaned {p}")
PY
fi
echo "image borders disabled — next Hyprland start is hyprbars only"
