"""
Check machinery (CONVENTIONS section 7): the registry, the model context, waivers and the runner.

A check is a function  fn(ctx) -> Result | [Result]  registered with its ID and tier:

    @check("check.mjcf.mirror", "gate")
    def mirror(ctx): ...

Checks never touch the sheet. They read the model (freyja.xml) and the snapshot
(params/snapshot.csv), so a result is reproducible from a commit. `run_checks` is used
by pytest, by the build gate (post_checks hook) and by `fy check`, so all three agree.

Statuses: PASS, FAIL, SKIP (with the reason in the message) and WAIVED (a known deviation
recorded in checks/waivers.yaml; the check still ran and its measured number is kept).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_FILE = REPO / "sim" / "models" / "freyja.xml"
SNAPSHOT_FILE = REPO / "params" / "snapshot.csv"
WAIVERS_FILE = REPO / "checks" / "waivers.yaml"

PASS, FAIL, SKIP, WAIVED = "PASS", "FAIL", "SKIP", "WAIVED"
GATE, ADVISORY = "gate", "advisory"


@dataclass
class Result:
    id: str
    tier: str
    status: str
    message: str = ""
    measured: dict | None = None  # the numbers behind the verdict, plain JSON types

    @property
    def blocking(self) -> bool:
        return self.status == FAIL and self.tier == GATE


@dataclass
class CheckSpec:
    id: str
    tier: str
    fn: object
    also: tuple = ()  # IDs of the extra results this check returns


REGISTRY: dict[str, CheckSpec] = {}


def check(check_id: str, tier: str, also=()):
    assert tier in (GATE, ADVISORY), tier

    def register(fn):
        REGISTRY[check_id] = CheckSpec(check_id, tier, fn, tuple(also))
        return fn
    return register


def all_ids(registry=None) -> set:
    reg = REGISTRY if registry is None else registry
    return {i for spec in reg.values() for i in (spec.id, *spec.also)}


def call(spec: CheckSpec, ctx) -> list:
    """Run one check. An exception inside a check is a failure of that check, never a crash."""
    try:
        out = spec.fn(ctx)
    except Exception as e:  # noqa: BLE001 - a broken check must be reported, not hide the others
        return [Result(spec.id, spec.tier, FAIL, f"the check itself raised {type(e).__name__}: {e}")]
    return list(out) if isinstance(out, (list, tuple)) else [out]


# ---------------------------------------------------------------- context

def load_snapshot(text: str) -> dict:
    return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(io.StringIO(text))}


class Context:
    """The model at the neutral pose (qpos0, forward kinematics done) plus the snapshot values."""

    def __init__(self, model, data, snapshot: dict, xml_text: str):
        self.model, self.data, self.snapshot, self.xml_text = model, data, snapshot, xml_text

    @classmethod
    def from_xml_text(cls, xml_text: str, snapshot: dict):
        import mujoco
        model = mujoco.MjModel.from_xml_string(xml_text)
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        return cls(model, data, dict(snapshot), xml_text)

    @classmethod
    def from_files(cls, xml_path=None, snapshot_path=None, snapshot_text=None):
        xml_text = Path(xml_path or MODEL_FILE).read_text(encoding="utf-8")
        text = snapshot_text if snapshot_text is not None else Path(snapshot_path or SNAPSHOT_FILE).read_text(encoding="utf-8")
        return cls.from_xml_text(xml_text, load_snapshot(text))


# ---------------------------------------------------------------- waivers

@dataclass
class Waiver:
    check: str
    reason: str
    source: str
    recorded: dt.date
    review_by: dt.date
    confirmed: bool = False  # a proposed waiver does nothing until Joe sets this to true


WAIVER_FIELDS = ("check", "reason", "source", "recorded", "review_by")


def _date(value, where: str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"{where}: '{value}' is not a YYYY-MM-DD date")


def load_waivers(path=None) -> list:
    import yaml
    data = yaml.safe_load(Path(path or WAIVERS_FILE).read_text(encoding="utf-8")) or []
    out = []
    for i, entry in enumerate(data):
        for field_name in WAIVER_FIELDS:
            if field_name not in entry:
                raise ValueError(f"waiver #{i + 1} ({entry.get('check', '?')}) is missing '{field_name}'")
        out.append(Waiver(entry["check"], str(entry["reason"]), str(entry["source"]),
                          _date(entry["recorded"], "recorded"), _date(entry["review_by"], "review_by"),
                          bool(entry.get("confirmed", False))))
    return out


def apply_waivers(results: list, waivers, known_ids: set, today: dt.date):
    """-> (results, warnings). A confirmed waiver turns a FAIL into WAIVED. A waiver on a check that
    passes, names an unknown check, was never confirmed or is past its review date produces a warning."""
    warnings, by_id = [], {}
    for w in waivers:
        by_id.setdefault(w.check, []).append(w)
        if w.check not in known_ids:
            warnings.append(f"waiver for unknown check {w.check}")
    out = []
    for r in results:
        for w in by_id.get(r.id, []):
            if r.status == PASS:
                warnings.append(f"waiver on {r.id} is no longer needed: the check passes. Remove it ({w.source})")
            elif r.status == FAIL and not w.confirmed:
                warnings.append(f"waiver proposed for {r.id} is not confirmed, so the failure stands")
            elif r.status == FAIL:
                r = Result(r.id, r.tier, WAIVED, f"{w.reason} [{w.source}] -- {r.message}", r.measured)
                if today > w.review_by:
                    warnings.append(f"waiver for {r.id} is past its review date {w.review_by}: review it")
        out.append(r)
    return out, warnings


# ---------------------------------------------------------------- runner

@dataclass
class RunReport:
    results: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def blocking(self) -> list:
        return [r for r in self.results if r.blocking]

    def to_json(self) -> str:
        return json.dumps({"results": [asdict(r) for r in self.results], "warnings": self.warnings},
                          indent=2, sort_keys=True, default=float) + "\n"

    def format(self) -> str:
        lines = [f"{r.status:7} {r.tier:8} {r.id}" + (f"  {r.message}" if r.message and r.status != PASS else "")
                 for r in self.results]
        lines += [f"WARNING {w}" for w in self.warnings]
        return "\n".join(lines)


def run_checks(ctx, tier=None, waivers=(), registry=None, today=None) -> RunReport:
    """Run every registered check (or only results of one tier) and apply the waivers.
    `waivers` is a list of Waiver; load them with load_waivers()."""
    reg = REGISTRY if registry is None else registry
    results = [r for spec in reg.values() for r in call(spec, ctx)]
    if tier:
        results = [r for r in results if r.tier == tier]
    results, warnings = apply_waivers(results, waivers, all_ids(reg), today or dt.date.today())
    return RunReport(results, warnings)
