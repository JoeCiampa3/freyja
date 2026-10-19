# Memo 23: Stage 2 diagnostics ahead of the snapshot change (D1 to D9)

STATE: base a11d2b1b555a | brief architecture sha256:2ecf3ee5c019, ariadne sha256:1ac4d746673a | snapshot sha256:e5cc96ceed7e | tests 1377/1377 | dirty no

## Decision summary

- Read-only run on snapshot e5cc96ceed7e (model c4d7757d45fe). Nothing in the model, template, sheet, preprocessor, spec or any tracked output changed. One commit, analysis code and its tests only: `a11d2b1` (`sim/scripts/snapshot_diag.py`, `tests/test_snapshot_diag.py`; suite 1377 passed in 374 s).
- **The static trials cannot give a measured ankle joint centre.** The marker set is lower limb and pelvis only; the medial malleolus exists for one subject of 17 (AB15). I used the OpenSim model's ankle centre instead, which is a uniformly scaled generic landmark, so its tight spread (fraction 0.682, SD 0.007) says nothing about anatomy. The one measured check (AB15) puts mid-malleoli 20 to 39 mm from the model's centre.
- **Foot, dataset markers (shoe markers, 17 subjects), at Freyja's scale (1.70 m):** ankle centre 66 mm behind the heel marker, 141 mm to the toe-tip marker, 130 mm to the model's MTP joint; heel to toe-tip marker 206 mm. Freyja's box today: 41 mm behind, 165 mm ahead, 206 mm long. ANSUR II women scaled to 1.70 m: foot length 257 mm, ball-of-foot length 190 mm. The markers span 80% of the anatomical foot length, so the 206 mm agreement with the box is a coincidence of the marker placement, not a validation.
- **Pelvic tilt in standing (Dumas frame, anterior positive): 12.4 deg, SD 3.9 across subjects (7.2 to 19.9).** The IK pelvis pitch in the same trials is -1.1 deg (SD 3.1). The two frames differ by 13.6 deg (SD 2.6). Freyja's stand_static pelvis pitch is +2.608 deg.
- **Hip extension against the 31.0 deg stop** (dataset IK, per-stride peak): relative to the IK pelvis 2.4%, 36.7% and 43.9% of strides are beyond it at 0.5, 1.4 and 1.6 m/s; relative to the vertical 0% at all three (maxima 16.3, 25.3, 28.1 deg); relative to the marker (Dumas) pelvis 0% as well (maxima 16.3, 20.7, 20.6). Whether the stop binds depends entirely on which pelvis the 31 deg is measured from.
- **Lumbosacral rigid lateral torque maxima are single strides, not the bulk:** 0.5 m/s is AB23 stride 0 at 139.2 N m, 2.35 times the p95 (next largest 79.2); 1.4 is AB11 at 112.3 (1.21 times); 1.6 is AB15 at 177.2 (1.60 times), and 16 of the 26 strides above its p95 are AB15's.
- **The stamps are dirty.** The tracked extract and record 1424 both say `git_dirty: true`, `diff_sha256` 38a282fc2528. Neither is reproducible from a clean clone by its own stamp.
- Decisions for you: (1) the AJC, MTP and heel positions for the next brief should come from ANSUR II plus a stated posture, not from the dataset's shoe markers (recommended); (2) say which pelvis frame the sheet's hip extension of 31 deg refers to, before the stop and the design pelvis pitch are fixed together (the 36.7% to 0% difference is this choice); (3) `.gitignore` already contains `data/ansur2/raw` (commit a681cb0), so I made no commit for it; say if you want the trailing-slash form anyway.
- What would change the conclusion: an independent ankle-centre measurement (a second subject with both malleolus markers, or a model fit to the malleoli) that moves the centre more than the 20 to 39 mm seen in AB15; or a different pelvis definition in the sheet.

## Findings

1. **D1 relies on a model landmark, not a measurement** (above). The foot-frame method and all numbers are in D1.
2. **A bug of mine, fixed before any number was used:** `foot_geometry` picked the heel and toe-tip markers by name suffix across both feet, so it could take the other foot's. The first run printed AB15 with an ankle centre 150 mm behind the heel; the cause was found (AB15's feet are far apart in its static trial), a regression test was written red first, and all D1 numbers here are from the corrected code.
3. **The dataset's pelvis frame sits 13.6 deg posterior to the ASIS-PSIS (Dumas) frame** (D2). That offset is larger than any hip, tilt or lean number in the earlier memos that compares the two without saying so.
4. **ADR 0001 open item 1 is partly answered** (D1, D8): the sheet's 165 mm (ankle centre to the midpoint of the first and fifth metatarsal heads) is longer than every reading of the same landmark from data: 130 mm (model MTP, dataset scale 1.70) and 108 to 123 mm (ANSUR ball-of-foot length 190 mm minus the ankle's distance from the heel, 82 or 67 mm).

## D1: foot geometry, 17 subjects, static trials

Markers present in the static trials (all 17): ASIS, PSIS (R, L); Heel, Toe_Tip, Toe_Lat, Toe_Med, Ankle_Lat; Knee_Lat; thigh and shank clusters (Upper, Front, Rear). Ankle_Med and Knee_Med exist for AB15 only. No metatarsal-head marker by that name: Toe_Lat and Toe_Med are forefoot markers (their midpoint is 179 mm ahead of the heel marker, 87% of the foot length, 16 mm short of the toe-tip marker), and the heel and toe-tip markers sit on the shoe, so they are not pternion and acropodion.

Method (`snapshot_diag.py foot`): each subject's OpenSim model gives the ankle centre and the MTP joint in the calcaneus frame (talocrural centre = subtalar child offset - subtalar parent offset + ankle child offset, subtalar angle 0; static IK subtalar angle is -0.3 to 0.2 deg, bounding the error at 0.07 m x 0.005 rad = 0.4 mm). The four foot markers (Heel, Toe_Lat, Toe_Med, Toe_Tip) are fitted rigidly (Kabsch, proper rotation) from the calcaneus frame to the static pose; fit RMS under 1 mm for all 34 feet, because the model's markers were placed from this trial. Forward is the horizontal heel-to-toe-tip direction, up is the lab vertical. Right and left feet are averaged per subject; the right-left foot length difference is -7.4 to +11.3 mm.

mm (fraction where stated), over 17 subjects:

| quantity | mean | SD | min | max |
|---|---|---|---|---|
| foot length (heel to toe-tip marker, along forward) | 206.9 | 10.6 | 186.5 | 223.5 |
| ankle centre ahead of heel marker | 65.8 | 3.7 | 58.4 | 70.9 |
| ankle centre to toe-tip marker, forward | 141.2 | 7.4 | 126.1 | 154.3 |
| ankle centre to toe-tip marker, 3D | 141.7 | 7.3 | 126.3 | 154.6 |
| ankle centre to model MTP, forward | 130.0 | 7.7 | 117.2 | 142.6 |
| ankle centre to model MTP, 3D | 137.4 | 7.6 | 123.7 | 150.2 |
| ankle centre to heel marker, 3D | 68.8 | 4.2 | 61.8 | 75.6 |
| ankle centre above heel marker | 19.2 | 5.5 | 9.5 | 30.7 |
| ankle centre above toe-tip marker | 10.2 | 5.5 | -1.8 | 19.0 |
| ankle centre to toe tip / foot length (forward) | 0.682 | 0.007 | 0.668 | 0.692 |
| ankle centre to MTP / foot length (forward) | 0.628 | 0.009 | 0.607 | 0.639 |
| ankle centre above lab y = 0 | 51.9 | 6.5 | 41.6 | 63.6 |
| lateral malleolus marker ahead of heel marker (measured) | 53.9 | 5.6 | 42.0 | 62.2 |
| lateral malleolus marker above y = 0 (measured) | 70.1 | 6.4 | 57.7 | 83.7 |

The 0.007 and 0.009 SDs are the OpenSim scaling (one factor on a generic foot), not anatomical variation. The measured lateral malleolus marker is 0.260 of the foot length ahead of the heel (SD 0.020), against 0.318 for the model's centre: the model puts the ankle 12 mm further forward than the malleolus marker, which is expected for a point at the middle of the ankle rather than on the lateral surface, but the sign and size are not verified.

AB15 (only subject with both malleolus markers): malleolar breadth 95 mm right, 92 mm left; mid-malleoli to the model's ankle centre 39.3 mm right, 19.6 mm left; mid-malleoli ahead of the heel 79 and 69 mm against the model's 66 and 72; mid-malleoli above the model centre by 37 and 17 mm. n = 1; it is a warning, not a statistic.

**At Freyja's scale.** Rule: each subject's length x (Freyja's 1.70 m, `target_stature`) / (that subject's stature), then mean and SD over subjects. The dataset's mean stature is 1.706 m, so the scaled values differ from the unscaled by under 1 mm.

| at 1.70 m | mean mm | SD | range |
|---|---|---|---|
| ankle centre behind heel marker | 65.5 | 2.4 | 60.9 to 69.2 |
| ankle centre to model MTP (forward) | 129.6 | 5.4 | 114.1 to 138.1 |
| ankle centre to toe-tip marker (forward) | 140.8 | 5.0 | 126.1 to 148.2 |
| heel marker to toe-tip marker | 206.3 | 6.7 | 188.1 to 216.2 |

Freyja's box now: 41 mm behind the ankle (`FOOT_REAR_FRACTION` 0.25 of 165), 165 mm ahead, 206 mm long.

## D2: static pelvic tilt

Dumas frame as in `snapshot_diag.dumas_pelvic_tilt_deg`: Z from the left to the right ASIS; X in the plane of the ASIS and the PSIS midpoint, perpendicular to Z, forward; tilt = dip of X below the horizontal, **anterior positive** (ASIS below the PSIS plane). Independent of the facing direction. Static trial frames per subject: 299 to 5051. Within-trial SD 0.07 to 0.81 deg (mean 0.18).

Over 17 subjects: mean **12.43 deg, SD 3.90, range 7.21 (AB12) to 19.87 (AB13)**. The line-based tilt already in `gait_diag.marker_pelvic_tilt_deg` agrees (12.42; Dumas minus line +0.01, SD 0.04), so the earlier marker numbers stand.

Against the IK pelvis: the dataset's pelvis pitch is minus `pelvis_list` (mapping `pelvis_pitch: {coordinate: pelvis_list, sign: -1}`). Static `pelvis_list` mean +1.14 (SD 3.11), i.e. IK pitch -1.14 deg. Dumas tilt minus IK pitch: **+13.57 deg, SD 2.62**, correlation of the two +0.74. So the IK pelvis frame is rotated about 13.6 deg posterior to the ASIS-PSIS frame, with 2.6 deg of subject-to-subject scatter. Per subject (Dumas / IK pitch / difference): AB11 9.1 / -6.4 / 15.5; AB13 19.9 / 5.0 / 14.9; AB19 7.3 / -1.0 / 8.3 (smallest); AB12 7.2 / 0.3 / 6.9 (also small). The manifest's `static_pelvis_pitch_deg` equals the IK pitch to the digit.

The model: `stand_static` root pitch **+2.608 deg** (forward lean positive), equal to its ankle angle. The retargeted walking cycle uses the dataset's pelvis rotation as the root orientation without adding that lean (Stage 2c). The model's pelvis frame is the root frame, identity at neutral; the repo does not contain what pelvis landmark plane that frame corresponds to. If Freyja's pelvis frame is the Dumas frame, 0 in the model is 12.4 deg anterior of where a standing subject's IK pelvis sits ("-1.1" plus 13.6), and stand_static's 2.608 deg is a lean of the body, not a pelvic tilt in any anatomical sense. That is an inference, not measured. I found no sheet or snapshot key for a pelvis pitch (`params/snapshot.csv` has none; the pelvis row carries mass, length, CoM, inertia, position and `jpos_z` only).

## D3: hip extension demand against the stop

Stop read from `freyja.xml` (`hip_fe_right` lower range): **31.00 deg**. Dataset IK, no retargeting, per-stride peak over both limbs. Reproduces memo12's 0.37 at 1.4 (36.7%).

| speed | strides | reference | beyond stop | median | p95 | max |
|---|---|---|---|---|---|---|
| 0.5 | 297 | pelvis (IK) | 7 = 2.4% | 13.9 | 29.2 | 32.7 |
| 0.5 | 297 | vertical | 0 | 9.1 | 14.6 | 16.3 |
| 1.4 | 469 | pelvis (IK) | 172 = 36.7% | 23.3 | 37.3 | 39.4 |
| 1.4 | 469 | vertical | 0 | 16.9 | 22.0 | 25.3 |
| 1.6 | 519 | pelvis (IK) | 228 = 43.9% | 24.3 | 36.4 | 38.2 |
| 1.6 | 519 | vertical | 0 | 20.3 | 24.1 | 28.1 |

Added, from the existing `gait_diag.py marker-hip` (relative to the marker pelvis, its tilt through the stride; strides 297, 469, 518): median / p95 / max **-1.4 / 12.6 / 16.3** at 0.5, **6.4 / 17.9 / 20.7** at 1.4, **8.4 / 17.6 / 20.6** at 1.6; none beyond 31. The IK-pelvis numbers are the ones the stop was compared with so far; the marker pelvis is the ISB/Dumas one.

## D4: polygon test at 0.5 m/s, by decile of that foot's stance

`gait_diag.py foot-pitch --speeds 0.5 1.4 --cap 0 --polygon-cap 0 --trunk rigid`, all strides, current mapping (ankle offset -3.4), 25 mm polygon band, measured CoP on each foot's own polygon. The 1.4 rows below reproduce memo12 T3's with-offset row to the digit (single 25.9, 19.8, 14.7, 14.9, 20.8, 39.3, 76.5, 98.2; double 0-10 56.2).

Outside % (median / p95 mm), n:

| stance % | 0.5 single | 0.5 double | 1.4 single | 1.4 double |
|---|---|---|---|---|
| 0-10 | - | 34.7 (35 / 83) n=4216 | - | 56.2 (33 / 73) n=6066 |
| 10-20 | 15.4 (32 / 45) n=52 | 8.7 (48 / 66) n=3963 | 25.9 (15 / 106) n=1830 | 19.8 (15 / 105) n=3804 |
| 20-30 | 7.0 (54 / 102) n=1938 | 7.4 (47 / 94) n=2103 | 19.8 (16 / 106) n=5438 | 12.3 (10 / 42) n=212 |
| 30-40 | 6.0 (18 / 110) n=3930 | 0.0 n=33 | 14.7 (26 / 135) n=5543 | 6.2 (19 / 58) n=112 |
| 40-50 | 5.6 (22 / 129) n=3923 | - | 14.9 (34 / 166) n=5478 | 0.0 n=57 |
| 50-60 | 6.4 (25 / 149) n=4080 | - | 20.8 (11 / 144) n=5772 | 6.7 (2 / 14) n=45 |
| 60-70 | 8.9 (23 / 160) n=3983 | 26.3 (24 / 36) n=38 | 39.3 (7 / 59) n=5607 | 14.8 (3 / 5) n=54 |
| 70-80 | 12.1 (7 / 146) n=1463 | 23.6 (10 / 50) n=2520 | 76.5 (10 / 66) n=5489 | 94.8 (9 / 77) n=155 |
| 80-90 | 93.3 (10 / 18) n=15 | 69.5 (10 / 63) n=4058 | 98.2 (17 / 39) n=1335 | 99.9 (31 / 98) n=4305 |
| 90-100 | - | 99.9 (34 / 145) n=3698 | - | 100.0 (78 / 411) n=5361 |

At 0.5 m/s the last 20% of stance is almost entirely double support (7,756 of 7,771 frames), and there 69.5% and 99.9% of frames are outside: the toe-region failure is the same, the single-support mid-stance failures (5.6 to 8.9%) are about half of 1.4's. Single-support frames at 10-20% and 80-90% are few (52 and 15): do not read those two cells.

## D5: the strides behind the lumbosacral rigid lateral torque maxima

`snapshot_diag.py lateral`, rigid trunk, lumbosacral lateral joint row of `qfrc_inverse`, every subject-stride (1,285). p95 and max equal the tracked extract's to 2 decimals at all three speeds, so this is the same computation. Stance percent is counted from each foot's own heel strike (longest run of the flag).

| speed | p95 N m | max N m | stride | ratio to p95 | stride phase | support at the peak | stance |
|---|---|---|---|---|---|---|---|
| 0.5 | 59.16 | 139.17 | AB23 stride 0 | 2.35 | 57% | double | right 90.5%, left 14.9% |
| 1.4 | 92.67 | 112.25 | AB11 stride 23 | 1.21 | 45% | single | right 75.0% |
| 1.6 | 110.46 | 177.20 | AB15 stride 18 | 1.60 | 9% | double | right 14.5%, left 95.2% |

Others: 0.5, second AB13 stride 16 at 79.2 (1.34, single, left 49.2%), then AB18 75.6, AB20 70.7; 15 strides above p95 (AB15 4, AB18 4, AB20 4, AB23 2, AB13 1), seven of the top eight in double support. 1.4: 24 above p95, AB18 15 of them (its two largest peak at stride phase 95 to 96%, single support, left foot at 73 to 78% of its stance). 1.6: 26 above p95, AB15 16; AB15's eight largest, 1.25 to 1.60 times the p95, peak at 4 to 14% of the stride (five in double support) except one at 97%. Peak phase over all strides: median 34% (0.5), 50% (1.4), 47% (1.6); single support at the peak 25%, 88%, 95%. The 0.5 maximum is one stride by a 1.76x margin over the next; I have not looked at why AB23's first stored stride differs, nor whether stride 0 is the first stride of its trial.

## D6: stamps

| file | git_dirty | diff_sha256 | git_commit |
|---|---|---|---|
| `sim/benchmarks/gait_extract.json` (tracked) | true | 38a282fc252834bf75e7ee4ae50e91bf821f3c727dce30df6c07db74a040aeee | e2317602879d |
| `sim/gait/20261019-1424-walk_treadmill/gait.json` (untracked) | true | 38a282fc252834bf75e7ee4ae50e91bf821f3c727dce30df6c07db74a040aeee | e2317602879d |

Identical, as memo22 finding 5 said (the extract was written from that record). HEAD when read: a681cb08e5a6.

## D7: trunk and head markers

None. The static trials hold pelvis and lower-limb markers only, so the sagittal inclination of the pelvis-to-C7 and C7-to-vertex chords cannot be computed from this dataset. `chord_inclination_deg` is implemented and tested for use on another source.

## D8: ANSUR II female (`data/ansur2/raw/ANSUR_II_FEMALE_Public.csv`, present; values in mm)

| variable | n | mean | SD | scaled to 1.70 m (x 1700 / 1628.5) |
|---|---|---|---|---|
| stature | 1986 | 1628.5 | 64.2 | 1700 |
| footlength | 1986 | 246.3 | 12.4 | 257.1 |
| balloffootlength | 1986 | 182.1 | 9.6 | 190.1 |
| lateralmalleolusheight | 1986 | 62.7 | 5.1 | 65.5 |

Measurer's Handbook (`data/ansur2/raw/measurers-handbook.pdf`, sections 6.4.37, 6.4.8, 6.4.60): **Foot length** is the maximum length of the right foot, from the back of the heel (pternion) to the tip of the longest toe (acropodion), on a Brannock device, standing, weight on both feet. **Ball of foot length** is the distance from the back of the heel (pternion) to the first metatarsophalangeal protrusion on the ball of the right foot (same device and stance). **Lateral malleolus height** is the vertical distance from the standing surface to the lateral malleolus landmark. Footwear is not stated in those three entries. The sheet's own definition of its 165 mm (ankle centre to the midpoint of MT1 and MT5 heads, from ADR 0001) is a different landmark than ball of foot length, which is heel to MT1 only. `.gitignore` already has `data/ansur2/raw` (line 12, commit a681cb0); nothing under it is tracked; no commit was needed.

## D9: inventory for the next brief (no edits made)

**(i) The foot in the template.** `sim/models/freyja_template.xml` lines 31 to 34 (right) and 55 to 58 (left): one body `foot_<s>` at `!{foot_<s>_pos_x/y/z}` inside `shank_<s>`; inertial from `${foot_<s>_mass}`, `_com_x/y/z`, `_ixx..._iyz`; one box geom at `!{foot_<s>_box_pos_x} 0 !{foot_<s>_box_pos_z}` with size `!{foot_<s>_box_half_x} 0.050 !{foot_<s>_box_half_z}` (half width 0.050 is a literal in the template; friction 1.0 0.005 0.0001, condim 3; comment "design choice, no sheet source"); one site `site_sole_<s>` at `0 0 !{foot_<s>_sole_z}`; two hinges `ankle_pdflex_<s>` (axis 0 -1 0, range `-ankle_plantarflexion` to `ankle_dorsiflexion`) and `ankle_ie_<s>` (axis 1 0 0, `-ankle_eversion` to `ankle_inversion`). `pre_processor.derive_keys` (lines ~724 to 734) derives `foot_<s>_box_pos_x = (L - rear)/2`, `_box_half_x = (L + rear)/2` with `rear = FOOT_REAR_FRACTION (0.25) * L`, `_box_pos_z = -ankle/2`, `_box_half_z = ankle/2`, `_sole_z = -ankle`, where ankle = `pelvis_pos_z + thigh_pos_z + shank_pos_z + foot_pos_z`. Sheet keys used directly: `foot_<s>_mass`, `_length` (0.165), `_com_*`, inertia, `_pos_x/y/z`, `_jpos_z`; `ankle_dorsiflexion/plantarflexion/inversion/eversion`.

**(ii) The preprocessor.** `RANGE_BSIP="bsip"`, `RANGE_POS="pos"`, `RANGE_ROM="rom"`, optional `RANGE_TARGETS="targets"`. From the snapshot's `sheet_source` column (the named ranges' own extents are not in the repo and I did not read the sheet): BSIP data rows 15 to 24 of `'MuJoCo Reference'` (foot row 24; columns B to L = mass, length, com xyz, ixx, iyy, izz, ixy, ixz, iyz), POS rows 5 to 14 of `'MuJoCo Positions '` (trailing space in the sheet name; foot row 14; columns B to E = pos_x, pos_y, pos_z, jpos_z), ROM column G rows 71 to 93 of `'MuJoCo Reference'` ("MuJoCo limit - FINAL"; header keyword `final`), targets `'BSIP Reference'!A1:B2`. `EXPECTED_SEGMENTS = [head_neck, thorax, abdomen, pelvis, upper_arm, forearm, hand, thigh, shank, foot]` (10; a missing or extra sheet segment stops the build, `pre_processor.py:423`), `BILATERAL = [upper_arm, forearm, hand, thigh, shank, foot]` (6). Segment keys are `ident(label)`; bilateral segments become `<seg>_right_<col>` and `<seg>_left_<col>` (left mirrored: `FLIP_BSIP` com_y, ixy, iyz; `FLIP_POS` pos_y), unilateral `<seg>_<col>`. ROM keys are `ident("<joint> <movement>")`, e.g. `ankle_dorsiflexion`, `hip_external_rotation`; 19 are in the snapshot (ankle 4, elbow 2, hip 6, knee 2, shoulder 3, wrist 2). `CHAIN_CHECKS` warns when a body's position is not one parent-segment length from its parent (includes `("foot_right", "shank_right")`). 261 snapshot keys.

**(iii) Counts, lists and hard-coded foot values.**
- Bodies 16 (`nbody - 1`) and hinges 31 (32 joints with the free root): `tests/test_thread_real.py:46` (`== 16 ... == 31`), `checks/test_thread_checks.py:32` (strings "16 bodies", "31 hinges"), `checks/test_mjcf_checks.py:127` (`checked == 31`), `tests/test_watch.py:198` (a fake build line, "16 bodies, 32 joints"), `pre_processor.py:930` (a docstring example), `pre_processor.py:1045` (computed).
- Segment lists: `EXPECTED_SEGMENTS` and `BILATERAL` are imported, not copied, by `tools/thread/build.py` (lines 63, 248 to 297) and the tests `test_gate.py:251 to 253`, `test_pre_processor.py:36, 76`, `test_template.py:140`, `test_thread_real.py:37` (set of `seg.*` records equals `EXPECTED_SEGMENTS`), `test_thread_validate.py:127`. Thread records: 10 `seg.*` (foot: `seg.foot`, body `foot`, sides both) and 9 `jnt.*` (`jnt.ankle`: hinges `ankle_pdflex`, `ankle_ie`; four ROM keys), plus five `lc.*`. `check.thread.coverage` (`checks/thread_checks.py`) requires every body and hinge bound by exactly one record.
- Mirror: `check.mjcf.mirror` (gate) pairs bodies and joints by the `_right`/`_left` suffix (`_bilateral_names`), so a new bilateral body and hinge are checked automatically; it has no list. `check.mjcf.joint_signs` (gate) reads `checks/joint_polarity.yaml` (88 lines, every hinge, `ankle_pdflex_*` probe point `[0.12, 0, -0.03]` m in the foot frame: a hard-coded foot point 120 mm ahead of the ankle and 30 mm below) and counts 31. `check.mjcf.mass_closure` (gate) sums body masses against the snapshot and `target_mass`; `check.mjcf.stature_chain` and `floor_contact` read the model; `check.mjcf.com_pct_stature` is the confirmed waiver (`checks/waivers.yaml`, CoM 55.26% of stature, review by 2027-01-10): a toe mass split or a new foot centre moves it.
- 165 mm / foot box / toe edge hard-coded: `foot_pitch.py:28` (`OFF_FLAT_DEG` comment, 206 mm and asin(25/206)) and `:305` (print string "206 mm long (165 mm ahead of the ankle, 41 mm behind)"); `sim/scenarios/hold_pose.yaml:7` and `stand_static.yaml:5` ("heel margin 41 mm") with `tests/test_stage2b_housekeeping.py:51` asserting "41 mm" in those headers; `tests/test_double_support.py:136` (box reaches 165 mm), `tests/test_scenarios.py:284` (CoM beyond the toe edge at 0.165), `tests/test_statics.py:144 to 145` (toe edge 0.165, CoM at 0.19), `tests/test_template.py:103 to 109` (lengths 0.165 and 0.17), `tests/test_double_support.py:155` (a point over the ankle, 0.057); `decisions/0001-toe-joint.md` (165 mm reach, ~140 N m); `thread/dossiers/seg.foot.md` (generated). In code the geometry is read from the model's box geoms (`dynamics._foot_boxes`, `dynamics.HULL_BAND_M = 0.025`), so the polygon follows the box.
- Foot touched by name in 14 scripts under `sim/scripts` and 15 test files (`grep foot_right|foot_left`), e.g. `gait.py:57 STANDING_FEET`, `dynamics.py`, `statics.py`, `gaitloads.py`, `retarget.py`, `ankle_gain.py`, `simrun.py`, `sweep.py`. `camargo_mapping.yaml` maps `ankle_pdflex_*` (offset -3.4) and `ankle_ie_*`; no toe. The dataset's mtp is locked at 0 (ADR 0001).

**(iv) Lean pose and the stand pose.** `leanpose.solve_lean(model, com_x_rel_ankle_m, feet)` uses the foot only through (a) the foot body's x axis (`xmat[first][6]`), levelled by bisection on the root pitch so the soles are flat, (b) `_bottom_z` over the feet's geoms (the box) to put the lowest point on z = 0, (c) the foot body's `xpos` x as the ankle reference, and (d) the ankle range `[lo, hi]` it searches. So any change to the box (position, size) or to the ankle frame moves the 2.608 deg. `gait.Ctx.stand = leanpose.solve_lean(model, 0.0, STANDING_FEET).qpos` (`gait.py:207`) is the standing pose every retargeted cycle and several diagnostics start from; `stand_static` and `hold_pose` use `com_x_rel_ankle_m: 0.0` ("a design choice, not a measurement").

**(v) Where the 2.608 deg and the pelvis pitch enter.** 2.608 deg is a result, not an input: the ankle angle that puts the CoM over the ankle at the current box and masses (stand_static root pitch equals it, both +2.608). It appears as text in `retarget.py:255` (comment), `ankle_gain.py:553` (a message), `tests/test_retarget.py:76`, `tests/test_retarget_pitch.py:4, 38, 105, 131` (the old composition and a tolerance of 0.5 deg vs 2.608; line 105 asserts it to 1e-3 deg), `tests/test_runs_report.py:345` and `sim/runs/DIGEST.md:50, 144`. In the retargeting it enters only as `R_stand` (`retarget.py`, `Cycle._R_world`), composed on the world side when `pitch_mean` is a number; with `pitch_mean: measured` (the spec default) it is not applied. The model's pelvis pitch is otherwise the free root's orientation, identity at neutral (`leanpose` requires it); the dataset's pitch enters as `-pelvis_list` (`camargo_mapping.yaml: pelvis_pitch {coordinate: pelvis_list, sign: -1}`) plus the spec's `pelvis_pitch_offset_deg` (0). There is no sheet or snapshot pelvis-pitch quantity (checked `params/snapshot.csv`, `pre_processor.py`, the template). If the sheet has one the preprocessor does not read, it is outside the evidence I have: ask Joe.

## Tolerances I chose

None for pass/fail. Report-only constants: fit rows use all four foot markers, no weights; tilt uses `arcsin` of the vertical component of X; `top_strides` reports eight per speed (`--top`); the p95 is NumPy's linear percentile, the same as the extract's `distribution`. The test tolerances are 1e-9 on exact synthetic geometry and 0.2 deg on the obliquity coupling test (the measured effect is 0.04 deg).

## My own mistakes

- The two-foot marker mix-up in `foot_geometry` (finding 2). My first test fixture had one foot, so it could not see it. Caught by the AB15 outlier, not by the test.
- Test scaffolding: I first wrote a Dumas test with a nonsense offset expression and a chord test ending in `or True`; I rewrote both before running anything (no result depended on them).
- The first Dumas fixture's expected offset had the wrong sign in my head; the analytic value (tilt + atan(0.03/0.16)) was derived and the test asserts it.
- The shell wrapper reported "completed" for background jobs that were still running (the `&` inside a backgrounded compound command); I checked the output files rather than trusting it.

## Questions for Joe

1. Source the next brief's ankle, MTP and heel positions from ANSUR II at the chosen posture rather than from these markers (recommended)? The data here support only: ankle centre about 0.32 of the marker foot length ahead of the heel, the lateral malleolus marker about 0.26.
2. Which pelvis frame does the sheet's 31 deg hip extension refer to? Against the IK pelvis 36.7% of 1.4 m/s strides exceed it; against the vertical or the Dumas pelvis none do.
3. Is the model's pelvis frame meant to be the Dumas (ASIS-PSIS) frame? If yes, the design pelvis pitch is a Dumas tilt (standing 12.4 deg, SD 3.9) and the model's 2.608 deg is separate; if no, say which.
4. Do you want a second source for the ankle centre (a subject with both malleolus markers is only AB15)?
5. Keep the dirty-stamped extract as is until the final regeneration (recommended, it is interim), or regenerate from a clean tree now?
