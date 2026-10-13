# Stage 2d brief (for Claude Code): close the Stage 2 loose ends

Read `CLAUDE.md`, `CONVENTIONS.md`, `docs/OVERVIEW.md`, `docs/memos/memo10-retarget-pitch.md` (the decision summary, T4, T5 and the questions), `docs/memos/memo9-ankle-gain.md` and the Decisions block below. Stage 2c is done. This brief closes what memo10 left open, in two sessions. **This file authorizes Session 1 only (T0 to T7).** Session 2 is outlined at the end and is confirmed by a revised brief after Joe has read the memo of Session 1.

What Stage 2 still owes, and the design decision each item serves: the foot's pitch in stance (it decides whether the polygon evidence for the toe joint, and B's failure, are real; it serves `decisions/0001`); the knee excess in A (it decides the basis for sizing the knee actuator); the knee's moment, angle and speed envelope (Joe will size a custom frameless motor with a ballscrew and tune its lever arm to the joint's moment-angle profile, so a peak torque alone is not enough); the marker-based pelvic tilt (it serves the hip extension stop and the design pelvis pitch). T3 is tooling hygiene that T2 and T7 need. Flag anything in the session that serves none of these.

## Ground rules

CONVENTIONS section 9 and `CLAUDE.md` apply. Tests first, one commit per task, files staged by explicit path, every multi-line edit made with the editor tool and confirmed from the file before committing. Run the full suite before every commit that follows a change to a tracked output (`memo10` committed a regeneration without it). Stop and ask before changing the model, the sheet, the template, the mapping, any default or any band, except the one mapping change T2 authorizes under its stated trigger. Report, do not fix, any result that contradicts this brief. Summarise; do not print raw dictionaries into the session. Do not run the sheet watcher. Never edit the sheet, `docs/OVERVIEW.md` or `decisions/0001-toe-joint.md`.

## Decisions (Joe confirms by committing this brief)

- **Hip extension stop.** Joe has entered 31 degrees in the sheet's `freyja` column (observed maximum from the vertical, 28.1 degrees at 1.6 m/s, plus 10%), with a provenance note. 31 degrees is relative to the pelvis only for a vertical walking pelvis; relative to the dataset's IK pelvis the demand is about 37 degrees, which is an artefact of the IK frame, not a requirement. T7 measures what a human-like pelvis posture would change.
- **Waiver.** `check.mjcf.com_pct_stature` is confirmed by Joe in a separate commit; it should now report WAIVED.
- **Gate for closing Stage 2 (Joe's).** The knee excess is explained and, if the cause is the pipeline, fixed; if the cause is Freyja's own geometry, nothing is "fixed", the sizing basis is stated, and Joe decides. The foot pitch is measured and the polygon rerun. The final record, baseline, extract and envelope are regenerated once, at the final snapshot and final code. Then the tag.
- **Foot pitch.** Joe approves in advance one constant ankle offset in `camargo_mapping.yaml`, only under T2's trigger, with no other mapping change.
- **Toe.** Deferred until after the Stage 2 tag. `decisions/0001-toe-joint.md` stays `proposed`. No toe joint is added to the sheet, template or model in this stage.
- **Carried forward.** B and H stay unbaselined. The provisional flag stays on the `A_filtered` rows. The band is unchanged. The dataset-direct row and A are both reported for the knee; Code does not choose between them. The lumbosacral joint is sized for the human-like trunk mode, and its flexion torque (about 107 N m at the 95th percentile at 1.6 m/s) is reported as it is.

## Predictions of the planning chat (written before any Session 1 result; do not edit)

- **P1, foot pitch.** In single support at 30 to 60% of stance the model's sole is toe-up of flat by 3 to 8 degrees, and the dataset's foot (heel and toe markers, relative to each subject's static trial) is flat within 2 degrees; the pitch fix removed 2.6 degrees of toe-down that had been masking part of a constant offset. A difference below 1 degree would mean the polygon rates in memo10 are honest and its mechanism sentence is wrong.
- **P2, knee.** At the knee torque peak, force 0.97 to 1.02, foot and shank weight and inertia 0.99 to 1.01, the dataset's own plate-against-ID closure about 1.02, leg ratio 0.96, and a lever factor of 1.3 to 1.6. Sensitivity filter: at about 750 N (1.15 body weights of 65 kg) each 10 mm of horizontal offset between the knee and the force line is about 7.5 N m, so the excess of 19 to 36 N m at the 95th percentile needs 25 to 50 mm of lever difference; any candidate cause that explains less than about 15 mm cannot be the main one. The realised-reach knob removes less than half of the excess. More than half of the excess sits in the loading response (10 to 30% of stance).
- **P3, pelvis.** The markers give a walking pelvic tilt between 5 and 15 degrees anterior, so the hip extension demanded of a joint that keeps a human-like pelvis is about 10 to 18 degrees at the 95th percentile at 1.6 m/s, not 24.

Code writes its own predictions beside these before running anything.

## T0. Pre-flight (report; change nothing except the CLAUDE.md pointer)

Point the "Current brief" line of `CLAUDE.md` at this brief. List the commits since `37b0232`. Confirm Joe's two commits are there (the sheet and the waiver). Run `fy state` and report the new snapshot hash against `4db751576eb9`. Show that the snapshot differs only in the hip extension limit (and the model's stop, from -18.1 to -31.0 degrees); if anything else differs, stop and report. Run the full suite once. List every failing test or check with the reason; a test whose expectation encoded the old 18.1 degree stop is updated for that reason only, one commit, and listed in the memo. Report what `check.sim.walk_reference` and `check.sim.rom_reachable` say now.

## T1. Predictions first

Create `docs/memos/memo11-stage2d-diagnosis.md` with the three planning predictions copied verbatim under "Predictions (planning chat)", and Code's own predictions under "Predictions (Code)". Commit that file alone before T2.

## T2. Foot pitch (measure; apply one offset under the trigger)

Tests first, on synthetic input: a foot box at a known pitch gives that pitch; heel and toe markers at a known slope give that slope. Sign: toe-up positive. Then, over the 17 subjects at both speeds, single support only, by decile of stance: the model's sole pitch from the retargeted pose (confirm it is 0.0 degrees at `stand_static`), the dataset's heel-to-toe marker pitch relative to each subject's static trial, and their difference; plus the fraction of frames where each is more than 6 degrees off flat (the size at which the 25 mm polygon changes shape on a box of about 230 mm: 165 mm ahead of the ankle plus the rear length, which you state). **Trigger:** if the pooled mean difference over 30 to 60% of stance exceeds 1.0 degree in magnitude and the standard deviation of the subject means is below 2.0 degrees, add a constant offset equal to the negative of that mean (to 0.1 degree) to the ankle in `camargo_mapping.yaml`; if the mapping has no offset field, stop and ask. Test first that the mean difference then falls below 0.3 degrees. If the trigger does not fire, change nothing and say which of memo10's statements is wrong. Either way report the polygon rates by decile at both speeds against memo10's, and the effect of any offset on A's ankle and knee torques (expected negligible).

## T3. Polygon subcommand

`gait_diag.py polygon` fails with `KeyError: 'feasibility'` at line 331 because `build_results(...)[speed]` is keyed by trunk mode. Test first, then fix. Nothing else in that file changes.

## T4. Knee decomposition (report only; no fix in this session)

Do for the knee what `memo9` did for the ankle (`gait_diag.py ankle-gain`, `ankle_gain.py`), as a new subcommand or an option of it. At the knee torque-peak frame, both speeds, 95th-percentile strides and the geometric mean over strides: the factors force, foot and shank weight and inertia, the dataset's plate-against-ID closure, the leg ratio and the lever, with their product against the observed ratio. Split the force moment about the knee into the vertical-force term (vertical force times the horizontal offset) and the horizontal-force term (horizontal force times the knee's height above the force application), A against the dataset scaled, at the peak frame and by decile of stance, and say in which decile and in which direction (flexion or extension moment) the 95th-percentile excess sits. Counterfactuals with existing knobs only, each with the knee slope and the 95th percentile: the realised reach as the scale (memo9 found it 2.7 to 3.2% longer than the leg ratio implies), and `A_native` against `A_filtered`. A geometry table, Freyja at `stand_static` against the subjects as measured and as scaled: thigh length, shank length, knee height, ankle height, hip half-separation. State the lever difference in millimetres at the peak frame and how much of the excess in N m each candidate accounts for. If more than 30% of the excess stays unexplained, say so and stop; do not try fixes.

## T5. Knee envelope for actuator sizing (report only)

For the dataset-direct row (the dataset's own knee moments scaled to Freyja by mass ratio and leg-length ratio, with the dataset's own angles and speeds scaled likewise) and for `A_filtered`, both speeds, state the sign convention and units, then report: the peak moment in each direction; peak angular speed; peak positive and negative mechanical power; the knee angle range used (95th percentile and maximum). Then, per 5 degree bin of knee flexion angle: the number of frames, the median, 95th-percentile and maximum moment in each direction, the angular speed at the frames of the 95th-percentile moment, and the maximum absolute speed. Finally the distribution (5th, 50th and 95th percentile) of the knee angle at which each stride's peak moment occurs. Memo only; stop and ask before adding any tracked artefact or schema.

## T6. Pelvic tilt from markers (report only)

From the pelvis markers in the raw archives (state which markers you use; the marker cache is gitignored), the absolute pelvic tilt, static and walking, per subject, against the IK pelvis pitch; and the hip extension relative to the marker-defined pelvis (95th percentile and maximum, both speeds) beside the 24.1 and 28.1 degrees from the vertical. If the markers are not in the archives, say so and skip.

## T7. Memo and lists

Complete `memo11-stage2d-diagnosis.md`: first line the STATE line, then the decision summary required by `CLAUDE.md` rule 6, then the findings with numbers, every tolerance chosen and why, which prediction held and which did not (the planning chat's and your own), your mistakes plainly, and the questions for Joe. List each sentence in `OVERVIEW.md` and `decisions/0001-toe-joint.md` that these numbers change, with a proposed replacement; edit neither file. Stage the memo before the final `fy state`.

## Done when

Suite green offline, tree clean, memo staged and `fy state` run last, no raw data tracked, and the final message opens with the STATE line and the decision summary. No record, baseline, extract or envelope is regenerated in this session, except as T2's trigger or T0's test updates strictly require.

## Session 2 (outline; confirmed by a revised brief after Joe reads memo11)

Apply Joe's decisions on the knee and the foot; any fix to the pipeline with its tests; then regenerate once, at the final code and snapshot: the gait record, the baseline, the extract, `GAIT.md` and `ENVELOPE.md`, the three scenario runs and the digest; verify from a clean clone that the envelope reproduces byte for byte; write the closing memo with the Stage 2 gate checklist; stop for Joe to tag `stage2-closed`.
