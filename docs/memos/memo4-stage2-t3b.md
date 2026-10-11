Steps 0 to 4 are done and committed at `dee54b0`. The working tree has no uncommitted files other than the output.

**Answers to your two questions**
- **Lateral CoM force:** your suspicion was right. With a rigid trunk, Freyja's lateral force has 1.4 to 2.3 times the measured peak-to-peak and correlation about zero (+0.17 to −0.08). The cause is the trunk (abdomen, thorax, head), which follows the pelvis's roll and yaw. Its share is 179 to 245 N peak-to-peak and anti-correlated with the measured force (−0.4). Legs and pelvis correlate well (+0.58 to +0.83). If the lumbosacral lateral and axial joints cancel the pelvis roll and yaw (a diagnostic variant only, not adopted), the total lateral force correlates +0.76. Its peak-to-peak is 168 N against 139 N measured.
- **Tilt-offset asymmetry:** it entered as a roll, and that was a bug of mine. In this lab the ground z axis is the walking direction, so the dataset's `pelvis_tilt` is the pelvis roll and `pelvis_list` is its sagittal pitch. My offset acted on the roll, which is why right and left hip ab/adduction and ankle inversion moved opposite ways while the sagittal torques didn't. The offset now acts on `pelvis_list` (positive = anterior), with tests, including one that it leaves roll unchanged.

**Step 0: method A against the dataset's moments (1.4 m/s, 51 strides)**
- **Reference point:** the dataset's hip centres sit 54 to 77 mm behind its pelvis origin. Freyja's sit 57 mm ahead of hers, and 97.5 mm below it. Referencing both the root translation and the measured CoP to the hip-centre midpoint is what fixed A.
- **Result:** A (filtered) now meets your targets for hip, knee and ankle (correlation 0.91 to 0.995, RMS 10.9 to 14.7% of peak-to-peak). A (native force) misses narrowly. Hip is 0.845 and 16.5%, and knee is 0.898 and 13.3%. I attribute that to impact-transient content, which is the native-versus-filtered gap the brief said to expect.
- **Foot-frame CoP (step 0c):** I ingested heel and toe-tip markers and placed the measured CoP at the same normalised place on Freyja's foot. Agreement is about the same as the hip-reference version, so keep either.
- **Mean pelvis pitch:** A only reaches the targets if the dataset's measured mean pitch is kept. Replacing it with the design parameter dropped knee correlation to 0.57 and ankle RMS to 50%. The subjects' mean `pelvis_list` ranges from 0.7° to 14.4° (mean 7.8°), which moves the legs' world position by centimetres. I added `pitch_mean` (design or measured). Verification must use measured, which conflicts with your T2b default (design). Which do you want for design loads?

**Steps 2 to 4 (rms of whole-body CoP error vs measured, mm; trunk rigid / trunk compensated)**
- **Step 2:** the point-mass term carries most of the error (single support at 1.4 m/s). Lateral: full error 210 / 79, point-mass-only 154 / 73, angular-momentum term 62 / 18. Fore-aft: full 105 / 103, point-mass-only 85 / 81, angular-momentum term 44 / 45. So the fore-aft error (about 100 mm) is mostly CoM position and is untouched by the trunk fix. The lateral error is mostly the trunk. The same pattern holds at 1.6 m/s.
- **Step 3:** the proportional split is off by 0.24 RMS from the measured share. A feasible split exists in only 0 to 2% of double-support frames, and the measured share falls inside it in under 1%. The measured-share variant doesn't help feasibility (86 to 96% outside).
- **Step 4:** I used a 25 mm segment band, named `SEGMENT_TOL_M` and set equal to the hull band. The measured CoP mapped onto Freyja's foot is outside the polygon in 32 to 43% of single-support frames (median 12 to 14 mm outside) and 72 to 75% of double-support frames (median 42 to 51 mm). With the band it is 19 to 27% and 56 to 66%. B, at 1.4 m/s with trunk rigid / compensated, is outside in 88.5% / 64% of single-support and 95% / 93% of double-support frames, with medians of 138 / 42 mm and 94 / 74 mm. The measured CoP fails the rigid box too, so the box test is harsh, particularly in double support. B is still clearly worse than the measured baseline, though the trunk fix closes much of the single-support gap.

**Not yet answered:** the next step in your order is swing-leg inertia, segment masses and foot lateral placement. I haven't started it. T6 and T7 are untouched.

**Decisions for you**
1. Should the trunk counter-roll and counter-yaw replace the rigid-trunk assumption for B? It fixes the lateral force but departs from "upper body held rigid".
2. Pitch mean: measured for verification and design for loads, or one for both?
3. Should the double-support rule stay as is, given that it is infeasible almost everywhere and the measured share doesn't rescue it?
4. Does the 25 mm segment band suit you?
