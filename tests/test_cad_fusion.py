"""
Stage 3b: the tests that need Joe's live Fusion with its MCP server and the scratch fixture document `freyja-bridge-fixture` open and active. Marked `fusion` and
deselected by default (tests/conftest.py); run them with

    python -m pytest tests/test_cad_fusion.py --fusion

T3 (gate G2): every user parameter survives set-by-expression and read-back; the fixture's mass properties meet their closed forms.
T4 (gates G3 and G4): see the second half of the file.

Every test leaves the fixture as it found it: the module fixture captures the user parameters before the first test and restores them after the last.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import binding as cb  # noqa: E402
from cad import frames, massprops, transport, units  # noqa: E402
from thread import addr  # noqa: E402

pytestmark = pytest.mark.fusion

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cad"
BINDING = cb.load(FIXTURE_DIR / "part.fixture.bridge.yaml")
NAME = BINDING["document"]["name"]
ROUND_TRIP_REL = 1e-9       # gate G2
MASS_REL, COM_MM, PRINCIPAL_REL = 1e-3, 0.01, 5e-3   # gate G2
RHO = 2.7e-6                # kg/mm^3
OD, WALL, L = 30.0, 2.0, 300.0
COMMITTED = {"in_fixture_length": "300 mm", "dv_fx_od": "30 mm", "dv_fx_wall": "2 mm", "dr_fx_id": "dv_fx_od - 2 * dv_fx_wall", "dv_fx_ratio": "3", "dv_fx_angle": "30 deg"}


@pytest.fixture(scope="module")
def fx():
    try:
        s = transport.Session().open()
        info = transport.call("doc_info", {"expect_name": NAME}, session=s)
    except transport.FusionError as e:
        pytest.skip(f"Fusion or the fixture document is not available: {e}")
    s.start = transport.call("capture", {"expect_name": NAME}, session=s)["expressions"]
    assert s.start == COMMITTED, "the fixture is not in its committed state; restore it before running"
    yield s
    transport.call("restore", {"expect_name": NAME, "expressions": s.start}, session=s)


@pytest.fixture(autouse=True)
def committed_state(request):
    """Every test starts from, and leaves, the fixture's committed parameter state."""
    if "fx" in request.fixturenames:
        fx = request.getfixturevalue("fx")
        transport.call("restore", {"expect_name": NAME, "expressions": fx.start}, session=fx)
        yield
        transport.call("restore", {"expect_name": NAME, "expressions": fx.start}, session=fx)
    else:
        yield


def call(fx, verb, **args):
    return transport.call(verb, {"expect_name": NAME, **args}, session=fx)


def params(fx):
    return {p["name"]: p for p in call(fx, "read_params")["parameters"]}


def test_g1_the_server_lists_its_tools_and_runs_a_verb_of_the_module(fx):
    names = {t["name"] for t in fx.tools()}
    assert {"fusion_mcp_execute", "fusion_mcp_read", "fusion_mcp_update"} <= names
    info = call(fx, "doc_info")
    assert info["name"] == NAME and info["parametric"] and info["length_units"] == "mm"
    assert info["id"] == BINDING["document"]["id"]


def test_a_verb_refuses_another_document(fx):
    with pytest.raises(transport.FusionError, match="not 'some-other-document'"):
        transport.call("read_params", {"expect_name": "some-other-document"}, session=fx)


def test_the_fixture_parameters_match_its_binding(fx):
    from cad import params as cparams
    assert cparams.check_document(BINDING, call(fx, "read_params")["parameters"]) == []


AWKWARD = [
    ("in_fixture_length", "mm", [312.4, 255.234699434, 0.123456789012, 1234.56789012345]),
    ("dv_fx_od", "mm", [30.000000001, 45.5, 27.123456789]),
    ("dv_fx_wall", "mm", [1.9999999, 2.5, 0.75]),
    ("dv_fx_angle", "deg", [62.000000001, 12.3456789, 89.999999, 0.5]),
    ("dv_fx_ratio", "unitless", [3.14159265358979, 2.0, 5.5]),
]


@pytest.mark.parametrize("name,unit,values", AWKWARD, ids=[a[0] for a in AWKWARD])
def test_g2_a_parameter_survives_set_by_expression_and_read_back(fx, name, unit, values):
    for v in values:
        expr = units.format_expression(v, unit)
        r = call(fx, "set_expressions", expressions={name: expr}, allowed_prefixes=["in_", "dv_"])
        assert r["ok"], r
        p = params(fx)[name]
        assert p["expression"] == expr
        got = units.fusion_value_to_unit(p["value"], unit)
        assert got == pytest.approx(v, rel=ROUND_TRIP_REL), (name, expr, got)


def test_g2_the_derived_parameter_follows_its_inputs(fx):
    call(fx, "set_expressions", expressions={"dv_fx_od": "41.5 mm", "dv_fx_wall": "3.25 mm"}, allowed_prefixes=["dv_"])
    p = params(fx)["dr_fx_id"]
    assert units.fusion_value_to_unit(p["value"], "mm") == pytest.approx(41.5 - 2 * 3.25, rel=ROUND_TRIP_REL)
    assert p["expression"] == "dv_fx_od - 2 * dv_fx_wall"


def test_the_bridge_refuses_to_set_a_derived_or_foreign_or_unallowed_parameter(fx):
    before = params(fx)
    for name, allowed in (("dr_fx_id", ["in_", "dv_", "dr_"]), ("no_such", ["in_"]), ("dv_fx_od", ["in_"])):
        r = call(fx, "set_expressions", expressions={name: "10 mm"}, allowed_prefixes=allowed)
        assert not r["ok"] and r["refused"], name
    assert {k: v["expression"] for k, v in params(fx).items()} == {k: v["expression"] for k, v in before.items()}


def test_g2_the_fixture_mass_properties_meet_the_closed_form_of_the_tube(fx):
    raw = call(fx, "physical_properties", body="tube", accuracy="veryhigh")
    mp = massprops.mass_properties(raw)
    ro, ri = OD / 2, OD / 2 - WALL
    m = RHO * math.pi * (ro**2 - ri**2) * L
    iz = m * (ro**2 + ri**2) / 2
    it = m * (3 * (ro**2 + ri**2) + L**2) / 12
    assert mp["mass_kg"] == pytest.approx(m, rel=MASS_REL)
    assert np.allclose(mp["com_mm"], (0.0, 0.0, -L / 2), atol=COM_MM)
    got = np.sort(frames.principal_moments(frames.to_matrix(mp["inertia_kgmm2"])))
    assert got == pytest.approx(np.sort([it, it, iz]), rel=PRINCIPAL_REL)


def test_g2_the_marker_sits_on_the_isb_point_and_lands_on_the_model_axis(fx):
    # gate G7 in the fixture: the marker at ISB (0, -L, 0) is at model (0, 0, -L)
    raw = call(fx, "physical_properties", body="marker", accuracy="veryhigh")
    isb = [units.fusion_length_to_mm(c) for c in raw["com_cm"]]
    assert np.allclose(isb, (0.0, -L, 0.0), atol=COM_MM)
    assert np.allclose(frames.points_to_model([isb], "right")[0], (0.0, 0.0, -L), atol=COM_MM)
    assert np.allclose(massprops.mass_properties(raw)["com_mm"], (0.0, 0.0, -L), atol=COM_MM)


def test_a_read_only_verb_cannot_modify_the_document(fx):
    # Fusion enforces readOnly: the same module function run as a read-only script is refused when it writes
    script = transport.build_script("set_expressions", {"expect_name": NAME, "expressions": {"dv_fx_od": "31 mm"}, "allowed_prefixes": ["dv_"]})
    before = params(fx)["dv_fx_od"]["expression"]
    try:
        out = fx.script(script, read_only=True)
        result = transport.parse_output(out)
        assert not result["ok"] or params(fx)["dv_fx_od"]["expression"] == before
    except transport.FusionError:
        pass
    assert params(fx)["dv_fx_od"]["expression"] == before


# ---- T4: safe edits and drift (gates G3 and G4) -----------------------------------------------------------------------------------------

import json  # noqa: E402

SNAPSHOT = json.loads((FIXTURE_DIR / "fixture_snapshot.json").read_text(encoding="utf-8"))


def resolve(address):
    source, pointer = addr.parse(address)
    return addr.pointer_get(SNAPSHOT, pointer) if source == "snapshot" else (False, None)


def expressions(fx):
    return {k: v["expression"] for k, v in params(fx).items()}


@pytest.mark.parametrize("wall", ["15 mm", "16 mm"], ids=["wall-equals-outer-radius", "wall-above-outer-radius"])
def test_g3_a_breaking_edit_is_reported_with_the_failed_features_and_rolled_back(fx, wall):
    before = expressions(fx)
    assert call(fx, "timeline_health")["healthy"]
    r = call(fx, "set_expressions", expressions={"dv_fx_wall": wall}, allowed_prefixes=["dv_"])
    assert r["ok"] is False and r["rolled_back"] is True
    assert r["failed_features"] == ["marker fillet"], r["failed_features"]
    assert r["failure_messages"] and "illet" in r["failure_messages"][0]       # Fusion's own text: "could not be created" (zero) or "negative value"
    assert r["rollback"]["equal"] is True and r["rollback"]["differing"] == []
    after = expressions(fx)
    assert after == before                                  # character for character
    assert all(after[k] == before[k] for k in before) and set(after) == set(before)
    health = call(fx, "timeline_health")
    assert health["healthy"] and health["failed_features"] == []


def test_g3_without_rollback_the_failure_is_reported_and_restore_repairs_it(fx):
    before = expressions(fx)
    r = call(fx, "set_expressions", expressions={"dv_fx_wall": "15 mm"}, allowed_prefixes=["dv_"], rollback_on_failure=False)
    assert not r["ok"] and r["failed_features"] == ["marker fillet"] and not r["rolled_back"]
    assert not call(fx, "timeline_health")["healthy"]
    rr = call(fx, "restore", expressions=before)
    assert rr["equal"] and rr["health"]["healthy"]
    assert expressions(fx) == before


def test_g3_a_good_edit_is_kept(fx):
    r = call(fx, "set_expressions", expressions={"dv_fx_wall": "2.5 mm"}, allowed_prefixes=["dv_"])
    assert r["ok"] and not r["rolled_back"] and r["failed_features"] == []
    assert params(fx)["dv_fx_wall"]["expression"] == "2.5 mm"


def push(fx):
    rows = cb.resolve_inherited(BINDING, resolve)
    return call(fx, "set_expressions", expressions={r["name"]: r["expression"] for r in rows}, allowed_prefixes=["in_"])


def drift(fx):
    return cd.check(BINDING, call(fx, "read_params")["parameters"], resolve)


from cad import drift as cd  # noqa: E402


def test_g4_every_inherited_value_comes_from_its_address_and_a_clean_document_has_no_drift(fx):
    assert push(fx)["ok"]
    assert drift(fx) == []
    p = params(fx)["in_fixture_length"]
    assert units.fusion_value_to_unit(p["value"], "mm") == pytest.approx(SNAPSHOT["fixture_length"] * 1000, rel=ROUND_TRIP_REL)


def test_g4_mutation_changing_an_inherited_parameter_in_fusion_is_drift_until_pushed(fx):
    assert push(fx)["ok"] and drift(fx) == []
    call(fx, "set_expressions", expressions={"in_fixture_length": "310 mm"}, allowed_prefixes=["in_"])      # a hand edit in Fusion
    d = drift(fx)
    assert [x["name"] for x in d] == ["in_fixture_length"]
    assert d[0]["fusion_value"] == pytest.approx(310.0) and d[0]["address_value"] == pytest.approx(300.0)
    assert push(fx)["ok"]
    assert drift(fx) == []


def test_g4_an_unprefixed_user_parameter_fails_validation_and_is_removed(fx):
    from cad import params as cparams
    transport.call("add_user_parameter", {"name": "stray", "expression": "5 mm", "unit": "mm"}, session=fx, module="fixture_builder")
    try:
        problems = cparams.check_document(BINDING, call(fx, "read_params")["parameters"])
        assert any("stray" in p and "prefix" in p for p in problems), problems
    finally:
        transport.call("remove_user_parameter", {"name": "stray"}, session=fx, module="fixture_builder")
    assert cparams.check_document(BINDING, call(fx, "read_params")["parameters"]) == []


def test_g4_an_extra_prefixed_parameter_and_a_missing_one_are_also_validation_errors(fx):
    from cad import params as cparams
    transport.call("add_user_parameter", {"name": "dv_extra", "expression": "5 mm", "unit": "mm"}, session=fx, module="fixture_builder")
    try:
        problems = cparams.check_document(BINDING, call(fx, "read_params")["parameters"])
        assert any("dv_extra" in p and "not in the binding" in p for p in problems), problems
    finally:
        transport.call("remove_user_parameter", {"name": "dv_extra"}, session=fx, module="fixture_builder")
    raw = [p for p in call(fx, "read_params")["parameters"] if p["name"] != "dv_fx_od"]
    assert any("dv_fx_od" in p and "missing" in p for p in cparams.check_document(BINDING, raw))


def test_the_fixture_is_in_its_committed_state_at_the_end(fx):
    assert expressions(fx) == COMMITTED
    assert call(fx, "timeline_health")["healthy"]
