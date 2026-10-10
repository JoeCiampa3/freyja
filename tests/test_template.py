"""
Tests that the template carries no hand-typed copies of sheet values (T2) and
that the derived placeholder keys are right. Offline: they read the tracked
params/snapshot.csv and the template, never the sheet.

Run from the repo root:
    python -m unittest discover -s tests -v
"""
import csv
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import pre_processor as pp

TEMPLATE = REPO / "sim" / "models" / "freyja_template.xml"
SNAPSHOT = REPO / "params" / "snapshot.csv"
DESIGN_COMMENT = "design choice, no sheet source"
MATCH_TOL = 1e-4  # m: closer than this to a snapshot value (or its negation) means it is a copy

PLACEHOLDER = re.compile(r"[$!]\{[^}]*\}")
GEOM_TAG = re.compile(r"<geom\b[^<>]*>")
GEOM_ATTR = re.compile(r'\b(pos|fromto|size)="([^"]*)"')


def snapshot_values():
    with SNAPSHOT.open(encoding="utf-8", newline="") as f:
        return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(f)}


def geom_literals(text):
    """(line number, attribute, number, line has the design comment) for every numeric literal in a geom."""
    for n, line in enumerate(text.splitlines(), 1):
        for tag in GEOM_TAG.findall(line):
            for attr, value in GEOM_ATTR.findall(tag):
                for tok in PLACEHOLDER.sub(" ", value).split():
                    yield n, attr, float(tok), DESIGN_COMMENT in line


def render_geoms(values):
    """Render the real template and return its geoms by (parent body name, index)."""
    report = pp.Report()
    plain = {k: v for k, v in values.items()}
    plain.update(pp.derive_keys(plain))
    xml = pp.render(TEMPLATE.read_text(encoding="utf-8"), plain, report)
    assert not report.errors, report.errors
    return xml


def floats(s):
    return [float(t) for t in s.split()]


def scaled(values, factor):
    """Stature scaled: every length and position scales, ROM and masses stay."""
    return {k: v * factor if k.endswith(("_length", "_pos_x", "_pos_y", "_pos_z", "_jpos_z")) else v
            for k, v in values.items()}


class NoHandTypedCopies(unittest.TestCase):
    def test_no_geom_literal_matches_a_snapshot_value(self):
        snap = snapshot_values()
        bad = []
        for line, attr, x, commented in geom_literals(TEMPLATE.read_text(encoding="utf-8")):
            if x == 0 or commented:
                continue
            hits = [k for k, v in snap.items() if abs(v - x) < MATCH_TOL or abs(v + x) < MATCH_TOL]
            if hits:
                bad.append(f"template line {line}: {attr} literal {x:g} equals {hits[:3]}")
        self.assertEqual(bad, [])

    def test_scan_catches_a_planted_copy(self):
        # mutation test: the scan must flag a literal copied from the sheet
        snap = snapshot_values()
        planted = f'<geom type="capsule" fromto="0 0 0 0 0 {snap["thigh_right_length"]:.4f}" size="0.05"/>'
        hits = [x for _, _, x, c in geom_literals(planted)
                if x and not c and any(abs(v - x) < MATCH_TOL for v in snap.values())]
        self.assertTrue(hits)

    def test_design_choice_comment_exempts_a_line(self):
        snap = snapshot_values()
        planted = f'<geom pos="{snap["thigh_right_length"]:.4f} 0 0" size="0.05"/> <!--{DESIGN_COMMENT}-->'
        self.assertTrue(all(c for _, _, _, c in geom_literals(planted)))


class DerivedKeys(unittest.TestCase):
    def test_foot_box_is_a_quarter_and_half_of_the_foot_length(self):
        d = pp.derive_keys({"foot_right_length": 0.165, "foot_left_length": 0.17})
        self.assertAlmostEqual(d["foot_right_box_pos_x"], 0.04125)
        self.assertAlmostEqual(d["foot_right_box_half_x"], 0.0825)
        self.assertAlmostEqual(d["foot_left_box_half_x"], 0.085)

    def test_knee_sphere_sits_one_radius_below_the_thigh_end(self):
        d = pp.derive_keys({"thigh_right_length": 0.4, "thigh_left_length": 0.4})
        self.assertAlmostEqual(d["thigh_right_knee_sphere_z"], -0.45)
        self.assertAlmostEqual(d["thigh_left_knee_sphere_z"], -0.45)

    def test_upper_arm_capsule_ends_one_radius_short_of_the_elbow(self):
        d = pp.derive_keys({"upper_arm_right_length": 0.243})
        self.assertAlmostEqual(d["upper_arm_right_capsule_end_z"], -0.213)

    def test_missing_inputs_give_no_key(self):
        self.assertEqual(pp.derive_keys({}), {})

    def test_derived_names_never_clash_with_sheet_names(self):
        self.assertFalse(set(pp.derive_keys({f"{s}_{side}_length": 1.0 for s in pp.BILATERAL
                                             for side in ("right", "left")})) & set(snapshot_values()))


class StatureScaling(unittest.TestCase):
    def geoms(self, values):
        root = ET.fromstring(render_geoms(values))
        out = {}
        for body in root.iter("body"):
            out[body.get("name")] = [g for g in body.findall("geom")]
        return out

    def test_geometry_follows_the_sheet_when_stature_scales_5_percent(self):
        base, big = self.geoms(snapshot_values()), self.geoms(scaled(snapshot_values(), 1.05))
        f = 1.05
        # pelvis capsule ends at the hip joint centres (x and z)
        b, g = floats(base["pelvis"][1].get("fromto")), floats(big["pelvis"][1].get("fromto"))
        for i in (0, 2, 3, 5):
            self.assertAlmostEqual(g[i], b[i] * f, places=9)
        for side in ("right", "left"):
            # thigh capsule end is the thigh length
            b, g = floats(base[f"thigh_{side}"][0].get("fromto")), floats(big[f"thigh_{side}"][0].get("fromto"))
            self.assertAlmostEqual(g[5], b[5] * f, places=9)
            # the knee sphere keeps its fixed radius offset below the scaled length
            b, g = floats(base[f"thigh_{side}"][1].get("pos")), floats(big[f"thigh_{side}"][1].get("pos"))
            self.assertAlmostEqual(g[2], (b[2] + 0.05) * f - 0.05, places=9)
            # the foot box is a collision geom: its length follows the foot length
            b, g = base[f"foot_{side}"][0], big[f"foot_{side}"][0]
            self.assertAlmostEqual(floats(g.get("size"))[0], floats(b.get("size"))[0] * f, places=9)
            self.assertAlmostEqual(floats(g.get("pos"))[0], floats(b.get("pos"))[0] * f, places=9)
            # upper-arm capsule end
            b, g = floats(base[f"upper_arm_{side}"][0].get("fromto")), floats(big[f"upper_arm_{side}"][0].get("fromto"))
            self.assertAlmostEqual(-g[5], (-b[5] + 0.03) * f - 0.03, places=9)

    def test_unscaled_geometry_matches_the_old_literals_to_a_tenth_of_a_millimetre(self):
        # Replacing literals by placeholders must not move a geom by more than the rounding of
        # the old literal (the thigh end 0.3975 versus the sheet's 0.397525 is the largest).
        g = self.geoms(snapshot_values())
        for side in ("right", "left"):
            for got, want in [(floats(g[f"thigh_{side}"][0].get("fromto"))[5], -0.3975),
                              (floats(g[f"thigh_{side}"][1].get("pos"))[2], -0.4475),
                              (floats(g[f"foot_{side}"][0].get("size"))[0], 0.0825),
                              (floats(g[f"foot_{side}"][0].get("pos"))[0], 0.04125),
                              (floats(g[f"upper_arm_{side}"][0].get("fromto"))[5], -0.213)]:
                self.assertAlmostEqual(got, want, delta=1e-4)
        self.assertAlmostEqual(floats(g["pelvis"][1].get("fromto"))[0], 0.0566394618834, places=9)


class CompilesWithMujoco(unittest.TestCase):
    def test_scaled_model_compiles(self):
        try:
            import mujoco
        except ImportError:
            self.skipTest("mujoco not installed")
        mujoco.MjModel.from_xml_string(render_geoms(scaled(snapshot_values(), 1.05)))


if __name__ == "__main__":
    unittest.main()
