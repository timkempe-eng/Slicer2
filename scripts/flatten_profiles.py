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
PROCESS_PATTERNS = {
    "0.12mm": ["*0.12mm*A1*", "*0.12mm Fine*", "*0.12mm*"],
    "0.20mm": ["*0.20mm Standard*A1*", "*0.20mm Standard*", "*0.20mm*"],
    "0.28mm": ["*0.28mm*A1*", "*0.28mm Extra Draft*", "*0.28mm*"],
}
FILAMENT_PATTERNS = {
    "pla": ["*PLA Basic @BBL A1*", "*Bambu PLA Basic*", "*Generic PLA*", "*PLA*"],
    "petg": ["*PETG @BBL A1*", "*Bambu PETG*", "*Generic PETG*", "*PETG*"],
}


def build_index(root: Path) -> dict[str, Path]:
    """Map every preset's ``name`` -> file path under the resources tree."""
    index: dict[str, Path] = {}
    for path in root.rglob("*.json"):
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resources", required=True, type=Path,
                    help="OrcaSlicer/Bambu Studio resources dir (contains profiles/).")
    ap.add_argument("--printer", choices=list(PRINTER_PATTERNS), default="a1_mini")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output profile dir, e.g. backend/profiles/a1")
    args = ap.parse_args()

    if not args.resources.exists():
        print(f"resources dir not found: {args.resources}", file=sys.stderr)
        return 2

    print(f"Indexing presets under {args.resources} …")
    index = build_index(args.resources)
    print(f"Found {len(index)} named presets.")

    args.out.mkdir(parents=True, exist_ok=True)
    ok = True
    ok &= _emit(index, PRINTER_PATTERNS[args.printer], args.out / "machine.json", "machine")
    for layer, pats in PROCESS_PATTERNS.items():
        ok &= _emit(index, pats, args.out / f"process_{layer}.json", f"process {layer}")
    for mat, pats in FILAMENT_PATTERNS.items():
        ok &= _emit(index, pats, args.out / f"filament_{mat}.json", f"filament {mat}")

    if not ok:
        print("\nSome profiles were not found — adjust patterns in this script "
              "or drop JSONs in manually (see backend/profiles/README.md).",
              file=sys.stderr)
        return 1
    print(f"\nWrote flattened profiles to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
