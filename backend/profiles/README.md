# Slicing profiles

The Bambu Studio CLI needs three JSON presets per slice — **machine**,
**process**, and **filament**. These are *not* committed here because they ship
with Bambu Studio and are large; you extract the ones you need.

Slicer2 resolves them by filename under `profiles/<printer>/`:

```
profiles/a1/
├── machine.json              # the A1 / A1 mini printer definition
├── process_0.12mm.json       # process preset per layer height
├── process_0.20mm.json
├── process_0.28mm.json
├── filament_pla.json         # "Standard PLA"   (MVP profile)
└── filament_petg.json        # "Overture PETG"  (MVP profile)
```

The filename for a slice is derived from the user's options:
`process_{layer_height:.2f}mm.json` and `filament_{filament}.json`
(see `app/slicer.py`).

## Quickest path: `scripts/setup_slicer.sh`

To populate this directory automatically, run from the repo root:

```bash
./scripts/setup_slicer.sh a1_mini   # or: a1
```

It downloads OrcaSlicer (a Bambu Studio fork with the same CLI that **bundles
A1 profiles**), then runs `scripts/flatten_profiles.py` to resolve OrcaSlicer's
`inherits` chains into the standalone `machine.json` / `process_*.json` /
`filament_*.json` files described below. Review the output before trusting
print quality. To do it manually instead, read on.

## Where to get them

1. Install Bambu Studio (or OrcaSlicer) on a desktop, or pull them from the
   open-source resources:
   <https://github.com/bambulab/BambuStudio/tree/master/resources/profiles/BBL>
2. Configure the A1 mini with your filament/quality in the GUI, then
   **export** the machine / process / filament presets to JSON.
3. Drop them in `profiles/a1/` with the names above.

> Each exported JSON usually `"inherits"` a system preset by name. For headless
> use, either flatten the inheritance or ensure the parent presets are also
> discoverable by the CLI. Validate with `scripts/slice.sh model.stl a1_mini_pla`
> before wiring a profile into the UI.

## Adding a printer or material

Create `profiles/<model>/` and add the matching `filament_<key>.json`. Expose
the new option in the frontend and in `PrinterModel` / the filament dropdown.
