"""The component registry (volume-extractor brief 6, item 2): what already sits inside a segment's envelope, one authored YAML per segment, `components/1`.

    schema: components/1
    segment: thigh_R                    # the segment frame everything below is in
    components:
      - id: free text                   # free text until Stage 4 fixes the CAD export format
        name: actuator
        status: designed                # designed | reserved | candidate | foreign
        owner: thigh_R                  # the owning segment; a foreign component is owned by another segment
        primitive: {type: cylinder, diameter: 70, length: 110}     # the required bounding primitive (the oracle's shape dict: capsule, cylinder, box; offset and rpy_deg allowed)
        mesh: actuator.stl              # optional: an STL (path relative to this file), vertices in the component frame; used instead of the primitive when present
        pose: {tx: 0, ty: 0, tz: -190, rx: 0, ry: 0, rz: 0}        # static 6-DOF pose, component frame to segment frame (mm, degrees, extrinsic x-y-z as in the oracle's pose files)
        poses_file: sweep.csv           # optional: a sweep (the oracle's pose CSV); replaces `pose`; required for a foreign component
        clearance_mm: 3.0               # the margin kept around the component (default 0)
        mass_kg: 0.42                   # optional
        source: free text               # where the geometry came from

A flexible component (cables, hoses) replaces `primitive` by `kind: flexible`, `polyline: [[x, y, z], ...]` (component frame, mm), `radius_mm` and `bend_radius_mm`; it is
checked as a chain of capsules of that radius, and a bend tighter than `bend_radius_mm` is reported.

Frame: the oracle's segment frame (x anterior, y left, z up, origin at the proximal joint centre). `isb_to_segment` is the fixed rotation from an ISB/CAD segment frame (x
anterior, y up, z right) to it, right side: (a, b, c) -> (a, -c, b). A CAD mesh exported in the ISB frame is rotated with it before it is written to the registry's STL.
"""
from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import numpy as np
import yaml

from . import oracle

SCHEMA = "components/1"
STATUSES = ("designed", "reserved", "candidate", "foreign")
OCCUPYING = ("designed", "reserved", "foreign")         # a candidate is a proposal: it takes no space in the check and the free field
KINDS = ("rigid", "flexible")
POSE_KEYS = oracle.POSE_COLUMNS
_ALLOWED = {"id", "name", "status", "owner", "kind", "primitive", "mesh", "pose", "poses_file", "clearance_mm", "mass_kg", "source", "polyline", "radius_mm", "bend_radius_mm", "revision", "sha256", "parameter_inputs"}
GENERATED_REQUIRED = ("revision", "sha256", "parameter_inputs")      # what the CAD bridge writes per component (Stage 3b)
PART_ID = re.compile(r"^part[.][a-z0-9_-]+([.][a-z0-9_-]+)*$")
CAD_SUBDIR = "cad"


class RegistryError(ValueError):
    """The registry file breaks the schema; the message names the file, the component and the field."""


@dataclass
class Component:
    id: str
    name: str
    status: str
    owner: str
    kind: str = "rigid"
    primitive: dict | None = None
    mesh: str | None = None
    pose: tuple = (0.0,) * 6
    poses_file: str | None = None
    clearance_mm: float = 0.0
    mass_kg: float | None = None
    source: str = ""
    polyline: list | None = None
    radius_mm: float | None = None
    bend_radius_mm: float | None = None
    revision: str | None = None             # the CAD bridge's fields (Stage 3b): the part's revision, the canonical mesh hash and the hash of what the CAD state consumed
    sha256: str | None = None
    parameter_inputs: str | None = None
    origin: Path | None = None              # the file the component was read from (not part of the data: to_dict leaves it out)

    @property
    def occupies(self) -> bool:
        return self.status in OCCUPYING

    def to_dict(self) -> dict:
        d = {"id": self.id, "name": self.name, "status": self.status, "owner": self.owner}
        if self.kind == "flexible":
            d.update({"kind": "flexible", "polyline": [[float(x) for x in p] for p in self.polyline], "radius_mm": self.radius_mm, "bend_radius_mm": self.bend_radius_mm})
        else:
            d["primitive"] = self.primitive
        if self.mesh:
            d["mesh"] = self.mesh
        d["pose"] = {k: float(v) for k, v in zip(POSE_KEYS, self.pose)}
        if self.poses_file:
            d["poses_file"] = self.poses_file
        d["clearance_mm"] = float(self.clearance_mm)
        if self.mass_kg is not None:
            d["mass_kg"] = float(self.mass_kg)
        d["source"] = self.source
        for k in GENERATED_REQUIRED:
            if getattr(self, k) is not None:
                d[k] = getattr(self, k)
        return d


@dataclass
class Registry:
    segment: str
    components: list = dc_field(default_factory=list)
    base: Path = Path(".")           # the directory the relative mesh and pose paths resolve against
    frame_offset_mm: tuple = (0.0, 0.0, 0.0)    # model body frame -> the built segment's own frame (frames.py; zero for a leg): the registry is authored in the model frame

    def origins(self) -> list:
        """The files the registry was read from, in order of first use."""
        out = []
        for c in self.components:
            if c.origin is not None and c.origin not in out:
                out.append(c.origin)
        return out

    def by_name(self, name):
        return next(c for c in self.components if c.name == name)

    def placed(self) -> list:
        """Components that take space: designed, reserved and foreign (a candidate does not)."""
        return [c for c in self.components if c.occupies]

    def poses(self, c: Component) -> np.ndarray:
        """(n, 6) poses of a component: its sweep file when it has one, else its static pose."""
        if c.poses_file:
            return oracle.to_segment_frame(oracle.read_poses(self.base / c.poses_file), self.frame_offset_mm)
        return oracle.to_segment_frame(np.array([c.pose], float), self.frame_offset_mm)

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, "segment": self.segment, "components": [c.to_dict() for c in self.components]}


def _pose(d, where) -> tuple:
    if d is None:
        return (0.0,) * 6
    if isinstance(d, (list, tuple)):
        if len(d) != 6:
            raise RegistryError(f"{where}: pose needs 6 numbers (tx, ty, tz, rx, ry, rz), got {len(d)}")
        return tuple(float(x) for x in d)
    bad = set(d) - set(POSE_KEYS)
    if bad:
        raise RegistryError(f"{where}: unknown pose key(s) {sorted(bad)}; the keys are {list(POSE_KEYS)}")
    return tuple(float(d.get(k, 0.0)) for k in POSE_KEYS)


def parse(doc: dict, base=".", name="registry") -> Registry:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise RegistryError(f"{name}: schema must be {SCHEMA!r}, got {doc.get('schema') if isinstance(doc, dict) else type(doc).__name__!r}")
    if not doc.get("segment"):
        raise RegistryError(f"{name}: segment is required")
    seg = str(doc["segment"])
    out, seen = [], set()
    for i, raw in enumerate(doc.get("components") or []):
        cname = raw.get("name", f"#{i}") if isinstance(raw, dict) else f"#{i}"
        where = f"{name}: component {cname!r}"
        if not isinstance(raw, dict):
            raise RegistryError(f"{where}: must be a mapping")
        unknown = set(raw) - _ALLOWED
        if unknown:
            raise RegistryError(f"{where}: unknown field(s) {sorted(unknown)}")
        for k in ("id", "name", "status", "owner"):
            if not raw.get(k):
                raise RegistryError(f"{where}: {k} is required")
        if raw["status"] not in STATUSES:
            raise RegistryError(f"{where}: status {raw['status']!r}, choose from {STATUSES}")
        if raw["name"] in seen:
            raise RegistryError(f"{where}: name is used twice")
        seen.add(raw["name"])
        kind = raw.get("kind", "rigid")
        if kind not in KINDS:
            raise RegistryError(f"{where}: kind {kind!r}, choose from {KINDS}")
        c = Component(id=str(raw["id"]), name=str(raw["name"]), status=raw["status"], owner=str(raw["owner"]), kind=kind, mesh=raw.get("mesh"), pose=_pose(raw.get("pose"), where),
                      poses_file=raw.get("poses_file"), clearance_mm=float(raw.get("clearance_mm", 0.0)), mass_kg=(float(raw["mass_kg"]) if raw.get("mass_kg") is not None else None),
                      source=str(raw.get("source", "")), revision=(str(raw["revision"]) if raw.get("revision") is not None else None),
                      sha256=(str(raw["sha256"]) if raw.get("sha256") is not None else None),
                      parameter_inputs=(str(raw["parameter_inputs"]) if raw.get("parameter_inputs") is not None else None))
        if c.clearance_mm < 0:
            raise RegistryError(f"{where}: clearance_mm must not be negative")
        if kind == "flexible":
            for k in ("polyline", "radius_mm", "bend_radius_mm"):
                if raw.get(k) is None:
                    raise RegistryError(f"{where}: a flexible component needs {k}")
            pl = np.asarray(raw["polyline"], float)
            if pl.ndim != 2 or pl.shape[1] != 3 or len(pl) < 2:
                raise RegistryError(f"{where}: polyline needs at least 2 points of 3 numbers")
            c.polyline, c.radius_mm, c.bend_radius_mm = pl.tolist(), float(raw["radius_mm"]), float(raw["bend_radius_mm"])
            if c.radius_mm <= 0 or c.bend_radius_mm <= 0:
                raise RegistryError(f"{where}: radius_mm and bend_radius_mm must be positive")
            if raw.get("primitive") or c.mesh:
                raise RegistryError(f"{where}: a flexible component has a polyline, not a primitive or a mesh")
        else:
            if not isinstance(raw.get("primitive"), dict):
                raise RegistryError(f"{where}: the bounding primitive is required (type capsule, cylinder or box)")
            try:
                oracle.sample_shape(raw["primitive"])
            except (ValueError, KeyError) as e:
                raise RegistryError(f"{where}: primitive: {e}") from e
            c.primitive = dict(raw["primitive"])
        if c.status == "foreign":
            if c.owner == seg:
                raise RegistryError(f"{where}: a foreign component is owned by another segment, not {seg}")
            if not c.poses_file:
                raise RegistryError(f"{where}: a foreign component needs poses_file (its poses in this segment's frame)")
        elif c.owner != seg:
            raise RegistryError(f"{where}: owner {c.owner!r} is not the segment {seg!r}; use status foreign for another segment's component")
        out.append(c)
    return Registry(seg, out, Path(base))


def load(path) -> Registry:
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    reg = parse(doc, path.parent, path.name)
    for c in reg.components:
        c.origin = path
    return reg


def dump(reg: Registry, path) -> None:
    Path(path).write_text("# Component registry (components/1, volume-extractor brief 6). Authored.\n" + yaml.safe_dump(reg.to_dict(), sort_keys=False, default_flow_style=None, allow_unicode=True),
                          encoding="utf-8", newline="\n")


def load_generated(path) -> Registry:
    """The CAD bridge's companion file (`components/cad/<segment>.yaml`): the same schema, and every component's id is a part id and carries revision, sha256 and
    parameter_inputs."""
    path = Path(path)
    reg = load(path)
    for c in reg.components:
        where = f"{path.name} (generated): component {c.name!r}"
        if not PART_ID.match(c.id):
            raise RegistryError(f"{where}: id {c.id!r} is not a part id (part.<assembly>.<name>)")
        for k in GENERATED_REQUIRED:
            if getattr(c, k) is None:
                raise RegistryError(f"{where}: {k} is required in the bridge's file")
    return reg


def find(components_dir, segment):
    """The registry of a segment: the authored `<segment>.yaml` and the bridge's `cad/<segment>.yaml` beside it, merged (authored components first), or None when
    neither exists. A duplicate id or name across the two is an error naming both files. The merged registry's base is the authored directory; the companion's
    relative mesh paths are rewritten to it."""
    base = Path(components_dir)
    f, g = base / f"{segment}.yaml", base / CAD_SUBDIR / f"{segment}.yaml"
    authored = load(f) if f.exists() else None
    if not g.exists():
        return authored
    gen = load_generated(g)
    if gen.segment != segment:
        raise RegistryError(f"{CAD_SUBDIR}/{g.name}: segment is {gen.segment!r}, expected {segment!r}")
    merged = authored if authored is not None else Registry(segment, [], base)
    for c in gen.components:
        for other in merged.components:
            for field in ("id", "name"):
                if getattr(c, field) == getattr(other, field):
                    raise RegistryError(f"{field} {getattr(c, field)!r} is used in both {f.name} and {CAD_SUBDIR}/{g.name}")
        if c.mesh:
            c.mesh = os.path.relpath(Path(gen.base) / c.mesh, merged.base).replace("\\", "/")
        merged.components.append(c)
    return merged


# ---- frames ----------------------------------------------------------------------------------------------------------------------------

ISB_TO_SEGMENT = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])      # rows: oracle x = a, oracle y = -c, oracle z = b


def isb_to_segment(points, side="right") -> np.ndarray:
    """Points given in an ISB/CAD segment frame (x anterior, y up, z right) in the oracle segment frame (x anterior, y left, z up): (a, b, c) -> (a, -c, b), right side.
    The origin is not moved: a CAD frame whose origin is the proximal joint centre stays there. The left side is not defined (ask Joe how the left CAD frames are oriented)."""
    if side != "right":
        raise NotImplementedError("the ISB to segment rotation is defined for the right side only")
    return np.atleast_2d(np.asarray(points, float)) @ ISB_TO_SEGMENT.T


# ---- STL -------------------------------------------------------------------------------------------------------------------------------

def read_stl(path) -> tuple:
    """(vertices (n, 3), faces (m, 3)) of a binary or ASCII STL, vertices merged by value. The units are whatever the file holds: the registry's are millimetres."""
    raw = Path(path).read_bytes()
    tris = None
    if len(raw) >= 84:
        n = struct.unpack("<I", raw[80:84])[0]
        if 84 + 50 * n == len(raw):
            a = np.frombuffer(raw[84:], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")]), count=n)
            tris = a["v"].astype(float)
    if tris is None:
        pts = [[float(x) for x in line.split()[1:4]] for line in raw.decode("ascii", "ignore").splitlines() if line.strip().startswith("vertex")]
        if not pts or len(pts) % 3:
            raise ValueError(f"{path}: not a binary or ASCII STL")
        tris = np.array(pts, float).reshape(-1, 3, 3)
    flat = tris.reshape(-1, 3)
    uniq, inv = np.unique(np.round(flat, 6), axis=0, return_inverse=True)
    return uniq, inv.reshape(-1, 3)


def write_stl(path, vertices, faces) -> None:
    """Binary STL (used by the tests and by anyone hand-writing a mesh component)."""
    v = np.asarray(vertices, float)[np.asarray(faces)]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-300)
    rec = np.zeros(len(v), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")]))
    rec["n"], rec["v"] = n, v
    Path(path).write_bytes(b"freyja component mesh (mm)".ljust(80, b" ") + struct.pack("<I", len(v)) + rec.tobytes())
