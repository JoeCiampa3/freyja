# Stage 0 brief (for Claude Code)

Read `CONVENTIONS.md` first; it is the contract. The sheet-to-MJCF pipeline already works (`sim/scripts/pre_processor.py`, `watch.py`, offline test suites, atomic install, MuJoCo compile gate). Stage 0 does not rebuild it. It makes the pipeline's output tracked and reproducible, removes the last hand-typed copies of sheet values from the template, and turns the ad hoc validation into named checks that run in the build.

## Ground rules

Work from the repo root on Windows. Tests run offline and never touch the sheet. Do the tasks in order, one commit each, tests first. Do not change what `pre_processor` reads from the sheet or the meaning of any placeholder. Do not rename the existing placeholder keys. No new dependencies without asking (pytest is pre-approved). No `eval`.

Stop and ask before: editing the sheet or any credential file; adding a dependency; touching the template in any way not listed in T2; changing a geometry value because a check failed.

## Prerequisites for Joe

Add a named range `targets` in the sheet covering the labelled total-mass and stature cells (`BSIP Reference` B1 and B2). Claude Code proposes the exact range in T0; Joe makes the edit. Review `checks/joint_polarity.yaml` (drafted in T3) before the joint-sign check is promoted to a gate.

## T0. Baseline and audit

From `sim/`, run `python -m unittest discover -s scripts`, `python scripts/pre_processor.py --dry-run` (use `--xlsx` if this machine has no credentials), and `python "scripts/validation/sprint 1/mass_check.py"`. Put the results in the commit message. Compare the real directory tree to CONVENTIONS section 2 and list deviations; do not move anything. Verify the root `.gitignore` covers the virtual environment, `local_config.json`, key patterns, `__pycache__`, `sim/models/freyja_FAILED.xml` and `sim/archive/`, and that `requirements.txt` exists. Update path references in docstrings and READMEs that still say "freyja-sim folder". Add a `CLAUDE.md` stub: three lines pointing at `CONVENTIONS.md`, the current brief, and the test command. Propose the layout of the `targets` named range.

Done when the baseline is green, the audit list is in the commit message, and nothing outside docs, `.gitignore` and the stub changed.

## T1. Tracked parameter snapshot

Implement section 5 of CONVENTIONS. `build_model()` writes `params/snapshot.csv` and `params/snapshot.meta.json` using the values it already archives, and adds the snapshot hash to the `freyja.xml` banner. The XML and the snapshot are installed together or not at all. The timestamped `archive/` behaviour stays as it is. If the `targets` range exists, its values enter the snapshot as `target_mass` and `target_stature`; until then, the keys are absent and later checks that need them skip with an explicit reason.

Tests first:
- Two builds from identical tables produce byte-identical snapshot, meta and XML.
- Changing one value changes exactly one snapshot row.
- `--dry-run` writes nothing.
- A failed build leaves snapshot, meta and XML untouched.
- The banner hash equals the hash of `snapshot.csv`.
- `snapshot.meta.json` contains no sheet ID, credential or absolute path.
- Every existing test still passes unmodified.

## T2. Remove hand-typed copies from the template

Audit every geom attribute (`pos`, `fromto`, `size`) in `freyja_template.xml`. Known examples: the thigh capsule end and knee sphere, the HJC coordinates inside the pelvis capsule, the shank, forearm and upper-arm capsule ends, the head sphere offset, and the foot box length. Replace each literal that is really a sheet-derived value with a placeholder. The placeholder language stays closed: use a leading-minus placeholder directly where the geometry allows, or add a small explicit set of derived keys computed in `pre_processor` with tests. Literals with no sheet origin (radii, widths, friction) stay, each with a comment `design choice, no sheet source`. List them in the commit message.

Note that the foot box is a collision geom, so its dimensions matter dynamically and are not cosmetic.

Tests first:
- A scan of the template finds no numeric literal in a geom attribute within 1e-4 of any snapshot value or its negation, unless it carries the design-choice comment.
- A fixture build with stature scaled 5% changes the affected capsule and sphere dimensions proportionally.
- The compile gate and all existing tests pass.

## T3. Checks

Create `checks/` with the checks below. Each has an ID, a tier, a named tolerance with a reason, and a mutation test. Add `site_vertex` (CJC plus `head_neck_length`) and `site_sole` (AJC minus the derived ankle height) to the template via placeholders where a check needs them.

`check.mjcf.mass_closure` (gate): model total mass equals the sum of segment masses in the snapshot (both sides) to 1e-9 relative. Advisory part: within 0.15% of `target_mass`. The known 64.935 kg against 65 kg is Dumas' published-fraction rounding (see the sprint memo).

`check.mjcf.mirror` (gate): for each bilateral pair, mass, CoM x and z, diagonal inertia and ranges are equal; position y and CoM y negate; Ixy and Iyz negate while Ixz is equal; hinge axes follow `(ax, ay, az) -> (-ax, ay, -az)`.

`check.mjcf.joint_signs` (gate): draft `checks/joint_polarity.yaml` from ISB (Wu 2002, 2005) and the sign comments already in the template. For each hinge, a probe point in the distal body frame and the expected world-displacement sign along a world axis at neutral. Set the joint to +0.1 rad, run forward kinematics, and assert the sign. The wrist is about the anteroposterior axis because the neutral hand is mid-pronation (palms toward the thighs); write that in the file header. Mark the file DRAFT until Joe approves it. Mutation test: negate one axis in a copy of the XML and assert failure.

`check.mjcf.floor_contact` (advisory): the lowest collision-geom point at neutral pose is within 1 mm of z = 0. Expected current result: this fails. The foot box spans -0.080 to 0 m about the AJC, while the AJC stands 0.0627 m above the floor, so the sole sits about 17 mm below the floor plane at spawn. Report the measured number, mark the check expected-fail with that reason, and do not change the geometry.

`check.mjcf.stature_chain` (advisory): `site_vertex` height minus `target_stature`, within 20 mm. The sheet's own integrity panel records a definitional offset of -14.684 mm; record it in the tolerance comment.

`check.mjcf.com` (advisory): refactor `mass_check.py` into reusable functions with targets from the snapshot instead of hardcoded 1.7 and 65.0. Whole-body CoM height as a percent of stature against 55.88 +/- 0.52% (Virmavirta and Isolehto); lateral CoM below 1 mm. The current 55.26% is known to sit about 0.1% outside the band; propose a waiver entry in `checks/waivers.yaml` for Joe to confirm.

Implement the waiver mechanism from CONVENTIONS section 7, including the warning for a waiver on a passing check.

## T4. Gate wiring

Add an optional `post_checks` hook to `build_model()`, called on the temporary XML before `os.replace`. `pre_processor.py` and `watch.py` both pass it. A gate failure parks the new XML as `freyja_FAILED.xml`, leaves the last good model and snapshot in place, and prints the failing check IDs. Advisory results print and are written to `checks/last_run.json` (gitignored).

Tests first: a gate failure keeps the previous model and snapshot; an advisory failure installs the new model; the watcher survives a gate failure and rebuilds when the input is fixed.

## T5. Thin `fy` entry point

`tools/fy/` provides `fy build`, `fy watch`, `fy test`, `fy check [--tier gate|advisory]`. Wrappers only; no domain logic. It finds the repo root by walking up to `CONVENTIONS.md` and works from any directory. Tests: each subcommand dispatches to the right function from a subdirectory.

## Done when

All suites green offline. `git status` clean, with no secrets or virtual environment tracked. CONVENTIONS updated for any schema that changed. The final message lists every expected-fail and waiver proposed, the measured numbers behind each, and every question that needs Joe.
