#!/usr/bin/env bash
# Fetch the pinned alcedo binary (github.com/hiyufan/alcedo, MIT) for this machine into ../tools/,
# where the backend finds it (backend/modules/video_source/alcedo.py). Nothing is installed globally:
# the npm package archive is downloaded with `npm pack` and unpacked.
#
#   ./scripts/install-alcedo.sh            the pinned version
#   ALCEDO_VERSION=0.2.0 ./scripts/install-alcedo.sh
set -euo pipefail

VERSION="${ALCEDO_VERSION:-0.2.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$(dirname "$ROOT")/tools"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) PLATFORM=darwin-arm64 ;;
  Darwin-x86_64) PLATFORM=darwin-x64 ;;
  Linux-x86_64) PLATFORM=linux-x64 ;;
  Linux-aarch64|Linux-arm64) PLATFORM=linux-arm64 ;;
  *) echo "没有这个平台的预编译 alcedo：$(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

DEST="$TOOLS/alcedo-$VERSION/alcedo-cli-$PLATFORM"
if [ -x "$DEST/bin/alcedo" ]; then
  echo "已安装：$DEST/bin/alcedo ($("$DEST/bin/alcedo" --version))"
  exit 0
fi
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
(cd "$WORK" && npm pack --silent "alcedo-cli-$PLATFORM@$VERSION" >/dev/null)
mkdir -p "$DEST"
tar -xzf "$WORK"/alcedo-cli-"$PLATFORM"-"$VERSION".tgz -C "$DEST" --strip-components=1
chmod +x "$DEST/bin/alcedo"
echo "已安装：$DEST/bin/alcedo ($("$DEST/bin/alcedo" --version))"
