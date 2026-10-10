# Stage 1 brief (for Claude Code): run records

Read `CONVENTIONS.md` and the Stage 0 brief first. Stage 0 made the model reproducible and checked. Stage 1 makes every simulation run leave a stamped, comparable, machine-readable record, and builds the two generated files Claude reads instead of Joe measuring and reporting: a per-scenario digest and a cross-scenario load envelope.

Out of scope: gait, stairs, sit-to-stand (they need reference kinematics with citable provenance and retargeting; that is Stage 2), actuator selection, the coupled-hip variant, any change to the template or to what `pre_processor` reads.

## Ground rules

CONVENTIONS section 9 applies in full. `fy` below means `python tools/fy` until it is on the PATH. Pre-approved dependencies: `jsonschema`, `pyyaml` (if not already present). No scipy; write the convex hull yourself. Tests are offline and deterministic. One commit per task, tests first.

Stop and ask before: changing a geometry value or a check tolerance because a result looks wrong; adding any other dependency; changing the model, the template, or the sheet reader.

## Prerequisites for Joe

None blocking. The foot geometry was rebuilt in Stage 0 so the sole sits at z = 0 (documented in `docs/memos/memo2-stage0-recap.md`, measured at -1.3e-12 m); T0 verifies it rather than assuming it. Approve the amendments below by committing this brief. Confirm that `summary.json` files are tracked in git (the default here) and `raw.npz` is not. After Stage 1, refresh this Project's copy of the repo so the digest is readable in chat.

## Amendments to CONVENTIONS (apply in T1, same commit as the schema)

1. Section 1, Determinism: applies to build artifacts. A run record is an event; its `run_id` encodes the start time and nothing else in it is time-dependent. Every metric is deterministic given the same inputs and seed.
2. Section 2: add `sim/controllers/` (authored) and `docs/schemas/` (authored). `sim/runs/*/summary.json`, `sim/runs/DIGEST.md` and `sim/runs/ENVELOPE.md` are tracked; `raw.npz` is gitignored.
3. Section 6: extend `run-summary/1` with `seed`, `env` (`mujoco`, `python`, `numpy` versions), `support` (`"ground"` or `"gantry"`), `window` (`start_s`, `end_s`), and `diff_sha256` (hash of `git diff HEAD`, null when clean). `torque_source` is `"applied"` or `"inverse_dynamics"`. `outcome` stays `completed | fell | diverged`. The schema is amended in place only because no records exist yet; after the first committed run, any change bumps the version.

## Method constraints

Joint torque is about the model's own hinge axes (the decoupled hip architecture). It is not actuator torque for the coupled variant; the mapping to actuator space happens later. Say so in the schema description.

Use inverse dynamics (`mj_inverse` with prescribed `qacc`) only in gantry mode, where nothing touches the floor. In ground mode, use forward dynamics with ideal joint torques written to `qfrc_applied`, and log the applied torque. Do not run `mj_inverse` on a prescribed trajectory with contacts: the inverse contact force comes from the soft-constraint model and the penetration state, not from the force that balances the motion, so the root rows will not close. I am confident of this trap; if you find otherwise, show the evidence rather than overriding it.

PD on `qfrc_applied` is explicit. Light distal joints (hands) will go unstable at the model's 0.002 s timestep with stiff gains. Scale gains to each joint's effective inertia at the pose, or override the integrator for the run through a scenario option. Record whichever you use in the scenario file and the summary.

## T0. Audit Stage 0

Report, without changing anything: whether each Stage 0 task landed as specified; the measured result for `check.mjcf.floor_contact` (expected to pass, with the lowest collision point within 1 mm of z = 0; if it does not, stop and report before T1); every waiver and expected-fail currently recorded; every place the repo departs from CONVENTIONS. Run `fy test` and `fy check` and put the results in the commit message. If `fy` or `checks/` differ from what Stage 0 specified, update CONVENTIONS to match reality or flag the gap; do not paper over it.

## T1. Schema and record library

Write `docs/schemas/run-summary-1.schema.json` with a description on every field, including the metric definitions below. Write the record library (id generation, git state including `diff_sha256`, file hashes, deterministic JSON writing with sorted keys and LF endings, schema validation on write). Apply the CONVENTIONS amendments.

Metric definitions, over the measurement window: `torque_peak_nm` is the maximum absolute torque; `torque_rms_nm` the time RMS; `speed_peak_rad_s` the maximum absolute joint velocity; `power_peak_w` the maximum of |torque times velocity|; `rom_used_deg` the signed `[min, max]` of the joint angle in the model's sign convention; `rom_limit_deg` the model's range, null if unlimited; `limit_hit_fraction` the fraction of window steps within 0.1 degrees of either limit, null if unlimited. For each foot (all geoms of the foot body against the floor): normal force is the sum over contacts, `friction_ratio_peak` is the maximum of tangential over normal force among steps with normal force of at least 1 N. `support_margin_min_m` is the minimum, over steps with floor contact, of the signed distance from the CoM's ground projection to the boundary of the convex hull of floor-contact points (positive inside). A hull of fewer than three non-collinear points gives a margin of zero or less, never positive.

Tests first:
- Metric extractors checked against hand-computed arrays, including negative extremes (peak uses absolute value, ROM uses signed extremes) and a constant signal.
- Support margin on a square hull with the CoM inside, on the boundary, outside, and on degenerate hulls.
- Every written summary validates; a corrupted copy fails.
- Writing the same record twice gives byte-identical files.
- In a temporary git repository, a dirty tree sets `git_dirty` and a non-null `diff_sha256`; a clean tree gives null.

## T2. Runner, controller hook, staleness gate

`sim/scenarios/<name>.yaml` (authored) names the model, seed, window, support mode, drive type (`inverse_dynamics_playback` or `controller`), duration and parameters, plus the fall thresholds (default: pelvis height below 60% of initial, or trunk tilt beyond 45 degrees). Controllers live in `sim/controllers/` and implement `reset(model, data, params)` and `step(model, data, t)`; `step` sets `data.qfrc_applied`. The runner writes `sim/runs/<id>/summary.json` and `raw.npz`.

Before running, the runner verifies that the SHA-256 of `freyja.xml` matches `params/snapshot.meta.json` and refuses to run otherwise, with no run directory created. It records the waived checks from `checks/waivers.yaml` and the advisory check status from the last run, and states if that status was computed for a different model hash.

Tests first, using a single-hinge pendulum fixture (point mass, negligible own inertia) built inline:
- Gantry inverse dynamics on a prescribed sinusoid matches the analytic torque `m l^2 theta_ddot + m g l sin(theta)` to 1e-6 relative.
- A forward-dynamics PD hold settles to a steady torque equal to `m g l sin(theta)` within 0.5%.
- At every logged step of a forward run, `mj_inverse` joint rows recover the applied torque within a stated tolerance; report the tolerance you needed and why.
- The same scenario run twice gives identical metrics; only `run_id` differs.
- A tampered `freyja.xml` makes the runner exit non-zero and create nothing.
- A controller that diverges produces `outcome: diverged`; one that tips the model produces `fell`.

## T3. First scenarios

`rom_sweep` (gantry, inverse dynamics): each joint in turn moves slowly across 99% of its model range with every other joint at neutral. It records the gravity-torque curve, and it is an end-to-end test of the sheet-to-model chain. Seven sheet ROM values are still missing, so some joints are unlimited (the lumbosacral joints, parts of the shoulder, and any joint with no range in the template; T0 lists them exactly). Do not invent a sweep span for them: skip each unlimited joint, record it as skipped with reason `unlimited`, and list it in the digest and envelope. Add `check.sim.rom_reachable` (advisory): each limited joint's `rom_used_deg` reaches 99% of the sheet value in the snapshot. It does not apply to unlimited joints.

`hold_pose` (ground, forward dynamics): ideal-torque PD holds the neutral standing pose, with a settle window and a measurement window afterward. These are the static standing loads. In the summary and the commit message, report the measured settled penetration, the total normal force against body weight, and the support margin.

Tests first for `hold_pose`: mean vertical contact force over the measurement window equals total weight within 0.5%; the mirror-image joints on left and right carry equal and opposite-sign (per the mirror rule) torques within 2%, or the asymmetry is reported as a finding with its cause.

If `hold_pose` falls, or the force closure fails, that is a result to report with numbers, not a bug to tune away.

## T4. Query, digest, envelope

`fy runs list [--scenario S]`, `fy runs show <id>`, and `fy runs compare <idA> <idB>`. Compare prints which inputs differ (commit, snapshot hash, model hash, scenario parameters, controller version, seed, environment) and then the metric deltas as absolute and percent. When both commits are available and clean, it also prints the changed snapshot rows via `git show <commit>:params/snapshot.csv`; otherwise it says it cannot attribute the change.

`fy runs digest` writes `sim/runs/DIGEST.md`: for each scenario, its latest run with a compact per-joint table (peak torque, RMS torque, peak speed, peak power, ROM used against limit), the contact and balance numbers, checks status, and the delta against the previous run of the same scenario. Deterministic, no timestamps other than run IDs, and under 400 lines for any number of historical runs.

`fy runs envelope` writes `sim/runs/ENVELOPE.md`: for each joint, the worst case across the latest run of every scenario, with the driving run ID. It opens with a plain statement of which scenario classes are included and which are not yet (gait, stairs, sit-to-stand), so nobody reads it as a complete sizing basis. It also lists every joint with no ROM data: an unlimited joint has no sweep, so its row reflects the standing hold only.

Tests first, using synthetic summaries: digest and envelope are byte-identical on a second run; envelope selects the right driving run, with ties broken by run ID; compare reports exactly the inputs that differ; the digest stays under the line cap with thirty synthetic runs.

## T5. Wiring

Add `fy run <scenario>`, and `fy runs ...` to `tools/fy/`, wrappers only. Add the digest and envelope paths to `CLAUDE.md`, and point its "current brief" line at this brief.

## Done when

All suites green offline. `git status` clean, with no `raw.npz` tracked. The final message lists, with measured numbers: the T0 audit result, the `rom_sweep` and `hold_pose` findings (penetration, force closure, support margin, symmetry), every tolerance you had to choose and why, and every question that needs Joe.
