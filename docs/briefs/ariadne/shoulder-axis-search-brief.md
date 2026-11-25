# Shoulder axis search brief (for Claude Code): where the shoulder gimbal's fixed axis points, so its singular directions miss every humeral direction Freyja must reach

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `roadmap/nodes/rm.v1-shoulder-concept.md`, `roadmap/nodes/rm.v1-shoulder-adduction-defined.md` (its last consequence is the singularity this brief moves), `thread/dossiers/jnt.shoulder.md` and `checks/joint_polarity.yaml`. This brief belongs to the Ariadne track. It is one group with one checkpoint. Its output is an input to `decisions/0025-shoulder-actuation-concept.md`, which Joe writes. It closes no roadmap leaf and changes no `done_when`.

Tag: Delegate. End the session with a few lines for Joe (the decision summary of `CLAUDE.md` rule 6, kept short); the full memo is for the record.

`upper-arm-characterization-brief.md` is paused, not superseded: its Group L waits on adr-0025, which waits on this result.

## Purpose

The shoulder concept Joe is converging on (chat, 2026-11-25) is a three-axis gimbal with all three axes intersecting at the shoulder joint centre (SJC). Axis 1 is fixed in the thorax (pitch, actuated from the thorax). Axis 2 is perpendicular to axis 1 (roll). Axis 3 runs along the humeral long axis (axial rotation, actuator in the upper arm). Axis 2 is perpendicular to axis 3. The centre is fixed: the shoulder-girdle DOF is deferred to a later version and the thorax reserves nothing for it. The module hangs on a clavicle member that meets the thorax at a spherical sternal joint, which is rigid in normal use and yields only in falls. That has no effect on this search beyond fixing the centre.

Such a gimbal is singular when the humerus is parallel to axis 1, in either direction. Axis 1 is a line, so it has two singular directions, ±u1. The model's current chain (`shoulder_fe` → `shoulder_aa` → `shoulder_ier`, axis 1 along ∓y) puts that line through "arm straight out to the side". That direction is on the abduction arc, the lateral fall and every sideways gesture. Near it the axis-1 and axis-3 rates grow as about 1/angle, which works against Joe's requirement that the shoulder never cap arm speed (overview, 2026-10-24).

This brief finds the u1 whose two ends lie as far as possible from every humeral direction Freyja must reach. It also reports what that choice costs in joint span. The working hypothesis from chat is one end up, behind and lateral (arm raised behind, rarely used) and the other end down, forward and medial (into the torso). The search decides; the hypothesis is only something to check against.

## What this brief does not do

- It changes nothing in the model, the template, `pre_processor` or the sheet. The sim keeps its anatomical chain. Whether the sim later re-chains to the hardware axes or maps between the two is Joe's question for adr-0025 (Decisions, item 4).
- It models no torso collision, no actuator, no transmission, no inertia and no load. Directions and kinematics only.
- It does not choose between a thorax-side differential and a serial roll stage. That comes after this result and a volume-extractor query around the SJC (separate brief).
- It reads nothing from `catalog/`.
- It edits no decision record, roadmap node or thread record, and stamps nothing.

## Definitions

Frame: the thorax body frame of `sim/models/freyja.xml` (x anterior, y left, z up). At neutral spine it coincides with the world axes. Right arm unless stated. The humeral direction d is the unit vector from the SJC to the elbow joint centre.

Elevation θ and plane of elevation φ follow ISB humerothoracic YXY (Wu et al. 2005): θ is measured from straight down, and φ = 0 is abduction in the frontal plane, φ = +90 is forward flexion and φ < 0 is behind the frontal plane. For the right arm:

  d(φ, θ) = (sin θ sin φ, −sin θ cos φ, −cos θ)

So (φ, θ) = (0, 90) points lateral (0, −1, 0), (90, 90) points anterior and (any, 180) points straight up. T1 checks this formula against the model before anything else uses it (gate V7).

Gimbal. u1 is a unit vector in the thorax frame. At zero pose the humerus points along d0, the unit projection of straight down (0, 0, −1) onto the plane perpendicular to u1, so the neutral arm is q = 0. Then u2 = u1 × d0, and d = R(u1, q1) R(u2, q2) d0. Axis 3 is d. Branch: q2 ∈ [−90°, 90°]. q2 is then the latitude of d measured from the plane perpendicular to u1, and q1 is its longitude about u1.

Conditioning. The orientation Jacobian of three intersecting revolute axes is the matrix of their unit axes in the thorax frame, [u1, u2(q1), d]. With u2 perpendicular to both u1 and d, its singular values are 1 and √(1 ± u1·d), so

  σ_min(d) = √(1 − |u1·d|),   joint-rate gain = 1/σ_min.

σ_min depends only on the angle between d and the line ±u1. Maximising the least σ_min over a set of directions is the same as maximising the least angular distance from that set to the line. Report both numbers everywhere. This σ is defined here and is not the hip's σ_floor of 0.500 (whose definition is not in the repo). Do not compare the two.

## The required set

The required set R is the humeral directions the gimbal must reach well conditioned. Its numbers come from two places only. ROM values come from snapshot addresses (T0 confirms each address resolves, e.g. `snapshot#/shoulder_flexion`), and are not typed. The rest come from `data/shoulder/inputs/axis_search.yaml`, which is authored, each entry `{value, unit, source}` as in the characterization inputs.

Basis entries (the optimum is computed on these):

- **A1, flexion arc.** d = (sin β, 0, −cos β), β from 0 to `shoulder_flexion` (172°), 0.5° steps.
- **A2, extension arc.** d = (−sin β, 0, −cos β), β from 0 to `shoulder_extension` (57.3°), 0.5° steps. Arm swing lives on A1 and A2.
- **A3, abduction arc.** d = (0, −sin α, −cos α), α from 0 to `shoulder_abduction` (182.7°), 0.5° steps. This includes the arm straight out to the side and the lateral fall direction.
- **B1, ADL envelope.** Every (φ, θ) on a 1° grid with edges, φ from −65° to 105° and θ from 0° to 108°: Gates et al. 2016, "Range of motion requirements for upper-limb activities of daily living", Am J Occup Ther (PMC4690598), abstract. It gives humeral plane angle −65°/0°/105° and elevation 0° to 108° as the minimum to complete all eight ADLs. Two cautions go in the inputs file's `source` and in the memo. First, the per-DOF extremes taken as a box are a superset of what the tasks used together, so B1 can only overstate the requirement. Second, the paper's zero and sign convention for plane angle is assumed to be ISB YXY as above. If T1 can read the paper's methods, confirm or correct the assumption and say which. If it cannot, carry the assumption as `provisional` and put it first in the questions for Joe.

Sensitivity entries (never in the basis; each is added alone in T4 and its effect reported):

- **S1, overhead in the scapular plane.** φ = 30°, θ from 0 to `shoulder_flexion`. Reaching a high shelf. Source needed for the plane: the scapular plane at about 30° anterior to frontal is the common figure, from memory. Flag `source_needed`.
- **S2, cross-body.** (φ, θ) = (130°, 90°). Horizontal adduction about 40° past forward, from memory (rm.v1-shoulder-adduction-defined, option C). Flag `source_needed` until decision 0043 exists.
- **S3, hand behind head.** (φ, θ) = (20°, 120°). From memory. Flag `source_needed`. Joe wants this pose and argued it mostly uses the elbow. It still puts the humerus high and near the hypothesised singular end, so it is checked explicitly.

## Stop and ask before

- Any change listed under "What this brief does not do".
- Adding a dependency. numpy and the installed MuJoCo bindings are enough. If scipy or matplotlib are already dependencies they may be used; if not, do without.
- Any required-set number that is neither a snapshot address nor an inputs-file entry with its source.
- Choosing a grid resolution, refinement tolerance or threshold by tuning toward a result.

## Report as a finding

- V7 fails: the d(φ, θ) formula or the sign conventions do not match the model. Stop: nothing downstream is meaningful.
- The best basis floor is below 15° of angular distance (σ_min ≈ 0.18). Report the binding entries. Joe decides which requirement gives way; do not drop one yourself.
- The optimum's two ends do not fall in the up/back/lateral and down/forward/medial regions of the working hypothesis. That is not a fail, but say so at the top of the memo.
- B1's convention cannot be confirmed (see B1).

## Gate criteria

Each gate is reported pass or fail with its numbers. Do not change a criterion to make a result pass.

- **V1, conditioning formula.** On 10 000 random (u1, d) pairs, the numerical σ_min of [u1, u2, d] (SVD) equals √(1 − |u1·d|) to 1e-9.
- **V2, baseline.** With u1 = (0, −1, 0), the model's current chain, the least σ_min over R is 0 to within the 0.5° arc step: σ_min ≤ √(1 − cos 0.5°). It occurs on A3 at α = 90°. This reproduces the singularity stated in rm.v1-shoulder-adduction-defined.
- **V3, round trip.** For the optimum u1, inverse kinematics then forward kinematics reproduces every d in R and in S1 to S3 to 1e-9, excluding directions within 1° of ±u1, whose count is reported.
- **V4, mirror.** Run for the left arm with y mirrored. The left optimum is the y-mirror of the right one to 1e-9, and its floor is equal.
- **V5, convergence.** The global search is a Fibonacci grid of directions on the hemisphere (u1 and −u1 are the same line) followed by local refinement. Seeded from 20 000 points and from 80 000 points, the refined optima agree within 0.1° and their floors agree within 1e-6.
- **V6, determinism.** Two runs produce byte-identical output.
- **V7, conventions against the model.** Using `mujoco` forward kinematics on the model (read-only), the upper arm's elbow-ward axis in the thorax frame equals d(φ, θ) to 1e-9 in four poses. All joints at 0 gives (0, 0, −1). `shoulder_fe_right` = 90° gives anterior. The abduction sign that `checks/joint_polarity.yaml` gives for `shoulder_aa_right`, at magnitude 90°, gives lateral. `shoulder_fe_right` = −30° gives posterior-down. Read the signs from the polarity file, do not assume them. Also confirm the left arm's mirror.

## Tasks

**T0. Baseline (no commit).** `fy thread build`, `fy test --quick`; record counts and timings. Confirm the three snapshot addresses resolve and give 172, 57.3 and 182.7. Confirm the model's shoulder joint names and axes match the Purpose section.

**T1. Conventions and inputs (one commit; tests first).** Write `tests/test_shoulder_axis_search.py` with V1 and V7 first. Then `analysis/shoulder_axis_search.py`, as far as d(φ, θ), the gimbal forward and inverse kinematics and σ_min. Then `data/shoulder/inputs/axis_search.yaml`, with B1 and S1 to S3 and their sources and flags exactly as above. If CONVENTIONS section 2 lists directories, add rows for `data/shoulder/` (`axis_search.json` generated, `inputs/` authored) and the script in the same commit (rule 7). Run V7 before anything else and stop if it fails.

**T2. Search (one commit; tests first).** Build R from the addresses and the inputs file. Run the baseline (V2), then the global search and refinement (V5), maximising the least σ_min over R. Report:

- the optimum u1 as a unit vector and both ends as (φ, θ);
- the floor as σ_min, angular distance and rate gain;
- the binding directions: which entry and where, every point within 0.5° of the floor's angular distance;
- up to three distinct local optima (basins more than 20° apart), each with its floor and binding entries;
- for the optimum, the q1 span (longitude about u1, unwrapped along each arc and over B1; say whether R encircles u1, in which case the span approaches 360°), the q2 span, and the gimbal pose of the neutral arm.

The axis-3 span is not computed here. It needs a definition of the gimbal's induced axial offset against ISB axial rotation, which is adr-0025's to choose. List it as open.

V3, V4 and V6 run on the result. The output is `data/shoulder/axis_search.json`, generated and tracked, with banner keys and no timestamp, written the way `analysis/fall_room.py` writes `data/falls/room.json`.

**T3. Map (same commit, or skip).** If matplotlib is already a dependency, write an equirectangular map of the floor over u1 (both hemispheres shown) with R overlaid to an untracked path, and give the path in the memo. Otherwise skip, and give a coarse table instead: floor by u1 on a 15° grid, at most 25 rows of the best cells.

**T4. Sensitivity (one commit).** Rerun the search on R ∪ S1, R ∪ S2, R ∪ S3 and R ∪ S1 ∪ S2 ∪ S3, then on R with B1 removed and on R with B1's plane bounds widened by 10° at each end. For each: the optimum (angle from the basis optimum), the floor, and the binding entry. Then evaluate S1 to S3 at the basis optimum without re-optimising. This answers whether Joe's hand-behind-head pose and high-shelf reach survive the basis choice.

**Checkpoint.** Memo per `CLAUDE.md` rule 6. Lead with the decision summary: where axis 1 points in words a reader can picture, the floor and rate gain beside the baseline's 0, the q1 and q2 spans, which requirement binds, and what S1 to S3 do to the answer. Then the gate table (V1 to V7), the basins, the sensitivity table, the B1 convention status, findings and questions. `fy state`, stop.

## Decisions this brief makes (Joe approves them by committing it)

1. An orthogonal gimbal with axis 3 along the humerus, per Joe's architecture. Non-orthogonal axis twists (the hip's 45°/45° class) are out of scope: for a pointing gimbal they shrink the reachable cone and buy only packaging, which is the transmission question.
2. The objective is the least σ_min over the required set, equivalently the least angular distance to the singular line. The rate gain is reported with it, not gated, because no actuator speed exists yet.
3. The required set is the three ROM arcs from the snapshot plus Gates 2016's ADL envelope as a box. S1 to S3 inform the decision without entering the basis until each has a source.
4. The model is not changed. Re-chaining the sim to the hardware axes, or mapping between the two chains, is Joe's question for adr-0025.
5. The centre is fixed and torso collision is not modelled. A singular end pointing into the torso is reported as such for Joe to judge; it is not credited automatically.

## Prerequisites for Joe

- Commit this brief and the `CLAUDE.md` line pointing at it, and prompt Code with its path, its `sha256sum` prefix and "run the shoulder axis search".
- If you have the Gates 2016 paper, confirming its plane-angle convention before the run removes the main provisional item.
