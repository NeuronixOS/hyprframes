#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
"${ROOT}/fetch-third-party.sh"
cmake -S "$ROOT" -B "$ROOT/build"
cmake --build "$ROOT/build" -j"$(nproc)"
echo "built $ROOT/build/libhyprframes.so"
echo "Next: ./enable-next-login.sh  then start a new Hyprland session."
