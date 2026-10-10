"""
Checks on simulation runs (CONVENTIONS section 7), as opposed to checks on the model alone (mjcf_checks.py).
They read run summaries from sim/runs/ and the snapshot, never the sheet.

check.sim.rom_reachable (advisory): every limited joint that rom_sweep moved reached 99% of the sheet's range
in the snapshot. It does not apply to unlimited joints (they are not swept). It is an end-to-end test of the
sheet-to-model chain: a model built from a stale or mis-mapped sheet value fails it.
"""
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
