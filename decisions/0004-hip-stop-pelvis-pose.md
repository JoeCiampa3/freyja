---
id: adr-0004
status: accepted
date: 2026-10-19
links: []
---
## Context

Memo 12 asked for the hip extension stop and the design pelvis pitch to be decided together. Memo 23 (D2, D3) supplies what that needs, and it changes the question.

- **The sheet's pelvis frame is the Dumas frame.** Its Joint Definitions sheet states that the pelvic coordinate system is Dumas's pelvis SCS exactly, and the MuJoCo Reference sheet transforms the ISB axes (X forward, Y up, Z right) to MuJoCo's (x, -z, y). The pelvis geometry (the hip centre 54 mm forward and 93 mm below the lumbosacral joint at Dumas's reference scale, 56.6 and 97.5 mm now), every hip angle, and the hip range rows (the 18.1 degree Soucie extension ceiling and the 31 degree Freyja target) are in that frame. The reference pose is ISB anatomical neutral, all angles zero.
- **The dataset's pelvis frame is a different one.** In the 17 static trials the Dumas-frame pelvic tilt is 12.43 degrees anterior (SD 3.90, range 7.21 to 19.87) and the inverse-kinematics pelvis pitch is -1.14 degrees (SD 3.11). The IK frame sits 13.57 degrees (SD 2.62) posterior of the Dumas frame (memo 23, D2).
- **The retargeting applies the dataset's pelvis orientation to the model's pelvis body, and the dataset's hip angles to the hinges, with no offset between the two frames** (`pelvis_pitch_offset_deg` is 0; memo 23, D9 v). Two consequences.
  - **The hip extension finding is a frame artefact.** Per-stride peak hip extension, median / 95th percentile / maximum, degrees (memo 23, D3):

    | speed (m/s) | IK pelvis (what the stop was compared with) | Dumas (marker) pelvis | vertical |
    |---|---|---|---|
    | 0.5 | 13.9 / 29.2 / 32.7 | -1.4 / 12.6 / 16.3 | 9.1 / 14.6 / 16.3 |
    | 1.4 | 23.3 / 37.3 / 39.4 | 6.4 / 17.9 / 20.7 | 16.9 / 22.0 / 25.3 |
    | 1.6 | 24.3 / 36.4 / 38.2 | 8.4 / 17.6 / 20.6 | 20.3 / 24.1 / 28.1 |

    Against the 31 degree stop, 2.4%, 36.7% and 43.9% of strides are beyond it in the IK frame and none are in the Dumas frame or against the vertical. The "85% beyond the 18.1 degree stop" of memo 6 was measured in the IK frame too.
  - **The pelvis assembly sits 13.6 degrees too far back in the model** (derived, not yet measured in a run). The hips are placed from the data, so the thighs are right in the world. But the lumbosacral joint, and the trunk on it, are placed from the pelvis body's orientation. At the current scale the hip centre is 58.6 mm forward and 96.4 mm below the lumbosacral joint in the model against 34.3 and 107.5 mm in a standing subject (Dumas tilt 12.43 degrees), a difference of 24 mm forward and 11 mm up. The trunk base is therefore 24 mm further behind the hips than in the human. With 45% of the body mass above the lumbosacral joint that moves the whole-body centre of mass about 11 mm backward relative to the hips (about 7 N m static at the hips). Whether this explains part of method B's 73 to 76 mm backward centre-of-pressure offset is not known; the Stage 2g brief measures it before the change is adopted.
- **There is no pelvis pitch quantity in the sheet, the snapshot or the preprocessor.** `stand_static`'s root pitch of 2.608 degrees is a result of the lean solve (centre of mass over the ankle), not a pelvic tilt.

## Decision

Joe to confirm each point; the values are my recommendation.

1. **The model's pelvis frame is the Dumas frame** (confirmed by the sheet, in MuJoCo coordinates). The dataset's IK pelvis frame is reconciled to it in the retargeting, not the other way round: Freyja's pelvis geometry stays in the frame the BSIP data, the hip-centre regression and the CAD use.
2. **Frame offset.** The retargeting adds a per-subject offset delta to the dataset's pelvis tilt and to its hip flexion, sagittal only. delta is the subject's static Dumas tilt minus its static IK pitch (mean 13.57 degrees, SD 2.62), measured by the ingestion from the static trial and stored beside the processed arrays. The thigh's world orientation, the hip centre's world position and every other joint are unchanged; the pelvis body takes the human's Dumas-frame orientation. This is adopted only after the Stage 2g brief's experiment (T1) shows its effect on `A_filtered`'s agreement and on B's offset, and Joe accepts it at Checkpoint A.
3. **Design pelvis tilt.** The standing reference pose has the pelvis tilted 12.0 degrees anterior in the Dumas frame (the dataset's static mean, 12.43, rounded), the hips flexed 12.0 degrees, the thighs vertical, and the lumbosacral joint extended 12.0 degrees so that the trunk stack is vertical. It is a sheet input, `stand_pelvis_tilt_deg`. The ankle is set by the existing lean solve.
4. **Hip extension stop: keep 31 degrees, and say what it is.** It is a margin over Dumas-frame walking demand (maximum 20.7 degrees at 1.4 m/s, 20.6 at 1.6, 16.3 at 0.5), not a match to it, and it is about the 97.5th percentile of the anatomical ceiling (Soucie 2011, female 20 to 44: 18.1 degrees, SD 6.6; 18.1 + 2 x 6.6 = 31.3, my arithmetic). The Joint ROM sheet's note on the row names the frame (Dumas pelvic frame, ISB).

## Consequences

- The retargeting, the ingestion (an additive per-subject key) and the stand pose change; all gait numbers regenerate once, at `rm.v1-stage2-closed`.
- `A_filtered`'s agreement with the dataset at the hip, knee and ankle can move either way. If the band verdict at 1.4 or 1.6 changes class, the brief stops and reports; the band constants are not touched.
- Hip extension in every later document is quoted in the Dumas frame with the frame named. The "36.7% beyond the stop" figure is retired.
- With the pelvis tilted 12.0 degrees in standing, the stature stack closes within about 5 mm instead of 14.7 (record 0038 closes it on vertical heights).

## Rejected options, and why each one died

**Leave the frames unreconciled.** The status quo: the hip stop is argued against the wrong frame, the trunk base is 24 mm too far behind the hips, and every hip angle quoted in a memo or the sheet is ambiguous by 13.6 degrees.

**Rotate Freyja's pelvis geometry into the IK frame.** Rejected: it would break the single frame the sheet, the BSIP table, the hip-centre regression and the CAD all share, and the offset is a property of the OpenSim pelvis definition, not of Freyja.

**Lower the stop to match Dumas-frame demand (about 21 to 25 degrees).** Not chosen: a stop costs nothing in the model, stairs and other tasks are not covered by the walking data, and I have not checked whether the frozen hip mechanism depends on 31 degrees. Check that before reducing it; revisit if the hip's mechanical design wants the range back.
