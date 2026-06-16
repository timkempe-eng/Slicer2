#!/usr/bin/env bash
# Prove the slicing pipeline end-to-end on a host that can run the slicer.
#
# This is the reproducible "does it actually slice?" check that can't run in a
# headless CI sandbox. Run it on the slicer Docker image, a DO worker droplet,
# or any box with OrcaSlicer / Bambu Studio installed.
#
#   1. Ensure a slicer binary is on PATH (or export SLICER2_SLICER_BIN).
#      OrcaSlicer is a Bambu Studio fork with the same CLI and bundles A1
#      profiles: https://github.com/SoftFever/OrcaSlicer/releases
#   2. Populate backend/profiles/a1/ per backend/profiles/README.md.
#   3. ./scripts/verify_slice.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLICER_BIN="${SLICER2_SLICER_BIN:-bambu-studio}"

if ! command -v "$SLICER_BIN" >/dev/null 2>&1; then
  echo "ERROR: slicer binary '$SLICER_BIN' not found on PATH." >&2
  echo "Install OrcaSlicer/Bambu Studio or set SLICER2_SLICER_BIN." >&2
  exit 1
fi

echo "==> Using slicer: $($SLICER_BIN --help >/dev/null 2>&1 && echo "$SLICER_BIN (ok)")"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
CUBE="$WORK/cube.stl"
OUT="$WORK/cube.gcode.3mf"

echo "==> Generating test cube"
python3 - "$CUBE" <<'PY'
import sys; sys.path.insert(0, "backend")
from tests._stl import write_cube_stl
from pathlib import Path
write_cube_stl(Path(sys.argv[1]))
print("wrote", sys.argv[1])
PY

echo "==> Slicing via scripts/slice.sh (profile: a1_mini_pla)"
SLICER2_SLICER_BIN="$SLICER_BIN" "$ROOT/scripts/slice.sh" "$CUBE" a1_mini_pla "$OUT"

if [[ -f "$OUT" && "$(head -c2 "$OUT")" == "PK" ]]; then
  echo "==> SUCCESS: produced $(du -h "$OUT" | cut -f1) .gcode.3mf (valid zip container)"
else
  echo "==> FAILURE: no valid .gcode.3mf produced" >&2
  exit 1
fi
