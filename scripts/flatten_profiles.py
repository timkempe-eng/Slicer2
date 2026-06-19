#!/usr/bin/env python3
"""Flatten OrcaSlicer / Bambu Studio bundled profiles into standalone JSONs.

OrcaSlicer ships printer / process / filament presets that use an ``inherits``
chain (a child preset names a parent and overrides a few keys). The headless
CLI works most reliably with self-contained settings files, so this resolves
the inheritance and writes flat JSONs named the way ``app/slicer.py`` expects:

    machine.json
    process_0.12mm.json / process_0.20mm.json / process_0.28mm.json
    filament_pla.json / filament_petg.json

Discovery is by flexible name patterns (presets are matched by their ``name``
field), so it tolerates version-to-version naming drift. It prints what it
picked — eyeball that before trusting a slice.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

# name-pattern candidates, tried in order; first match wins.
PRINTER_PATTERNS = {
    "a1_mini": ["Bambu Lab A1 mini 0.4 nozzle", "*A1 mini*0.4*nozzle*", "*A1 mini*"],
    "a1": ["Bambu Lab A1 0.4 nozzle", "*A1 0.4*nozzle*", "*Lab A1*0.4*"],
}
# Process/filament are matched by quality/material here; the correct *printer
# variant* (A1 vs A1 mini — '@BBL A1' vs '@BBL A1M') is then chosen by
# compatible_printers + the name suffix, since OrcaSlicer rejects a process
# whose compatible_printers doesn't include the machine.
PRINTER_SUFFIX = {"a1_mini": "A1M", "a1": "A1"}
PROCESS_BASE = {
    "0.12mm": ["*0.12mm Fine*", "*0.12mm*"],
    "0.20mm": ["*0.20mm Standard*", "*0.20mm*"],
    "0.28mm": ["*0.28mm Extra Draft*", "*0.28mm Draft*", "*0.28mm*"],
}
# Lead with the real material presets so we never grab e.g. a support filament.
FILAMENT_BASE = {
    "pla": ["*Bambu PLA Basic*", "*PLA Basic*", "*Generic PLA*"],
    "petg": ["*Bambu PETG Basic*", "*PETG Basic*", "*PETG HF*", "*Generic PETG*"],
}


def build_index(root: Path, vendor: str | None = None) -> dict[str, Path]:
    """Map every preset's ``name`` -> file path under the resources tree.

    OrcaSlicer ships ~120 vendors that reuse the *same* base preset names (e.g.
    ``fdm_process_common``), many with incompatible values (percentage line
    widths). Resolving a Bambu preset against another vendor's base produces a
    broken config. When ``vendor`` is given and a ``<vendor>/`` directory exists
    in the tree, index only presets under it so inheritance stays self-consistent
    (fall back to the whole tree if that vendor isn't present).
    """
    paths = sorted(root.rglob("*.json"))
    if vendor:
        scoped = [p for p in paths if vendor in p.parts]
        if scoped:
            paths = scoped
    index: dict[str, Path] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            name = data.get("name")
            if name and name not in index:
                index[name] = path
    return index


def resolve(name: str, index: dict[str, Path], _seen: set[str] | None = None) -> dict:
    """Return the fully-merged settings dict for a preset name."""
    _seen = _seen or set()
    if name in _seen:
        raise ValueError(f"inheritance cycle detected at '{name}'")
    _seen.add(name)

    path = index.get(name)
    if path is None:
        raise KeyError(name)
    data = json.loads(path.read_text())

    parent_name = data.get("inherits")
    if parent_name and parent_name in index:
        merged = resolve(parent_name, index, _seen)
    else:
        if parent_name:
            print(f"  ! parent '{parent_name}' not on disk; using child only", file=sys.stderr)
        merged = {}
    merged.update(data)
    merged.pop("inherits", None)
    return merged


def find_name(index: dict[str, Path], patterns: list[str]) -> str | None:
    for pat in patterns:
        for name in index:
            if fnmatch.fnmatch(name, pat):
                return name
    return None


def _emit(index, patterns, out: Path, label: str) -> bool:
    name = find_name(index, patterns)
    if name is None:
        print(f"  ✗ {label}: no preset matched {patterns}", file=sys.stderr)
        return False
    flat = resolve(name, index)
    out.write_text(json.dumps(flat, indent=2))
    print(f"  ✓ {label}: '{name}' -> {out.name}")
    return True


def _suffix_ok(name: str, suffix: str) -> bool:
    """True if the preset name targets this printer variant (e.g. '@BBL A1M').

    The plain 'A1' suffix must not match the 'A1M' variant (substring clash).
    """
    if f"@BBL {suffix}" not in name:
        return False
    return not (suffix == "A1" and "@BBL A1M" in name)


def pick_for_printer(index, base_patterns, machine_name: str, suffix: str) -> str | None:
    """Choose the preset for THIS printer among material/quality candidates.

    Rank by: compatible_printers contains the machine (authoritative), then the
    name suffix. Returns None if no candidate can be tied to the printer, so we
    never bake an incompatible preset (which OrcaSlicer would reject anyway).
    """
    cands: list[str] = []
    for pat in base_patterns:
        for name in index:
            if fnmatch.fnmatch(name, pat) and name not in cands:
                cands.append(name)
    if not cands:
        return None

    def score(name: str) -> tuple[int, int]:
        compat = 0
        try:
            if machine_name in (resolve(name, index).get("compatible_printers") or []):
                compat = 1
        except Exception:
            pass
        return (compat, 1 if _suffix_ok(name, suffix) else 0)

    cands.sort(key=score, reverse=True)
    best = cands[0]
    return best if score(best) != (0, 0) else None


def _emit_name(index, name: str | None, out: Path, label: str, patterns) -> bool:
    if name is None:
        print(f"  ✗ {label}: no printer-compatible preset among {patterns}", file=sys.stderr)
        return False
    out.write_text(json.dumps(resolve(name, index), indent=2))
    print(f"  ✓ {label}: '{name}' -> {out.name}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resources", required=True, type=Path,
                    help="OrcaSlicer/Bambu Studio resources dir (contains profiles/).")
    ap.add_argument("--printer", choices=list(PRINTER_PATTERNS), default="a1_mini")
    ap.add_argument("--vendor", default="BBL",
                    help="Resolve inheritance within this vendor subtree only "
                         "(default BBL — Bambu). Avoids cross-vendor name clashes.")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output profile dir, e.g. backend/profiles/a1")
    args = ap.parse_args()

    if not args.resources.exists():
        print(f"resources dir not found: {args.resources}", file=sys.stderr)
        return 2

    print(f"Indexing presets under {args.resources} (vendor={args.vendor}) …")
    index = build_index(args.resources, vendor=args.vendor)
    print(f"Found {len(index)} named presets.")

    args.out.mkdir(parents=True, exist_ok=True)
    suffix = PRINTER_SUFFIX[args.printer]
    machine_name = find_name(index, PRINTER_PATTERNS[args.printer])

    ok = _emit_name(index, machine_name, args.out / "machine.json", "machine",
                    PRINTER_PATTERNS[args.printer])
    if machine_name is not None:
        for layer, pats in PROCESS_BASE.items():
            name = pick_for_printer(index, pats, machine_name, suffix)
            ok &= _emit_name(index, name, args.out / f"process_{layer}.json",
                             f"process {layer}", pats)
        for mat, pats in FILAMENT_BASE.items():
            name = pick_for_printer(index, pats, machine_name, suffix)
            ok &= _emit_name(index, name, args.out / f"filament_{mat}.json",
                             f"filament {mat}", pats)

    if not ok:
        print("\nSome profiles were not found — adjust patterns in this script "
              "or drop JSONs in manually (see backend/profiles/README.md).",
              file=sys.stderr)
        return 1
    print(f"\nWrote flattened profiles to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
