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
sys.path.insert(0, str(REPO / "checks"))
sys.path.insert(0, str(REPO / "tests"))

import pre_processor as pp

TEMPLATE = REPO / "sim" / "models" / "freyja_template.xml"
SNAPSHOT = REPO / "params" / "snapshot.csv"
DESIGN_COMMENT = "design choice, no sheet source"
MATCH_TOL = 1e-4  # m: closer than this to a snapshot value (or its negation) means it is a copy

PLACEHOLDER = re.compile(r"[$!]\{[^}]*\}")
GEOM_TAG = re.compile(r"<geom\b[^<>]*>")
GEOM_ATTR = re.compile(r'\b(pos|fromto|size)="([^"]*)"')


def snapshot_values():
    """The committed snapshot as the sheet will make it once it carries the design range and ADR 0038's scaling (tests/foot_help.py): the template needs both."""
    import foot_help as fh
    return fh.scaled_snapshot_values()


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


DESIGN_LENGTHS = ("foot_heel_behind_ankle", "foot_length_total", "foot_ball_length", "toe_hinge_ahead_ankle", "toe_tip_ahead_ankle", "foot_half_width", "toe_height")


def scaled(values, factor):
    """Stature scaled: every length, position and centre of mass scales by the factor, every inertia by its square (the toe's geometry from the design range
    with the lengths), ROM, masses and fractions stay."""
    out = {}
    for k, v in values.items():
        if k.endswith(("_length", "_pos_x", "_pos_y", "_pos_z", "_jpos_z", "_com_x", "_com_y", "_com_z")) or k in DESIGN_LENGTHS:
            out[k] = v * factor
        elif k.endswith(("_ixx", "_iyy", "_izz", "_ixy", "_ixz", "_iyz")):
            out[k] = v * factor * factor
        else:
            out[k] = v
    return out


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
    def test_capsule_tips_touch_both_joints(self):
        # a capsule's end spheres stick out by one radius: centres go in by that much
        d = pp.derive_keys({"thigh_right_length": 0.4})
        r = d["thigh_right_radius"]
        self.assertAlmostEqual(d["thigh_right_cap_top_z"], -r)
        self.assertAlmostEqual(d["thigh_right_cap_bot_z"], -(0.4 - r))
        for seg in ("shank", "upper_arm", "forearm"):
            self.assertIn(f"{seg}_left_cap_bot_z", pp.derive_keys({f"{seg}_left_length": 0.3}))

    def test_foot_box_runs_from_the_heel_to_the_toe_hinge_and_down_to_the_floor(self):
        """The foot's box comes from the design range (heel, toe hinge, half width) and the ankle height from the position chain, not from the foot length."""
        import foot_help as fh
        v = fh.snapshot_values()
        design = {pp.DESIGN_KEYS[k][0]: x * pp.DESIGN_KEYS[k][1] for k, x in fh.SPEC_DESIGN.items()}
        # the ankle height is set by the chain (pelvis + thigh + shank + foot positions): 0.05 m here
        v.update({"pelvis_pos_z": 0.9, "thigh_right_pos_z": -0.1, "shank_right_pos_z": -0.4, "foot_right_pos_z": -0.35, **design})
        d = pp.derive_keys(v)
        heel, hinge = design["foot_heel_behind_ankle"], design["toe_hinge_ahead_ankle"]
        self.assertAlmostEqual(d["foot_right_box_pos_x"] - d["foot_right_box_half_x"], -heel, delta=1e-12)  # rear face
        self.assertAlmostEqual(d["foot_right_box_pos_x"] + d["foot_right_box_half_x"], hinge, delta=1e-12)  # front face is the toe hinge
        self.assertAlmostEqual(d["foot_right_box_half_y"], design["foot_half_width"])
        self.assertAlmostEqual(d["foot_right_box_half_z"], 0.025)  # ankle 0.05 above the floor
        self.assertAlmostEqual(d["foot_right_box_pos_z"], -0.025)
        self.assertAlmostEqual(d["foot_right_sole_z"], -0.05)  # site_sole: minus the ankle height
        self.assertAlmostEqual(d["toe_right_pos_z"], -0.05 + design["toe_height"] / 2)  # the hinge axis at the mid-height of the toe box
        self.assertNotIn("foot_left_box_half_z", pp.derive_keys({k: x for k, x in v.items() if not k.startswith("foot_left_") and k != "shank_left_pos_z"}))
        self.assertNotIn("foot_right_box_pos_x", pp.derive_keys({k: x for k, x in v.items() if k not in design}))  # no design range, no foot box

    def test_head_top_is_the_vertex(self):
        d = pp.derive_keys({"head_neck_length": 0.27})
        self.assertAlmostEqual(d["head_neck_head_z"] + d["head_neck_head_half_z"], 0.27)

    def test_upper_body_keys_follow_the_thorax_length_and_shoulders(self):
        d = pp.derive_keys({"thorax_length": 0.3})
        self.assertAlmostEqual(d["thorax_chest_z"], -0.3 * pp.CHEST_Z_FRACTION)
        self.assertAlmostEqual(d["thorax_chest_half_z"], 0.3 * pp.CHEST_HALF_FRACTION)
        self.assertLess(d["thorax_chest_z"] + d["thorax_chest_half_z"], 0.0)  # chest stays inside the top joint
        self.assertAlmostEqual(d["trapezius_start_z"], -d["trapezius_radius"])  # tip at the neck base

    def test_hanging_segments_are_centred_between_their_joints(self):
        d = pp.derive_keys({"thorax_length": 0.3, "hand_left_length": 0.08, "abdomen_length": 0.1})
        self.assertAlmostEqual(d["thorax_mid_z"], -0.15)
        self.assertAlmostEqual(d["thorax_half_z"], 0.15)
        self.assertAlmostEqual(d["hand_left_mid_z"], -0.04)
        self.assertGreater(d["abdomen_half_z"], 0.05)  # abdomen and pelvis overlap their neighbours

    def test_missing_inputs_give_no_key(self):
        self.assertEqual(pp.derive_keys({}), {})

    def test_derived_names_never_clash_with_sheet_names(self):
        every = {f"{s}_{side}_length": 1.0 for s in pp.BILATERAL for side in ("right", "left")}
        every.update({f"{s}_length": 1.0 for s in ("abdomen", "thorax", "head_neck", "pelvis")})
        self.assertFalse(set(pp.derive_keys(every)) & set(snapshot_values()))


def model_xml(values):
    return ET.fromstring(render_geoms(values))


def body(root, name):
    return next(b for b in root.iter("body") if b.get("name") == name)


class Geometry(unittest.TestCase):
    """The rendered model, against the sheet. Run at the sheet's values and at stature x 1.05."""
    FACTORS = (1.0, 1.05)

    def values(self, f):
        return scaled(snapshot_values(), f)

    def test_limb_capsules_run_exactly_joint_to_joint(self):
        for f in self.FACTORS:
            v, root = self.values(f), model_xml(self.values(f))
            for seg in ("thigh", "shank", "upper_arm", "forearm"):
                for side in ("right", "left"):
                    cap = next(g for g in body(root, f"{seg}_{side}").findall("geom") if g.get("type") == "capsule")
                    z1, z2 = floats(cap.get("fromto"))[2], floats(cap.get("fromto"))[5]
                    r = floats(cap.get("size"))[0]
                    self.assertAlmostEqual(z1 + r, 0.0, places=9, msg=f"{seg} {side} top tip")
                    self.assertAlmostEqual(z2 - r, -v[f"{seg}_{side}_length"], places=9, msg=f"{seg} {side} bottom tip")

    def test_knee_sphere_is_centred_on_the_knee(self):
        root = model_xml(self.values(1.0))
        for side in ("right", "left"):
            sph = next(g for g in body(root, f"shank_{side}").findall("geom") if g.get("type") == "sphere")
            self.assertEqual(floats(sph.get("pos")), [0.0, 0.0, 0.0])

    def test_head_top_is_at_the_vertex(self):
        for f in self.FACTORS:
            v, root = self.values(f), model_xml(self.values(f))
            head = next(g for g in body(root, "head_and_neck").findall("geom") if g.get("type") == "ellipsoid")
            self.assertAlmostEqual(floats(head.get("pos"))[2] + floats(head.get("size"))[2], v["head_neck_length"], places=9)

    def test_neck_starts_at_the_cervical_joint(self):
        root = model_xml(self.values(1.0))
        neck = next(g for g in body(root, "head_and_neck").findall("geom") if g.get("type") == "capsule")
        self.assertAlmostEqual(floats(neck.get("fromto"))[2] - floats(neck.get("size"))[0], 0.0, places=9)

    def test_shoulder_girdle_and_trapezius_end_at_the_shoulder_joint_centres(self):
        for f in self.FACTORS:
            v, root = self.values(f), model_xml(self.values(f))
            caps = [floats(g.get("fromto")) for g in body(root, "thorax").findall("geom") if g.get("type") == "capsule"]
            sh = {side: [v[f"upper_arm_{side}_pos_{a}"] for a in "xyz"] for side in ("right", "left")}
            girdle = next(c for c in caps if c[1] != c[4])
            for got, want in zip(girdle, sh["right"] + sh["left"]):
                self.assertAlmostEqual(got, want, places=9)
            traps = [c for c in caps if c is not girdle]
            self.assertEqual(len(traps), 2)
            for c in traps:
                self.assertEqual(c[:2], [0.0, 0.0])
                self.assertIn([round(x, 9) for x in c[3:]], [[round(x, 9) for x in sh[sd]] for sd in sh])

    def test_pelvis_spans_the_hip_joint_centres(self):
        v, root = snapshot_values(), model_xml(snapshot_values())
        g = floats(body(root, "pelvis").find("geom[@type='capsule']").get("fromto"))
        self.assertAlmostEqual(g[1], v["thigh_right_pos_y"], places=9)
        self.assertAlmostEqual(g[4], v["thigh_left_pos_y"], places=9)
        self.assertAlmostEqual(g[0], v["thigh_right_pos_x"], places=9)
        self.assertAlmostEqual(g[2], v["thigh_right_pos_z"], places=9)

    def test_hanging_segments_cover_their_full_length(self):
        # thorax and hands end exactly at their joints; abdomen and pelvis may overlap the
        # neighbours (so the silhouette has no pinch) but never fall short
        for f in self.FACTORS:
            v, root = self.values(f), model_xml(self.values(f))
            for name, key, exact in (("abdomen", "abdomen_length", False), ("pelvis", "pelvis_length", False),
                                     ("thorax", "thorax_length", True), ("hand_right", "hand_right_length", True),
                                     ("hand_left", "hand_left_length", True)):
                e = body(root, name).find("geom[@type='ellipsoid']")
                zc, hz = floats(e.get("pos"))[2], floats(e.get("size"))[2]
                top, bot = zc + hz, zc - hz
                if exact:
                    self.assertAlmostEqual(top, 0.0, places=9, msg=name)
                    self.assertAlmostEqual(bot, -v[key], places=9, msg=name)
                else:
                    self.assertGreaterEqual(top, -1e-12, msg=name)
                    self.assertLessEqual(bot, -v[key] + 1e-12, msg=name)

    def test_chest_sits_inside_the_thorax_below_the_neck(self):
        v, root = snapshot_values(), model_xml(snapshot_values())
        ell = [g for g in body(root, "thorax").findall("geom") if g.get("type") == "ellipsoid"]
        self.assertEqual(len(ell), 2)
        chest = max(ell, key=lambda g: floats(g.get("size"))[1])  # the wider one
        zc, hz = floats(chest.get("pos"))[2], floats(chest.get("size"))[2]
        self.assertLess(zc + hz, 0.0)
        self.assertGreater(zc - hz, -v["thorax_length"])

    def test_foot_box_follows_foot_length(self):
        base, big = model_xml(self.values(1.0)), model_xml(self.values(1.05))
        for side in ("right", "left"):
            b, g = body(base, f"foot_{side}").find("geom"), body(big, f"foot_{side}").find("geom")
            self.assertAlmostEqual(floats(g.get("size"))[0], floats(b.get("size"))[0] * 1.05, places=9)
            self.assertAlmostEqual(floats(g.get("pos"))[0], floats(b.get("pos"))[0] * 1.05, places=9)


class FootBoxOnTheRealModel(unittest.TestCase):
    """The committed model: the foot's box runs from the design heel to the design toe hinge (before the sheet carried the design range, from a quarter of the
    sheet's foot length behind the ankle to the whole length ahead of it), and the sole stays on the floor."""

    def test_edges_sole_and_floor_contact(self):
        import mujoco
        import checklib
        import mjcf_checks  # noqa: F401
        ctx = checklib.Context.from_files()
        m, d = ctx.model, ctx.data
        snap = ctx.snapshot
        if "toe_hinge_ahead_ankle" in snap:
            rear, front = -snap["foot_heel_behind_ankle"], snap["toe_hinge_ahead_ankle"]
        else:  # the model of the Stage 2 snapshot, which has no toe
            rear, front = -snap["foot_right_length"] / 4, snap["foot_right_length"]
        for side in ("right", "left"):
            b = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"foot_{side}")
            g = next(g for g in range(m.ngeom) if m.geom_bodyid[g] == b)
            x0, half = d.geom_xpos[g][0] - d.xpos[b][0], m.geom_size[g][0]
            self.assertAlmostEqual(x0 - half, rear, delta=1e-9)
            self.assertAlmostEqual(x0 + half, front, delta=1e-9)
            self.assertAlmostEqual(d.geom_xpos[g][2] - m.geom_size[g][2], 0.0, delta=1e-9)  # sole at z = 0
        (r,) = [x for x in checklib.call(checklib.REGISTRY["check.mjcf.floor_contact"], ctx)]
        self.assertEqual(r.status, checklib.PASS, r.message)


class NeutralPose(unittest.TestCase):
    def setUp(self):
        try:
            import mujoco
        except ImportError:
            self.skipTest("mujoco not installed")
        self.mj = mujoco

    def pose(self, f):
        model = self.mj.MjModel.from_xml_string(render_geoms(scaled(snapshot_values(), f)))
        data = self.mj.MjData(model)
        self.mj.mj_forward(model, data)
        return model, data

    def test_soles_stand_on_the_floor_at_every_scale(self):
        for f in (1.0, 1.05):
            model, data = self.pose(f)
            lows = []
            for side in ("right", "left"):
                gid = model.geom(model.body(f"foot_{side}").geomadr[0]).id
                lows.append(data.geom_xpos[gid][2] - model.geom_size[gid][2])  # box, identity orientation at neutral
            for low in lows:
                self.assertAlmostEqual(low, 0.0, places=9)

    def test_no_contact_between_body_parts_at_neutral(self):
        model, data = self.pose(1.0)
        floor = model.geom("floor").id
        pairs = [(self.mj.mj_id2name(model, self.mj.mjtObj.mjOBJ_BODY, model.geom_bodyid[a]),
                  self.mj.mj_id2name(model, self.mj.mjtObj.mjOBJ_BODY, model.geom_bodyid[b]))
                 for a, b in zip(data.contact.geom1, data.contact.geom2) if floor not in (a, b)]
        self.assertEqual(pairs, [])

    def test_scaled_model_compiles(self):
        self.pose(1.05)

    def test_sites_mark_the_vertex_and_the_soles(self):
        for f in (1.0, 1.05):
            v = scaled(snapshot_values(), f)
            model, data = self.pose(f)
            vertex = data.site_xpos[model.site("site_vertex").id]
            cervical = data.xpos[model.body("head_and_neck").id]
            self.assertAlmostEqual(vertex[2] - cervical[2], v["head_neck_length"], places=9)  # CJC + head_neck_length
            for side in ("right", "left"):
                sole = data.site_xpos[model.site(f"site_sole_{side}").id]
                self.assertAlmostEqual(sole[2], 0.0, places=9)  # AJC minus the ankle height is the floor


if __name__ == "__main__":
    unittest.main()
