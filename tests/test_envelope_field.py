"""Volume-extractor brief 1, gate 4 (part): the voxel field reproduces synthetic solids. Tolerance is the brief's: one voxel (2 mm),
read as a displacement of the surface: |dV| / surface area, |dA| / perimeter, |dr| all below 2 mm."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests"))

from envelope import field  # noqa: E402
from envelope.synthetic import box, frustum, frustum_volume  # noqa: E402

VOXEL = 2.0
TOL = 2.0


def seg_for(v, f, z_top, z_bot, **kw):
    """A segment from the solid with the slab z_bot..z_top (mm) and the solid extended 40 mm beyond both ends."""
    return field.build_segment(v, f, length=z_top - z_bot, voxel=VOXEL, z_top=z_top, margin=20.0, **kw)


def test_cylinder_volume_section_area_and_inscribed_radius():
    R, H = 45.0, 300.0
    v, f = frustum(R, R, 60, -H - 60)
    seg = seg_for(v, f, 0.0, -H)
    vol = seg.volume()
    assert abs(vol - np.pi * R * R * H) / (2 * np.pi * R * H) < TOL
    sec = seg.section(150.0)
    assert abs(sec.area() - np.pi * R * R) / (2 * np.pi * R) < TOL
    cx, cy, r = sec.chebyshev()
    assert abs(r - R) < TOL and np.hypot(cx, cy) < TOL
    assert abs(seg.sd_max() - R) < TOL


def test_ends_do_not_shrink_the_inscribed_radius():
    """Distance is measured to the skin of the extended solid, not to the cut planes: at s = 0 and s = L the radius is still R."""
    R, H = 45.0, 300.0
    v, f = frustum(R, R, 60, -H - 60)
    seg = seg_for(v, f, 0.0, -H)
    for s in (0.0, 1.0, H - 1.0, H):
        assert abs(seg.section(s).chebyshev()[2] - R) < TOL, s


def test_box():
    hx, hy, H = 40.0, 25.0, 300.0
    v, f = box(hx, hy, (H + 120) / 2, center=(0, 0, -H / 2))
    seg = seg_for(v, f, 0.0, -H)
    area_surf = 2 * (2 * hx * 2 * hy) + 2 * (2 * hx + 2 * hy) * H
    assert abs(seg.volume() - 4 * hx * hy * H) / area_surf < TOL
    sec = seg.section(100.0)
    assert abs(sec.area() - 4 * hx * hy) / (4 * (hx + hy)) < TOL
    assert abs(sec.chebyshev()[2] - hy) < TOL
    assert abs(seg.sd_max() - hy) < TOL


def test_tapered_cone():
    r0, r1, H = 60.0, 30.0, 300.0
    v, f = frustum(r0 + (r0 - r1) * 60 / H, r1 - (r0 - r1) * 60 / H, 60, -H - 60)
    seg = seg_for(v, f, 0.0, -H)
    slant = np.hypot(H, r0 - r1)
    surf = np.pi * (r0 + r1) * slant + np.pi * (r0 ** 2 + r1 ** 2)
    assert abs(seg.volume() - frustum_volume(r0, r1, H)) / surf < TOL
    for s in (20.0, 150.0, 280.0):
        r = r0 + (r1 - r0) * s / H
        sec = seg.section(s)
        assert abs(sec.area() - np.pi * r * r) / (2 * np.pi * r) < TOL
        assert abs(sec.chebyshev()[2] - r) < TOL


def test_signed_distance_is_positive_inside_and_measured_to_the_skin():
    R = 45.0
    v, f = frustum(R, R, 60, -360)
    seg = seg_for(v, f, 0.0, -300.0)
    sd = seg.signed_distance(np.array([[0, 0, -150.0], [30, 0, -150.0], [60, 0, -150.0], [0, 0, 15.0]]))
    assert np.allclose(sd, [45, 15, -15, 45], atol=1.0)


def test_inner_envelope_volume_shrinks_by_the_shell_thickness():
    R, H, t = 45.0, 300.0, 8.0
    v, f = frustum(R, R, 60, -H - 60)
    seg = seg_for(v, f, 0.0, -H)
    assert abs(seg.volume(t) - np.pi * (R - t) ** 2 * H) / (2 * np.pi * (R - t) * H) < TOL


def test_a_closed_solid_is_watertight_and_an_open_one_is_not():
    v, f = frustum(40, 40, 0, -100)
    assert field.watertight(f)["boundary_edges"] == 0
    assert field.watertight(f[1:])["boundary_edges"] > 0


def test_parity_flags_columns_through_an_open_mesh():
    v, f = frustum(40, 40, 60, -360)
    seg = seg_for(v, np.delete(f, [0, 1], axis=0), 0.0, -300.0)   # open a hole in the side wall at angle 0
    assert seg.odd_columns > 0
