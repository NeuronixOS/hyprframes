#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cmake -S "$ROOT" -B "$ROOT/build"
cmake --build "$ROOT/build" -j"$(nproc)"
echo "built $ROOT/build/libimgborders.so"
echo "Next: ./enable-next-login.sh  then start a new Hyprland session."
