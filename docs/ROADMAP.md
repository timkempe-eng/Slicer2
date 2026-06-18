# Slicer2 — Roadmap

Target hardware for v1: **Bambu Lab A1 / A1 mini**.
End goal: upload from a phone → slice in the cloud → get a ready-to-print
`.gcode.3mf`, all with **no PC and no Bambu Studio**.

> **Committed delivery model (revised June 2026):** **slice + download**, then
> print from a **microSD card** via *Print Files* on the A1's screen.
>
> The earlier "Bambu Cloud push, monitor in Handy" plan is **not viable** for a
> hosted service:
> - Bambu's **Authorization Control System** (Jan 2025) makes cloud
>   print-initiation exclusive to Bambu's own apps — third parties get
>   monitoring only.
> - **Bambu Handy can't import a local `.gcode.3mf`** (only MakerWorld / cloud
>   library files).
> - A cloud server **can't reach a home printer behind NAT** over LAN.
>
> Automated delivery is therefore deferred to an opt-in **on-network local
> bridge** (a small agent / Tailscale to a printer in LAN/Developer mode) — the
> only sanctioned way to automate phone→home-printer.

## MVP — Slice in the cloud, print via microSD  ✅
- [x] FastAPI backend + mobile web UI
- [x] Upload endpoint (STL / 3MF / STEP / OBJ)
- [x] OrcaSlicer CLI wrapper + A1 profiles baked into the worker image
- [x] Durable jobs (Postgres) + RQ worker (Redis) + object storage (Spaces),
      with sqlite/local-disk fallbacks for dev/test
- [x] Download the resulting `.gcode.3mf`; UI explains the microSD print flow
- [x] Test harness: unit + API + job-persistence tests, skip-marked real-slice
      integration test (`pytest`), and `scripts/verify_slice.sh`
- [ ] **Verify a real slice on a build host** (`scripts/verify_slice.sh`) and
      pin the OrcaSlicer release + asset URL in `docker/slicer.Dockerfile`
- [ ] Tune the estimate parser against the pinned OrcaSlicer stdout (prefer
      reading estimates from the `.gcode.3mf` metadata later)

## Next — Automated on-network delivery (opt-in "local bridge")
The only sanctioned way to automate phone→home-printer. Requires software on the
user's network and the printer in LAN/Developer mode (which disables ACS).
- [ ] On-network agent (or Tailscale) so the service can reach the printer
- [ ] FTPS upload (port 990) + MQTT `start_print` (port 8883) — `printer/lan.py`
      is already written; validate against real A1 hardware
- [ ] Live status (progress %, stage, errors) over MQTT in our own UI

## Later — Product
- [ ] User accounts + multiple saved printers + print history / re-slice
- [ ] Profile presets per material; AMS / multi-color support
- [ ] Additional printer models (P1, X1, H2D)

## Open questions / risks
- Profile management (per nozzle / material) is the main quality lever.
- Hosting the slicer is CPU/RAM heavy — the RQ worker needs a pool + limits.
- Bambu's ACS may tighten further; keep delivery paths sanctioned.
