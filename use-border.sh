#!/bin/bash
# Point hyprframes at a generated border and reload live.
# Usage:
#   ./use-border.sh borders/01-medium-thick
#   ./use-border.sh 03
#   ./use-border.sh list
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BDIR="$ROOT/borders"
CONF="${HOME}/.config/hypr/hyprframes.conf"

if [[ "${1:-}" == "list" || -z "${1:-}" ]]; then
  ls -1 "$BDIR"/*.png 2>/dev/null | sed "s|$BDIR/||"
  exit 0
fi

arg="$1"
arg="${arg%.png}"
arg="${arg%.conf}"
case "$arg" in
  borders/*) base="${arg#borders/}" ;;
  */*) base="$(basename "$arg")" ;;
  [0-9][0-9]) base=$(basename "$(ls -1 "$BDIR"/${arg}-*.png 2>/dev/null | head -1)")
       base="${base%.png}"
       ;;
  *) base="$arg" ;;
esac

png="$BDIR/${base}.png"
src_conf="$BDIR/${base}.conf"
if [[ ! -f "$png" ]]; then
  echo "missing $png — run: python3 $BDIR/generate.py" >&2
  exit 1
fi

mkdir -p "$(dirname "$CONF")"
if [[ -f "$src_conf" ]]; then
  # Sample .conf files ship with basename image=; point at this checkout.
  sed -E "s|^[[:space:]]*image[[:space:]]*=.*|image = ${png}|" "$src_conf" >"$CONF"
else
  # fallback sizes: guess thickness from filename …tN or default 5
  thick=5
  if [[ "$base" =~ t([0-9]+)$ ]]; then
    thick="${BASH_REMATCH[1]}"
  fi
  cat >"$CONF" <<EOF
image = $png
sizes = $thick,$thick,$thick,$thick
insets = 1,1,1,1
scale = 1
smooth = true
blur = false
EOF
fi

echo "→ $CONF"
grep -E '^(image|sizes|insets|scale|smooth)' "$CONF" || true

if command -v hyprctl >/dev/null 2>&1 && hyprctl plugin list 2>/dev/null | grep -qi hyprframes; then
  hyprctl dispatch hyprframesreload
  echo "dispatched hyprframesreload"
else
  echo "hyprframes not loaded (or no hyprctl) — conf updated for next session"
fi
