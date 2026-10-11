# Stage 2 brief (for Claude Code): level-walking loads

Read `CONVENTIONS.md`, the Stage 1, 1b and 1c briefs, and `docs/memos/memo3-stage1-recap.md` first.

Goal: walking loads at 1.4 and 1.6 m/s on Freyja's own mass distribution, driven by measured human kinematics (the Camargo et al. 2021 open dataset, Georgia Tech), computed three ways and compared. Freyja's mass data is currently human-based, so agreement between the methods and the dataset's own joint moments is a soft check on the pipeline. Once CAD numbers replace the anthropometry, disagreement will be legitimate rather than a bug, so the baseline is recorded now and pinned to the snapshot hash (T6).

Methods, all on the same retargeted kinematics:
- **B (primary).** Freyja's own dynamics. The root rows of inverse dynamics give the net wrench the ground must supply; the centre of pressure is solved from moment balance, so the root rows close by construction (except the vertical-axis moment).
- **A (cross-check).** The measured ground reaction force and CoP, scaled to Freyja. The root rows will not close; the residual measures how far her motion is from the subject's.
- **H (cross-check).** Total force from Freyja's own CoM motion, applied at the measured CoP. The force rows close; the moment rows leave a residual.

Out of scope: stairs, ramps, sit-to-stand, overground walking, running, toes, arm swing, the closed-loop controller (Joe's own project), actuator selection, any change to the sheet, the template or `pre_processor`.

## Ground rules

CONVENTIONS section 9 applies. Pre-approved dependencies: `scipy` (filtering, splines) and, only if the dataset files are MATLAB v7.3, `h5py`. No others. Tests first, one commit per task, offline and deterministic. The raw dataset is never committed. Stop and ask before: changing the model; clipping or silently dropping any frame; choosing a tolerance by tuning toward a result. Never print raw arrays or full directory trees into the session; summarise (counts, shapes, a few names).

The work is in two parts. Stop after T2 and report; do not start T3 until Joe replies.

## Decisions already made

B primary, A and H as cross-checks (C, a whole-body controller, is Joe's later project). Double support: vertical force split proportional to the CoM's position between the feet as the nominal rule, plus a bound that sweeps the split over its feasible range and keeps the worst case per joint. Treadmill walking first. Upper body held rigid at the standing pose with arms at the sides, recorded as an assumption in every record. Envelope statistic: the 95th percentile across subject-strides, with the maximum shown beside it (Joe may override).

## Prerequisites for Joe

Use Version 2 of each part (Mendeley Data: DOIs 10.17632/fcgm3chfff.2, 10.17632/k9kvm5tn3f.2, 10.17632/jj3r5f9pnf.2). Part 1 carries a CC BY 4.0 licence; confirm the same on Parts 2 and 3. Part 1 first: `README.txt`, `SubjectInfo.mat` and `scripts.zip` (about 204 MB), which is all T0 needs, then `Subjects_Part1_AB06-AB14.zip` (9.38 GB, nine subjects in one archive). Parts 2 and 3 come after the Part 1 checkpoint. Keep the downloads outside the repo, in the folder named by the `camargo_raw_dir` key in `local_config.json` (gitignored).

## Amendments to CONVENTIONS (apply in T7)

1. Section 2: add `data/camargo2021/` (manifest and processed arrays), `sim/gait/` (generated), `sim/benchmarks/` (tracked), `sim/scenarios/gait/` (authored). `sim/gait/*/gait.json` and processed arrays are gitignored; `GAIT.md` and the benchmark file are tracked.
2. Section 3: add `gait.<YYYYMMDD>-<HHMM>-<spec>`. Section 6: add `gait-summary/1` with its schema in `docs/schemas/`.
3. Method constraint: `mj_inverse` with contacts disabled and explicit ground wrenches is permitted for dynamic frames (non-zero `qvel` and `qacc`). The contact solver is never used for loads.
4. The envelope takes gait rows from the statistic named above and lists the scenario classes it does and does not cover.

## T0. Dataset audit

Inspect the actual files; assume nothing. Start with `README.txt`, `SubjectInfo.mat` and `scripts.zip` (the authors' processing scripts; at 204 MB, check whether it holds more than code), then the subject archive. Note any content the README or scripts identify as belonging to a third party. Document in `data/camargo2021/README.md` and `manifest.json`: file format and layout, channels and units, the coordinate and sign conventions for each joint angle, whether joint moments are normalised and by what, which force-plate channels exist (force, moment, CoP), sampling rates, per-subject mass, height and sex, which treadmill speeds each subject has, and the licence text. Stop and report if the licence prohibits derived data.

## T1. Ingestion

`analysis/ingest_camargo.py` converts the walking trials at 1.4 and 1.6 m/s into per-stride, phase-normalised arrays (101 points) of joint angles, pelvis pose, joint moments, ground force and CoP, with heel-strike and toe-off events from the vertical force. The manifest records the DOI, version, retrieval date, file hashes, subject IDs used and the script path. Processed arrays are gitignored. Read trials on demand (zip archives give random access, including ZIP64, so no trial needs the rest of the archive read), or extract the outer archive once and leave any nested subject archives zipped; either way load only the trials used, never the whole dataset. The raw folder comes from `camargo_raw_dir`. The subject list is part of the spec hash. Write `data/camargo2021/ATTRIBUTION.md` (CC BY 4.0): dataset title and contributor, the version and DOI of each part, the paper's DOI and its author list copied from the paper itself, the licence name and link, the retrieval date, the changes made (stride segmentation, phase normalisation, filtering, retargeting to Freyja's model, load computation), and a line that the dataset's authors have not endorsed this work.

Tests first: stride counts and durations are plausible; phase continuity at the wrap; units; and gait-feature checks on the sign mapping (knee near full extension at heel strike, a swing peak of roughly 55 to 75 degrees in the model's flexion-positive convention; ankle plantarflexion at toe-off; hip extension late in stance). A mutation test flips one sign and the feature check must fail.

## T2. Retargeting and root trajectory

`sim/scenarios/gait/camargo_mapping.yaml` (authored) maps dataset joints to model joints with signs, validated by T1's feature checks. Spine and arm joints are held at the standing pose from `stand_static`. Smooth with a zero-lag Butterworth filter (default 6 Hz, a named constant) and differentiate the periodic cycle with documented, tested derivatives. The root pose comes from the dataset's pelvis rotation, a horizontal translation scaled by leg-length ratio, and a height set so the lowest point of the stance foot box sits on z = 0. Propose the rule; record it.

Tests first: integrating the derived `qvel` back with `mj_integratePos` reproduces `qpos` within 1e-9 (this covers the free joint's quaternion); a finite-difference check of the spline derivatives; the root rule keeps stance-foot penetration and swing-foot clearance within reported bounds.

Report, without clipping: the fraction of frames outside each joint's model limit, the stance-foot penetration and slip, the swing-foot clearance, the sagittal pelvis and CoM trajectories, and the subject list with mass and height.

Checkpoint: stop here and report T0 to T2.

## T3. Dynamic wrench solver (B)

`sim/scripts/dynamics.py`, generalising `statics.py` to frames with non-zero `qvel` and `qacc`. Per frame, contacts disabled, `mj_inverse` gives `qfrc_inverse`. The root rows give the net ground wrench. Joint torque is the joint rows of `qfrc_inverse - qfrc_ground`. Single support: the total force acts at a CoP on the floor plane, solved from the two horizontal-moment equations; the vertical-axis moment is left in the root rows and reported. Double support: the proportional split of force (and of horizontal force), each foot's CoP at the same normalised offset along its own box with a shared lateral shift, both solved from the two moment equations. Swing foot: zero. Feasibility, reported per frame and never clipped: the CoP must lie inside the hull of the foot-box points within 1 mm of the floor; the friction ratio must be below the model's `mu`. The double-support bound sweeps the force split over its feasible range and keeps the worst case per joint.

Tests first:
- A single rigid body on a foot box with prescribed sway reproduces the ZMP formula for the CoP to 1e-9, with and without rotational inertia.
- In free fall the root rows are zero.
- Symmetric double support with the CoM centred gives an equal split.
- Flipping the sign of the ground wrench breaks the root-row residual, and the test detects it.
- Independent check: the hip, knee and ankle torques on five frames equal a bottom-up Newton-Euler recursion written in the test, using the solved ground force and MuJoCo kinematics but not `mj_inverse`, to 1e-6 relative.

## T4. Methods A and H

A: scale the measured force by the weight ratio and the CoP along the foot by the length ratio (document the scaling and report its sensitivity). H: total force from Freyja's CoM motion, applied at the measured CoP. For both, report the root-row residual per frame and in aggregate.

Tests first: in H the force rows close to round-off and only the moments leave a residual; in A both generally leave one; the scale factors are applied where intended.

## T5. Batch runner and record

`fy gait <spec>` reads `sim/scenarios/gait/walk_treadmill.yaml` (dataset, speeds, subject selection, stride cap per subject, methods, smoothing, the upper-body assumption, the double-support rule) and runs every subject-stride. It writes `sim/gait/<id>/gait.json` (untracked) and a deterministic `GAIT.md` under 400 lines whose header carries the dataset attribution line. The record is stamped like a run: commit, dirty hash, snapshot and model hashes, spec hash, dataset manifest hash, environment.

It reports per joint and per method, across subject-strides: mean, 95th percentile and maximum of peak torque, peak speed, and positive and negative peak power (regeneration matters for drives). It reports feasibility fractions, residual magnitudes, and the agreement with the dataset's own joint moments for the sagittal hip, knee and ankle (moments per kilogram: RMS difference as a percentage of the dataset's peak-to-peak range, peak difference, correlation). It also gives a smoothing-sensitivity table: the change in each joint's 95th-percentile peak torque at 4, 6 and 8 Hz. No pass or fail on agreement yet.

Tests first, on synthetic strides with known answers: aggregation statistics; point caps; byte-identical output on a second run.

## T6. Baseline

Write `sim/benchmarks/walk_reference.json`: the agreement metrics, snapshot hash, spec hash and commit. Add `check.sim.walk_reference` (advisory): when the current snapshot hash equals the baseline's, the metrics must reproduce within 1e-6; otherwise it reports that the baseline is superseded by a design change and shows the agreement for information. It never fails on a design change.

## T7. Envelope and docs

Add the gait rows to the envelope using the 95th percentile, with the maximum shown, and update its list of covered and uncovered scenario classes. Apply the CONVENTIONS amendments. Update `CLAUDE.md` and the scenarios README.

## Done when

All suites green offline, `git status` clean, no raw data tracked. The final message reports, with numbers: the B, A and H comparison per joint at both speeds; the 95th-percentile and maximum peak torque and power per joint; the fraction of frames with CoP outside the foot box or friction exceeded, by phase; residual magnitudes for each method; the smoothing sensitivity; the agreement with the dataset moments; the subjects and strides used; every tolerance you chose and why; and every question that needs Joe.
