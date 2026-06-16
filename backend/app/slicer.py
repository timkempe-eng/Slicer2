"""Headless slicing via the Bambu Studio (a.k.a. OrcaSlicer) CLI.

This module builds and runs the slicer command line, then parses the output for
the print-time / filament estimates. It deliberately knows nothing about HTTP or
jobs — it just turns an input model + options into a `.gcode.3mf`.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import config
from .models import PrinterModel, SliceOptions, SliceResult


class SlicerError(RuntimeError):
    """Raised when slicing fails (bad input, missing profile, CLI error)."""


@dataclass
class _ProfileSet:
    machine: Path
    process: Path
    filament: Path


def _profile_dir(printer: PrinterModel) -> Path:
    # A1 and A1 mini share a profile directory for now; split if they diverge.
    name = "a1" if printer in (PrinterModel.A1, PrinterModel.A1_MINI) else printer.value
    return config.PROFILES_DIR / name


def _resolve_profiles(opts: SliceOptions) -> _ProfileSet:
    """Pick the machine/process/filament JSONs for the requested options.

    Profiles are expected under ``profiles/<printer>/``. See
    ``backend/profiles/README.md`` for how to populate them.
    """
    base = _profile_dir(opts.printer)
    machine = base / "machine.json"
    # Process preset is selected by layer height, e.g. ``process_0.20mm.json``.
    process = base / f"process_{opts.layer_height_mm:.2f}mm.json"
    filament = base / f"filament_{opts.filament.lower()}.json"

    missing = [p for p in (machine, process, filament) if not p.exists()]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise SlicerError(
            f"Missing slicing profile(s) for {opts.printer.value}: {names}. "
            f"Populate {base} — see backend/profiles/README.md."
        )
    return _ProfileSet(machine=machine, process=process, filament=filament)


def build_command(input_path: Path, output_path: Path, opts: SliceOptions) -> list[str]:
    """Construct the slicer CLI argv. Pure function — easy to unit test.

    Note: per-knob overrides (infill density, supports) are selected via the
    process preset chosen in ``_resolve_profiles``. The Bambu Studio CLI does
    not accept arbitrary ``key=value`` overrides like PrusaSlicer; to vary a
    setting that has no dedicated preset, generate a merged process JSON and
    point ``--load-settings`` at it (see ROADMAP Phase 0).
    """
    profiles = _resolve_profiles(opts)
    settings = f"{profiles.machine};{profiles.process}"
    return [
        config.SLICER_BIN,
        "--slice", "1",
        "--load-settings", settings,
        "--load-filaments", str(profiles.filament),
        "--curr-bedtype", "Textured PEI Plate",
        "--export-3mf", str(output_path),
        str(input_path),
    ]


_NUM = r"([0-9]+(?:\.[0-9]+)?)"
_TIME_RE = re.compile(rf"(?:estimated|total).*?time[^0-9]*([0-9]+)\s*h.*?([0-9]+)\s*m", re.I)
# Grams, optionally followed by meters on the same "filament used" line.
_FILAMENT_RE = re.compile(rf"filament[^0-9]*{_NUM}\s*g(?:[^0-9]*{_NUM}\s*m\b)?", re.I)


def _parse_estimates(stdout: str) -> SliceResult:
    """Best-effort parse of estimates from CLI output.

    The CLI's exact wording varies by version, so this is lenient and may need
    tuning once we pin a Bambu Studio version in the Docker image. The estimates
    also live in the sliced .3mf metadata, which is a more robust source to add
    later.
    """
    result = SliceResult()
    if m := _TIME_RE.search(stdout):
        result.estimated_print_seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
    if m := _FILAMENT_RE.search(stdout):
        result.filament_grams = float(m.group(1))
        if m.group(2) is not None:
            result.filament_meters = float(m.group(2))
    return result


def slice_model(input_path: Path, output_path: Path, opts: SliceOptions) -> SliceResult:
    """Run the slicer. Raises SlicerError on any failure."""
    cmd = build_command(input_path, output_path, opts)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.SLICE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise SlicerError(
            f"Slicer binary '{config.SLICER_BIN}' not found. Install Bambu Studio "
            f"CLI or set SLICER2_SLICER_BIN. ({exc})"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SlicerError(f"Slicing timed out after {config.SLICE_TIMEOUT_SECONDS}s") from exc

    if proc.returncode != 0 or not output_path.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise SlicerError(f"Slicer exited {proc.returncode}: {tail}")

    return _parse_estimates(proc.stdout)
