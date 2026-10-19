"""
Checks on the thread (CONVENTIONS section 7), as opposed to checks on the model alone (mjcf_checks.py) and on runs (sim_checks.py).

check.thread.coverage (advisory): every model body maps to exactly one segment record and every model hinge to exactly one joint record.
It reads the model text and the records in thread/records/, never the sheet. It is advisory and not a build gate: the gate checks the
model, and the thread has its own build (`fy thread build`), which reports an unbound body or hinge as a warning and a doubly bound one as
an error.
"""
import sys
from collections import defaultdict
from pathlib import Path

import checklib
from checklib import ADVISORY, FAIL, PASS, SKIP, Result, check

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))
from thread import build as thread_build  # noqa: E402
from thread import store as thread_store  # noqa: E402

RECORDS_DIR = REPO / "thread" / "records"


def _claims(records_dir, model):
    """({body: [segment record ids]}, {hinge: [joint record ids]}) from the records' bindings, by the library's own expansion rule."""
    import yaml  # the records are read from the directory given, which may be a copy of thread/records
    bodies, hinges = defaultdict(list), defaultdict(list)
    for p in sorted(Path(records_dir).glob("*.yaml")):
        r = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(r, dict):
            continue
        if r.get("kind") == "segment" and r.get("status") != "superseded":
            for b in thread_build.expand(r.get("body", ""), model.bodies)[0] or [r.get("body", "")]:
                bodies[b].append(r["id"])
        elif r.get("kind") == "joint" and r.get("status") != "superseded":
            for h in r.get("hinges", []):
                for n in thread_build.expand(h, model.hinges)[0] or [h]:
                    hinges[n].append(r["id"])
    return bodies, hinges


def coverage_problems(xml_text: str, records_dir) -> list:
    """Lines naming each body without exactly one segment record and each hinge without exactly one joint record."""
    model = thread_store.Model.parse(xml_text.encode("utf-8"))
    bodies, hinges = _claims(records_dir, model)
    problems = []
    for what, names, claims, noun in (("body", model.bodies, bodies, "segment"), ("hinge", model.hinges, hinges, "joint")):
        for n in sorted(names):
            k = len(claims.get(n, []))
            if k == 0:
                problems.append(f"the model {what} {n} has no {noun} record")
            elif k > 1:
                problems.append(f"the model {what} {n} is bound by {k} {noun} records ({', '.join(sorted(claims[n]))})")
    return problems


@check("check.thread.coverage", ADVISORY)
def coverage(ctx):
    if not RECORDS_DIR.is_dir():
        return Result("check.thread.coverage", ADVISORY, SKIP, "thread/records/ does not exist")
    model = thread_store.Model.parse(ctx.xml_text.encode("utf-8"))
    problems = coverage_problems(ctx.xml_text, RECORDS_DIR)
    measured = {"bodies": len(model.bodies), "hinges": len(model.hinges), "problems": problems}
    if problems:
        return Result("check.thread.coverage", ADVISORY, FAIL, f"{len(problems)} problem(s): " + "; ".join(problems[:5]), measured)
    return Result("check.thread.coverage", ADVISORY, PASS, f"{len(model.bodies)} bodies and {len(model.hinges)} hinges are each bound by exactly one record", measured)
