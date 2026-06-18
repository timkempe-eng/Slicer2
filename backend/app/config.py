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

# Path to the headless slicer binary. Slicer2 standardises on OrcaSlicer (a
# Bambu Studio fork with the same CLI that bundles A1 profiles); override with
# SLICER2_SLICER_BIN to point at Bambu Studio or an absolute path.
SLICER_BIN = os.getenv("SLICER2_SLICER_BIN", "orca-slicer")

# Per-slice wall-clock timeout, seconds.
SLICE_TIMEOUT_SECONDS = int(os.getenv("SLICER2_SLICE_TIMEOUT", "600"))

# Upload limits / accepted input formats.
MAX_UPLOAD_BYTES = int(os.getenv("SLICER2_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".stl", ".3mf", ".step", ".stp", ".obj"}

# --- Durable stack ---------------------------------------------------------
# Persistent jobs. Defaults to a local sqlite file so dev/test need no Postgres;
# production injects a managed Postgres URL via DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'slicer2.db'}")

# Task queue. When REDIS_URL is set we enqueue slices to an RQ worker; otherwise
# slicing runs inline in-process (fine for dev/test and a single small host).
REDIS_URL = os.getenv("REDIS_URL")
RQ_QUEUE = os.getenv("SLICER2_RQ_QUEUE", "slicing")

# Object storage (DigitalOcean Spaces / any S3). When unset, uploads and sliced
# outputs live on local disk under DATA_DIR instead.
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
SPACES_REGION = os.getenv("SPACES_REGION", "nyc3")
SPACES_ACCESS_ID = os.getenv("SPACES_ACCESS_ID")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")

for _d in (UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
