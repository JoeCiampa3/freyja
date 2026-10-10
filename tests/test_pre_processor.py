"""
Tests for pre_processor.py. They need no internet, no sheet and no MuJoCo.

Run from the repo root:
    python -m unittest discover -s tests -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sim" / "scripts"))

import unittest

import pre_processor as pp


def seg_rows(header, rows):
    return pp.RawTable("bsip", "Sheet One", 14, 1, [header] + rows)


GOOD_HEADER = ["Segment", "mass (kg)", "length (m)", "CoM_x (m)", "CoM_y (m)", "CoM_z (m)",
               "Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]


def good_row(name, mass=2.0, **over):
    v = dict(mass=mass, length=0.4, com_x=0.01, com_y=-0.02, com_z=-0.1,
             ixx=0.10, iyy=0.12, izz=0.05, ixy=0.001, ixz=0.002, iyz=0.003)
    v.update(over)
    return [name] + [v[k] for k in pp.BSIP_COLUMNS]


def full_bsip_table(**per_segment):
    names = {"head_neck": "Head & Neck", "thorax": "Thorax", "abdomen": "Abdomen", "pelvis": "Pelvis",
             "upper_arm": "Upper Arm", "forearm": "Forearm", "hand": "Hand", "thigh": "Thigh",
             "shank": "Shank", "foot": "Foot"}
    return seg_rows(GOOD_HEADER, [good_row(names[s], **per_segment.get(s, {})) for s in pp.EXPECTED_SEGMENTS])


class Helpers(unittest.TestCase):
    def test_ident(self):
        self.assertEqual(pp.ident("Head & Neck"), "head_neck")
        self.assertEqual(pp.ident("  Upper Arm "), "upper_arm")

    def test_column_key_drops_units(self):
        self.assertEqual(pp.column_key("CoM_x (m)"), "com_x")
        self.assertEqual(pp.column_key("mass (kg)"), "mass")
        self.assertEqual(pp.column_key("MuJoCo limit — FINAL (°)"), "mujoco_limit_final")
        self.assertEqual(pp.column_key(None), "")

    def test_fmt_has_no_negative_zero(self):
        self.assertEqual(pp.fmt(-0.0), "0")
        self.assertEqual(pp.fmt(0.1 + 0.2), "0.3")

    def test_to_number(self):
        self.assertEqual(pp.to_number(3), 3.0)
        self.assertIsNone(pp.to_number(""))
        self.assertIsNone(pp.to_number(None))
        for bad in ("#REF!", "abc", float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                pp.to_number(bad)

    def test_cell_references(self):
        t = pp.RawTable("bsip", "MuJoCo Reference", 14, 1, [])
        self.assertEqual(t.ref(0, 0), "'MuJoCo Reference'!A14")
        self.assertEqual(t.ref(6, 6), "'MuJoCo Reference'!G20")
        t = pp.RawTable.from_range("pos", "'MuJoCo Positions '!A4:E14", [])
        self.assertEqual((t.sheet, t.first_row, t.first_col), ("MuJoCo Positions ", 4, 1))
        self.assertEqual(pp.col_letter(27), "AA")


class SegmentTable(unittest.TestCase):
    def test_reads_good_table(self):
        r = pp.Report()
        out = pp.read_segment_table(full_bsip_table(), pp.BSIP_COLUMNS, r)
        self.assertEqual(r.errors, [])
        self.assertEqual(set(out), set(pp.EXPECTED_SEGMENTS))
        self.assertEqual(out["thigh"]["mass"].value, 2.0)

    def test_column_order_does_not_matter(self):
        t = full_bsip_table()
        order = list(range(len(GOOD_HEADER)))[::-1]
        t.rows = [[row[i] for i in order] for row in t.rows]
        r = pp.Report()
        out = pp.read_segment_table(t, pp.BSIP_COLUMNS, r)
        self.assertEqual(r.errors, [])
        self.assertEqual(out["foot"]["com_z"].value, -0.1)

    def test_bad_cell_names_the_cell(self):
        t = full_bsip_table()
        t.rows[4][1] = "#REF!"  # 4th segment row (Pelvis), mass column
        r = pp.Report()
        pp.read_segment_table(t, pp.BSIP_COLUMNS, r)
        self.assertEqual(len(r.errors), 1)
        self.assertIn("B18", r.errors[0])
        self.assertIn("#REF!", r.errors[0])

    def test_sheet_drift_is_reported(self):
        t = full_bsip_table()
        t.rows[1][0] = "Upper Torso"  # Head & Neck renamed
        r = pp.Report()
        pp.read_segment_table(t, pp.BSIP_COLUMNS, r)
        self.assertTrue(any("sheet drift" in e and "head_neck" in e and "upper_torso" in e for e in r.errors))

    def test_duplicate_segment(self):
        t = full_bsip_table()
        t.rows.append(good_row("Thigh"))
        r = pp.Report()
        pp.read_segment_table(t, pp.BSIP_COLUMNS, r)
        self.assertTrue(any("twice" in e for e in r.errors))

    def test_missing_column(self):
        t = full_bsip_table()
        t.rows = [[c for i, c in enumerate(row) if i != 3] for row in t.rows]  # drop CoM_x
        r = pp.Report()
        pp.read_segment_table(t, pp.BSIP_COLUMNS, r)
        self.assertTrue(any("'com_x' not found" in e for e in r.errors))


class PhysicsChecks(unittest.TestCase):
    def check(self, **over):
        r = pp.Report()
        bsip = pp.read_segment_table(full_bsip_table(thigh=over), pp.BSIP_COLUMNS, r)
        pp.check_bsip(bsip, r)
        return r

    def test_good_data_passes(self):
        r = self.check()
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_negative_mass(self):
        self.assertTrue(any("mass must be > 0" in e for e in self.check(mass=-1).errors))

    def test_not_positive_definite(self):
        r = self.check(ixy=0.5)  # product larger than the diagonal can support
        self.assertTrue(any("positive definite" in e for e in r.errors))

    def test_triangle_inequality(self):
        r = self.check(ixx=0.01, iyy=0.01, izz=0.5, ixy=0, ixz=0, iyz=0)
        self.assertTrue(any("triangle inequality" in e for e in r.errors))

    def test_com_outside_segment_warns(self):
        self.assertTrue(any("further than the segment" in w for w in self.check(com_z=-0.9).warnings))


class Mirroring(unittest.TestCase):
    def test_only_y_terms_flip(self):
        r = pp.Report()
        bsip = pp.read_segment_table(full_bsip_table(), pp.BSIP_COLUMNS, r)
        flat = pp.flatten(pp.mirror(bsip, pp.FLIP_BSIP))
        self.assertEqual(flat["thigh_left_com_y"].value, -flat["thigh_right_com_y"].value)
        self.assertEqual(flat["thigh_left_ixy"].value, -flat["thigh_right_ixy"].value)
        self.assertEqual(flat["thigh_left_iyz"].value, -flat["thigh_right_iyz"].value)
        for same in ("mass", "com_x", "com_z", "ixx", "iyy", "izz", "ixz"):
            self.assertEqual(flat[f"thigh_left_{same}"].value, flat[f"thigh_right_{same}"].value)
        self.assertIn("pelvis_mass", flat)  # not bilateral: no suffix
        self.assertNotIn("pelvis_left_mass", flat)


ROM_HEADER = ["Joint", "Movement", "", "Ceiling (°)", "Functional (°)", "Freyja target (°)",
              "MuJoCo limit — FINAL (°)"]


def rom_table(rows):
    return pp.RawTable("rom", "MuJoCo Reference", 70, 1, [ROM_HEADER] + rows)


class RomTable(unittest.TestCase):
    def test_reads_values_and_blanks(self):
        t = rom_table([["Hip", "Flexion", "", 133.8, 67, "", 133.8],
                       ["Hip", "Internal rotation", "", 44.4, "", "", 44.4],
                       ["Lumbosacral", "Flexion", "", "", "", "", ""]])
        r = pp.Report()
        vals, blank = pp.read_rom_table(t, r)
        self.assertEqual(r.errors, [])
        self.assertEqual(vals["hip_flexion"].value, 133.8)
        self.assertIn("hip_internal_rotation", vals)
        self.assertEqual(blank, {"lumbosacral_flexion"})

    def test_negative_rom_is_an_error(self):
        r = pp.Report()
        pp.read_rom_table(rom_table([["Knee", "Extension", "", -1.6, "", "", -1.6]]), r)
        self.assertTrue(any("positive magnitudes" in e for e in r.errors))

    def test_text_in_value_cell(self):
        r = pp.Report()
        pp.read_rom_table(rom_table([["Knee", "Flexion", "", 1, "", "", "TBD"]]), r)
        self.assertTrue(any("'TBD' is not a number" in e for e in r.errors))

    def test_limit_below_functional_demand_warns(self):
        r = pp.Report()
        pp.read_rom_table(rom_table([["Ankle", "Dorsiflexion", "", 13.8, 18, 25, 13.8]]), r)
        self.assertTrue(any("below the functional demand" in w for w in r.warnings))

    def test_text_in_functional_column_is_ignored(self):
        r = pp.Report()
        pp.read_rom_table(rom_table([["Hip", "Extension", "", 18.1, "low", "", 18.1]]), r)
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_duplicate_movement(self):
        r = pp.Report()
        pp.read_rom_table(rom_table([["Hip", "Flexion", "", 1, "", "", 1], ["Hip", "Flexion", "", 2, "", "", 2]]), r)
        self.assertTrue(any("twice" in e for e in r.errors))


class Rendering(unittest.TestCase):
    VALUES = {"a_mass": 2.5, "hip_flexion": 120.0, "hip_extension": 18.1, "zero": -0.0}

    def render(self, text, strict=False, values=None):
        r = pp.Report()
        return pp.render(text, values or self.VALUES, r, strict), r

    def test_both_placeholder_styles(self):
        out, r = self.render('<x m="${a_mass}" n="!{a_mass}"/>')
        self.assertEqual(out, '<x m="2.5" n="2.5"/>')
        self.assertEqual(r.errors, [])

    def test_negation(self):
        out, _ = self.render('<joint range="!{-hip_extension} !{hip_flexion}"/>')
        self.assertEqual(out, '<joint range="-18.1 120"/>')

    def test_negated_zero_prints_as_zero(self):
        out, _ = self.render("!{-zero}")
        self.assertEqual(out, "0")

    def test_unknown_name_is_error_with_suggestion_and_line(self):
        _, r = self.render('<a/>\n<x m="!{a_mas}"/>')
        self.assertEqual(len(r.errors), 1)
        self.assertIn("line 2", r.errors[0])
        self.assertIn("a_mass", r.errors[0])

    def test_empty_placeholder_is_error(self):
        _, r = self.render('<joint range="!{} !{}"/>')
        self.assertEqual(len(r.errors), 2)

    def test_missing_rom_leaves_joint_unlimited(self):
        out, r = self.render('<joint name="s" type="hinge" limited="true" range="!{-shoulder_abduction} !{hip_flexion}"/> <!--aa-->')
        self.assertEqual(r.errors, [])
        self.assertNotIn("range=", out)
        self.assertNotIn('limited="', out)
        self.assertIn("FIXME(pre_processor)", out)
        self.assertIn("<!--aa-->", out)  # the user's own comment survives
        self.assertEqual(len(r.warnings), 1)

    def test_strict_makes_missing_rom_an_error(self):
        _, r = self.render('<joint name="s" range="!{-shoulder_abduction} !{hip_flexion}"/>', strict=True)
        self.assertEqual(len(r.errors), 1)

    def test_missing_value_outside_a_range_is_always_an_error(self):
        _, r = self.render('<body pos="!{nowhere_pos_x} 0 0"/>')
        self.assertEqual(len(r.errors), 1)

    def test_banner_goes_after_xml_declaration(self):
        out = pp.add_banner('<?xml version="1.0"?>\n<mujoco/>')
        self.assertTrue(out.startswith('<?xml'))
        self.assertLess(out.index("?>"), out.index("GENERATED"))
        self.assertNotIn("--", out.split("GENERATED")[1].split("-->")[0])


class XmlChecks(unittest.TestCase):
    def test_bad_range_order(self):
        r = pp.Report()
        pp.check_xml('<mujoco><joint name="j" range="10 -10"/></mujoco>', r)
        self.assertTrue(any("not below max" in e for e in r.errors))

    def test_range_excluding_zero_warns(self):
        r = pp.Report()
        pp.check_xml('<mujoco><joint name="j" range="5 10"/></mujoco>', r)
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)

    def test_malformed_xml(self):
        r = pp.Report()
        pp.check_xml("<mujoco><body></mujoco>", r)
        self.assertTrue(any("not well-formed" in e for e in r.errors))


class Positions(unittest.TestCase):
    def values(self, **over):
        v = {"pelvis_pos_z": 0.96, "thigh_right_pos_z": -0.09, "shank_right_pos_z": -0.40,
             "foot_right_pos_z": -0.41, "thigh_right_length": 0.40, "shank_right_length": 0.41,
             "thigh_right_pos_y": -0.09, "upper_arm_right_pos_y": -0.19}
        v.update(over)
        return {k: pp.Param(x, "t") for k, x in v.items()}

    def test_good(self):
        r = pp.Report()
        ankle = pp.check_positions(self.values(), r)
        self.assertAlmostEqual(ankle, 0.06)
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_ankle_below_floor(self):
        r = pp.Report()
        pp.check_positions(self.values(pelvis_pos_z=0.5), r)
        self.assertTrue(any("BELOW the floor" in e for e in r.errors))

    def test_chain_length_mismatch_warns(self):
        r = pp.Report()
        pp.check_positions(self.values(shank_right_pos_z=-0.30), r)
        self.assertTrue(any("shank_right sits" in w for w in r.warnings))

    def test_right_side_y_sign(self):
        r = pp.Report()
        pp.check_positions(self.values(thigh_right_pos_y=0.09), r)
        self.assertTrue(any("NEGATIVE y" in w for w in r.warnings))


class Unused(unittest.TestCase):
    def test_flags_unused_pos_and_rom_but_not_bsip_or_zero(self):
        vals = {"a_length": pp.Param(1, "x", "bsip"), "b_pos_z": pp.Param(0.2, "x", "pos"),
                "c_pos_z": pp.Param(0.0, "x", "pos"), "hip_flexion": pp.Param(5, "x", "rom"),
                "used_pos_z": pp.Param(0.3, "x", "pos")}
        r = pp.Report()
        pp.warn_unused("!{used_pos_z}", vals, r)
        flagged = " ".join(r.warnings)
        self.assertIn("b_pos_z", flagged)
        self.assertIn("hip_flexion", flagged)
        self.assertNotIn("a_length", flagged)
        self.assertNotIn("c_pos_z", flagged)
        self.assertNotIn("used_pos_z", flagged)


if __name__ == "__main__":
    unittest.main()
