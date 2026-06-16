"""Test helpers, including a tiny binary-STL generator.

We generate the test model at runtime instead of committing a binary blob, so
the fixture is transparent and easy to tweak.
"""
from __future__ import annotations

import struct
from pathlib import Path


def write_cube_stl(path: Path, size: float = 20.0) -> Path:
    """Write a watertight axis-aligned cube as a binary STL.

    12 triangles (2 per face). Good enough to feed a real slicer end-to-end.
    """
    s = float(size)
    v = [
        (0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0),  # bottom
        (0, 0, s), (s, 0, s), (s, s, s), (0, s, s),  # top
    ]
    # Each face as two triangles, wound counter-clockwise (outward normals).
    faces = [
        (0, 3, 2), (0, 2, 1),  # bottom (z=0)
        (4, 5, 6), (4, 6, 7),  # top (z=s)
        (0, 1, 5), (0, 5, 4),  # front (y=0)
        (2, 3, 7), (2, 7, 6),  # back (y=s)
        (1, 2, 6), (1, 6, 5),  # right (x=s)
        (0, 4, 7), (0, 7, 3),  # left (x=0)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"Slicer2 test cube".ljust(80, b"\0"))  # 80-byte header
        f.write(struct.pack("<I", len(faces)))
        for a, b, c in faces:
            f.write(struct.pack("<3f", 0.0, 0.0, 0.0))  # normal (slicers recompute)
            for idx in (a, b, c):
                f.write(struct.pack("<3f", *v[idx]))
            f.write(struct.pack("<H", 0))  # attribute byte count
    return path
