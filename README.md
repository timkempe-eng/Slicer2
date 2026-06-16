# Slicer2

**Better slicing as a service.**

Slicer2 is an online 3D-print slicing service. Upload a model (`STL`/`STEP`/`3MF`)
from any device — including your phone — and Slicer2 slices it **in the cloud**
into a ready-to-print Bambu `.gcode.3mf`, then (optionally) pushes the job
straight to your Bambu Lab printer. The goal: go from model to printing **without
ever touching a PC**, while still monitoring the print in **Bambu Handy**.

> First target printer: **Bambu Lab A1 / A1 mini.**

## Why

Bambu Handy can start *pre-sliced* models, but it can't slice an arbitrary STL,
and slicing normally means sitting at a desktop running Bambu Studio. Slicer2
moves the slicer to the server so the whole flow works from a browser on your
phone.

## How it works

```
Phone / browser ──upload model──▶ FastAPI backend ──queue──▶ Slicer worker
                                                              (Bambu Studio CLI, Docker)
                                                                    │
                                                            produces .gcode.3mf
                                                                    │
        ┌───────────────────────────────────────────────────────────┤
        ▼                                                             ▼
  Download .gcode.3mf                                   Push to printer (LAN or Bambu Cloud)
  (send from Handy / SD)                                monitor the running print in Handy
```

The two hard parts and how Slicer2 solves them:

| Problem | Solution | Status |
|---|---|---|
| Slice without a PC | Headless **Bambu Studio CLI** in Docker | Implemented (needs the CLI binary in the image) |
| Deliver to printer without a PC | **FTPS upload + MQTT start** over LAN or Bambu Cloud | LAN scaffolded; Cloud scaffolded, needs live test |

## Project status

Early scaffold. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased plan and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

- ✅ FastAPI backend, job model, mobile web UI
- ✅ Slicer abstraction that shells out to the Bambu Studio CLI
- ⚠️ A1 slicing **profiles** must be supplied (see `backend/profiles/README.md`)
- ⚠️ Printer delivery (LAN/Cloud) is wired against the community-documented
  protocol but **not yet verified against real hardware**

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
