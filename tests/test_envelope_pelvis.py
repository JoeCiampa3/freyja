"""Volume-extractor brief 1, step 5: the pelvis frame, the scale k and the joint centres, and the sheet-input guards."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import pelvis, sheet  # noqa: E402

# The values the brief asserts for the sheet's table B1 (ISB pelvis frame, mm). They live here as a fixture for the unit tests
# only: the pipeline reads them from the sheet pull and asserts against these.
B1 = {"RASIS": (87.0, -13.0, 119.0), "LASIS": (87.0, -13.0, -119.0), "MPSIS": (-108.0, -13.0, 0.0), "HJC (Dumas)": (54.0, -93.0, 88.0)}


def rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    R = np.eye(3)
    R[i, i] = R[j, j] = c
    R[i, j], R[j, i] = -s, s
    return R


def synthetic_pelvis(R0, k0, ljc):
    """ASIS_R, ASIS_L, a sacral point, and the true right hip centre, for a pelvis posed by R0 (columns X, Y, Z) at scale k0."""
    P = lambda row: ljc + R0 @ (np.array(B1[row]) * k0)
    return P("RASIS"), P("LASIS"), P("MPSIS"), P("HJC (Dumas)")


@pytest.mark.parametrize("R0", [np.eye(3), rot(0, 20) @ rot(1, -35) @ rot(2, 70), rot(2, 12)])
@pytest.mark.parametrize("k0", [1.0, 1.0504, 0.93])
def test_round_trip_of_the_b1_numbers_through_a_synthetic_pelvis(R0, k0):
    ljc = np.array([10.0, -20.0, 900.0])
    ar, al, ms, hjc_true = synthetic_pelvis(R0, k0, ljc)
    k = pelvis.scale_from_asis(ar, al, B1)
    assert np.isclose(k, k0)
    frame = pelvis.pelvis_frame(ar, al, ms)
    assert np.allclose(frame.R, R0, atol=1e-9)
    assert np.allclose(pelvis.hip_joint_centre(ar, al, ms, B1, k), hjc_true, atol=1e-7)
    assert np.allclose(pelvis.lumbosacral_joint_centre(ar, al, ms, B1, k), ljc, atol=1e-7)


def test_frame_is_right_handed_with_z_to_the_right_and_x_anterior():
    ar = np.array([0, -119.0, 0]); al = np.array([0, 119.0, 0]); ms = np.array([-195.0, 0, 0])   # sheet frame: y is left
    f = pelvis.pelvis_frame(ar, al, ms)
    assert np.isclose(np.linalg.det(f.R), 1)
    assert np.allclose(f.X, [1, 0, 0]) and np.allclose(f.Z, [0, -1, 0]) and np.allclose(f.Y, [0, 0, 1])


def test_x_is_perpendicular_to_z_even_when_the_sacral_point_is_off_axis():
    ar, al, ms = np.array([0, -119.0, 0]), np.array([0, 119.0, 0]), np.array([-190.0, 15.0, 30.0])
    f = pelvis.pelvis_frame(ar, al, ms)
    assert abs(f.X @ f.Z) < 1e-12


def sheet_b1(**over):
    d = {"rows": {k: list(v) for k, v in B1.items()}, "pelvis_ref_length_mm": 107.0}
    d["rows"].update(over)
    return d


def test_b1_guard_accepts_the_brief_values():
    sheet.assert_b1(sheet_b1())


@pytest.mark.parametrize("row,val", [("RASIS", [87, -13, 120]), ("MPSIS", [-108, -12, 0]), ("HJC (Dumas)", [54, -93, 89])])
def test_b1_guard_stops_when_a_row_differs(row, val):
    with pytest.raises(sheet.StopAndAsk, match=row.split()[0]):
        sheet.assert_b1(sheet_b1(**{row: val}))


def test_b1_guard_stops_when_a_row_is_missing():
    d = sheet_b1()
    del d["rows"]["LASIS"]
    with pytest.raises(sheet.StopAndAsk, match="LASIS"):
        sheet.assert_b1(d)


def test_thigh_inputs_come_from_the_snapshot_in_millimetres_and_kilograms():
    t = sheet.thigh_inputs(REPO / "params" / "snapshot.csv", "right")
    assert 300 < t["length_mm"] < 500 and 3 < t["mass_kg"] < 20


def test_missing_snapshot_key_stops_and_names_it(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("placeholder,value,sheet_source\nthigh_right_mass,9.0,x\n")
    with pytest.raises(sheet.StopAndAsk, match="thigh_right_length"):
        sheet.thigh_inputs(p, "right")
