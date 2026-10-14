#!/usr/bin/env bash
# Fetch hyprutils 0.13 headers into third_party/ if missing.
# Needed because libhyprutils 0.14 made operator bool explicit; Hyprland 0.55.2
# still converts those pointers implicitly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${ROOT}/third_party/hyprutils-0.13"
MARKER="${DEST}/hyprutils/memory/SharedPtr.hpp"
TAG="v0.13.0"
URL="https://github.com/hyprwm/hyprutils/archive/refs/tags/${TAG}.tar.gz"

if [[ -f "${MARKER}" ]]; then
	echo "third_party: hyprutils ${TAG} headers already present"
	exit 0
fi

tmpdir="$(mktemp -d)"
cleanup() { rm -rf "${tmpdir}"; }
trap cleanup EXIT

echo "third_party: fetching hyprutils ${TAG} headers…"
if command -v curl >/dev/null 2>&1; then
	curl -fsSL "${URL}" | tar -xzf - -C "${tmpdir}"
elif command -v wget >/dev/null 2>&1; then
	wget -qO- "${URL}" | tar -xzf - -C "${tmpdir}"
else
	echo "error: need curl or wget to download ${URL}" >&2
	exit 1
fi

src="${tmpdir}/hyprutils-0.13.0/include/hyprutils"
if [[ ! -d "${src}" ]]; then
	echo "error: archive missing include/hyprutils" >&2
	exit 1
fi

mkdir -p "${DEST}"
rm -rf "${DEST}/hyprutils"
cp -a "${src}" "${DEST}/"

echo "third_party: installed headers → ${DEST}"
