"""Real end-to-end slice. Skipped unless a slicer binary AND A1 profiles exist.

This is the test that *proves the pipeline* on a properly provisioned host
(the slicer Docker image, a DO worker droplet, or a dev box with OrcaSlicer/
Bambu Studio installed). Provide profiles per backend/profiles/README.md, set
SLICER2_SLICER_BIN if the binary isn't named `bambu-studio`, then run:

    pytest -m integration

It generates a cube, slices it, and asserts a non-trivial .gcode.3mf appears.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import config, slicer
from app.models import SliceOptions
from tests._stl import write_cube_stl

_HAS_BINARY = shutil.which(config.SLICER_BIN) is not None
_A1 = config.PROFILES_DIR / "a1"
_HAS_PROFILES = (_A1 / "machine.json").exists() and (_A1 / "process_0.20mm.json").exists() \
    and (_A1 / "filament_pla.json").exists()

pytestmark = pytest.mark.skipif(
    not (_HAS_BINARY and _HAS_PROFILES),
    reason="needs a real slicer binary + A1 profiles (see this file's docstring)",
)


def test_slice_cube_produces_gcode_3mf(tmp_path):
    model = write_cube_stl(tmp_path / "cube.stl")
    out = tmp_path / "cube.gcode.3mf"

    result = slicer.slice_model(model, out, SliceOptions(filament="pla"))

    assert out.exists(), "slicer did not produce an output file"
    assert out.stat().st_size > 1024, "output .gcode.3mf is suspiciously small"
    # A .gcode.3mf is a zip container; sanity-check the magic bytes.
    assert out.read_bytes()[:2] == b"PK", "output is not a valid 3mf (zip) container"
    # Estimates are best-effort; if present they should be positive.
    if result.estimated_print_seconds is not None:
        assert result.estimated_print_seconds > 0
