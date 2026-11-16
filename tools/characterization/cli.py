"""`fy characterize <segment> [--dry-run]`: a segment's characterization (tools/characterization). Group G of the upper-arm brief provides the
geometry and a summary on --dry-run (no arrays, nothing written); writing data/characterization/<segment>.json comes with the loads and the work item
(Groups L and F), and until then the command refuses to write."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .geometry import geometry
from .reader import CharacterizationError, Reader


def summary(g: dict) -> list:
    p, r = g["part"], g["report"]
    out = [f"{g['segment']}: geometry (right-side CAD frame, mm, deg)"]
    for led, v in r["provenance"].items():
        out.append(f"  ledger {led}: {v['mesh_file']}, inputs {v['inputs_sha256_12']}")
    fc = r["frame_checks"]
    out.append(f"  frame: axes orthonormal to {fc['orthonormal_error']:.1e}, det {fc['determinant']:+.0f}, shared {fc['axes_shared']}; "
               f"distal origin {fc['distal_distance_mm']:.4f} mm along {fc['distal_direction']} (sheet {fc['sheet_length_mm']:.4f})")
    for n, a in p["anchors"].items():
        b = a["position"]["bar"]
        out.append(f"  anchor {n}: {a['position']['mm']}, bar {b['value_mm']}{' mm' if b['value_mm'] != 'unstated' else ''}"
                   f"{' ' + b['direction'] if 'direction' in b else ''}")
    t = p["axis_tilt_bound"]
    out.append(f"  axis tilt bound {t['value_deg']:.4f} deg ({t['from']}; {t['plane']})")
    for n, i in p["interfaces"].items():
        rows = "; ".join(f"s {x['station_mm']} (offset {x['offset_from_joint_mm']:+.4f}): "
                         f"{sum(v['label'] == 'skin' for v in x['rays'].values())} skin, {sum(v['label'] == 'cut_plane' for v in x['rays'].values())} cut_plane"
                         for x in i["sections"])
        out.append(f"  interface {n}: station {i['joint_station_mm']}; rows {rows}")
    d = r["distal_room"]
    out.append(f"  distal room: row s {d['station_mm']} (offset {d['offset_from_joint_mm']:+.4f}); min r_ {min(d['r_mm'].values())}, min hw_ {min(d['hw_mm'].values())}; "
               f"r ant-post {d['r_ant_minus_post_mm']}, med-lat {d['r_med_minus_lat_mm']}; hw ant-post {d['hw_ant_minus_post_mm']}, med-lat {d['hw_med_minus_lat_mm']}")
    rom = p["rom"]
    out.append(f"  ROM {rom['joint']}: anatomical {rom['anatomical']['min_deg']} to {rom['anatomical']['max_deg']}, mechanism {rom['mechanism']['min_deg']} to "
               f"{rom['mechanism']['max_deg']}, loaded arc {'source needed' if rom['loaded_arc'].get('source_needed') else rom['loaded_arc']}; {rom['sign']}")
    fc = rom["flexion_clearance"]
    pick = {r["angle_deg"]: r for r in fc["rows"]}
    at = ", ".join(f"{a:g} deg {pick[a]['inner_separation_mm']:+.2f}/{pick[a]['skin_interpenetration_mm']:.2f}" for a in (0.0, 90.0, rom["mechanism"]["max_deg"]) if a in pick)
    first = "none within the travel" if fc["inner_first_contact_deg"] is None else f"{fc['inner_first_contact_deg']:g} deg"
    out.append(f"  flexion clearance (zones {fc['zone_h_mm']:g} mm excluded): inner shells first contact {first}; inner separation/skin mm at {at}; {len(fc['rows'])} rows")
    v = p["volume"]
    out.append(f"  volume: {v['inner_volume_l']} l inside the {v['shell_mm']:g} mm shell; {len(v['stations'])} station rows")
    out.append(f"  consumes {len(g['consumes'])} addresses")
    return out


def main(args, default_root=None, say=print) -> int:
    ap = argparse.ArgumentParser(prog="fy characterize", description=__doc__)
    ap.add_argument("segment", help="the pre_processor segment name (upper_arm)")
    ap.add_argument("--dry-run", action="store_true", help="print a summary; write nothing")
    ap.add_argument("--root", default=None)
    ns = ap.parse_args(args)
    root = Path(ns.root or default_root or ".")
    if not ns.dry_run:
        say("fy characterize: only --dry-run exists until the loads and the work item (Groups L and F); nothing written")
        return 2
    try:
        rd = Reader(root)
        g = geometry(rd, ns.segment)
    except CharacterizationError as e:
        say(f"fy characterize: {e}")
        return 1
    g["consumes"] = rd.consumes
    for line in summary(g):
        say(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
