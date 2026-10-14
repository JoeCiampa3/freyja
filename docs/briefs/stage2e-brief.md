# Stage 2e brief (for Claude Code): close Stage 2

Read `CLAUDE.md`, `CONVENTIONS.md`, `docs/OVERVIEW.md`, `docs/memos/memo11-stage2d-diagnosis.md` (the decision summary, T2, T4, T5, the lists and the seven questions), `docs/memos/memo10-retarget-pitch.md` (T5) and the Decisions block below. This brief authorizes one session, T0 to T9, which ends in one regeneration and the closing memo; Joe tags `stage2-closed` after reading it. Stage 2d session 1 is done.

What this session serves, item by item. The ankle offset field and the decile fix serve the polygon evidence behind `decisions/0001` and the integrity of every by-stance table. The knee audit (T5 to T7) serves the sizing basis of the knee actuator: Joe will size a custom frameless motor with a ballscrew and tune its lever arm to the moment-angle profile, so he needs to know how far the knee moment depends on the thigh to shank split. The hard-coded constants serve the reliability of the diagnostics. The regeneration serves the Stage 2 gate. Flag anything that serves none of these.

## Ground rules

CONVENTIONS section 9 and `CLAUDE.md` apply. Tests first (including for report logic, not only for helpers), one commit per task, files staged by explicit path, multi-line edits with the editor tool confirmed from the file before committing, the full suite before every commit that follows a change to a tracked output. Stop and ask before changing the model, the sheet, the template, any default or any band; the one mapping change authorized is T3's offset field. Report, do not fix, any result that contradicts this brief. Summarise; do not print raw dictionaries into the session. Do not run the sheet watcher. Never edit the sheet, `docs/OVERVIEW.md` or `decisions/0001-toe-joint.md`. After the final `fy state`, stage `docs/STATE.md` together with the memo and leave both staged for Joe to commit in one commit.

## Decisions (Joe confirms by committing this brief; each line is a one-line revert)

- **Foot offset.** Joe approves adding a constant per-joint offset field to `camargo_mapping.yaml`, read by `retarget.Cycle`, documented as the convention difference between the dataset's OpenSim ankle zero and Freyja's, with a test. It is used for the ankle only. **Value:** the criterion is "flat on the plate": the offset that makes the mean model sole pitch 0.0 degrees over single-support frames at 20 to 40% of stance counted from heel strike, pooled over the 17 subjects, at 1.4 m/s. The dataset's heel and toe markers relative to each subject's static trial are the cross-check, not the target (markers sit on shoe and skin and read -1.7 and -2.4 degrees at 30 to 60%). Default -3.4 degrees (memo11's recommendation): use -3.4 if the criterion gives a value within 1.0 degree of it, otherwise use the criterion's value and report both. Round to 0.1 degree.
- **Decile defect.** Fix `pushoff`'s binning so that each foot's stance is counted from its own heel strike, including a stance that wraps the stride boundary, and audit every other table that bins or flags stance (`gait_diag.py`, `knee_gain.py`, `ankle_gain.py`, the extract): in particular T4's knee deciles and T5's stance flags, since the knee gap was localised by decile.
- **Knee.** Joe wants both the 95th percentile and the maximum reported, for A and for the dataset-direct row, at both speeds and under each exclusion set (`all`, `without_offset`, `without_pitch_flagged`). Joe intends Freyja's own geometry to be the basis in the end, but not before the thigh to shank split is verified. Until then the bracket stands, Code chooses nothing, and neither row is declared the basis. For reference, Winter's appendix A has a peak knee moment of 55 N m at 56.7 kg (63 N m scaled to Freyja): the dataset-direct row is near it; A's 95th percentile is 1.5 to 1.75 times it and A's maximum 2.5 to 2.7 times.
- **Hip stop.** 31 degrees stays in the sheet, with Joe's note. Nothing for Code to change except the hard-coded 18.1 in `hipext` (T2).
- **Envelope test.** `test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce` stays failing until T8 regenerates; it must pass at the end.
- **Carried forward.** The toe joint is deferred until after the tag, and `decisions/0001-toe-joint.md` stays `proposed`. B and H stay unbaselined. The provisional flag stays on the `A_filtered` rows. The band is unchanged. The lumbosacral joint is sized for the human-like trunk mode.

## Predictions of the planning chat (written before any result; do not edit)

- **P1, offset.** The criterion gives a value between -2.0 and -3.4 degrees; with it, the single-support polygon failure rates at 10 to 50% of stance (1.4 m/s) are 15 to 25%.
- **P2, deciles.** The knee gap's localisation survives the corrected binning: more than 60% of the 95th-percentile excess is still in 10 to 30% of stance. The wrap affects the left limb's binning only.
- **P3, tails.** Geometry scales every stride alike (about 1.37 at the 95th percentile), so a maximum of 112 to 131 N m would be geometry; the observed 158 and 171 N m are not. A's maximum falls by more than 20% at one or both speeds without the offset subjects (AB13, AB15), and A's maximum to 95th-percentile ratio stays above the dataset-direct row's (about 1.2) in every exclusion set.
- **P4, split.** The 17 OpenSim thigh to shank ratios have a mean of 0.883 and a between-subject standard deviation of 0.03 to 0.06. A shank length from the epicondyle and malleolus markers (if the marker set has them) lies between 410 and 435 mm; a regression hip centre gives a thigh of 375 to 410 mm. The audit narrows the uncertainty to about 15 mm of knee-centre position and does not decide between 0.883 and 0.977.
- **P5, sensitivity.** A's knee 95th percentile changes by 0.5 to 0.9 N m per millimetre of thigh length at fixed thigh plus shank; at a ratio of 0.883 it is within 10% of the dataset-direct row's.
- **P6, constants.** At least two more values duplicated from the sheet or the spec are hard-coded in `gait_diag.py`, `ankle_gain.py` and `knee_gain.py` besides the 18.1.

Code writes its own predictions beside these before running anything.

## T0. Pre-flight (report; change nothing except the CLAUDE.md pointer)

Point the "Current brief" line of `CLAUDE.md` at this brief. List the commits since `402e4281f525`; confirm the memo11 commit and the STATE commit are in. Run `fy state`. Run the full suite and confirm the envelope test is the only failure.

## T1. Predictions first

Create `docs/memos/memo12-stage2-close.md` with the planning predictions copied verbatim under "Predictions (planning chat)" and yours under "Predictions (Code)". Commit that file alone.

## T2. Hard-coded constants

`gait_diag.py hipext` prints a hard-coded 18.1 degree stop (line 959 at the time of memo11). Read the stop from the loaded model's joint range. Test first: the printed stop equals the model's range, and changes when a throwaway model's range changes. Then list every numeric literal in `gait_diag.py`, `ankle_gain.py`, `knee_gain.py` and `gait_extract.py` that duplicates a value in the sheet, the spec, the mapping or the model (state each with its source). Replace those where the object is already loaded; list the rest. No sheet parsing is to be added.

## T3. The offset field

Tests first: the field is optional and defaults to zero (every existing result unchanged to 1e-9); a synthetic IK with a given offset shifts the model's ankle angle by it and nothing else; the sign convention is stated in the mapping's comment. Apply the criterion above and report the value, the marker cross-check, and the pooled and per-subject spread. Report the polygon rates by decile with and without it (after T4's binning fix), and the effect on A's ankle and knee torques over all 988 strides (not two subjects).

## T4. The decile defect

Tests first: a synthetic stance that wraps the stride boundary is binned from its own heel strike. Fix `pushoff`, apply the audit above, and restate, from the corrected code, memo10's and memo11's decile tables and the figures quoted in the lists for `OVERVIEW.md` and `decisions/0001-toe-joint.md`. Report which tables were affected and which were not.

## T5. The knee's tails (report only)

For A and for the dataset-direct row, both speeds, all three exclusion sets: the knee extension moment's 95th percentile and maximum, the maximum to 95th-percentile ratio, and the ten largest strides of A (subject, stride, limb, stance percent of the peak, the moment, and which of force, lever and inertia term carries it relative to the same stride's dataset-direct value). Say whether the tail comes from the loading-response force transient, the CoP at low load, the 6 Hz filter or one subject's geometry.

## T6. Where the thigh to shank split comes from (dataset side only; report)

(a) Inventory what the dataset provides: the marker set (names the epicondyle, malleolus and pelvis markers if present), any measured segment or leg lengths in the subject data, and the OpenSim models' hip, knee and ankle centres. (b) Per subject and pooled: the OpenSim thigh and shank lengths and their ratio (minimum, median, maximum, standard deviation across the 17), so that the between-subject spread is on the table. (c) If the epicondyle and malleolus markers exist: the knee centre as the midpoint of the epicondyle markers and the ankle centre as the midpoint of the malleolus markers in the static trial, hence a direct shank length per subject beside the OpenSim one. (d) A regression hip centre from the pelvis markers (name the regression and its published error), hence a thigh length per subject beside the OpenSim one. (e) The sum thigh plus shank against Freyja's 804.5 mm. State plainly what the audit can and cannot decide.

## T7. Knee sensitivity to the split (report only; scratch model)

On a throwaway modified copy of the generated MJCF kept outside the repository (no change to the sheet, template or tracked model), move the knee along the hip to ankle line so that thigh plus shank is fixed and the thigh to shank ratio takes the values 0.883, 0.935, 0.977 and 1.0, scaling the segments' centre-of-mass offsets with their lengths (say how). Report A's knee 95th percentile and maximum, both speeds, and the slope against the dataset per kg. If this needs more than a small script, say so and skip it.

## T8. Regenerate once

At the final code and snapshot: the gait record, the baseline (`A_filtered` must meet the band at both speeds before it is written; B and H are not baselined), the extract, `GAIT.md` and `ENVELOPE.md`, the three scenario runs and the digest. Verify from a clean clone that `ENVELOPE.md` reproduces byte for byte. The envelope test and the full suite must pass.

## T9. Closing memo

`docs/memos/memo12-stage2-close.md`: first line the STATE line, then the decision summary required by `CLAUDE.md` rule 6, then a Stage 2 gate checklist (each item, its status, the memo or commit that shows it: retargeting fix, foot pitch and polygon, knee explained and the basis stated, hip stop and pelvis, lumbosacral rows, regeneration, clean clone, waiver, open decisions that remain Joe's), then the findings with numbers, every tolerance chosen and why, which predictions held and which did not (the planning chat's and your own), your mistakes plainly, and the questions for Joe. Include the updated lists of sentences in `OVERVIEW.md` and `decisions/0001-toe-joint.md` that the regenerated numbers change, with proposed replacements. Edit neither file.

## Done when

Suite green offline, tree clean apart from the staged memo and `docs/STATE.md`, no raw data tracked, the clean-clone check done, and the final message opens with the STATE line and the decision summary.
