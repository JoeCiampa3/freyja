"""
Stage 2e T4: the decile defect. `gait_diag.py pushoff` took `st[0]` and `st[-1]` of the stance flag of the first 100 frames as heel strike and toe-off;
a stance that wraps the stride boundary (the contralateral foot's, in every stride of this dataset) then spans frames 0 to 99, and its "deciles of
stance" are deciles of stride phase. The binning now counts from each foot's own heel strike (foot_pitch.stance_deciles).

Run from the repo root:
    python -m pytest tests/test_stage2e_deciles.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import gait_diag as gd  # noqa: E402


def _fp(right_frames, left_frames):
    """A (2, 101, 7) force-plate array whose stance channel (6) is 1 on the given frames of each foot (right, then left)."""
    fp = np.zeros((2, 101, 7))
    for fi, frames in enumerate((right_frames, left_frames)):
        for k in frames:
            fp[fi, k % 100, 6] = 1.0
        fp[fi, 100, 6] = fp[fi, 0, 6]
    return fp


def _old_binning(flag):
    """The pre-Stage 2e rule, kept here to show it was wrong: first and last flagged frame of the 100 unique frames."""
    st = np.flatnonzero(flag)
    first, last = st[0], st[-1]
    return {int(k): min(9, int(10 * (k - first) / max(1, last - first + 1))) for k in st}


def test_a_stance_that_wraps_the_stride_boundary_is_binned_from_its_own_heel_strike():
    # the left foot's stance: 60 frames from frame 51 through frame 110, i.e. 51 to 99 and 0 to 10
    fp = _fp(range(0, 60), range(51, 111))
    dec = gd.frame_stance_deciles(fp, 1)
    assert dec[51] == 0 and dec[99] == int(10 * 48 / 60) and dec[0] == int(10 * 49 / 60) and dec[10] == int(10 * 59 / 60) == 9
    assert (dec[11:51] == -1).all()
    # the old rule put frame 99 (late stance) in decile 9 of 0..99 and frame 0 in decile 0: deciles of stride phase
    old = _old_binning(fp[1, :100, 6] >= 0.5)
    assert old[0] == 0 and old[99] == 9 and old[0] != dec[0]


def test_the_non_wrapping_foot_is_unchanged_by_the_fix():
    fp = _fp(range(0, 60), range(51, 111))
    dec = gd.frame_stance_deciles(fp, 0)
    old = _old_binning(fp[0, :100, 6] >= 0.5)
    assert all(dec[k] == v for k, v in old.items()) and (dec[60:] == -1).all()


def test_a_flicker_after_toe_off_is_not_stance():
    fp = _fp(list(range(10, 70)) + [75, 76], range(0, 5))
    dec = gd.frame_stance_deciles(fp, 0)
    assert dec[75] == -1 and dec[76] == -1 and dec[10] == 0 and dec[69] == 9


def test_the_double_support_frames_of_the_two_feet_get_their_own_deciles():
    # right 0..59, left 51..110: frames 51..59 and 0..10 are double support; in decile terms the right foot's 51..59 are 8 and 9, the left's 0 and 1
    fp = _fp(range(0, 60), range(51, 111))
    r, l = gd.frame_stance_deciles(fp, 0), gd.frame_stance_deciles(fp, 1)
    assert r[55] == int(10 * 55 / 60) == 9 and l[55] == 0
    assert r[5] == 0 and l[5] == int(10 * 54 / 60) == 9
