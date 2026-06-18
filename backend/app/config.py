"""Runtime configuration for the Slicer2 backend.

All values can be overridden with environment variables so the same code runs
locally, in Docker, and in production.
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Where uploads, sliced outputs, and other runtime artifacts live.
DATA_DIR = Path(os.getenv("SLICER2_DATA_DIR", BACKEND_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

# Bambu Studio / OrcaSlicer profile JSONs, organised per printer model.
PROFILES_DIR = Path(os.getenv("SLICER2_PROFILES_DIR", BACKEND_DIR / "profiles"))

# Path to the headless slicer binary (Bambu Studio or OrcaSlicer).
SLICER_BIN = os.getenv("SLICER2_SLICER_BIN", "bambu-studio")

# Per-slice wall-clock timeout, seconds.
SLICE_TIMEOUT_SECONDS = int(os.getenv("SLICER2_SLICE_TIMEOUT", "600"))

# Upload limits / accepted input formats.
MAX_UPLOAD_BYTES = int(os.getenv("SLICER2_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".stl", ".3mf", ".step", ".stp", ".obj"}

for _d in (UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
