#!/usr/bin/env bash
# Example: slice a model with a named profile using the headless Bambu Studio CLI.
# (PRD §11.2 — "pass a file and a profile flag to it".)
#
# Usage:
#   ./scripts/slice.sh <input.stl> <profile> [output.gcode.3mf]
#
# Profiles map to JSON presets under backend/profiles/a1/:
#   a1_mini_pla   -> machine.json + process_0.20mm.json + filament_pla.json
#   a1_mini_petg  -> machine.json + process_0.20mm.json + filament_petg.json
set -euo pipefail

INPUT="${1:?usage: slice.sh <input> <profile> [output]}"
PROFILE="${2:?usage: slice.sh <input> <profile> [output]}"
OUTPUT="${3:-${INPUT%.*}.gcode.3mf}"

PROFILE_DIR="$(dirname "$0")/../backend/profiles/a1"
MACHINE="$PROFILE_DIR/machine.json"
PROCESS="$PROFILE_DIR/process_0.20mm.json"

case "$PROFILE" in
  a1_mini_pla)  FILAMENT="$PROFILE_DIR/filament_pla.json" ;;
  a1_mini_petg) FILAMENT="$PROFILE_DIR/filament_petg.json" ;;
  *) echo "Unknown profile: $PROFILE (expected a1_mini_pla | a1_mini_petg)" >&2; exit 2 ;;
esac

# Run via the slicer Docker image (built from docker/slicer.Dockerfile).
SLICER_BIN="${SLICER2_SLICER_BIN:-orca-slicer}"

exec "$SLICER_BIN" \
  --slice 1 \
  --load-settings "$MACHINE;$PROCESS" \
  --load-filaments "$FILAMENT" \
  --curr-bedtype "Textured PEI Plate" \
  --export-3mf "$OUTPUT" \
  "$INPUT"
