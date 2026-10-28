"""The canonical mesh (Stage 3b): the tracked STL is written by the bridge, not by Fusion, so its bytes are deterministic, and its hash does not depend on Fusion's
vertex or face order.

Canonical form: vertices rounded to 1e-4 mm (integers of 0.1 micron), each triangle rotated cyclically to start at its smallest vertex (winding kept), triangles
sorted. The hash is the sha256 of those integers; the file holds the same rounded values as float32 with a fixed header, so the hash of the file equals the
hash of the mesh.
"""
from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import numpy as np

from envelope import registry

ROUND_MM = 1e-4         # the mesh hash resolves 0.1 micron, far below the 0.05 mm chord tolerance of the export
HEADER = b"freyja cad canonical mesh v1".ljust(80, b" ")
_SCALE = 1.0 / ROUND_MM
_STL = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])


def _canonical_ints(vertices, faces) -> np.ndarray:
    """(n_faces, 3, 3) int64: rounded, cyclically rotated to the smallest vertex, sorted."""
    v = np.rint(np.asarray(vertices, np.float32).astype(np.float64) * _SCALE).astype(np.int64)
    tri = v[np.asarray(faces, int)]
    out = np.empty_like(tri)
    for i, t in enumerate(tri):
        k = min(range(3), key=lambda j: tuple(t[j]))
        out[i] = np.roll(t, -k, axis=0)
    flat = out.reshape(len(out), 9)
    order = np.lexsort(tuple(flat[:, c] for c in range(8, -1, -1)))
    return out[order]


def mesh_hash(vertices, faces) -> str:
    return hashlib.sha256(_canonical_ints(vertices, faces).astype("<i8").tobytes()).hexdigest()


def _normals(tri: np.ndarray) -> np.ndarray:
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)


def write_canonical_stl(path, vertices, faces) -> str:
    """Write the binary STL of the canonical mesh; returns its hash."""
    ints = _canonical_ints(vertices, faces)
    tri = ints.astype(np.float64) * ROUND_MM
    rec = np.zeros(len(tri), dtype=_STL)
    rec["n"] = _normals(tri).astype(np.float32)
    rec["v"] = tri.astype(np.float32)
    Path(path).write_bytes(HEADER + struct.pack("<I", len(tri)) + rec.tobytes())
    return hashlib.sha256(ints.astype("<i8").tobytes()).hexdigest()


def hash_stl_file(path) -> str:
    raw = Path(path).read_bytes()
    n = struct.unpack("<I", raw[80:84])[0]
    a = np.frombuffer(raw[84:], dtype=_STL, count=n)
    flat = a["v"].reshape(-1, 3)
    return mesh_hash(flat, np.arange(len(flat)).reshape(-1, 3))


MIN_NORMAL_DEG = 2.0       # below this a large radius would make the mesh enormous (the 5 MB limit on the tracked STL)
MAX_NORMAL_DEG = 15.0      # Fusion's own default normal deviation


def normal_deviation_deg(chord_tolerance_mm: float, max_radius_mm) -> float:
    """The normal deviation, in degrees, that keeps the chord error of the largest analytic arc within the tolerance: s = r (1 - cos(theta / 2)). Fusion's
    STL export takes this and ignores its surface deviation setting (T3 finding); a part with no analytic curved face gets the default."""
    if max_radius_mm is None or max_radius_mm <= chord_tolerance_mm:
        return MAX_NORMAL_DEG
    theta = 2.0 * math.degrees(math.acos(1.0 - chord_tolerance_mm / max_radius_mm))
    return min(MAX_NORMAL_DEG, max(MIN_NORMAL_DEG, theta))


def bounds(vertices):
    v = np.asarray(vertices, float)
    return v.min(axis=0), v.max(axis=0)


def read(path):
    return registry.read_stl(path)
