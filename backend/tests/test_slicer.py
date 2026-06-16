"""Unit tests for the slicer command construction and output parsing.

These run with no slicer binary present — they prove the *logic* that turns
options into a correct Bambu Studio CLI invocation and parses its estimates.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import slicer
from app.models import PrinterModel, SliceOptions


def _make_profiles(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    for name in ("machine.json", "process_0.20mm.json", "filament_pla.json"):
        (base / name).write_text("{}")


def test_build_command_uses_resolved_profiles(tmp_path, monkeypatch):
    profiles_root = tmp_path / "profiles"
    _make_profiles(profiles_root / "a1")
    monkeypatch.setattr(slicer.config, "PROFILES_DIR", profiles_root)
    monkeypatch.setattr(slicer.config, "SLICER_BIN", "bambu-studio")

    opts = SliceOptions(printer=PrinterModel.A1_MINI, layer_height_mm=0.20, filament="pla")
    cmd = slicer.build_command(Path("in.stl"), Path("out.gcode.3mf"), opts)

    assert cmd[0] == "bambu-studio"
    assert "--slice" in cmd and "--export-3mf" in cmd
    # machine + process joined with ';' for --load-settings
    settings = cmd[cmd.index("--load-settings") + 1]
    assert "machine.json;" in settings and "process_0.20mm.json" in settings
    assert cmd[cmd.index("--load-filaments") + 1].endswith("filament_pla.json")
    assert cmd[-1] == "in.stl"  # input model is the final positional arg


def test_missing_profile_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(slicer.config, "PROFILES_DIR", tmp_path / "empty")
    opts = SliceOptions(printer=PrinterModel.A1, filament="petg")
    with pytest.raises(slicer.SlicerError) as exc:
        slicer.build_command(Path("in.stl"), Path("out.3mf"), opts)
    assert "filament_petg.json" in str(exc.value)


def test_layer_height_selects_process_preset(tmp_path, monkeypatch):
    base = tmp_path / "profiles" / "a1"
    base.mkdir(parents=True)
    (base / "machine.json").write_text("{}")
    (base / "process_0.12mm.json").write_text("{}")
    (base / "filament_pla.json").write_text("{}")
    monkeypatch.setattr(slicer.config, "PROFILES_DIR", tmp_path / "profiles")

    opts = SliceOptions(layer_height_mm=0.12, filament="pla")
    cmd = slicer.build_command(Path("in.stl"), Path("o.3mf"), opts)
    assert "process_0.12mm.json" in cmd[cmd.index("--load-settings") + 1]


def test_parse_estimates_reads_time_and_filament():
    out = "Total estimated time: 1 h 23 m\nTotal filament used: 12.5 g, 4.1 m"
    res = slicer._parse_estimates(out)
    assert res.estimated_print_seconds == 1 * 3600 + 23 * 60
    assert res.filament_grams == 12.5
    assert res.filament_meters == 4.1


def test_missing_binary_raises_slicer_error(tmp_path, monkeypatch):
    base = tmp_path / "profiles" / "a1"
    _make_profiles(base)
    monkeypatch.setattr(slicer.config, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(slicer.config, "SLICER_BIN", "definitely-not-a-real-binary-xyz")

    with pytest.raises(slicer.SlicerError) as exc:
        slicer.slice_model(Path("in.stl"), tmp_path / "out.gcode.3mf", SliceOptions())
    assert "not found" in str(exc.value).lower()
