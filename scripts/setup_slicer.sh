#!/usr/bin/env bash
# Fetch OrcaSlicer (a Bambu Studio fork with the same CLI + bundled A1 profiles)
# and flatten its presets into backend/profiles/a1/, so a real slice works.
#
# Usage:
#   ./scripts/setup_slicer.sh [a1_mini|a1]
#
# Env overrides:
#   ORCA_APPIMAGE_URL  pin an exact AppImage URL (skips the GitHub API lookup)
#   ORCA_TAG           release tag to fetch, e.g. V2.2.0
#   GITHUB_TOKEN       avoids GitHub API rate limits
#   SLICER2_SLICER_DIR install location (default: ~/.slicer2/orca)
#
# Runtime deps for the AppImage (already in deploy/Dockerfile.app):
#   xvfb libgl1 libgtk-3-0 libwebkit2gtk-4.1-0 libgstreamer1.0-0 \
#   libgstreamer-plugins-base1.0-0 libsoup-3.0-0 libosmesa6 libfuse2
set -euo pipefail

PRINTER="${1:-a1_mini}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${SLICER2_SLICER_DIR:-$HOME/.slicer2/orca}"
OUT_DIR="$ROOT/backend/profiles/a1"

# --- 1. Resolve the AppImage download URL ---------------------------------
url="${ORCA_APPIMAGE_URL:-}"
if [ -z "$url" ]; then
  if [ -n "${ORCA_TAG:-}" ]; then
    api="https://api.github.com/repos/SoftFever/OrcaSlicer/releases/tags/${ORCA_TAG}"
  else
    api="https://api.github.com/repos/SoftFever/OrcaSlicer/releases/latest"
  fi
  auth=()
  [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
  resp="$(curl -fsSL "${auth[@]}" "$api" 2>/dev/null || true)"
  url="$(printf '%s' "$resp" \
        | grep -oE 'https://[^"]*Linux[^"]*\.AppImage' | head -1)"
fi

if [ -z "$url" ]; then
  echo "ERROR: couldn't resolve an OrcaSlicer Linux AppImage URL." >&2
  echo "The GitHub API may be rate-limited. Re-run with an explicit URL:" >&2
  echo "  ORCA_APPIMAGE_URL=https://github.com/SoftFever/OrcaSlicer/releases/download/<tag>/<asset>.AppImage \\" >&2
  echo "    ./scripts/setup_slicer.sh $PRINTER" >&2
  exit 1
fi

# --- 2. Download + extract -------------------------------------------------
mkdir -p "$INSTALL_DIR"
echo "==> Downloading $url"
curl -fSL "$url" -o "$INSTALL_DIR/orca.AppImage"
chmod +x "$INSTALL_DIR/orca.AppImage"
echo "==> Extracting AppImage"
( cd "$INSTALL_DIR" && ./orca.AppImage --appimage-extract >/dev/null )

# Wrapper so callers can invoke the CLI headlessly.
cat > "$INSTALL_DIR/orca-slicer" <<EOF
#!/bin/sh
exec xvfb-run -a "$INSTALL_DIR/squashfs-root/AppRun" "\$@"
EOF
chmod +x "$INSTALL_DIR/orca-slicer"

# --- 3. Flatten the bundled profiles --------------------------------------
RES="$INSTALL_DIR/squashfs-root/resources/profiles"
if [ ! -d "$RES" ]; then
  echo "ERROR: bundled profiles not found at $RES" >&2
  exit 1
fi
echo "==> Flattening $PRINTER profiles into $OUT_DIR"
python3 "$ROOT/scripts/flatten_profiles.py" --resources "$RES" --printer "$PRINTER" --out "$OUT_DIR"

# --- 4. Next steps ---------------------------------------------------------
cat <<EOF

Done. To use this slicer:
  export SLICER2_SLICER_BIN="$INSTALL_DIR/orca-slicer"

Prove a real end-to-end slice:
  SLICER2_SLICER_BIN="$INSTALL_DIR/orca-slicer" "$ROOT/scripts/verify_slice.sh"

Review the generated JSONs in $OUT_DIR before trusting print quality.
EOF
