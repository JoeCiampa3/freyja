"""The elbow's flexion clearance (upper-arm characterization brief, T7; Amendment 1, T7a and T7b; G-G8 as amended): the right forearm's envelope swept over elbow flexion against
the right upper arm's, in the upper arm's frame.

Writes data/characterization/upper_arm_flexion_clearance.json. Takes no arguments. Read-only on data/envelope/. It is the one reader of data/envelope/cache/ (gitignored) in the
characterization: the fields' signed distance and region are read from `<body>.npz`, which the ledgers were built from (the cache's own inputs hash must equal the ledger's), and
the file records each cache file's sha256 and size, so a result is tied to the fields it came from.

The measure (memo 64, unchanged; Amendment 1 adds only the zone exclusion). Each body's set at shell t is {sd >= t} within its region, sd the signed distance to the skin of the
extended solid (tools/envelope/field.py). With the zone excluded, the set is further bounded by the plane `zone` mm from the joint: the upper arm's last `zone` mm above its distal
plane, the forearm's first `zone` mm below its proximal plane. On each body's own voxel grid
    S = min(sd - t, the signed distance to the region's voxel boundary, the signed distance to the zone plane)        (positive inside the set)
and, with T the pose of the forearm frame in the upper arm frame,
    m = max over the forearm's voxel centres p of S_upper(T p) + S_fore(p)            (S_upper trilinear; beyond its grid, the nearest value less the distance to the grid)
Inner separation = -m at t = the shell (5 mm, the T5 inputs); skin interpenetration = max(m at t = 0, 0). For two parallel faces m is exactly their overlap (or minus their gap);
at a convex corner it reads at most the Euclidean distance, never more (S is a minimum of the constraints' distances): the error is towards contact. Resolution about one voxel.

Poses: the model's elbow hinge (tools/envelope/joint_poses.py: the hinge chain from the model, the clinical sign from checks/joint_polarity.yaml, not clamped to the model's
150 degrees). The forearm field's origin is the elbow node and its axes the upper arm's at the model's zero; the cache's forearm origin must equal the model's within FRAME_TOL_MM,
and every positive angle passes the polarity file's probe.

What it reports (Amendment 1): M1, the inner separation with the 25 mm zones excluded (the ledgers' `joint_zone_volumes_l.zone_h_mm`) at memo 64's angles, and the first-contact
angle scanned at 1 degree from 0 to the mechanism's end; sensitivity rows at zones of 35 and 50 mm (first contact only, not basis); M2, skin interpenetration with the same
exclusion; M3, the keep-out, per body: the part of its inner set outside its zone that the other body's posed inner set passes through at some 1 degree step; V2, the sculpt
reassembly (the two fields posed by the registration's own frames, no zone excluded) and T7b, that relative rotation decomposed into flexion about the model's hinge, the
carrying angle and the axial twist; V3, the zero pose with zones excluded; and memo 64's literal table with no exclusion, labelled `no_exclusion`.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from envelope import arms, field, foreign, joint_poses  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402

OUT = "data/characterization/upper_arm_flexion_clearance.json"
HOST, OWNER = "upper_arm_R", "forearm_R"                       # the ledgers and cache files
HOST_BODY, OWNER_BODY, HINGE = "upper_arm_right", "forearm_right", "elbow_right"
INPUTS = "data/characterization/inputs/upper_arm.yaml"
TABLE_LOW_DEG = (0.0, 30.0, 60.0, 90.0)                       # the brief's G-G8 angles below 120 degrees
TABLE_FROM_DEG = 120.0                                        # and 1 degree steps from here to the mechanism's end
STEP_DEG = 1.0                                                # the first-contact scan and the keep-out sweep
SENSITIVITY_ZONES_MM = (35.0, 50.0)                           # Amendment 1, M1: sensitivity, not basis
FRAME_TOL_MM = 0.01                                           # the cache's forearm origin against the model's: the sheet length's printed precision
FRAME_ROT_TOL = 1e-9                                          # the cache's rotation against arms.rotation_to_frame of its own axis
TWIST_FINDING_DEG = 2.0                                       # Amendment 1, T7b: a twist above this is a finding for memo 64 finding 3
SIDES = ("ant", "med", "post", "lat")                         # the ledgers' hw_ directions at 0, 90, 180, 270 degrees from +x towards +y (y left: medial on the right)


# ---- the measure --------------------------------------------------------------------------------------------------------------------------

class Clipped:
    """S on a body's own voxel grid (module docstring) at shell t, with the joint zone of `zone_mm` excluded at the body's `zone_end` ("distal": the last zone_mm above the
    field's distal plane; "proximal": the first zone_mm below its top)."""

    def __init__(self, seg: field.Segment, t: float, zone_mm: float = 0.0, zone_end: str | None = None):
        self.seg, self.t, self.zone_mm, self.zone_end = seg, float(t), float(zone_mm), zone_end
        h = seg.h
        reg = np.asarray(seg.region, bool)
        rd = np.where(reg, ndimage.distance_transform_edt(reg, sampling=h) - h / 2, -(ndimage.distance_transform_edt(~reg, sampling=h) - h / 2))
        S = np.minimum(seg.sd - t, rd)
        if zone_mm > 0.0:
            z = seg.centres(2)
            if zone_end == "distal":
                zp = z - (seg.z_top - seg.length + zone_mm)
            elif zone_end == "proximal":
                zp = (seg.z_top - zone_mm) - z
            else:
                raise ValueError(f"zone_end must be 'distal' or 'proximal', not {zone_end!r}")
            S = np.minimum(S, zp[None, None, :])
        self.S = S
        self.h, self.o = h, np.asarray(seg.o, float)
        X, Y, Z = np.meshgrid(*[seg.centres(i) for i in range(3)], indexing="ij")
        self.points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])

    def value(self, points) -> np.ndarray:
        p = np.atleast_2d(np.asarray(points, float))
        g = (p - self.o) / self.h - 0.5
        gc = np.clip(g, 0, np.array(self.S.shape) - 1)
        return ndimage.map_coordinates(self.S, gc.T, order=1, mode="nearest") - np.linalg.norm((g - gc) * self.h, axis=1)


def _apply(T, P):
    return P @ T[:3, :3].T + T[:3, 3]


def measure(host: Clipped, owner: Clipped, T) -> dict:
    """m (module docstring) and where it binds, in the host frame."""
    v = owner.S.ravel() + host.value(_apply(T, owner.points))
    i = int(np.argmax(v))
    return {"m": float(v[i]), "point_host_mm": _apply(T, owner.points[i:i + 1])[0]}


def poses(model, angles_deg, origin=None, polarity=None) -> np.ndarray:
    """T_upper_fore (mm) at each clinical elbow angle from the model's hinge; `origin` replaces the hinge's position (the synthetic tests' fields)."""
    T = joint_poses.relative_transforms(model, HOST_BODY, OWNER_BODY, [HINGE], [[a] for a in angles_deg], polarity)
    if origin is not None:
        T[:, :3, 3] = np.asarray(origin, float)
    return T


def sweep_inner(model, host: Clipped, owner: Clipped, angles_deg, origin=None, polarity=None, stop_at_contact=False) -> list:
    out = []
    for a, T in zip(angles_deg, poses(model, angles_deg, origin, polarity)):
        r = measure(host, owner, T)
        out.append({"angle_deg": float(a), **r})
        if stop_at_contact and r["m"] >= 0.0:
            break
    return out


def keep_out(host: Clipped, owner: Clipped, Ts) -> dict:
    """M3. For each body, the voxels of its set (S >= 0: inner, outside its zone) that the other body's posed set holds at some pose: volume (voxel count x h^3), the deepest
    such voxel below its body's inner shell (max sd - t), the stations spanned (z_top - z) and the volume per side by the hw_ directions."""
    Ts = [np.asarray(T, float) for T in Ts]
    out = {}
    for name, body, other, maps in (("host", host, owner, [np.linalg.inv(T) for T in Ts]), ("owner", owner, host, Ts)):
        sel = np.flatnonzero(body.S.ravel() >= 0.0)
        P = body.points[sel]
        hit = np.zeros(len(sel), bool)
        for T in maps:
            hit |= other.value(_apply(T, P)) >= 0.0
        Q = P[hit]
        v = body.h ** 3 / 1e6
        if not len(Q):
            out[name] = {"volume_l": 0.0, "deepest_mm": None, "stations_mm": None, "sides_l": {s: 0.0 for s in SIDES}}
            continue
        sd = body.seg.sd.ravel()[sel][hit] - body.t
        ang = np.degrees(np.arctan2(Q[:, 1], Q[:, 0])) % 360.0
        side = np.array(SIDES)[(((ang + 45.0) % 360.0) // 90.0).astype(int)]
        st = body.seg.z_top - Q[:, 2]
        out[name] = {"volume_l": round(float(len(Q) * v), 4), "deepest_mm": round(float(sd.max()), 2), "stations_mm": [round(float(st.min()), 1), round(float(st.max()), 1)],
                     "sides_l": {s: round(float((side == s).sum() * v), 4) for s in SIDES}}
    return out


# ---- the sculpt (T7b) ---------------------------------------------------------------------------------------------------------------------

def decompose(model, R) -> dict:
    """R: a rotation of the forearm frame in the upper arm frame. R = R_hinge(flexion) R_x(carrying) R_z(twist), intrinsic: flexion about the model's elbow hinge (its clinical
    sign measured on the model, as the poses), then the carrying angle about the anterior axis, then the twist about the forearm's own long axis."""
    from scipy.spatial.transform import Rotation
    unit = Rotation.from_matrix(poses(model, [1.0])[0][:3, :3]).as_euler("YXZ", degrees=True)
    if abs(abs(unit[0]) - 1.0) > 1e-9 or abs(unit[1]) > 1e-9 or abs(unit[2]) > 1e-9:
        raise StopAndAsk(f"the model's elbow hinge is not about its body y axis (one degree of flexion reads {unit} as Y, X, Z)")
    a, b, c = Rotation.from_matrix(np.asarray(R, float)).as_euler("YXZ", degrees=True)
    distal = np.asarray(R, float) @ np.array([0.0, 0.0, -1.0])
    return {"flexion_deg": float(a * np.sign(unit[0])), "carrying_deg": float(b), "twist_deg": float(c),
            "carrying_direction": "medial" if distal[1] > 0 else "lateral" if distal[1] < 0 else "none",
            "axes_angle_deg": float(math.degrees(math.acos(np.clip(R[2, 2], -1.0, 1.0))))}


def arm_frame(meta: dict) -> arms.ArmFrame:
    """The registration's own frame of a cached arm field (arms.ArmFrame from the origin, axis and stretch the cache records); its rotation must equal the cache's."""
    R = np.asarray(meta["rotation_mesh_to_segment"], float)
    fr = arms.ArmFrame(meta["frame_origin_mesh_mm"], -R[2], meta["axial_stretch"])
    if np.abs(fr.R - R).max() > FRAME_ROT_TOL:
        raise StopAndAsk(f"{meta['segment']}: arms.rotation_to_frame of the cached axis differs from the cached rotation by {np.abs(fr.R - R).max():.2e}")
    return fr


def sculpt_transform(meta_host: dict, meta_owner: dict) -> np.ndarray:
    """T (4x4, affine: the two axial stretches make it not quite rigid) taking the forearm field's frame to the upper arm field's as the sculpt has them: mesh = owner.inverse,
    then host.forward."""
    fh, fo = arm_frame(meta_host), arm_frame(meta_owner)
    f = lambda P: fh.forward(fo.inverse(np.atleast_2d(P)))  # noqa: E731
    T = np.eye(4)
    T[:3, 3] = f([0.0, 0.0, 0.0])[0]
    T[:3, :3] = (f(np.eye(3)) - T[:3, 3]).T
    return T


# ---- inputs, stamp, build ----------------------------------------------------------------------------------------------------------------

def input_files() -> list:
    return sorted([f"data/envelope/{HOST}.yaml", f"data/envelope/{OWNER}.yaml", INPUTS, "sim/models/freyja.xml", "checks/joint_polarity.yaml", "params/snapshot.csv"])


def inputs_hash(root: Path) -> str:
    h = hashlib.sha256()
    for n in input_files():
        h.update(n.encode())
        h.update((Path(root) / n).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def _yaml(root, rel):
    return yaml.safe_load((Path(root) / rel).read_text(encoding="utf-8"))


def angles(end: float):
    table = list(TABLE_LOW_DEG) + [float(a) for a in np.arange(TABLE_FROM_DEG, end + 1e-9, STEP_DEG)]
    scan = [float(a) for a in np.arange(0.0, end + 1e-9, STEP_DEG)]
    if scan[-1] != end:
        scan.append(float(end))
        table.append(float(end))
    return table, scan


def _mm(x):
    return round(float(x), 2) + 0.0


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    inp = _yaml(root, INPUTS)
    t = float(inp["shell"]["value"])
    end = float(inp["rom"]["mechanism_ends"]["flexion"]["value"])
    led = {n: _yaml(root, f"data/envelope/{n}.yaml") for n in (HOST, OWNER)}
    zones = {n: float(led[n]["joint_zone_volumes_l"]["zone_h_mm"]) for n in led}
    if len(set(zones.values())) != 1:
        raise StopAndAsk(f"the two ledgers record different joint zones: {zones}")
    zone = zones[HOST]
    segs, cache = {}, {}
    for n in (HOST, OWNER):
        p = root / "data" / "envelope" / "cache" / f"{n}.npz"
        b = p.read_bytes()
        cache[n] = {"path": f"data/envelope/cache/{n}.npz", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
        segs[n] = field.Segment.load(p)
        if segs[n].meta.get("inputs_sha256_12") != led[n]["inputs_sha256_12"]:
            raise StopAndAsk(f"{n}: the cache was built from inputs {segs[n].meta.get('inputs_sha256_12')}, the ledger from {led[n]['inputs_sha256_12']}")
    model = foreign.load_model(root / "sim" / "models" / "freyja.xml")
    pol = foreign.load_polarity(root / "checks" / "joint_polarity.yaml")[0]
    T0 = poses(model, [0.0], polarity=pol)[0]
    off = float(np.abs(T0[:3, 3] - np.asarray(segs[OWNER].meta["origin_xyz"], float)).max())
    if off > FRAME_TOL_MM or not np.allclose(T0[:3, :3], np.eye(3), atol=1e-12):
        raise StopAndAsk(f"the cache's forearm origin is {off:.4f} mm from the model's elbow (tolerance {FRAME_TOL_MM} mm), or the zero pose is rotated")
    table, scan = angles(end)
    Ts = dict(zip(scan, poses(model, scan, polarity=pol)))
    for a in scan:
        if a > 0:
            joint_poses.check_probe_direction(model, HOST_BODY, OWNER_BODY, HINGE, a, Ts[a])
    up, fo = segs[HOST], segs[OWNER]
    C = lambda seg, tt, z, e: Clipped(seg, tt, z, e)  # noqa: E731
    inner = (C(up, t, zone, "distal"), C(fo, t, zone, "proximal"))
    skin = (C(up, 0.0, zone, "distal"), C(fo, 0.0, zone, "proximal"))
    inner0, skin0 = (C(up, t, 0.0, None), C(fo, t, 0.0, None)), (C(up, 0.0, 0.0, None), C(fo, 0.0, 0.0, None))

    def row(pair, a):
        r = measure(*pair, Ts[a])
        return r["m"], [_mm(x) for x in r["point_host_mm"]]

    m1 = {a: row(inner, a) for a in scan}
    first = next((a for a in scan if m1[a][0] >= 0.0), None)
    hc_rows = [{"angle_deg": a, "inner_separation_mm": _mm(-m1[a][0]), "binding_point_upper_arm_mm": m1[a][1]} for a in table]
    sens = []
    for z in SENSITIVITY_ZONES_MM:
        pair = (C(up, t, z, "distal"), C(fo, t, z, "proximal"))
        f = next((a for a in scan if measure(*pair, Ts[a])["m"] >= 0.0), None)
        sens.append({"zone_h_mm": z, "first_contact_deg": f})
    skin_rows = [{"angle_deg": a, "skin_interpenetration_mm": _mm(max(measure(*skin, Ts[a])["m"], 0.0))} for a in table]
    lit = [{"angle_deg": a, "inner_separation_mm": _mm(-measure(*inner0, Ts[a])["m"]), "skin_interpenetration_mm": _mm(max(measure(*skin0, Ts[a])["m"], 0.0))} for a in table]
    ko = keep_out(*inner, [Ts[a] for a in scan])
    # V2 and T7b: the sculpt
    Ts_sculpt = sculpt_transform(up.meta, fo.meta)
    fh, fr = arm_frame(up.meta), arm_frame(fo.meta)
    dec = decompose(model, fh.R @ fr.R.T)
    v2 = {"t0": measure(*skin0, Ts_sculpt)["m"], f"t{t:g}": measure(*inner0, Ts_sculpt)["m"]}
    h = float(up.h)
    nodes = led[HOST]["mesh_nodes_mm"]
    u = np.subtract(nodes["elbow"], nodes["sjc"])
    w = np.subtract(nodes["wrist"], nodes["elbow"])
    ledger_bend = math.degrees(math.acos(float(u @ w / np.linalg.norm(u) / np.linalg.norm(w))))
    v3 = -m1[0.0][0]
    return {
        "schema": "flexion-clearance/1", "generated_by": "analysis/elbow_flexion_clearance.py", "inputs": f"sha256:{inputs_hash(root)}", "arguments": {},
        "frame": f"the upper arm field's frame ({HOST}: origin at the SJC, x anterior, y left, z up, mm); stations are the ledger's, distances below its top",
        "provenance": {
            "ledgers": {n: {"file": f"data/envelope/{n}.yaml", "mesh_file": led[n]["mesh_file"], "inputs_sha256_12": led[n]["inputs_sha256_12"]} for n in (HOST, OWNER)},
            "cache": cache, "voxel_mm": h,
            "shell_mm": {"value": t, "source": f"{INPUTS}#/shell (adr-0007 D4)"},
            "mechanism_end_deg": {"value": end, "source": f"{INPUTS}#/rom/mechanism_ends/flexion (adr-0008 D4)"},
            "zone_h_mm": {"value": zone, "source": f"data/envelope/{HOST}.yaml#/joint_zone_volumes_l/zone_h_mm and data/envelope/{OWNER}.yaml (equal); written by tools/envelope/arms.zone_numbers from tools/envelope/bodies.ZONE_H_MM"},
            "pose": f"the model's {HINGE} (sim/models/freyja.xml) through tools/envelope/joint_poses.relative_transforms, clinical sign from checks/joint_polarity.yaml, not clamped",
            "forearm_origin_vs_model_mm": round(off, 4), "probe_checked_angles": sum(1 for a in scan if a > 0)},
        "measure": "m = max over the forearm's voxel centres p of S_upper(T p) + S_fore(p), S = min(sd - t, the signed distance to the region's voxel boundary, the signed distance to the zone plane); "
                   "inner separation = -m at the shell; skin interpenetration = max(m at t = 0, 0); touch is inner separation <= 0",
        "hardware_clearance": {"label": "M1, basis", "zone_h_mm": zone, "shell_mm": t, "step_deg": STEP_DEG, "first_contact_deg": first, "rows": hc_rows,
                               "first_contact_note": "the first 1 degree step from 0 at which the inner shells touch; null if none up to the mechanism's end"},
        "sensitivity": {"label": "sensitivity, not basis: first contact at other zone heights", "rows": sens},
        "skin": {"label": "M2, reported, not gated", "zone_h_mm": zone, "rows": skin_rows},
        "keep_out": {"label": "M3, reported, not subtracted from any volume", "zone_h_mm": zone, "shell_mm": t, "swept_deg": [0.0, end], "step_deg": STEP_DEG,
                     "definition": "per body: the voxels of its inner set outside its zone that the other body's posed inner set holds at some step; deepest = max sd - t there; stations in that body's ledger",
                     HOST: ko["host"], OWNER: ko["owner"]},
        "sculpt": {"label": "T7b: the forearm field's rotation in the upper arm field's frame as the sculpt has them (arms.ArmFrame from the cache's frames)",
                   **{k: round(v, 4) + 0.0 if isinstance(v, float) else v for k, v in dec.items()},
                   "ledger_elbow_bend_deg": round(ledger_bend, 2), "axial_stretch": {HOST: up.meta["axial_stretch"], OWNER: fo.meta["axial_stretch"]},
                   "twist_finding": abs(dec["twist_deg"]) > TWIST_FINDING_DEG, "twist_finding_above_deg": TWIST_FINDING_DEG},
        "validation": {
            "v1_synthetic": "tests/test_elbow_flexion_clearance.py (cylinders side by side and overlapping, an axial gap across the slab planes, a cut solid reassembled, zone "
                            "exclusion at zero, a hinged pair at 90 degrees, symmetry, the sign mutation through the sweep); no cache",
            "v2_reassembly": {"m_mm": {k: _mm(v) for k, v in v2.items()}, "tolerance_mm": h, "pass": all(abs(v) <= h for v in v2.values()),
                              "pose": "the sculpt's own transform (sculpt_transform), no zone excluded"},
            "v3_zero_pose": {"inner_separation_mm": _mm(v3), "expected_mm": 2 * zone, "tolerance_mm": h, "pass": abs(v3 - 2 * zone) <= h},
            "v4": "two builds byte-identical: tests/test_elbow_flexion_clearance.py rebuilds and compares with this file"},
        "no_exclusion": {"label": "memo 64's literal G-G8 table: no zone excluded (what the old measure gave; superseded by M1)", "rows": lit},
    }


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def render(result: dict) -> str:
    return json.dumps(result, indent=1, sort_keys=True, default=_default) + "\n"


def main(argv) -> int:
    if argv:
        print("analysis/elbow_flexion_clearance.py takes no arguments", file=sys.stderr)
        return 2
    text = render(build(ROOT))
    with open(ROOT / OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
