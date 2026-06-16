# Slicer2 — Architecture

## Overview

Slicer2 is a web service that slices 3D models server-side and delivers the
result to a Bambu Lab printer. It has three logical components:

1. **Web API + UI** (`backend/app`) — FastAPI app serving a mobile-first
   frontend and a small REST API for uploads, jobs, and printing.
2. **Slicer** (`backend/app/slicer.py`) — wraps the headless **Bambu Studio
   CLI**, which runs in a Docker image and converts an input model into a
   `.gcode.3mf` using printer/process/filament **profiles**.
3. **Printer delivery** (`backend/app/printer/`) — sends the sliced file to a
   printer and starts the job, over **LAN** or **Bambu Cloud**.

```
                ┌──────────────────────────────────────────┐
   phone ──────▶│  FastAPI (app/main.py)                    │
   browser      │   POST /api/slice   ── creates a Job      │
                │   GET  /api/jobs/{id}                      │
                │   GET  /api/jobs/{id}/download             │
                │   POST /api/jobs/{id}/print                │
                └───────────────┬──────────────────────────┘
                                │
                    jobs.py (in-memory store + background task)
                                │
                 ┌──────────────┴───────────────┐
                 ▼                               ▼
        slicer.py (Bambu Studio CLI)   printer/ (LAN | Cloud)
                 │                               │
          data/outputs/*.gcode.3mf       FTPS upload + MQTT start
```

## Request flow (slice → print)

1. Client `POST /api/slice` with the model file + options (printer model,
   filament, layer height, infill, etc.).
2. Backend stores the upload in `data/uploads/`, creates a `Job` (status
   `queued`), and runs slicing in a background task.
3. `slicer.py` resolves the right profile JSONs for the chosen printer (A1),
   invokes the Bambu Studio CLI, and writes `data/outputs/<job>.gcode.3mf`.
   It parses estimated print time / filament usage from the CLI output.
4. Client polls `GET /api/jobs/{id}` until `done`, then either:
   - `GET /api/jobs/{id}/download` to get the `.gcode.3mf`, or
   - `POST /api/jobs/{id}/print` to push it to a configured printer.

## Slicing

The Bambu Studio CLI (a superset shared with OrcaSlicer) is invoked roughly as:

```
bambu-studio --slice 1 \
  --load-settings "machine.json;process.json" \
  --load-filaments "filament.json" \
  --export-3mf <out>.gcode.3mf <input>.stl
```

Profiles are **not** bundled (they are large and shipped with Bambu Studio).
See `backend/profiles/README.md` for how to populate
`backend/profiles/a1/`. The slicer resolves a small set of named presets
(layer height, infill density) onto a base process profile.

## Printer delivery

Both transports implement the same `PrinterClient` interface
(`app/printer/base.py`):

- **LAN** (`lan.py`): connects on the local network using the printer's
  IP + access code. Uploads the `.gcode.3mf` via **FTPS (implicit TLS, port
  990, user `bblp`)**, then starts the print by publishing an MQTT message to
  `device/<serial>/request` on the printer's broker (**TLS port 8883**).
  Well-documented and testable without internet.
- **Cloud** (`cloud.py`): authenticates to Bambu Cloud, uploads through the
  cloud, and issues the print command via the cloud MQTT broker so it works
  from anywhere and stays visible in Bambu Handy. **Unofficial / reverse
  engineered** — implemented against community projects (pybambu,
  bambulabs_api, Bambuddy) and must be validated against a real account +
  printer before it can be trusted. Prefer wrapping a maintained community
  library over hand-rolling the protocol.

## Data & state

- Uploads: `data/uploads/<job_id>/<filename>`
- Outputs: `data/outputs/<job_id>.gcode.3mf`
- Job state: in-memory dict for the MVP (`jobs.py`). Replace with Redis +
  a real queue (RQ/Celery/arq) and object storage (S3/R2) before multi-user.

## Known limitations / non-goals (for now)

- No auth / multi-tenant accounts yet.
- In-memory jobs do not survive a restart.
- One printer model (A1) wired; others are a profile + nozzle-config exercise.
- Bambu Cloud automation may conflict with Bambu Lab ToS (see README).
