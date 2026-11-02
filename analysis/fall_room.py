"""The room at each fall zone's contact and the lowest fitting first cap (fall inputs brief, T1; adr-0037 D1(d), D2(c)).

Writes data/falls/room.json. Takes no arguments. Read-only on data/envelope/: it decides nothing and applies nothing.

Skin depths come from the ledgers (`*_sections.csv`): `hw_*` is the ray from the body's frame axis, `r_*` the ray from the section's Chebyshev centre. A ledger holds a shell thickness only as
`cheb_r_t*` and `area_t*`, so the depth inside the shell along the normal is the ray less t. Contact points are vertices of the conformed baseline mesh, used to name the station and pick the
ledger row; no room number comes from a vertex. Occupants come from the component registries, in the built bodies' frames. Strokes and claims are read from the decision records, never typed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from envelope import bodies, frames, masses, trial  # noqa: E402

BASELINE_MESH = "data/makehuman/freyja-body-v3.obj"     # adr-0042
OUT = "data/falls/room.json"
SHELL_MM = 5.0                                           # adr-0007 D4
SHELLS_MM = (3.0, 5.0, 8.0, 10.0)                        # the shell thicknesses the ledgers carry
CAPS_KN = (10, 20, 40)                                   # adr-0037 D2(c)
HIP_SLAB_MM = 15.0                                       # half height of the slab at the HJC plane the hip vertex is searched in: a locator only, wider than the mesh's vertex spacing there (5 mm missed the lateral ring by 12 mm)
KNEE_SLAB_MM = 10.0                                      # the same at the KJC plane
ARM_EXCLUDE_MM = 180.0                                   # trunk vertices further than this from the midline are arm or shoulder: below the SJC's 192 mm


class NotBaseline(Exception):
    """A file built from a mesh other than the baseline (G1): reported, never used."""


def usable(header: dict) -> bool:
    return header.get("mesh_file") == BASELINE_MESH


class Ledger:
    def __init__(self, directory, name: str):
        self.name = name
        self.header = yaml.safe_load((Path(directory) / f"{name}.yaml").read_text(encoding="utf-8"))
        if not usable(self.header):
            raise NotBaseline(f"{name}.yaml was built from {self.header.get('mesh_file')}, not {BASELINE_MESH}")
        lines = [l for l in (Path(directory) / f"{name}_sections.csv").read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        self.rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(lines)]

    def row(self, station_mm: float) -> dict:
        return min(self.rows, key=lambda r: abs(r["s_mm"] - station_mm))

    def source(self, row: dict, column: str) -> dict:
        return {"file": f"data/envelope/{self.name}_sections.csv", "mesh_file": self.header["mesh_file"], "inputs_sha256_12": self.header["inputs_sha256_12"],
                "station_mm": row["s_mm"], "column": column, "value_mm": row[column], "shell_mm": SHELL_MM}


def lowest_cap(room_mm: float, strokes: dict):
    """adr-0037 D2(c): the lowest cap in the series whose reserved stroke fits; None when none does."""
    for kn in sorted(strokes):
        if strokes[kn] <= room_mm:
            return kn
    return None


def ray_to_cylinder(origin, direction, station_mm: float, cyl: dict):
    """Distance along a transverse unit ray from `origin` to the near face of a vertical cylinder, or None when it misses. The cylinder's axial extent grows by its clearance, so a ray that
    grazes the end of a reservation still counts."""
    if not cyl["s_top"] - cyl["clearance"] <= station_mm <= cyl["s_bottom"] + cyl["clearance"]:
        return None
    o, d, c = np.array(origin, float), np.array(direction, float), np.array((cyl["cx"], cyl["cy"]))
    along = float((c - o) @ d)
    off = float(np.linalg.norm((c - o) - along * d))
    if off > cyl["r"] or along <= 0.0:
        return None
    return along - math.sqrt(cyl["r"] ** 2 - off ** 2)


def _clean_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def read_strokes(root: Path) -> dict:
    """s_res at 10, 20 and 40 kN per zone: adr-0037 D3 for the five capless zones, its first Revisions entry of 2026-10-31 for the hand and arm (adr-0008 D5, D6(b))."""
    text = _clean_text(Path(root) / "decisions/0037-fall-design-basis.md")
    out = {}
    for zone in ("hip", "shoulder", "buttock", "back", "knee"):
        m = re.search(rf"^\| {zone} \|.*?\| (\d+) / (\d+) / (\d+) mm \|", text, re.M)
        out[zone] = dict(zip(CAPS_KN, (int(v) for v in m.groups())))
    m = re.search(r"strokes at 10 / 20 / 40 kN are (\d+) / (\d+) / (\d+) mm", text)
    out["hand_arm"] = dict(zip(CAPS_KN, (int(v) for v in m.groups())))
    return out


def read_claims(root: Path) -> dict:
    """adr-0037 D7: per zone the element mass at each cap and the present claim."""
    text = _clean_text(Path(root) / "decisions/0037-fall-design-basis.md")
    element = {}
    for kn in CAPS_KN:
        m = re.search(rf"^\| {kn} kN \| ([\d.]+) kg \| ([\d.]+) kg \| ([\d.]+) kg \|", text, re.M)
        element[kn] = dict(zip((60, 40, 30), (float(v) for v in m.groups())))
    out = {}
    for zone, label in (("hip", "hip"), ("shoulder", "shoulder"), ("buttock", "buttock"), ("back", "back"), ("knee", "knee"), ("hand_arm", "hand and arm")):
        m = re.search(rf"^\| {label} \| \w+ \| (\d+) mm(?: \(default\))? \| ([\d.]+) \| (\d) \| ([\d.]+) \|", text, re.M)
        standoff = int(m.group(1))
        out[zone] = {"standoff_mm": standoff, "kg_per_unit_now": float(m.group(2)), "units": int(m.group(3)), "element_kg": {kn: element[kn][standoff] for kn in CAPS_KN}}
    return out


def released_kg(claim: dict, cap_kn):
    """The claim released if the zone took this cap: the present claim less the element at the cap, rounded up to the next 0.05 kg (D7), times the units."""
    if cap_kn is None:
        return None
    kg = math.ceil(round(claim["element_kg"][cap_kn] / 0.05, 6)) * 0.05
    return round((claim["kg_per_unit_now"] - kg) * claim["units"], 2)


def cylinders(path: Path, hjc_x_mm: float, length_mm: float, name: str) -> list:
    """The cylinders of a registry in the built body's frame (oracle = model + (-hjc_x, 0, 0); stations are distances below the upper plane)."""
    reg = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for c in reg["components"]:
        off = frames.model_to_segment_mm(name, hjc_x_mm, length_mm)
        half = c["primitive"]["length"] / 2.0
        out.append({"id": c["id"], "cx": c["pose"]["tx"] + off[0], "cy": c["pose"]["ty"], "r": c["primitive"]["diameter"] / 2.0, "s_top": -c["pose"]["tz"] - half, "s_bottom": -c["pose"]["tz"] + half,
                    "clearance": float(c["clearance_mm"]), "status": c["status"], "file": path.relative_to(ROOT).as_posix()})
    return out


def nearest(origin, direction, station_mm: float, cyls: list):
    """The first occupant on the ray: (distance, cylinder), or (None, None)."""
    hits = [(d, c) for c in cyls if (d := ray_to_cylinder(origin, direction, station_mm, c)) is not None]
    return min(hits, key=lambda h: h[0]) if hits else (None, None)


def side_gap(origin, direction, station_mm: float, cyls: list):
    """The closest occupant the ray misses at this station: how far a column around the ray can spread before it enters that occupant's clearance. None when the ray misses nothing."""
    o, d = np.array(origin, float), np.array(direction, float)
    gaps = []
    for c in cyls:
        if c["s_top"] - c["clearance"] <= station_mm <= c["s_bottom"] + c["clearance"] and ray_to_cylinder(origin, direction, station_mm, c) is None:
            w = np.array((c["cx"], c["cy"])) - o
            gaps.append((float(np.linalg.norm(w - (w @ d) * d)) - c["r"] - c["clearance"], c["id"]))
    if not gaps:
        return None
    gap, name = min(gaps)
    return {"occupant": name, "gap_mm": round(gap, 2)}


def reading(room_mm: float, strokes: dict, claim: dict) -> dict:
    cap = lowest_cap(room_mm, strokes)
    return {"room_mm": round(room_mm, 2), "lowest_cap_kN": cap, "s_res_mm": strokes[cap] if cap else None, "claim_released_kg": released_kg(claim, cap)}


def ray_case(label: str, skin_mm: float, origin, direction, station_mm: float, cyls: list, strokes: dict, claim: dict) -> dict:
    """Reading (a) on one ray that starts on the skin: depth to the first occupant, less the shell and the occupant's clearance. With nothing on the ray, reading (a) is the ledger depth."""
    d, c = nearest(origin, direction, station_mm, cyls)
    gap = side_gap(origin, direction, station_mm, cyls)
    if c is None:
        return {"label": label, "occupant": None, "skin_to_occupant_mm": None, "beside_the_ray": gap, **reading(skin_mm - SHELL_MM, strokes, claim)}
    return {"label": label, "occupant": c["id"], "occupant_status": c["status"], "occupant_file": c["file"], "clearance_mm": c["clearance"], "skin_to_occupant_mm": round(d, 2), "beside_the_ray": gap,
            **reading(d - SHELL_MM - c["clearance"], strokes, claim)}


def shells(skin_mm: float, row: dict, occupant_mm=None, clearance=0.0) -> dict:
    """The sensitivity to the shell: reading (b), reading (a) and the ledger's inscribed radius at each thickness it carries."""
    out = {}
    for t in SHELLS_MM:
        tag = f"t{t:g}"
        out[tag] = {"reading_b_mm": round(skin_mm - t, 2), "cheb_r_mm": row[f"cheb_r_{tag}_mm"]}
        if occupant_mm is not None:
            out[tag]["reading_a_mm"] = round(occupant_mm - t - clearance, 2)
    return out


def station(vertex: int, segment: str, s_mm: float, point, frame: str, normal: str) -> dict:
    return {"vertex": int(vertex), "segment": segment, "section_station_mm": round(float(s_mm), 1), "point_mm": [round(float(v), 2) for v in point], "frame": frame, "normal": normal}


def support(V, mask, direction) -> int:
    idx = np.where(mask)[0]
    return int(idx[np.argmax(V[idx] @ np.array(direction, float))])


def input_files(root: Path) -> list:
    env = ["pelvis", "abdomen", "thorax", "thigh_R", "shank_R", "upper_arm_R"]
    names = [f"data/envelope/{n}.yaml" for n in env] + [f"data/envelope/{n}_sections.csv" for n in env]
    names += ["data/envelope/reservations.yaml", "data/envelope/reservations_result.json", "data/envelope/reserved/pelvis.yaml", "data/envelope/reserved/thorax.yaml", "data/envelope/corridor/thorax.yaml",
              "data/envelope/components/thigh_R.yaml", "data/envelope/components/cad/upper_arm_R.yaml", "data/envelope/hip_registration.json", "data/envelope/trunk_bodies.json",
              "decisions/0037-fall-design-basis.md", "params/snapshot.csv", BASELINE_MESH]
    return sorted(names)


def inputs_hash(root: Path) -> str:
    h = hashlib.sha256()
    for n in input_files(root):
        h.update(n.encode())
        h.update((Path(root) / n).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def conformed_mesh(root: Path):
    """The baseline mesh in the conformed frame: the legs' conform with the trunk map, exactly what `fy envelope build` writes as conformed.obj, from tracked inputs."""
    inp = trial.load_inputs(root, root / BASELINE_MESH)
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    return bodies.trunk_map(inp, reg, masses.load_dumas_table1(root)).apply(inp.V)


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    env = root / "data/envelope"
    led = {n: Ledger(env, n) for n in ("pelvis", "abdomen", "thorax", "thigh_R", "shank_R", "upper_arm_R")}
    strokes, claims = read_strokes(root), read_claims(root)
    hip_reg = json.loads((env / "hip_registration.json").read_text(encoding="utf-8"))
    trunk = json.loads((env / "trunk_bodies.json").read_text(encoding="utf-8"))
    reserved = json.loads((env / "reservations_result.json").read_text(encoding="utf-8"))
    hjc_x = frames.hjc_x_in_pelvis_mm(root / "params/snapshot.csv")
    V = conformed_mesh(root)

    pelvis_o = np.array(hip_reg["origins_conformed_mm"]["pelvis"])
    thigh_o = np.array(hip_reg["origins_conformed_mm"]["thigh"])
    thorax_o = np.array([pelvis_o[0], pelvis_o[1], led["thorax"].header["planes"]["upper_sheet_mm"]])
    kjc_z = thigh_o[2] - led["thigh_R"].header["length_mm"]
    lateral_sjc = trunk["shoulder"]["plane"]["lateral_mm"]
    sjc_below = trunk["shoulder"]["plane"]["below_cjc_mm"]
    right = V[:, 1] < pelvis_o[1]

    pelvis_cyl = cylinders(env / "reserved/pelvis.yaml", hjc_x, led["pelvis"].header["length_mm"], "pelvis")
    thorax_mod = cylinders(env / "reserved/thorax.yaml", hjc_x, led["thorax"].header["length_mm"], "thorax")
    corridor = cylinders(env / "corridor/thorax.yaml", hjc_x, led["thorax"].header["length_mm"], "thorax")
    thorax_cyl = thorax_mod + corridor

    ties = {b: {"reserved_inner_volume_l": round(reserved["bodies"][b]["with_modules"]["at_required_margin"]["inner_volume_l"], 4), "ledger_inner_volume_t5_l": led[b].header["inner_volume_l"]["t5"]}
            for b in ("pelvis", "thorax")}
    for t in ties.values():
        t["ties"] = t["reserved_inner_volume_l"] == t["ledger_inner_volume_t5_l"]

    zones = {}

    # hip: right lateral skin at the HJC plane, the plane the pelvis's lower end and the thigh's top share
    p = pelvis_ledger = led["pelvis"]
    v = support(V, right & (np.abs(V[:, 2] - thigh_o[2]) <= HIP_SLAB_MM) & (V[:, 1] > pelvis_o[1] - 260.0), (0, -1, 0))
    pt = V[v] - pelvis_o
    s = pelvis_o[2] - V[v, 2]
    row = p.row(s)
    skin = row["hw_right_mm"]
    th_row = led["thigh_R"].row(0.0)
    case = ray_case("ledger ray at x = 0 (the hip line), spine modules in the pelvis", skin, (0.0, -skin), (0.0, 1.0), row["s_mm"], pelvis_cyl, strokes["hip"], claims["hip"])
    hjc_pelvis = hip_reg["lateral_skin_distance_at_hjc_plane_mm"]["pelvis_frame"]
    hjc_thigh = hip_reg["lateral_skin_distance_at_hjc_plane_mm"]["thigh_frame"]
    zones["hip"] = {
        "outcome": "answered",
        "station": station(v, "pelvis (lower plane) / thigh_R (top)", row["s_mm"], pt, "pelvis ledger frame: origin on the hip line and midline at the LSJ plane, x anterior, y left, z up", "-y (right lateral)"),
        "sources": [p.source(row, "hw_right_mm"), led["thigh_R"].source(th_row, "hw_lat_mm")],
        "skin_depth_mm": skin, "vertex_minus_ledger_mm": round(float(-pt[1] - skin), 2),
        "reading_b": reading(skin - SHELL_MM, strokes["hip"], claims["hip"]), "reading_a": case,
        "variants": [
            ray_case("the same ray at the contact vertex's own x", skin, (float(pt[0]), -skin), (0.0, 1.0), row["s_mm"], pelvis_cyl, strokes["hip"], claims["hip"]),
            ray_case("spine modules not in the pelvis (thorax candidate): nothing named on the ray", skin, (0.0, -skin), (0.0, 1.0), row["s_mm"], [], strokes["hip"], claims["hip"]),
            ray_case("10 mm below the HJC plane, in the hip zone: below the modules, nothing named", skin, (0.0, -skin), (0.0, 1.0), row["s_mm"] + 10.0, pelvis_cyl, strokes["hip"], claims["hip"]),
            {"label": "to the HJC node, pelvis frame (a node, not an occupant; the mesh places the hip)", "skin_to_node_mm": round(hjc_pelvis, 2), **reading(hjc_pelvis - SHELL_MM, strokes["hip"], claims["hip"])},
            {"label": "to the HJC node, thigh frame (the model places the hip)", "skin_to_node_mm": round(hjc_thigh, 2), **reading(hjc_thigh - SHELL_MM, strokes["hip"], claims["hip"])},
            {"label": "thigh ledger radius from its axis, hw_lat at station 0", "skin_to_node_mm": th_row["hw_lat_mm"], **reading(th_row["hw_lat_mm"] - SHELL_MM, strokes["hip"], claims["hip"])},
        ],
        "shell_sensitivity": shells(skin, row, case.get("skin_to_occupant_mm"), case.get("clearance_mm", 0.0)),
        "not_in_a_file": ["the hip mechanism: components/thigh_R.yaml holds two hand-typed worked examples, the higher ending 40 mm below the HJC, outside the hip zone, and neither is a hip part", "any pelvis structure or the LSJ actuators"],
    }

    # buttock and back: the posterior support vertex on the right; the ledger ray is r_post from the section's Chebyshev centre, which sits in the right half at these rows
    def posterior(zone, ledger, origin, lo, hi, cyls, spine_elsewhere):
        band = (V[:, 2] >= lo) & (V[:, 2] <= hi) & right & (np.abs(V[:, 1] - pelvis_o[1]) < ARM_EXCLUDE_MM)
        vid = support(V, band, (-1, 0, 0))
        q = V[vid] - origin
        r = ledger.row(origin[2] - V[vid, 2])
        if not r["cheb_cy_mm"] < 0.0:
            raise ValueError(f"{zone}: the row's centre is not in the right half")
        depth = r["r_post_mm"]
        o = (r["cheb_cx_mm"] - depth, r["cheb_cy_mm"])
        c = ray_case("ledger ray r_post through the section's centre, at the support vertex's side", depth, o, (1.0, 0.0), r["s_mm"], cyls, strokes[zone], claims[zone])
        mid = r["hw_post_mm"]
        return {
            "outcome": "answered",
            "station": station(vid, ledger.name, r["s_mm"], q, f"{ledger.name} ledger frame: origin on the hip line and midline at the body's upper plane, x anterior, y left, z up", "-x (posterior)"),
            "sources": [ledger.source(r, "r_post_mm"), ledger.source(r, "hw_post_mm")],
            "skin_depth_mm": depth, "ray_origin_mm": [r["cheb_cx_mm"], r["cheb_cy_mm"]], "vertex_minus_ledger_mm": round(float(-q[0] - (depth - r["cheb_cx_mm"])), 2),
            "reading_b": reading(depth - SHELL_MM, strokes[zone], claims[zone]), "reading_a": c,
            "variants": [
                ray_case("midline ray hw_post from the frame axis", mid, (-mid, 0.0), (1.0, 0.0), r["s_mm"], cyls, strokes[zone], claims[zone]),
                ray_case("spine modules not in this body: the support-vertex ray", depth, o, (1.0, 0.0), r["s_mm"], spine_elsewhere, strokes[zone], claims[zone]),
                ray_case("spine modules not in this body: the midline ray", mid, (-mid, 0.0), (1.0, 0.0), r["s_mm"], spine_elsewhere, strokes[zone], claims[zone]),
            ],
            "shell_sensitivity": shells(depth, r, c.get("skin_to_occupant_mm"), c.get("clearance_mm", 0.0)),
        }

    pelvis_top = pelvis_o[2]
    zones["buttock"] = posterior("buttock", pelvis_ledger, pelvis_o, thigh_o[2], pelvis_top, pelvis_cyl, [])
    zones["buttock"]["not_in_a_file"] = ["the LSJ actuators and pelvis structure", "the hip mechanism"]
    zones["back"] = posterior("back", led["thorax"], thorax_o, thorax_o[2] - led["thorax"].header["length_mm"], thorax_o[2], thorax_cyl, corridor)
    zones["back"]["not_in_a_file"] = ["the thorax structure and any spine other than the v2 modules and the corridor", "the shoulder mechanism"]

    # shoulder: right lateral skin of the deltoid at the SJC height; the contact lies in the upper arm's ledger and the thorax ledger stops at the shoulder plane, which is not skin
    ua = led["upper_arm_R"]
    r = next(x for x in ua.rows if x["s_mm"] >= ua.header["stations"]["joint_station_mm"] and x["hw_lat_mm"] > 0.0)
    lat = r["hw_lat_mm"]
    # the mesh's arm is in an A-pose and the ledger's at zero, so no support search agrees with the ledger here: the vertex is the one nearest the ledger's skin point
    sjc_x = ua.header["mesh_nodes_mm"]["sjc"][0] - pelvis_o[0]
    v = int(np.argmin(np.linalg.norm(V - (thorax_o + np.array([sjc_x, -(lateral_sjc + lat), -sjc_below])), axis=1)))
    member = yaml.safe_load((env / "components/cad/upper_arm_R.yaml").read_text(encoding="utf-8"))["components"][0]
    member_face = member["primitive"]["half"][1] - member["primitive"]["offset"][1]
    d_member = lat - member_face
    a = {"label": "ledger ray at the skin, in the upper arm", "occupant": member["id"], "occupant_status": member["status"], "occupant_file": "data/envelope/components/cad/upper_arm_R.yaml", "clearance_mm": float(member["clearance_mm"]),
         "skin_to_occupant_mm": round(d_member, 2), **reading(d_member - SHELL_MM - float(member["clearance_mm"]), strokes["shoulder"], claims["shoulder"])}
    skin = lateral_sjc + lat
    trow = led["thorax"].row(sjc_below)
    inboard = []
    for label, x in (("model SJC x", _snapshot(root, "upper_arm_right_pos_x") * 1000.0 - hjc_x),
                     ("mesh SJC x", sjc_x)):
        for sublabel, cyls in (("spine modules in the thorax", thorax_cyl), ("modules elsewhere, corridor only", corridor)):
            d, c = nearest((x, -lateral_sjc), (0.0, 1.0), sjc_below, cyls)
            d, name, clearance = (lateral_sjc, "the midline (nothing named on the ray)", 0.0) if c is None else (d, c["id"], c["clearance"])
            inboard.append({"label": f"inboard of the SJC, arm moving as a block, ray at {label} ({x:.2f} mm), {sublabel}", "occupant": name, "clearance_mm": clearance, "sjc_to_occupant_mm": round(d, 2),
                            **reading(d - clearance, strokes["shoulder"], claims["shoulder"])})
    q = V[v] - thorax_o
    zones["shoulder"] = {
        "outcome": "answered",
        "station": station(v, "upper_arm_R (the zone is housed in the thorax)", r["s_mm"], q, "thorax ledger frame: origin on the hip line and midline at the CJC plane, x anterior, y left, z up; station is the upper arm ledger's, 4 mm below its joint station", "-y (right lateral)"),
        "sources": [ua.source(r, "hw_lat_mm"), led["thorax"].source(trow, "hw_right_mm")],
        "skin_depth_mm": round(skin, 2), "shoulder_plane_lateral_mm": lateral_sjc, "skin_to_sjc_mm": lat, "vertex_minus_ledger_mm": round(float(-q[1] - skin), 2),
        "thorax_ray_is_the_cut_plane_not_skin": trow["hw_right_mm"],
        "reading_b": reading(skin - SHELL_MM, strokes["shoulder"], claims["shoulder"]), "reading_a": a, "variants": inboard,
        "shell_sensitivity": shells(skin, trow, d_member, float(member["clearance_mm"])),
        "not_in_a_file": ["the shoulder mechanism and any joint hardware at the SJC (rm.v1-shoulder-concept)", "the sternal pivot position (adr-0008 D6(c))", "the thorax structure"],
    }

    # knee: anterior skin at the KJC plane in the zero pose
    thigh = led["thigh_R"]
    v = support(V, right & (np.abs(V[:, 2] - kjc_z) <= KNEE_SLAB_MM), (1, 0, 0))
    r, r2 = thigh.row(thigh.header["length_mm"]), led["shank_R"].row(0.0)
    skin = r["hw_ant_mm"]
    q = V[v] - thigh_o
    knee_a = ray_case("ledger ray at the KJC plane; nothing named on it", skin, (-skin, 0.0), (1.0, 0.0), r["s_mm"], [], strokes["knee"], claims["knee"])
    sh_min = led["shank_R"].header["min_inscribed_radius_inner"]["t5"]
    zones["knee"] = {
        "outcome": "answered",
        "station": station(v, "thigh_R (distal end)", r["s_mm"], q, "thigh_R ledger frame: origin at the HJC, x anterior, y left, z up", "+x (anterior, zero pose)"),
        "sources": [thigh.source(r, "hw_ant_mm"), led["shank_R"].source(r2, "hw_ant_mm")],
        "skin_depth_mm": skin, "shank_top_hw_ant_mm": r2["hw_ant_mm"], "vertex_minus_ledger_mm": round(float(q[0] - skin), 2),
        "thigh_min_inscribed_t5": thigh.header["min_inscribed_radius_inner"]["t5"], "shank_min_inscribed_t5": sh_min,
        "reading_b": reading(skin - SHELL_MM, strokes["knee"], claims["knee"]), "reading_a": knee_a,
        "variants": [{"label": "the inscribed radius at the same row, cheb_r_t5", "skin_to_node_mm": r["cheb_r_t5_mm"], **reading(r["cheb_r_t5_mm"], strokes["knee"], claims["knee"])},
                     {"label": "shank top, hw_ant at station 0", "skin_to_node_mm": r2["hw_ant_mm"], **reading(r2["hw_ant_mm"] - SHELL_MM, strokes["knee"], claims["knee"])}],
        "shell_sensitivity": shells(skin, r),
        "not_in_a_file": ["the knee mechanism: the thigh registry's two worked examples end 245 mm below the HJC"],
    }
    zones["hand_arm"] = {
        "outcome": "cannot be answered",
        "reason": "the stroke home is a swept arc about the sternal end of the clavicle (adr-0008 D6(c)). No file holds that pivot (adr-0008 D6(c), D9), no ledger or registry holds the shoulder shell's sweep, and the "
                  "repo's sweeps cover the model's hinges and the column corridor, not this arc. Answering needs a new sweep tool and a pivot choice adr-0007 does not make. Not built (brief, T1).",
        "fits_45_mm": None, "fits_90_mm": None,
    }
    return {"schema": "fall-room/1", "generated_by": "analysis/fall_room.py", "inputs": f"sha256:{inputs_hash(root)}", "arguments": {}, "baseline_mesh": BASELINE_MESH, "shell_mm": SHELL_MM,
            "strokes_mm_by_cap_kN": strokes, "registry_ties": ties, "zones": zones}


def _snapshot(root: Path, key: str) -> float:
    with open(root / "params/snapshot.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith("#")):
            if r["placeholder"] == key:
                return float(r["value"])
    raise KeyError(key)


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def render(result: dict) -> str:
    return json.dumps(result, indent=1, sort_keys=True, default=_default) + "\n"


def main(argv) -> int:
    if argv:
        print("analysis/fall_room.py takes no arguments", file=sys.stderr)
        return 2
    with open(ROOT / OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(build(ROOT)))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
