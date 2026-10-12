"""
Checks on simulation runs (CONVENTIONS section 7), as opposed to checks on the model alone (mjcf_checks.py).
They read run summaries from sim/runs/ and the snapshot, never the sheet.

check.sim.walk_reference (advisory): the agreement of the baselined gait methods with the dataset's own joint moments (T6) reproduces within
1e-6 on a fixed subset while the snapshot and model are the baseline's; after a design change the baseline is superseded and the check reports
the current agreement for information and never fails.

check.sim.rom_reachable (advisory): every limited joint that rom_sweep moved reached 99% of the sheet's range
in the snapshot. It does not apply to unlimited joints (they are not swept). It is an end-to-end test of the
sheet-to-model chain: a model built from a stale or mis-mapped sheet value fails it.
"""
import json
import re
import sys
from pathlib import Path

import checklib
from checklib import ADVISORY, FAIL, PASS, SKIP, Result, check

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
import runrecord  # noqa: E402

TEMPLATE_FILE = REPO / "sim" / "models" / "freyja_template.xml"
RUNS_DIR = REPO / "sim" / "runs"
BASELINE_FILE = REPO / "sim" / "benchmarks" / "walk_reference.json"
META_FILE = REPO / "params" / "snapshot.meta.json"
PROCESSED_PROBE = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
SCENARIO = "rom_sweep"

ROM_REACH_FRACTION = 0.99  # of the sheet value. The sweep goes to 99% of the model range, so this is the brief's bar.
ROM_REACH_TOL_DEG = 1e-6  # deg. The sweep ends exactly on 99%: this only absorbs floating-point round-off.

_JOINT = re.compile(r'<joint\b[^>]*?\bname="([^"]+)"[^>]*?\brange="([^"]+)"')
_TOKEN = re.compile(r"^!\{(-?)([A-Za-z0-9_]+)\}$")


def sheet_limits(template_text: str, snapshot: dict) -> dict:
    """{joint: (lower_deg, upper_deg)} from the template's range placeholders and the snapshot's sheet values.
    A joint whose range is not made of snapshot placeholders (or whose value the sheet lacks) is absent."""
    out = {}
    for name, rng in _JOINT.findall(template_text):
        tokens = rng.split()
        if len(tokens) != 2:
            continue
        values = []
        for tok in tokens:
            m = _TOKEN.match(tok)
            if not m or m.group(2) not in snapshot:
                break
            values.append(-snapshot[m.group(2)] if m.group(1) else snapshot[m.group(2)])
        else:
            out[name] = (values[0], values[1])
    return out


def rom_shortfalls(summary: dict, limits: dict) -> tuple:
    """-> (joints_checked, shortfalls). A shortfall is a text line naming the joint and the number."""
    checked, short = 0, []
    for name, j in sorted(summary["joints"].items()):
        if j["rom_limit_deg"] is None:
            continue
        if name not in limits:
            short.append(f"{name}: limited in the model but has no sheet value to compare with")
            continue
        checked += 1
        lo_sheet, hi_sheet = limits[name]
        lo_used, hi_used = j["rom_used_deg"]
        if lo_used > ROM_REACH_FRACTION * lo_sheet + ROM_REACH_TOL_DEG:
            short.append(f"{name}: reached {lo_used:.3f} deg of the sheet's {lo_sheet:.3f} (needs {ROM_REACH_FRACTION * lo_sheet:.3f})")
        if hi_used < ROM_REACH_FRACTION * hi_sheet - ROM_REACH_TOL_DEG:
            short.append(f"{name}: reached {hi_used:.3f} deg of the sheet's {hi_sheet:.3f} (needs {ROM_REACH_FRACTION * hi_sheet:.3f})")
    return checked, short


def latest_sweep(model_sha256, runs_dir=None):
    """The newest rom_sweep summary recorded for this exact model, or None."""
    mine = [s for s in runrecord.load_summaries(runs_dir or RUNS_DIR)
            if s["scenario"]["name"] == SCENARIO and s["model_sha256"] == model_sha256]
    return mine[-1] if mine else None


@check("check.sim.rom_reachable", ADVISORY)
def rom_reachable(ctx):
    """Each limited joint's rom_used_deg in the latest rom_sweep reaches 99% of the sheet value in the snapshot."""
    summary = latest_sweep(getattr(ctx, "model_sha256", None))
    if summary is None:
        return Result("check.sim.rom_reachable", ADVISORY, SKIP, "no rom_sweep run recorded for this model; run `fy run rom_sweep`")
    limits = sheet_limits(TEMPLATE_FILE.read_text(encoding="utf-8"), ctx.snapshot)
    checked, short = rom_shortfalls(summary, limits)
    measured = {"run_id": summary["run_id"], "joints_checked": checked, "shortfalls": len(short)}
    if short:
        return Result("check.sim.rom_reachable", ADVISORY, FAIL, f"{summary['run_id']}: " + "; ".join(short), measured)
    return Result("check.sim.rom_reachable", ADVISORY, PASS,
                  f"{checked} limited joints in {summary['run_id']} each reached {ROM_REACH_FRACTION:.0%} of the sheet range", measured)


def dataset_available() -> bool:
    """The processed Camargo arrays are gitignored and absent from a fresh clone."""
    return PROCESSED_PROBE.exists()


def current_reference_metrics(methods) -> dict:
    """The reproducible subset's agreement metrics now (sim/scripts/gait.py reference_metrics)."""
    import gait
    return gait.reference_metrics(methods=list(methods))


def _summarise(metrics: dict) -> str:
    """One line per baselined method: correlation and RMS of the three sagittal joints, limbs averaged."""
    out = []
    for key in sorted(metrics):
        parts = []
        for stem in ("hip_fe", "knee", "ankle_pdflex"):
            v = [metrics[key][j] for j in (f"{stem}_right", f"{stem}_left") if j in metrics[key]]
            if v:
                parts.append(f"{stem} {sum(x['corr'] for x in v) / len(v):.3f}/{sum(x['rms_pct_ptp'] for x in v) / len(v):.1f}%")
        out.append(f"{key}: " + ", ".join(parts))
    return "; ".join(out)


@check("check.sim.walk_reference", ADVISORY)
def walk_reference(ctx):
    """Advisory. Same snapshot and model as sim/benchmarks/walk_reference.json: the baselined methods' agreement metrics on the reference subset
    must reproduce within the baseline's relative tolerance (1e-6: the computation is deterministic, the tolerance only absorbs round-off).
    Otherwise the baseline is superseded by a design change and the check reports the current agreement without failing."""
    if not BASELINE_FILE.exists():
        return Result("check.sim.walk_reference", ADVISORY, SKIP, "no sim/benchmarks/walk_reference.json; run `fy gait walk_treadmill --write-baseline`")
    if not dataset_available():
        return Result("check.sim.walk_reference", ADVISORY, SKIP, "the processed Camargo arrays are not present (raw data stays outside the repo)")
    base = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    if getattr(ctx, "model_sha256", None) != meta["model_sha256"]:
        return Result("check.sim.walk_reference", ADVISORY, SKIP, "the context is not the installed model (a candidate during a build); the agreement is computed on the installed model")
    methods = base["baselined_methods"]
    if meta["snapshot_sha256"] == base["snapshot_sha256"] and meta["model_sha256"] == base["model_sha256"]:
        import gait
        current = current_reference_metrics(methods)
        diffs = gait.compare_reference(base["reproduction"]["metrics"], current, base["reproduction"]["tolerance_rel"])
        measured = {"gait_id": base["gait_id"], "baselined_methods": methods, "differences": len(diffs)}
        if diffs:
            return Result("check.sim.walk_reference", ADVISORY, FAIL, f"{len(diffs)} metrics differ from {base['gait_id']}: " + "; ".join(diffs[:6]), measured)
        return Result("check.sim.walk_reference", ADVISORY, PASS, f"agreement of {', '.join(methods)} reproduces {base['gait_id']} within {base['reproduction']['tolerance_rel']:g}", measured)
    shown = current_reference_metrics(methods)
    return Result("check.sim.walk_reference", ADVISORY, SKIP,
                  f"baseline {base['gait_id']} superseded by a design change (snapshot {base['snapshot_sha256'][:12]} -> {meta['snapshot_sha256'][:12]}); "
                  f"agreement now, for information (corr/rms % of ptp): {_summarise(shown)}", {"superseded": True})
