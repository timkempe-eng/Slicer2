# Slicer2 — Roadmap

Target hardware for v1: **Bambu Lab A1 / A1 mini**.
End goal: upload from a phone → slice in the cloud → push to the printer via
**Bambu Cloud**, monitored in Bambu Handy, with no PC involved.

> **Committed delivery model:** direct **Bambu Cloud push** (Phase 2) — the
> "no PC, works anywhere, monitor in Handy" path. Download stays available as a
> fallback. (Decision supersedes the PRD's download-only delivery.)

## Phase 0 — Slice in the cloud  ✅ scaffolded
- [x] FastAPI backend + mobile web UI
- [x] Upload endpoint (STL / 3MF / STEP / OBJ)
- [x] Job model + background slicing task
- [x] Bambu Studio CLI wrapper
- [x] Download the resulting `.gcode.3mf`
- [x] Test harness: unit + API tests, generated cube, skip-marked real-slice
      integration test (`pytest`), and `scripts/verify_slice.sh`
- [ ] **Supply real A1 profiles** (`backend/profiles/a1/`) and verify a slice
      (run `scripts/verify_slice.sh` on a host with OrcaSlicer/Bambu Studio)
- [ ] Parse + show estimated print time and filament usage (best-effort parser
      in place; prefer reading estimates from the .3mf metadata)
- [ ] Build + run the slicer Docker image (verify the AppImage asset URL)

## Phase 1 — LAN push (your own bench testing)
- [ ] FTPS upload to the printer (port 990, user `bblp`, access code)
- [ ] MQTT `start_print` to `device/<serial>/request` (port 8883, TLS)
- [ ] Live status (progress %, stage, errors) over MQTT
- [ ] "Print now" button in the UI

## Phase 2 — Bambu Cloud push (the no-PC goal)
- [ ] Bambu Cloud login (account link + token storage)
- [ ] Cloud file upload + cloud MQTT `start_print`
- [ ] Verify the job appears / is controllable in Bambu Handy
- [ ] Decide whether to wrap a maintained lib (pybambu / bambulabs_api)

## Phase 3 — Product
- [ ] User accounts + multiple saved printers
- [ ] Persistent jobs (DB) + real queue + object storage
- [ ] Print history, re-slice, profile presets per material
- [ ] AMS / multi-color support
- [ ] Additional printer models (P1, X1, H2D)

## Open questions / risks
- Bambu Cloud API is unofficial and may change or violate ToS.
- Profile management (per nozzle / material) is the main quality lever.
- Hosting the slicer is CPU/RAM heavy — needs a worker pool + limits.
