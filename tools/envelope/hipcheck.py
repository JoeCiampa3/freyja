"""The hip registration check (volume-extractor brief 8, item 6b): report only, nothing is fixed.

The model puts the thigh's origin (its HJC) at the sheet's lateral offset from the pelvis origin; the mesh's hip joint centres are 75.6 mm either side of its midline (the sheet's: 92.43 mm), and
the conform moves the legs to the sheet's lateral position and the trunk by the shear at the HJC node, a translation. Read in the model frames, the same physical hip is then two points 16.8 mm
apart in the mesh. This reports, in the thigh frame and in the pelvis frame:

  * the signed skin distance (positive inside) at the model's HJC;
  * the skin distance, lateral, at the HJC plane from the HJC;
  * the lateral extent of the right half of the pelvis section at its HJC plane against the thigh's at its own, placed where the model places it, and the same two extents in the conformed
    mesh frame (where they are one surface and agree);
  * the pelvis and thigh volumes under the other shear target (the mesh's own HJC section centroid, not the sheet's lateral offset): a translation, so no change expected, checked.

The flag is the brief's: the two frames differ by more than 5 mm.
"""
from __future__ import annotations

import dataclasses

import numpy as np

from . import bodies, decompose, features, field, frames, masses, trial, trunk

FLAG_MM = 5.0
STEP_IN_MM = 1.0                      # sections are taken this far inside each body's end plane


def _extent_y(sec, half: str | None = None):
    """(min y, max y) of the section's mask, optionally the half y < 0 (right) only."""
    m = sec.mask(0.0)
    if half == "right":
        m = m & (sec.y[None, :] < 0.0)
    if not m.any():
        return float("nan"), float("nan")
    ys = np.broadcast_to(sec.y[None, :], m.shape)[m]
    return float(ys.min()), float(ys.max())


def frame_numbers(thigh: field.Segment, pelvis: field.Segment, lateral_y_mm: float, hjc_x_mm: float) -> dict:
    """Everything of the report that comes from the two built bodies. `lateral_y_mm` is the sheet's signed lateral offset of the right HJC (negative), `hjc_x_mm` the model's HJC x ahead of its
    pelvis origin. Heights: the thigh's origin is its HJC plane (z = 0); the pelvis body's lower plane is at z = -length."""
    t_o, p_o = np.array(thigh.meta["origin_xyz"], float), np.array(pelvis.meta["origin_xyz"], float)
    p_off = frames.segment_offset_mm("pelvis", pelvis.meta)
    # the model's HJC: thigh frame origin; pelvis frame (oracle) x = model x + offset = hjc_x - hjc_x = 0, y = the sheet's lateral offset, z the pelvis's lower plane
    hjc_thigh = np.array([0.0, 0.0, 0.0])
    hjc_pelvis = np.array([hjc_x_mm + p_off[0], lateral_y_mm, pelvis.z_top - pelvis.length])
    sd_t, sd_p = float(thigh.signed_distance(hjc_thigh[None, :])[0]), float(pelvis.signed_distance(hjc_pelvis[None, :])[0])
    sec_t = thigh.section(STEP_IN_MM)
    sec_p = pelvis.section(pelvis.length - STEP_IN_MM)
    lat_t = sec_t.ray((0.0, 0.0), 270)
    lat_p = sec_p.ray((hjc_pelvis[0], hjc_pelvis[1]), 270)
    tmin, _ = _extent_y(sec_t)
    pmin, _ = _extent_y(sec_p, "right")
    model_t = tmin + lateral_y_mm                                                           # the thigh's lateral extent where the model puts the thigh (its origin at the sheet's offset)
    mesh_t = tmin + (t_o[1] - p_o[1])                                                       # and where the mesh has it (the conformed frame: both origins in the conformed mesh)
    out = {
        "model_hjc": {"thigh_frame_mm": hjc_thigh.tolist(), "pelvis_frame_mm": [float(v) for v in hjc_pelvis]},
        "signed_skin_distance_at_hjc_mm": {"thigh_frame": sd_t, "pelvis_frame": sd_p, "difference": sd_p - sd_t},
        "lateral_skin_distance_at_hjc_plane_mm": {"thigh_frame": lat_t, "pelvis_frame": lat_p, "difference": lat_p - lat_t},
        "lateral_extent_right_half_pelvis_frame_mm": {"pelvis_section": pmin, "thigh_section_placed_by_the_model": model_t, "step_model_frames": model_t - pmin,
                                                      "thigh_section_placed_by_the_mesh": mesh_t, "step_conformed_mesh": mesh_t - pmin},
        "origins_conformed_mm": {"thigh": [float(v) for v in t_o], "pelvis": [float(v) for v in p_o], "thigh_minus_pelvis_y": float(t_o[1] - p_o[1])},
        "sheet_lateral_offset_mm": lateral_y_mm, "mesh_hjc_separation_from_midline_mm": float(abs(t_o[1] - p_o[1])),
        "hip_spacing_difference_mm": float(abs(lateral_y_mm) - abs(t_o[1] - p_o[1])),
        "section_station_in_mm": STEP_IN_MM,
    }
    out["flag"] = {"limit_mm": FLAG_MM, "frames_differ_by_more_than_limit": bool(abs(sd_p - sd_t) > FLAG_MM or abs(lat_p - lat_t) > FLAG_MM or abs(out["lateral_extent_right_half_pelvis_frame_mm"]["step_model_frames"]) > FLAG_MM),
                   "signed_distance": bool(abs(sd_p - sd_t) > FLAG_MM), "lateral_distance": bool(abs(lat_p - lat_t) > FLAG_MM), "step": bool(abs(out["lateral_extent_right_half_pelvis_frame_mm"]["step_model_frames"]) > FLAG_MM)}
    return out


def alternative_target(root, mesh_path, voxel=2.0) -> dict:
    """The thigh and pelvis volumes if the shear's lateral target were the mesh's own HJC section centroid instead of the sheet's lateral offset (the conform then does not move the leg
    sideways at the hip). Builds both bodies again; the volumes are expected unchanged (a translation does not change a section or a length)."""
    inp = trial.load_inputs(root, mesh_path)
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    own_y = float(reg.centroids["hjc"][1])
    alt_sheet = dataclasses.replace(inp.sheet, lateral_y=own_y)
    inp_alt = dataclasses.replace(inp, sheet=alt_sheet)
    reg_alt = trial.make_registration(inp_alt, feats, "chords")
    thigh = trial.build_segment(inp_alt, feats, reg_alt, "thigh", voxel)
    table = masses.load_dumas_table1(root)
    raster = features.BodyRaster(inp.V, inp.F, inp.stature_mesh + 10.0, h=bodies.RASTER_MM)
    prof = decompose.profile(raster)
    names = np.array(decompose.vertex_regions(inp.V, raster, {"apex": feats["crotch_apex_mm"], "neck": decompose.neck_height(prof, inp.stature_mesh)}))
    ax = bodies.axilla(prof, feats["crotch_apex_mm"])
    sh = {"ajc": inp.sheet.ajc, "kjc": inp.sheet.kjc, **trunk.sheet_nodes(inp.sheet)}
    sj = bodies.sjc(table, inp.sheet)
    tm = bodies.trunk_map(inp_alt, reg_alt, table)
    pelvis = bodies.build_body(inp_alt, raster, tm, "pelvis", names == "arms", sh, ax["level_mm"], sj["lateral_mm"], voxel)
    return {"target_lateral_y_mm": own_y, "sheet_lateral_y_mm": inp.sheet.lateral_y, "thigh_volume_l": thigh.seg.volume(0.0) / 1e6, "pelvis_volume_l": pelvis.seg.volume(0.0) / 1e6,
            "thigh_origin_y_mm": float(thigh.origin_xyz[1]), "pelvis_origin_y_mm": float(pelvis.origin_xyz[1])}
