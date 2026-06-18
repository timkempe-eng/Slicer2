"""Tests for the OrcaSlicer profile flattener's inheritance resolution.

We can't download OrcaSlicer in CI, but we can prove the merge logic against
synthetic presets that mimic its ``inherits`` chains.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Load scripts/flatten_profiles.py (outside the package) by path.
_FLATTEN = Path(__file__).resolve().parents[2] / "scripts" / "flatten_profiles.py"
_spec = importlib.util.spec_from_file_location("flatten_profiles", _FLATTEN)
flat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flat)


def _write(root: Path, rel: str, data: dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


@pytest.fixture()
def tree(tmp_path):
    # base <- mid <- child inheritance chain, plus a sibling for indexing.
    _write(tmp_path, "process/base.json", {"name": "base", "layer_height": "0.2", "walls": "2"})
    _write(tmp_path, "process/mid.json", {"name": "mid", "inherits": "base", "walls": "3"})
    _write(tmp_path, "process/child.json",
           {"name": "0.20mm Standard @BBL A1", "inherits": "mid", "infill": "15%"})
    _write(tmp_path, "machine/a1mini.json", {"name": "Bambu Lab A1 mini 0.4 nozzle", "bed": "180"})
    return tmp_path


def test_index_collects_all_names(tree):
    index = flat.build_index(tree)
    assert "base" in index and "mid" in index
    assert "Bambu Lab A1 mini 0.4 nozzle" in index


def test_resolve_merges_chain_child_wins(tree):
    index = flat.build_index(tree)
    merged = flat.resolve("0.20mm Standard @BBL A1", index)
    assert merged["layer_height"] == "0.2"   # from base
    assert merged["walls"] == "3"            # mid overrides base
    assert merged["infill"] == "15%"         # child adds
    assert "inherits" not in merged          # stripped


def test_resolve_detects_cycle(tmp_path):
    _write(tmp_path, "a.json", {"name": "a", "inherits": "b"})
    _write(tmp_path, "b.json", {"name": "b", "inherits": "a"})
    index = flat.build_index(tmp_path)
    with pytest.raises(ValueError, match="cycle"):
        flat.resolve("a", index)


def test_missing_parent_is_tolerated(tmp_path, capsys):
    _write(tmp_path, "c.json", {"name": "c", "inherits": "nonexistent", "k": "v"})
    index = flat.build_index(tmp_path)
    merged = flat.resolve("c", index)
    assert merged["k"] == "v"  # resolves using child only


def test_find_name_pattern_priority(tree):
    index = flat.build_index(tree)
    name = flat.find_name(index, ["*A1 mini*0.4*nozzle*"])
    assert name == "Bambu Lab A1 mini 0.4 nozzle"
    assert flat.find_name(index, ["*nothing*"]) is None


def test_emit_writes_flattened_file(tree, tmp_path):
    index = flat.build_index(tree)
    out = tmp_path / "out" / "process_0.20mm.json"
    out.parent.mkdir(parents=True)
    assert flat._emit(index, ["*0.20mm Standard*"], out, "process") is True
    written = json.loads(out.read_text())
    assert written["infill"] == "15%" and "inherits" not in written
