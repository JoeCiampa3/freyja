# Hip packing search brief (for Claude Code): an experiment, not a track

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then `docs/schemas/envelope-oracle.md`, `tools/envelope/README.md`, `decisions/0007-envelope-extraction.md` (D4, D5, D9, D11), `decisions/0004-hip-stop-pelvis-pose.md`, `catalog/actuators/akh70-48-specs.md` and its technical drawing, `data/envelope/reservations.yaml`, `data/envelope/reserved/pelvis.yaml`, and the roadmap nodes `rm.v1-hip-architecture-adr`, `rm.v1-hip-b2-transmission` and `rm.v1-hip-registration-decided`.

Tag: Delegate. End each checkpoint with a few lines for Joe; the full memo is for the next session.

## Purpose

Joe packs the hip actuation module by hand: choose bearings, transmission and structure, place them, find a clash, change one thing, repeat. This experiment tests whether that loop can be written down as a search: parameterize the module, score a candidate against the body envelope and the occupied space with one number, and let an optimizer run thousands of candidates outside the session. The deliverable is the harness and the ranked near-misses, not a design. A feasible candidate is a candidate for design work. Nothing here checks strength, stiffness, fatigue or life (adr-0019's job), and the envelope is advisory geometry (adr-0007, Consequences).

The hip architecture is an open decision (`rm.v1-hip-architecture-adr`: earlier hip-module work is an input, not a commitment). You choose the architectures, bearings, transmissions, structure and the rotation actuator. The one fixed choice: the two actuators that drive flexion-extension and ab-adduction (the coupled pair in a differential; the first two axes in a serial chain) are AKH70-family modules. AKH70-48 is the catalog entry; another reduction variant may be used only if you cite its datasheet. The internal-external rotation actuator is yours to choose from a cited datasheet (motor, gearing, or an integrated module); Joe's earlier inputs, none required, were the CubeMars AKE90-8 (judged oversized) and a size-25 harmonic drive stage.

## Experiment boundary (Joe's exception to the repo rules, 2026-11-15)

- Work only in a git worktree on its own branch: `git worktree add ../freyja-hippack-<label> -b exp/hippack-<label>` from the current `main`, where the prompt gives `<label>`. Nothing merges to main. This brief stays untracked on main; read it from there.
- Every file goes under `experiments/hip-packing/` on the branch, memos included (`experiments/hip-packing/memos/memoN-<slug>.md`, numbered from 1). Do not claim a `docs/memos/` number.
- Tests: rule 1's test-first discipline holds for the harness, but commits run only `experiments/hip-packing/tests/`. No `fy test --quick`, no full suite, no `fy state`. Open each memo with a line naming the branch, the base commit and the test count, in place of the STATE line.
- Do not edit `CLAUDE.md` (its current-brief lines included), `CONVENTIONS.md`, or anything under `data/`, `tools/`, `thread/`, `roadmap/`, `decisions/` or `sim/`, and never touch the sheet. Import `tools/envelope` and read the model; do not modify them. Write registries and pose files under the experiment directory and point the oracle at them (`--components-dir`, the registry's `poses_file`).
- Dependencies: numpy, scipy (`scipy.optimize`: `differential_evolution`, `dual_annealing`, `minimize`), matplotlib and what the repo already imports. Adding a package is stop-and-ask.

## The problem

Right side only. Two bodies, `pelvis` and `thigh_R`, in the model body frames (adr-0007 D9). A candidate is a set of parts, each a primitive the oracle accepts (cylinder, capsule, box), owned by the pelvis (pelvis-fixed) or by the thigh (moves with the hip).

A candidate contains: the two AKH70 modules and the rotation actuator, wherever they sit; every bearing that carries a joint or transmission shaft, as a housing primitive (bearing OD plus twice the wall; width plus the wall at a closed end); every transmission element (drums, pulleys, links with their sweep, cables or belts as `kind: flexible` where they run free); and the structural members that connect each housing to its body. Structure is represented, not sized: each housing reaches its body's anchor through an unbroken chain of occupied primitives. You choose and state the anchors (the pelvis has no designed structure yet; the thigh member runs along the thigh axis) and the member sections, with your reasoning. Section adequacy is not checked, and the memo says so.

Hard constraints, each a non-negative term of the score:

1. **Skin.** Every part's skin margin is at least t = 5 mm, adr-0007 D4's default shell. Pelvis-fixed parts are checked against the pelvis body and thigh parts against the thigh body; hardware that straddles the hip plane is checked against the union of the two (adr-0007 D5, the oracle's `--union`).
2. **Self-interference.** The module's own parts keep the larger of each pair's `clearance_mm`. Pelvis-fixed parts are checked against thigh parts over the hip sweep: the default sampling of `fy envelope foreign` (590 poses over the model's hip limits) or a denser one, never sparser. A part driven by a linkage enters as a poses CSV from your own linkage solver (the oracle schema's "Foreign components").
3. **Reserved space.** The three spine modules in `data/envelope/reserved/pelvis.yaml`, with their 5 mm clearance.
4. **The left hip.** The right module's pelvis-fixed parts clear their own mirror image across the pelvis midline (y = 0), at the same clearance. Left-thigh parts against right-thigh parts are not modelled; say so.
5. **Minimum wall.** 3.0 mm [design, provisional for this experiment, Joe]. Every housing wall and member section is at least this.
6. **Range of motion.** Every hip joint reaches the model's limits (read from `sim/models/freyja.xml`, never typed) with every part clear over the sweep, and every actuator stays inside its own travel if it has one.
7. **Conditioning, coupled architectures only.** No singularity inside the range of motion. Report the floor of the smallest singular value of the actuator-to-joint Jacobian over the ROM grid, normalized so that a decoupled 1:1 drive scores 1. The floor is 0.5 [design, from Joe's earlier anteromedial-axis differential, which reached 0.500].
8. **Transmission constraints you author for each family**: cable D/d and wrap, belt minimum pulley, linkage transmission angle, and so on. Each cites a source or is tagged [design] with your reason. The torque ratio from each actuator to its joint is at least 1 (no speed-up stage).

Reported for every ranked candidate, not constrained: module mass (catalog masses plus primitive volumes at a density you state); each degree of freedom's peak joint torque capacity (each actuator's cited peak, 222 N·m for the AKH70-48, through the transmission and the Jacobian, at the worst point of the ROM); each bearing's basic static and dynamic ratings; the achieved skin margin; and the wall slack (the largest wall at which the candidate stays feasible).

Not modelled, and listed in every memo: loads and strength; the battery, electronics and the pelvis torque box; the left leg; fasteners, wiring and assembly access; machinability on the DMC2 (three-axis mill, no lathe) beyond the minimum wall.

## Data and provenance

`experiments/hip-packing/catalog.csv` (or `.yaml`): one row per part type used, every dimension and rating cited (document, page or table, URL). Bearings: a candidate list from manufacturer catalogs (NTN, SKF, Misumi or similar) covering at least the deep-groove, angular-contact and thin-section series between 8 and 70 mm bore, plus Joe's earlier picks as candidates (7204B, the 7204 DB pair, 7003B, NU204ET, drawn-cup needle rollers), none of them required. AKH70: from `catalog/actuators/`. The rotation actuator: its datasheet, cited like any other row. A dimension you can only read off the drawing PNG is cited to it with your reading error. A number you cannot cite is tagged `unsourced`, used, and listed in the memo; it does not stop the work.

## Architectures

Search at least three families, each separately with its own parameter vector.

- **A. Joe's earlier concept, as a family.** Two AKH70 in a 45/45 differential about an anteromedial axis in the transverse plane, one pelvis-fixed (M1) and one thigh-mounted (M2), driving through cable drums with figure-8 routing, plus a rotation actuator of your choice. Parameterize it; there is no CAD of it to read.
- **B. A serial chain.** Two AKH70 on, or driving through a transmission to, the flexion-extension and ab-adduction axes, and your rotation actuator on the third, the three axes orthogonal or near-orthogonal.
- **C. One of your own.** Say why it might pack better than A and B before you search it.

A fourth family is optional. Discrete choices (bearing, variant, routing) are enumerated or encoded; say how.

## Score and search

Score = the sum over the hard terms of each violation in mm. Angles convert at a radius you state; the conditioning and ratio terms scale to mm by a factor you state. Zero is feasible. Feasible candidates rank by achieved skin margin, then by mass.

If the oracle is too slow for an inner loop (measured in G-P0), build a surrogate: trilinear interpolation of the cached signed-distance fields (`data/envelope/cache/<body>.npz`) for the skin, and analytic distances between primitives for clearances. The oracle is the final judge of everything ranked (G-P3).

Search with seeded scipy optimizers, several restarts per family. Compute cap: 45 minutes of wall clock per family. Run it in the background and do not watch it. Report evaluations, restarts, wall clock and the best-score trace.

## Gate criteria

Authored before the work. Each is reported pass or fail with its numbers. A criterion that looks wrong is a finding, not something to adjust.

### Checkpoint A: the harness

- **G-P0 Oracle and speed.** Confirm from the code that the oracle returns signed skin and component margins and the binding point. Report the time per evaluation of a 10-part candidate with the 590-pose sweep, for the oracle and for the surrogate if there is one. If a surrogate is used: on 50 random candidates, every surrogate margin agrees with the oracle's to within the body's voxel size (the oracle's own "marginal" line). Report the largest difference.
- **G-P1 Soundness**, each a test under `experiments/hip-packing/tests/`:
  - (a) a candidate you construct to be feasible (small primitives at interior points, clear of the reservations, confirmed by the oracle) scores exactly 0;
  - (b) a candidate with one part outside the skin and one overlapping a spine module scores positive and names both terms as binding;
  - (c) for each hard term, a mutation test: with that term zeroed, a candidate built to violate only that term scores 0;
  - (d) 20 perturbations of 0.5 mm or 0.5 degree about a candidate near the feasibility boundary each change the score by no more than one voxel size;
  - (e) two runs with the same seed produce byte-identical results.
  
  The provenance table is complete, or every gap is listed.
- **Stop rule.** A G-P1 check still failing after three fix attempts ends the session with a memo.

### Checkpoint B: the search

- **G-P2 Ranked near-misses.** Per family, the top 10 by score. Each comes with its parameter vector, part list, per-term violation and binding term, plus the smallest single relaxation that makes it feasible with everything else held: shell thickness t, wall, spine clearance, ROM degrees, and so on. Each also carries the reported quantities above. Mark a candidate `registration-sensitive` when its binding skin point lies within 25 mm of the hip plane (adr-0007 D5's joint zone, h = 25 mm): the pelvis and thigh bodies are 17 mm apart there in the model frames (adr-0007 D11, `rm.v1-hip-registration-decided`).
- **G-P3 Oracle verification.** The top 3 per family are rechecked through `fy envelope check`, and `foreign` for the sweep, with registries written under the experiment directory. The oracle's verdict is the result. A surrogate disagreement beyond one voxel is a finding.
- **G-P4 Pictures.** For the best candidate of each family: sagittal, coronal and transverse silhouettes of the parts inside the pelvis and thigh outlines, at neutral and at the binding pose (matplotlib, PNGs under the experiment directory).
- Feasible results are reported as feasible and not refined further.

## Memo

Use rule 6's form, shortened. The decision summary is about 10 lines: which family came closest and by how much, the binding constraint across families, what relaxation would make the best one feasible, and what you would try next. Then the gate table, then the detail. State every [design] choice and every tolerance you picked, and why. State your own mistakes plainly. Record the session's wall clock and how many times a gate check had to be fixed.

## Stop and ask before

- Adding a dependency.
- Editing anything outside `experiments/hip-packing/` on the branch.
- Extending the oracle.
- Changing t, the reservations, the clearances or the model's limits because a result looks wrong.
