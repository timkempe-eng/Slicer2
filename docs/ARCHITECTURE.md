# Slicer2 — Architecture

## Overview

Slicer2 is a web service that slices 3D models server-side and hands back a
ready-to-print `.gcode.3mf`. The user prints it with no PC by copying it to a
microSD card and selecting it on the A1's screen. It has three logical parts:

1. **Web API + UI** (`backend/app`) — FastAPI app serving a mobile-first
   frontend and a small REST API for uploads, jobs, and download.
2. **Slicer** (`backend/app/slicer.py`) — wraps the headless **OrcaSlicer CLI**
   (a Bambu Studio fork with the same CLI that bundles A1 profiles), which runs
   in a Docker image and turns an input model into a `.gcode.3mf` using
   printer/process/filament **profiles**.
3. **Durable stack** — jobs in **Postgres** (`db_models.JobRow`), a **Redis/RQ**
   task queue draining to a separate slicing **worker**, and uploads/outputs in
   **Spaces/S3** object storage.

```
                ┌──────────────────────────────────────────┐
   phone ──────▶│  FastAPI (app/main.py)                    │
   browser      │   POST /api/slice   ── creates a Job      │
                │   GET  /api/jobs/{id}                      │
                │   GET  /api/jobs/{id}/download             │
                └───────────────┬──────────────────────────┘
          jobs.py ──────────────┼──────────────────────────────┐
            │                    │                              │
        Postgres            Redis / RQ  ──▶  worker: run_slice  │
        (JobRow)              queue            │                │
            │                          slicer.py (OrcaSlicer)   │
            └────────────  Spaces/S3 (uploads, outputs)  ◀──────┘
                                   │
                          download .gcode.3mf ─▶ microSD ─▶ A1 screen
```

Both the queue and storage have **local fallbacks** (inline slicing + sqlite +
local disk) so dev/test and a single small host need no external services — the
behaviour is selected purely by whether `REDIS_URL` / `SPACES_*` / `DATABASE_URL`
are set (see `config.py`).

## Request flow (slice → download)

1. Client `POST /api/slice` with the model file + options (printer, filament,
   layer height, infill, supports).
2. The API streams the upload to object storage (`uploads/<id>/<file>`), creates
   a `Job` row (status `queued`), and enqueues `jobs.run_slice`.
3. The worker pulls the job, downloads the model to a temp dir, runs the
   OrcaSlicer CLI (`slicer.py`) into `<id>.gcode.3mf`, uploads it to
   `outputs/<id>.gcode.3mf`, parses estimates, and sets the job `done`.
4. Client polls `GET /api/jobs/{id}` until `done`, then `GET /…/download` — a
   presigned redirect (remote storage) or a streamed file (local).

## Slicing

The OrcaSlicer CLI is invoked roughly as:

```
orca-slicer --slice 1 \
  --load-settings "machine.json;process.json" \
  --load-filaments "filament.json" \
  --export-3mf <out>.gcode.3mf <input>.stl
```

Profiles are **baked into the worker image** at build time by flattening
OrcaSlicer's bundled A1 presets (`scripts/flatten_profiles.py`), so the binary
version and profiles always match. The slicer resolves named presets by layer
height/filament under `backend/profiles/a1/`; see `backend/profiles/README.md`.

## Delivery (and why there's no auto-push)

The MVP delivers the **file**: download → microSD → *Print Files* on the A1
screen. Fully sanctioned, no PC, no Bambu Studio.

Automated push to the printer is intentionally **out of scope**:

- Bambu's **Authorization Control System** (2025) blocks third-party tools from
  starting cloud prints — that's reserved for Bambu's own apps (Studio/Handy).
- **Bambu Handy can't import a local `.gcode.3mf`** (only MakerWorld / cloud
  library files).
- A hosted server **can't reach a home printer behind NAT** over LAN.

`printer/lan.py` (FTPS + MQTT) and `printer/cloud.py` remain in the tree for a
future **opt-in on-network "local bridge"** (an agent / Tailscale to a printer
in LAN/Developer mode) — the only sanctioned way to automate phone→home-printer.
The `POST /api/jobs/{id}/print` endpoint exercises the LAN path for on-network
self-hosters; cloud returns `501`.

## Data & state

- Uploads: object key `uploads/<job_id>/<filename>`
- Outputs: object key `outputs/<job_id>.gcode.3mf`
- Jobs: `jobs` table in Postgres (Alembic-migrated; `ensure_schema()` covers dev)
- Object lifecycle: the Spaces bucket expires uploads/outputs (infra: 1 day)

## Known limitations / non-goals (for now)

- No auth / multi-tenant accounts yet.
- One printer model (A1) wired; others are a profile + nozzle-config exercise.
- Estimate parsing is best-effort stdout scraping; pin the OrcaSlicer release
  and tune it (or read estimates from the `.gcode.3mf` metadata).
