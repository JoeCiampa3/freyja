"""The geometry of a segment's characterization (docs/briefs/ariadne/upper-arm-characterization-brief.md, T6; adr-0045 D3, D4, D6): the frames, the anchors
and their bars, the axis tilt bound, the bracketing section rows at each interface with their ray labels, the room around the distal node, the ROM and the
volume. Segment-generic: the segment's body, its proximal and distal joints and the joints further down the chain are read from the thread's derived
documents; every value is read through `Reader` (an address) or computed here from such values; the authored inputs are
`data/characterization/inputs/<segment name>.yaml` (characterization-inputs/1).

Frames. The file's frame is the right-side ISB/CAD segment frame (CONVENTIONS section 3): origin at the proximal joint centre, x anterior, y proximal,
z lateral, mm. The ledger (`data/envelope/<body>_R.yaml` and its sections CSV) is in the arm segment frame (x anterior, y left, z up, origin at the
proximal node; `tools/envelope/arms.py`), which `tools/envelope/registry.isb_to_segment` maps the CAD frame onto; this module converts the other way with
that rotation's transpose (`to_cad`) and never a second copy of it. A ledger station s is a distance below the top of the field: its z is
`stations.top_z_mm` - s and its CAD y the same number.

Ray labels. The ledger's rays are `Section.ray` (`tools/envelope/field.py`, lines 258-273): from the segment axis (`hw_<dir>_mm`) or from the section's
Chebyshev centre (`r_<dir>_mm`, `tools/envelope/ledger.py` lines 59-62), the distance to where {sd >= 0} within the segment's region is left. A ray that
leaves on the skin is interpolated across the crossing (field.py:273); one that leaves the region first (a cut plane: the field's end planes, the
elbow's bisector, the membership boundary against the thorax) returns the last 0.25 mm step inside (field.py:271-272); one whose origin is outside
returns 0 (field.py:265-266). The CSV holds only the distance (rounded to 0.01 mm), so the label is read from it: a value that is not a multiple of
the 0.25 mm step can only be a skin crossing and is `skin`; a multiple is `cut_plane`. The rule never labels a cut-plane ray skin; it labels a skin
ray whose crossing falls within 0.005 mm of a step `cut_plane` (about 4% of skin rays; memo 63).
"""
from __future__ import annotations

import math
from decimal import Decimal

import numpy as np

from .reader import CharacterizationError, Reader

RAY_STEP = Decimal("0.25")        # field.Section.ray's default step (tools/envelope/field.py:258), mm: a region exit returns a multiple of it
STATION_HALF_PRECISION_MM = 0.05  # the CSV's s_mm is rounded to 0.1 mm (tools/envelope/ledger.py:56): a row within half of that is at the station
ORTHO_TOL = 1e-9                  # the brief's G-G2 tolerance on the frame axes
SIDE = "right"
SIDE_TAG = "R"
UNITS = {"length": "mm", "angle": "deg", "force": "N", "moment": "N m", "mass": "kg", "energy": "J"}


def to_cad(points) -> np.ndarray:
    """Points in the oracle/ledger segment frame (x anterior, y left, z up) in the right-side CAD frame: the transpose of registry.isb_to_segment."""
    from envelope import registry
    return np.atleast_2d(np.asarray(points, float)) @ registry.ISB_TO_SEGMENT


def cad_axes() -> list:
    """The CAD frame's x, y, z as unit vectors in the file's frame: the round trip through isb_to_segment and its transpose (the identity, by construction)."""
    from envelope import registry
    return [[_r(x) for x in a] for a in to_cad(registry.isb_to_segment(np.eye(3)))]


def ray_label(text: str) -> str:
    """`skin` or `cut_plane` for a ray as the CSV writes it (module docstring)."""
    d = Decimal(text.strip())
    return "cut_plane" if (d / RAY_STEP) == (d / RAY_STEP).to_integral_value() else "skin"


def _num(text: str) -> float:
    x = float(text)
    if not math.isfinite(x):
        raise CharacterizationError(f"a ledger cell reads {text!r}, not a finite number")
    return x


def _r(x, nd=6):
    return round(float(x), nd) + 0.0


class Segment:
    """The addresses and values of one segment's geometry, read through a Reader."""

    def __init__(self, reader: Reader, name: str):
        self.rd, self.name = reader, name
        self.id = f"seg.{name}"
        self.inputs_path = f"data/characterization/inputs/{name}.yaml"
        g = reader.get
        self.body = g(f"thread/derived/{self.id}.json#/body")
        prox, dist = g(f"thread/derived/{self.id}.json#/joints_as_child"), g(f"thread/derived/{self.id}.json#/joints_as_parent")
        if len(prox) != 1 or len(dist) != 1:
            raise CharacterizationError(f"{self.id}: expected one proximal and one distal joint, found {prox} and {dist}")
        self.proximal, self.distal = prox[0], dist[0]
        self.ledger = f"data/envelope/{self.body}_{SIDE_TAG}.yaml"
        self.csv = "data/envelope/" + g(f"{self.ledger}#/sections_csv")
        self.length_mm = 1000.0 * float(g(f"snapshot#/{self.body}_{SIDE}_length"))
        self.joint_station_mm = float(g(f"{self.ledger}#/stations/joint_station_mm"))
        self.top_z_mm = float(g(f"{self.ledger}#/stations/top_z_mm"))
        rows = g(f"{self.csv}#")
        self.rows = sorted(rows.values(), key=lambda r: _num(r["s_mm"]))

    # ---- anchors -----------------------------------------------------------------------------------------------------------------------

    def input_entry(self, pointer: str):
        return self.rd.get(f"{self.inputs_path}#{pointer}")

    def chain(self):
        """[(anchor name, joint id, distance below the proximal joint in the model's zero pose, mm)] from the proximal joint down the chain, as far as the
        inputs name anchors. The zero pose is the model's: every arm segment hangs straight down (the forearm at -L_upper_arm, the hand at -L_forearm)."""
        g = self.rd.get
        bars = self.input_entry("/anchor_bars")
        out = [(self.proximal.split(".", 1)[1], self.proximal, 0.0)]
        joint, seg, depth = self.distal, self.id, self.length_mm
        while True:
            out.append((joint.split(".", 1)[1], joint, depth))
            if set(bars) <= {n for n, _, _ in out}:
                break
            kids = g(f"thread/derived/{joint}.json#/child_segments")
            if len(kids) != 1:
                raise CharacterizationError(f"the inputs name anchors {sorted(set(bars) - {n for n, _, _ in out})} beyond {joint}, whose child segments are {kids}")
            seg = kids[0]
            nxt = g(f"thread/derived/{seg}.json#/joints_as_parent")
            if len(nxt) != 1:
                raise CharacterizationError(f"{seg} has distal joints {nxt}; cannot reach the anchors {sorted(set(bars) - {n for n, _, _ in out})}")
            body = g(f"thread/derived/{seg}.json#/body")
            depth += 1000.0 * float(g(f"snapshot#/{body}_{SIDE}_length"))
            joint = nxt[0]
        missing = {n for n, _, _ in out} - set(bars)
        if missing:
            raise CharacterizationError(f"{self.inputs_path}: no anchor bar for {sorted(missing)}")
        return out

    def bar(self, anchor: str) -> dict:
        e = self.input_entry(f"/anchor_bars/{anchor}")
        b = {"value_mm": e["value"], "source": e["source"]}
        if "direction" in e:
            b["direction"] = e["direction"]
        return b

    def anchors(self) -> dict:
        defs = {0: "the sheet's joint centre carried through the trunk registration (adr-0042 D1; tools/envelope/arms.py registration)",
                1: "the adr-0042 D1 node: the proximal segment's section centre line at the joint station"}
        out = {}
        for i, (name, joint, depth) in enumerate(self.chain()):
            p = to_cad([[0.0, 0.0, -depth]])[0]
            d = defs.get(i, "the adr-0042 D1 node of the next segment, placed in this frame at the model's zero pose (every joint at 0 degrees)")
            out[name] = {"definition": f"{joint}: {d}", "position": {"mm": [_r(x) for x in p], "bar": self.bar(name)}}
        return out

    def tilt_bound(self) -> dict:
        """atan(bar / length) of the distal anchor (adr-0045 D6(a))."""
        name = self.distal.split(".", 1)[1]
        e = self.input_entry(f"/anchor_bars/{name}")
        if not isinstance(e["value"], (int, float)):
            raise CharacterizationError(f"the distal anchor's bar is {e['value']!r}; the tilt bound needs a number")
        v = math.degrees(math.atan(e["value"] / self.length_mm))
        plane = "mostly sagittal: the bar is mostly " + e["direction"] if "direction" in e else "any plane through the axis"
        return {"value_deg": _r(v), "from": f"atan({e['value']:g} mm / {self.length_mm:.4f} mm), the {name} bar over the segment length", "plane": plane}

    # ---- sections ----------------------------------------------------------------------------------------------------------------------

    def y_of(self, s: float) -> float:
        return float(to_cad([[0.0, 0.0, self.top_z_mm - s]])[0][1])

    def section_row(self, row: dict, joint_y=None) -> dict:
        s = _num(row["s_mm"])
        out = {"station_mm": s, "y_mm": _r(self.y_of(s))}
        if joint_y is not None:
            out["offset_from_joint_mm"] = _r(self.y_of(s) - joint_y)
        out["values"] = {k: _num(v) for k, v in sorted(row.items()) if k != "s_mm" and not k.startswith(("hw_", "r_"))}
        out["rays"] = {k: {"mm": _num(v), "label": ray_label(v)} for k, v in sorted(row.items()) if k.startswith(("hw_", "r_"))}
        return out

    def bracket(self, station: float) -> list:
        """The two ledger rows that bracket a joint station, not interpolated: the last row above it and the first row at or below it. A row within
        half the CSV's station precision of the station is at it."""
        s = [_num(r["s_mm"]) for r in self.rows]
        above = [i for i, x in enumerate(s) if x < station - STATION_HALF_PRECISION_MM]
        below = [i for i, x in enumerate(s) if x >= station - STATION_HALF_PRECISION_MM]
        if not above or not below:
            raise CharacterizationError(f"{self.csv}: no pair of rows brackets station {station:.4f} mm")
        return [self.rows[above[-1]], self.rows[below[0]]]

    def interfaces(self) -> dict:
        out = {}
        for name, joint, depth in self.chain()[:2]:
            station = self.joint_station_mm + depth
            jy = self.y_of(station)
            out[name] = {"anchor": name,
                         "frame": {"origin": {"mm": [_r(x) for x in to_cad([[0.0, 0.0, -depth]])[0]], "bar": self.bar(name)},
                                   "axes": cad_axes()},
                         "joint_station_mm": _r(station),
                         "sections": [self.section_row(r, jy) for r in self.bracket(station)],
                         "wrenches": []}
        return out

    def distal_room(self) -> dict:
        """The last row above the distal joint station whose twelve rays all end on skin, its eight `r_` rays (from the section's Chebyshev centre) and
        four `hw_` rays (from the segment axis, on which the D1 node lies), and the anterior-minus-posterior and medial-minus-lateral differences."""
        station = self.joint_station_mm + self.length_mm
        cand = [r for r in self.rows if _num(r["s_mm"]) < station - STATION_HALF_PRECISION_MM]
        for r in reversed(cand):
            rays = {k: v for k, v in r.items() if k.startswith(("hw_", "r_"))}
            if all(ray_label(v) == "skin" for v in rays.values()):
                rr = {k: _num(v) for k, v in rays.items()}
                return {"station_mm": _num(r["s_mm"]), "offset_from_joint_mm": _r(self.y_of(_num(r["s_mm"])) - self.y_of(station)),
                        "chebyshev_centre_mm": [_num(r["cheb_cx_mm"]), _num(r["cheb_cy_mm"])],
                        "r_mm": {k: x for k, x in sorted(rr.items()) if k.startswith("r_")}, "hw_mm": {k: x for k, x in sorted(rr.items()) if k.startswith("hw_")},
                        "r_ant_minus_post_mm": _r(rr["r_ant_mm"] - rr["r_post_mm"], 2), "r_med_minus_lat_mm": _r(rr["r_med_mm"] - rr["r_lat_mm"], 2),
                        "hw_ant_minus_post_mm": _r(rr["hw_ant_mm"] - rr["hw_post_mm"], 2), "hw_med_minus_lat_mm": _r(rr["hw_med_mm"] - rr["hw_lat_mm"], 2),
                        "bar": self.bar(self.distal.split(".", 1)[1])}
        raise CharacterizationError(f"{self.csv}: no row above station {station:.4f} has all its rays on skin")

    # ---- ROM and volume ----------------------------------------------------------------------------------------------------------------

    def rom(self) -> dict:
        g = self.rd.get
        joint = self.input_entry("/rom/joint")
        if joint != self.distal:
            raise CharacterizationError(f"{self.inputs_path}: rom.joint is {joint}, the segment's distal joint is {self.distal}")
        hinges = g(f"{joint}#/hinges")
        if len(hinges) != 1:
            raise CharacterizationError(f"{joint} has hinges {hinges}; the ROM here is a single hinge's")
        hinge = f"{hinges[0]}_{SIDE}"
        pol = g(f"checks/joint_polarity.yaml#/joints/{hinge}")
        keys = g(f"{joint}#/rom_keys")
        pos = [k for k in keys if k.endswith("_" + pol["positive"])]
        neg = [k for k in keys if k not in pos]
        if len(pos) != 1 or len(neg) != 1:
            raise CharacterizationError(f"{joint}: rom_keys {keys} do not split into one {pol['positive']} key and one other")
        hi, lo = float(g(f"snapshot#/{pos[0]}")), float(g(f"snapshot#/{neg[0]}"))
        neg_word = neg[0].split("_", 1)[1]
        mech = self.input_entry("/rom/mechanism_ends")
        if set(mech) != {pol["positive"]}:
            raise CharacterizationError(f"{self.inputs_path}: mechanism_ends names {sorted(mech)}; only the {pol['positive']} end is authored, the other is the snapshot's")
        end = mech[pol["positive"]]
        arc = self.input_entry("/rom/loaded_arc")
        cite = lambda e: ", ".join(f"{c['record']} {c['clause']}" for c in e["source"])  # noqa: E731
        loaded = {"min_deg": None, "max_deg": None, "basis": cite(arc) + (f"; {arc['note']}" if "note" in arc else "")}
        if arc["value"] is not None:
            raise CharacterizationError(f"{self.inputs_path}: the loaded arc has a value; its form (two bounds) is not defined yet")
        loaded["source_needed"] = True
        return {"joint": joint,
                "sign": f"{pol['positive']} positive, {neg_word} negative (checks/joint_polarity.yaml {hinge}: sign {pol['sign']}, positive {pol['positive']})",
                "anatomical": {"min_deg": -lo, "max_deg": hi, "basis": f"snapshot {neg[0]} and {pos[0]}"},
                "mechanism": {"min_deg": -lo, "max_deg": float(end["value"]), "basis": f"snapshot {neg[0]}; {pol['positive']} end {cite(end)}"},
                "loaded_arc": loaded}

    def volume(self) -> dict:
        shell = self.input_entry("/shell")
        t = float(shell["value"])
        key = f"t{t:g}"
        return {"definition": f"the body envelope inside the {t:g} mm shell (adr-0007 D4), not the free field; read from the ledger, not recomputed",
                "shell_mm": t, "inner_volume_l": float(self.rd.get(f"{self.ledger}#/inner_volume_l/{key}")),
                "stations": [self.section_row(r) for r in self.rows]}

    # ---- provenance and checks -----------------------------------------------------------------------------------------------------------

    def provenance(self) -> dict:
        g = self.rd.get
        kids = g(f"thread/derived/{self.distal}.json#/child_segments")
        out = {}
        for seg in [self.id, *kids]:
            body = g(f"thread/derived/{seg}.json#/body")
            led = f"data/envelope/{body}_{SIDE_TAG}.yaml"
            out[f"{body}_{SIDE_TAG}"] = {"mesh_file": g(f"{led}#/mesh_file"), "inputs_sha256_12": g(f"{led}#/inputs_sha256_12")}
        return out

    def frame_checks(self) -> dict:
        """G-G2: the CAD axes from the transpose of isb_to_segment are orthonormal and right-handed; the distal origin's distance and direction; the
        ledger's own lengths against the sheet's."""
        A = to_cad(np.eye(3))
        g = self.rd.get
        ifs = self.interfaces()
        names = list(ifs)
        o0, o1 = (np.array(ifs[n]["frame"]["origin"]["mm"]) for n in names)
        d = o1 - o0
        return {"orthonormal_error": float(np.abs(A @ A.T - np.eye(3)).max()), "determinant": float(np.linalg.det(A)),
                "axes_shared": ifs[names[0]]["frame"]["axes"] == ifs[names[1]]["frame"]["axes"],
                "distal_distance_mm": float(np.linalg.norm(d)), "sheet_length_mm": self.length_mm,
                "distal_direction": [_r(x, 9) for x in d / np.linalg.norm(d)],
                "ledger_length_less_joint_station_mm": float(g(f"{self.ledger}#/length_mm")) - self.joint_station_mm,
                "ledger_mesh_length_mm": float(g(f"{self.ledger}#/mesh_length_mm"))}


def geometry(reader: Reader, name: str) -> dict:
    """The geometry parts of the characterization (frame, anchors, axis_tilt_bound, interfaces with no wrenches yet, rom without the flexion
    clearance, volume) and a `report` of what the checkpoint memo states (provenance, frame checks, the room at the distal node)."""
    s = Segment(reader, name)
    anchors = s.anchors()
    origin = s.proximal.split(".", 1)[1]
    part = {"frame": {"statement": f"Right-side ISB/CAD segment frame of {s.id} (CONVENTIONS section 3): origin at the {origin} joint centre, x anterior, "
                                   f"y proximal, z lateral, mm; the model's zero pose (every joint at 0 degrees; the forearm at neutral rotation, adr-0042 D5).",
                      "origin": origin, "axes": {"x": "anterior", "y": "proximal", "z": "lateral"}, "units": dict(UNITS)},
            "anchors": anchors, "axis_tilt_bound": s.tilt_bound(), "interfaces": s.interfaces(), "rom": s.rom(), "volume": s.volume()}
    report = {"provenance": s.provenance(), "frame_checks": s.frame_checks(), "distal_room": s.distal_room(),
              "joint_stations_mm": {n: _r(s.joint_station_mm + depth) for n, _, depth in s.chain()[:2]}}
    return {"segment": s.id, "part": part, "report": report}
