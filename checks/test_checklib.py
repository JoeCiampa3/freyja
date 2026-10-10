"""The machinery behind the checks: registry, tiers and waivers (CONVENTIONS section 7). No model needed."""
import datetime as dt

import pytest

import checklib as cl

TODAY = dt.date(2026, 10, 10)


def fake_registry(**statuses):
    """One check per keyword: id 'check.fake.<name>', status as given, tier gate or advisory by name."""
    reg = {}
    for name, status in statuses.items():
        tier = "advisory" if name.startswith("adv") else "gate"
        cid = f"check.fake.{name}"
        reg[cid] = cl.CheckSpec(cid, tier, (lambda ctx, cid=cid, tier=tier, status=status:
                                            cl.Result(cid, tier, status, "msg")))
    return reg


def waiver(check, confirmed=True, review_by="2027-01-10"):
    return cl.Waiver(check=f"check.fake.{check}", reason="why", source="docs/memos/memo1b.md",
                     recorded=dt.date(2026, 10, 10), review_by=dt.date.fromisoformat(review_by), confirmed=confirmed)


@pytest.mark.check("check.infra.registry", tier="gate")
def test_run_checks_filters_by_tier_and_reports_blocking():
    reg = fake_registry(a=cl.PASS, b=cl.FAIL, adv_c=cl.FAIL)
    rep = cl.run_checks(None, registry=reg, today=TODAY)
    assert [r.id for r in rep.blocking] == ["check.fake.b"]  # only a failing gate blocks
    assert {r.id for r in cl.run_checks(None, tier="advisory", registry=reg, today=TODAY).results} == {"check.fake.adv_c"}
    assert {r.id for r in cl.run_checks(None, tier="gate", registry=reg, today=TODAY).results} == {"check.fake.a", "check.fake.b"}


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_confirmed_waiver_turns_a_failure_into_waived_and_unblocks():
    rep = cl.run_checks(None, registry=fake_registry(b=cl.FAIL), waivers=[waiver("b")], today=TODAY)
    assert [r.status for r in rep.results] == [cl.WAIVED]
    assert rep.blocking == [] and rep.warnings == []
    assert "why" in rep.results[0].message


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_unconfirmed_waiver_does_not_waive():
    rep = cl.run_checks(None, registry=fake_registry(b=cl.FAIL), waivers=[waiver("b", confirmed=False)], today=TODAY)
    assert [r.status for r in rep.results] == [cl.FAIL]
    assert any("not confirmed" in w for w in rep.warnings)


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_waiver_on_a_passing_check_warns():
    rep = cl.run_checks(None, registry=fake_registry(a=cl.PASS), waivers=[waiver("a")], today=TODAY)
    assert [r.status for r in rep.results] == [cl.PASS]
    assert any("passes" in w and "check.fake.a" in w for w in rep.warnings)


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_waiver_on_a_skipped_check_is_quiet():
    rep = cl.run_checks(None, registry=fake_registry(a=cl.SKIP), waivers=[waiver("a")], today=TODAY)
    assert rep.warnings == []


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_waiver_for_an_unknown_check_and_an_overdue_review_warn():
    rep = cl.run_checks(None, registry=fake_registry(b=cl.FAIL),
                        waivers=[waiver("nope"), waiver("b", review_by="2026-01-01")], today=TODAY)
    assert any("unknown check" in w for w in rep.warnings)
    assert any("review" in w and "check.fake.b" in w for w in rep.warnings)
    assert rep.results[0].status == cl.WAIVED  # an overdue waiver still waives, loudly


@pytest.mark.check("check.infra.waivers", tier="gate")
def test_waivers_file_parses_and_needs_every_field(tmp_path):
    good = ("- check: check.fake.a\n  reason: r\n  source: s\n  recorded: 2026-10-10\n"
            "  review_by: 2027-01-10\n  confirmed: true\n")
    (tmp_path / "w.yaml").write_text(good, encoding="utf-8")
    (w,) = cl.load_waivers(tmp_path / "w.yaml")
    assert w.check == "check.fake.a" and w.confirmed and w.review_by == dt.date(2027, 1, 10)
    (tmp_path / "bad.yaml").write_text("- check: check.fake.a\n  reason: r\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        cl.load_waivers(tmp_path / "bad.yaml")
    (tmp_path / "empty.yaml").write_text("", encoding="utf-8")
    assert cl.load_waivers(tmp_path / "empty.yaml") == []


@pytest.mark.check("check.infra.registry", tier="gate")
def test_a_check_that_raises_is_a_failure_not_a_crash():
    def boom(ctx):
        raise RuntimeError("kaboom")
    reg = {"check.fake.boom": cl.CheckSpec("check.fake.boom", "gate", boom)}
    rep = cl.run_checks(None, registry=reg, today=TODAY)
    assert rep.results[0].status == cl.FAIL and "kaboom" in rep.results[0].message
    assert rep.blocking


@pytest.mark.check("check.infra.registry", tier="gate")
def test_report_json_is_plain_data():
    import json
    rep = cl.run_checks(None, registry=fake_registry(a=cl.PASS, adv_b=cl.FAIL), today=TODAY)
    data = json.loads(rep.to_json())
    assert data["results"][0]["id"] == "check.fake.a" and set(data) == {"results", "warnings"}
