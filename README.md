# Slicer2

**Better slicing as a service.**

Slicer2 is an online 3D-print slicing service. Upload a model (`STL`/`STEP`/`3MF`)
from any device — including your phone — and Slicer2 slices it **in the cloud**
into a ready-to-print Bambu `.gcode.3mf`. You then print it on the A1's screen
straight from a **microSD card** — no PC and no Bambu Studio, ever.

> First target printer: **Bambu Lab A1 / A1 mini.**

## Why

Slicing normally means sitting at a desktop running Bambu Studio. Slicer2 moves
the slicer to the server, so the one thing that needed a PC now works from a
browser on your phone. The sliced file is the deliverable.

> **A note on auto-push.** We deliberately do *not* push prints to the printer
> for you. A hosted service can't reach a printer behind your home router, and
> Bambu's **Authorization Control System** (2025) blocks third-party tools from
> starting cloud prints — that's reserved for Bambu's own apps. Bambu Handy also
> can't import an arbitrary local file. So the sanctioned, reliable no-PC route
> is **download → microSD → Print Files on the A1's screen**. A future,
> opt-in *on-network* "local bridge" could automate delivery for users who run
> their printer in LAN/Developer mode.

## How it works

```
Phone / browser ──upload model──▶ FastAPI API ──RQ queue (Redis)──▶ Slicer worker
                                       │                            (OrcaSlicer CLI, Docker)
                                  Postgres (jobs)                          │
                                  Spaces (files)  ◀──── .gcode.3mf ────────┘
                                       │
                                       ▼
                            Download .gcode.3mf  ─▶  microSD  ─▶  Print Files on the A1 screen
```

The hard part and how Slicer2 solves it:

| Problem | Solution | Status |
|---|---|---|
| Slice without a PC | Headless **OrcaSlicer CLI** in Docker (RQ worker) | Implemented (needs the binary + baked A1 profiles in the image) |
| Durable, multi-request jobs | **Postgres** + **Redis/RQ** queue + **Spaces** object storage | Implemented |
| Deliver to printer without a PC | **microSD → Print Files** on the A1's screen | Works today (manual, fully sanctioned) |
| Automated delivery | On-network **local bridge** (LAN/Developer mode) | Deferred — cloud auto-push is blocked by Bambu's ACS |

## Project status

Early scaffold. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased plan and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

- ✅ FastAPI backend, mobile web UI, durable jobs (Postgres) + RQ worker (Redis)
      + object storage (Spaces), with sqlite/local-disk fallbacks for dev
- ✅ Slicer abstraction that shells out to the OrcaSlicer CLI
- ⚠️ A1 slicing **profiles** are baked into the worker image at build time from
      OrcaSlicer's bundled presets — verify a real slice on a build host
      (`scripts/verify_slice.sh`); see `backend/profiles/README.md`
- ⛔ Automated printer delivery is **out of scope** (blocked by Bambu's ACS and
      home-NAT); the no-PC path is **download → microSD → Print Files**

## Quick start (local)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://localhost:8000
```

The API boots and serves the UI without the slicer binary; actual slicing
requires the Bambu Studio CLI on `PATH` (or run via Docker — see
`docker-compose.yml`). See `docs/ARCHITECTURE.md` for details.

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest                 # unit + API tests (no slicer binary needed)
pytest -m integration  # real slice; needs a slicer binary + A1 profiles
```

To prove a real end-to-end slice on a capable host (the slicer Docker image or
a box with OrcaSlicer/Bambu Studio installed):

```bash
./scripts/verify_slice.sh   # generates a cube, slices it, validates the .gcode.3mf
```

## Hosting / deploy (DigitalOcean)

Terraform under [`infra/terraform`](infra/terraform) provisions the whole stack
— a CPU-Optimized **Droplet** (app + in-process slicer + Redis via
docker-compose), **Managed PostgreSQL**, a **Spaces** bucket with a 1-day
retention rule, and a cloud firewall — mirroring DO's marketplace blueprints.
The droplet runs [`deploy/docker-compose.prod.yml`](deploy). Starter cost is
roughly **$60/mo**. See [`infra/README.md`](infra/README.md) for sizing,
the App-Platform alternative, and the deploy steps.

```bash
cd infra/terraform && cp terraform.tfvars.example terraform.tfvars
terraform init && terraform plan   # review billable resources before apply
```

## License & disclaimer

Slicer2 is an independent project and is **not affiliated with or endorsed by
Bambu Lab**. The Bambu Cloud integration relies on a reverse-engineered,
unofficial API and may break or conflict with Bambu Lab's Terms of Service —
use it with your own account and printer at your own risk.
