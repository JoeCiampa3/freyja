STATE: base b1ebc26dcd3a | brief architecture sha256:61e4b1bc4023, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1612/1616 | dirty yes

# Memo 32: Phase B on v2, sourced densities, Dumas-landmark mass cuts (volume-extractor brief 4)

Brief: `docs/briefs/architecture/volume-extractor-brief4.md` (saved verbatim; CLAUDE.md names it). All ten items done. No stop condition tripped: every gate passes, whole-body deviation from the rebuild is 0.008 mm, v2 chord stretches are within 1%, 0.011 l of the v2-v1 volume change is unexplained, the computed volume is 0.003% from Blender, and Table 1 places along the abdomen axis.

## Decision summary

- **What it means for Freyja.** v2 is a clean baseline: the exported mesh is exactly what the `.mhm` predicts, and the registration no longer has to stretch the legs (thigh -0.9%, shank +0.07%, foot -0.03%, against +6.8% / -6.7% on v1). On the basis you set (sheet masses are volume shares at 1 g/cm3, ratio 1.00 = same distribution), the sculpt is **9% light in volume share in the abdomen + pelvis + thighs region** (raw ratio 1.099) and **5% / 8% heavy in the shank / foot** (0.954 / 0.926). That is smaller than the Dempster-normalised 17% and 15-18% of memo 30, because the density correction was a second correction on top of masses that already assume uniform density.
- The +1.07 l from v1 to v2 is not geometry in the ratios. 0.45 l is the pose coming off (shoulders and arms), 0.63 l is the sliders (0.19 Height alone, 0.44 the two leg measures, which add 0.85 l of thigh and take 0.35 l of shank in the raw mesh that the conform then removes). The lumped region's conformed volume moved -0.14%; its raw ratio moved +2.2% (1.075 to 1.099) only because the whole-mesh denominator grew 2.1%.

| Number | v2 | Reference |
|---|---|---|
| Whole-body deviation from rebuild, max / mean (mm) | 0.0083 / 0.0048 | flag 0.1, stop 1.0 |
| Volume, computed / Blender (l) | 52.3315 / 52.3331 (-0.003%) | gate 0.5% |
| Volume change v1 to v2, exact (l): pose / sliders / unexplained | +0.447 / +0.628 / 0.011 | Blender +1.0726, stop at 0.3 unexplained |
| Stretch thigh / shank / foot | 0.9914 / 1.0007 / 0.9997 | v1 1.0683 / 0.9329 / 1.0007; gate 8%, expect 1% |
| Raw ratio, lumped (MSR10 to KJC planes) | 1.099 (MSR10 +-10 mm: 1.086-1.113; RR10 top 1.128) | 1.00 |
| Raw ratio, thigh x2 + pelvis (RI top, hip-centre cut) | 1.121 (RI +-10 mm: 1.102-1.142) | 1.00; lumbosacral top 1.248 |
| Raw ratio, shank / foot | 0.954 / 0.926 | 1.00 |
| Dempster lumped share vs sheet | 48.10% vs 47.95% | independent check |
| M_mesh (f = 0.207, lung gas out) / sculpt BMI / robot required average density | 52.10 kg / 18.05 / 1.311 kg/l | v1: 50.97 / 17.69 / 1.340; sheet 64.94 kg |

- **Decisions for you.**
  1. Whether the 9% shortfall in the hip-and-thigh region is a sculpt problem. Recommended: do not re-sculpt yet. Wait for your Dumas 2007a uniform-density confirmation for the limbs, because it decides whether the shank and foot 5-8% excess is real; the lumped number does not depend on any internal cut, so it will stand.
  2. Fill in the edition and page of `reference_densities.json` and the full Dumas 2015 citation in `dumas2015_table1_female.json` (both blank or partial on purpose).
  3. The abdomen row (MSR10 to RI, a 78 mm slab) is a diagnostic, not a result: 0.916 raw, and 10 mm of either cut moves it by 12-16% of its value. Recommended: never use it alone; it enters only through the lumped region.
- **What would change the conclusion.** A uniform-density statement in Dumas 2007a that does not hold for the limbs (then shank and foot are compared on the wrong basis); a different sculpt in which the waist-to-hip proportions move; or evidence that the sheet's pelvis mass is meant to include more or less than the slab below the iliocristale.

## 1. Gate table (v2, chords, 2 mm, N = 200)

| Gate | Result | Numbers |
|---|---|---|
| 1 topology, thigh and shank | pass | 13,380 vertices, 13,378 faces identical to `base.obj` (sha 8e761e66...); boundary edges 0, non-manifold 0, odd columns 0 |
| 1 whole v2 against the rebuild | pass | max 0.0083 mm, mean 0.0048 mm over all 13,380 vertices after the exporter's translation (8.0890 dm in y only); legs 3,170 vertices max 0.0083 mean 0.0048; torso 1,969 max 0.0082 mean 0.0047; arms 4,082 max 0.0083 mean 0.0048; head 4,159 max 0.0083 mean 0.0048; vertices over 0.1 mm: 0 |
| 2 thigh | pass | stretch 0.9914 (-0.9%); min inscribed radius 46.76 mm at station 390, robust 46.40 (diff 0.36); volume 6.421 l, 95% range 5.824-6.879 l (max diff 9.3%, gate 10%) |
| 2 shank | pass | stretch 1.0007 (+0.1%); radius 24.75 mm at 360, robust 24.66 (diff 0.09); volume 2.471 l, 95% 2.407-2.547 l (3.1%) |
| 2 foot | pass | 0.9997 (-0.03%) |
| 3 thigh, shank | pass | lengths exact; worst area change 0.243% and 0.178% (gate 1%) |
| 4 synthetic solids | pass | cylinder, box, cone within 0.83 mm (gate 2 mm) |
| 5 oracle CLI | pass | feasible margin 16.61 mm, infeasible -8.18 mm, both at station 275 mm |
| 6 volume vs Blender | pass | 52.3315 l against 52.3331 l (-0.003%) |

The whole-body figure is from `analysis/makehuman_v2_check.py` (output `data/envelope/v2_check.json`); the regions for it are labelled by the method in section 3 (legs, torso, arms, head by the piece a vertex sits on). The 0.008 mm is the OBJ's four-decimal rounding in dm (0.005 mm rms), not geometry. The torso is unposed, so the torso check that v1 could not pass (29 mm mean, pose) is now clean.

## 2. v1 against v2 (trial, same code, same settings)

| | v1 | v2 | Change |
|---|---|---|---|
| Stretch thigh / shank / foot | 1.0683 / 0.9329 / 1.0007 | 0.9914 / 1.0007 / 0.9997 | removed by the sliders |
| Conformed volume thigh / shank / foot (l) | 6.449 / 2.467 / 0.563 | 6.420 / 2.470 / 0.566 | -0.45% / +0.15% / +0.5% (expected within 1%: yes) |
| Knee / hip chord anchors (mm above sole) | 502.2 / 871.5 | 472.7 / 870.6 | sheet 473.0 / 871.1 |
| Mesh volume (l) | 51.257 | 52.331 | +1.074 (+2.10%) |
| Stature (mm) | 1697.3 (posed) | 1699.0 | +1.7 |
| Mean mesh density, M_mesh (kg) | 0.9944, 50.97 | 0.9956, 52.10 | |
| Sculpt BMI; robot required average density | 17.69; 1.340 kg/l | 18.05; 1.311 kg/l | sheet BMI 22.5 |
| Ruler girth against section perimeter: thigh / knee / calf / ankle | -2.7 / +0.7 / -2.3 / +0.2 % | -2.7 / +0.7 / -1.5 / +0.1 % | calf now under the 2% flag |

Mass base at f = 0.15 / 0.35 (v2): M_mesh 52.74 / 50.57 kg, BMI 18.27 / 17.52, robot needs 1.311 kg/l in all cases (it depends on volume only). The Blender volume is within 0.003% of the computed one, so using it instead moves nothing visible.

## 3. Volume attribution (item 2)

Rebuilt v1 at rest is 51.7037 l; exact volumes: v1 posed 51.2570 l (committed OBJ; Blender 51.2605), v1 at rest 51.7037, v2 52.3315 (Blender 52.3331). Pose effect +0.4466 l; slider effect +0.6278 l (Height 0.623 to 0.625 alone +0.1857; the two leg measures alone +0.4411; they do not add exactly, the 0.0010 is their cross term); total +1.0744 l against Blender's +1.0726 l.

By region, the same three meshes (litres; planes are each mesh's own anatomy: ajc 65.5, kjc 502.2 / 502.2 / 472.7, crotch apex 809.1 / 809.4 / 808.4, MSR10 1098.6 / 1098.9 / 1098.0, neck 1475 / 1473 / 1475 mm):

| Region | v1 posed | v1 rest | v2 | Pose effect | Slider effect | Total |
|---|---|---|---|---|---|---|
| Head | 3.377 | 3.399 | 3.392 | +0.021 | -0.007 | +0.014 |
| Arms | 3.191 | 3.042 | 3.056 | -0.149 | +0.014 | -0.135 |
| Trunk above the tenth rib | 16.204 | 16.786 | 16.867 | +0.583 | +0.081 | +0.663 |
| Abdomen and pelvis (crotch apex to MSR10) | 13.702 | 13.694 | 13.729 | -0.008 | +0.035 | +0.027 |
| Thighs (KJC to crotch apex, both) | 8.353 | 8.366 | 9.217 | +0.013 | +0.851 | +0.864 |
| Shanks | 5.293 | 5.291 | 4.940 | -0.001 | -0.351 | -0.353 |
| Feet | 1.126 | 1.126 | 1.131 | 0.000 | +0.004 | +0.005 |
| Sum (raster) | 51.245 | 51.704 | 52.332 | +0.459 | +0.626 | +1.086 |

The regions sum to the raster's volume, which differs from the exact mesh volume by -0.0118 l (posed), +0.0009 (rest) and -0.0006 (v2); the exact total is +1.0744, so **0.011 l is unexplained** (limit 0.3).

- The pose touches only the upper body, as it should: shanks, feet and thighs move by 0.013 l or less. The arms-versus-trunk split of the pose effect (-0.149 / +0.583) depends on how the armpit is divided in the posed mesh, where the arms lie against the body; their sum, +0.434 l, is the robust figure.
- The sliders put +0.851 l in the raw thighs and take 0.351 l out of the raw shanks, as 29 mm of length at 290 cm2 and 120 cm2 would. The conform removes exactly this (v1's stretches were +6.8% / -6.7%), which is why the conformed segment volumes barely move while the whole-mesh volume does.
- The trunk and abdomen gains of the slider step (+0.081, +0.035) are the Height slider's: +0.002 on Height is +0.186 l in all, i.e. +0.36% of volume.

Method of the split (mine): the arm label is decided once, on v2, where the arms hang free: each 2 mm horizontal layer is cut into connected pieces; below the crotch apex a piece with its centroid within 300 mm of the midline is a leg and any other an arm; from the apex up the largest piece is the core and the rest are arms. The label belongs to the vertex, so it carries to the other two meshes by index; each mesh's raster cells then go to the arm label or the rest by the nearest labelled vertex, and the rest is cut by horizontal planes (layers straddling a plane are split by overlap). My first attempt classified each mesh's layers independently and put 0.11 l of posed hand into the thighs (the posed arms hang against the thighs); the thigh row of the pose effect caught it, since the pose cannot move the legs.

## 4. Cut heights (item 6)

s_a = sheet abdomen length 127.092 mm over Table 2's 121 mm = 1.0503. Above the LJC plane: TJC +127.09, MSR10 +120 s_a = +126.04, RR10 +100 s_a = +105.03, RI +46 s_a = +48.32. Mesh frame, with the LJC plane at 972.5 (v1) and 971.9 (v2) mm (the plane is the hip-centre node plus the sheet's LJC offset, so it follows the crotch apex):

| Landmark | Brief (LJC 972.5) | v1 | v2 | ANSUR (v1 / v2 stature) | v2 minus ANSUR |
|---|---|---|---|---|---|
| MSR10 | 1098.5 | 1098.6 | 1098.0 | tenth rib 1100.7 / 1101.8 | -3.8 mm (-0.20 SD of 18.8) |
| RR10 | 1077.5 | 1077.6 | 1076.9 | | |
| RI | 1020.8 | 1020.9 | 1020.2 | iliocristale 1037.5 / 1038.6 | -18.4 mm (-0.84 SD of 21.9) |
| TJC | | 1099.6 | 1099.0 | | |

The Dumas landmarks sit inside the ANSUR bands for both ribs and crest. Only the Y (up) coordinate of Table 1 is used: each cut is a horizontal plane, and the sheet's abdomen body stands vertical on the LJC in the zero pose (its position has no x or y offset), so the coordinates place without ambiguity. A horizontal plane at RI's height is a simplification of an oblique crest; the lateral Z = 153 mm is not used. MSR10 lies 1.05 mm below TJC, i.e. the sheet's abdomen body ends at the tenth rib; the sheet abdomen mass (2.665 kg) is a 127 mm body, while the Dumas abdomen of Joe's decision is the 78 mm slab MSR10 to RI. That inconsistency is why the abdomen row is a diagnostic.

## 5. Share rows (items 7 and 8)

Definitions as in memo 30 with the primary now the **raw ratio** = sheet mass share / sculpt volume share (no density anywhere). Dempster-normalised = raw / (reference density / mean mesh density 0.9956) is secondary. Sheet mass / skin volume uses the sheet's own masses. Densities (kg/l, Winter Table 4.1, `data/envelope/reference_densities.json`): thigh 1.05, shank 1.09, foot 1.10, abdomen and pelvis 1.01 each, and the lumped region takes 1.01 for its abdomen + pelvis part and 1.05 for the thighs. Volume share is over the whole mesh (52.331 l, lung gas in). Report only, no pass/fail.

**Primary (Dumas cuts) on v2, with v1 beside it:**

| Row | Cut | Volume l (v2) | Vol. share | Mass share | **Raw ratio v2 (v1)** | Normalised v2 (v1) | Sheet kg / skin l v2 (v1) |
|---|---|---|---|---|---|---|---|
| Abdomen (diagnostic) | MSR10 to RI | 2.344 | 4.48% | 4.10% | **0.916 (0.896)** | 0.903 (0.882) | 1.137 (1.135) |
| Pelvis | hip-centre plane to RI | 7.628 | 14.58% | 14.61% | **1.003 (0.981)** | 0.988 (0.966) | 1.244 (1.243) |
| Pelvis | crotch apex to RI | 11.341 | 21.67% | 14.61% | **0.674 (0.647)** | 0.665 (0.637) | 0.837 (0.819) |
| Thigh x2 + pelvis | hip-centre cut | 20.467 | 39.11% | 43.84% | **1.121 (1.094)** | 1.077 (1.050) | 1.391 (1.386) |
| Thigh x2 + pelvis | crotch cut | 20.478 | 39.13% | 43.84% | **1.120 (1.096)** | 1.076 (1.051) | 1.390 (1.388) |
| **Lumped** | MSR10 to KJC planes | 22.823 | 43.61% | 47.95% | **1.099 (1.075)** | 1.058 (1.034) | 1.364 (1.362) |
| Shank | KJC to AJC | 2.470 | 4.72% | 4.50% | **0.954 (0.936)** | 0.872 (0.854) | 1.184 (1.186) |
| Foot | sole to AJC | 0.566 | 1.08% | 1.00% | **0.926 (0.911)** | 0.838 (0.823) | 1.149 (1.154) |

(The pelvis rows trade volume with the thigh as the lower cut moves; the sum, thigh x2 + pelvis, does not move: 1.121 against 1.120.)

**Sensitivities (v2; raw, with normalised in brackets):**

| Variant | Abdomen | Thigh x2 + pelvis (hip-centre) | Lumped |
|---|---|---|---|
| Primary (RI, MSR10) | 0.916 (0.903) | 1.121 (1.077) | 1.099 (1.058) |
| Upper cut +10 mm | 0.815 (0.803) | 1.102 (1.058) [RI +10] | 1.086 (1.045) |
| Upper cut -10 mm | 1.041 (1.027) | 1.142 (1.097) [RI -10] | 1.113 (1.071) |
| RI +10 mm (abdomen row) | 1.079 (1.064) | | |
| RI -10 mm (abdomen row) | 0.788 (0.777) | | |
| RR10 as the top | 1.222 (1.205) | | 1.128 (1.086) |
| ANSUR iliocristale (1038.6) / tenth rib (1101.8) as the cuts | | 1.088 (1.044) | 1.094 (1.053); +-1 SD of rib: 1.120 / 1.068 |
| Lumbosacral plane as the pelvis top | | 1.248 (1.199) | |

Diagnostic (label as such): moving the cut up by 10 mm changes the abdomen slab by **-0.368 l for RI** and **+0.287 l for MSR10** (central differences of the +-10 mm rows; the slab is 2.344 l, so 16% and 12% of it). The same on v1: -0.370 and +0.285 l.

**Item 8, the independent cross-check.** Winter Table 4.1: abdomen and pelvis 0.281 + two thighs 2 x 0.100 = **48.10%** of body mass; the sheet's abdomen + pelvis + two thighs is 31.135 kg of 64.935 kg = **47.95%** (difference -0.15 percentage points). The sheet's masses for this region agree with Dempster to 0.3% of the share, so the 9% in the raw ratio is not a disagreement between the sheet and the tabulated distribution but between both and the sculpt.

## 6. Girth check (item 9)

The Ruler readouts of the exported `freyja-body-v2.obj`, computed with MakeHuman's own arithmetic, against the memo-31 prediction: the largest difference over all 21 readouts (20 Measure boxes and the Statistics height) is 0.0008 cm (waisttohip-dist); the Statistics height is 169.8950 against a predicted 169.8954, which MakeHuman displays as 169.9. Loop heights match to 0.003 mm and tilts to 0.002 degrees (thigh 732.6 mm / 25.08 degrees, knee 467.5 / 14.04, calf 327.3 / 25.57, ankle 122.7 / 9.65). That is the check you did by eye in MakeHuman, repeated on the file.

Ledger perimeter against the Ruler loop, on the unconformed mesh: thigh 463 mm against 476 (-2.7%, flagged at 2%), knee 326 / 324 (+0.7%), calf 325 / 330 (-1.5%, below the flag, was -2.3%), ankle 192 / 191 (+0.1%). ANSUR II female: calf maximum 326 mm against 373 +- 29 (z = -1.65); ankle minimum 191 against 216 +- 15 (z = -1.65). The thigh loop is tilted 25 degrees, which probably accounts for its length exceeding the horizontal section's perimeter (not tested); the -2.7% is the same as in v1.

## 7. What the Dumas-landmark cuts and the uniform-density basis change (plain paragraph)

Before, the pelvis ended at the lumbosacral plane, 972.5 mm up, and the lumped region ended at an ANSUR tenth-rib height; densities were recalled; every share was divided by a tissue density (thigh 1.05, shank 1.09, foot 1.10) before being called 1.00. Now the pelvis ends at the right iliocristale and the lumped region at the tenth rib, both read from Dumas 2015 Table 1 scaled to the sheet's own abdomen, which puts them 18 mm below and 4 mm below the ANSUR means, inside one standard deviation of each. The thigh x2 + pelvis ratio at the new top is 1.121, against 1.248 at the lumbosacral plane on the same mesh: the lumbosacral top left out the iliac volume, so 0.13 of that number was the cut. The density correction was the larger change. Dumas 2015 expresses the segment masses at 1 g/cm3, so the sheet's shares are volume shares, and dividing by Dempster densities invented a 4-11% difference that neither source supports: the shank reads 0.954 raw against 0.872 normalised, the foot 0.926 against 0.838, the lumped region 1.099 against 1.058. On the basis you set, the sculpt's hip-and-thigh region is 9.0% below the sheet's share (1 - 1/1.099) and its lower leg is 4.8% above, its foot 8.0% above. Those are the numbers to carry forward; the earlier 17% and 15-18% should be treated as overstated.

## 8. Method choices and tolerances (mine)

- No gate tolerance, check tolerance or geometry value was changed. 0.1 mm (flag), 1 mm (stop), 0.3 l (unexplained), 0.5% (Blender), 8% (stretch), 10% and 5 mm (robustness) are the brief's or the existing constants.
- New constants, none tuned toward a result: raster 2 mm for the region split (the same as the trial's voxel; raster minus exact volume is 0.0006-0.012 l); `LEG_Y_MM_MAX` = 300 mm to separate a leg piece from an arm piece below the crotch apex (thigh centroids are within about 130 mm of the midline, the hands hang at 400 mm or more; the check that it is not wrong is that the pose changes the thighs by 0.013 l); neck plane = the narrowest core section between 80% and 90% of stature (found at 1473-1475 mm, 86.8%, inside the window), which only separates the head from the trunk in section 3.
- The lumped region keeps the memo-30 construction (connected-body slab from the crotch apex plus two right-thigh volumes below it), with MSR10 as its top. Its abdomen + pelvis density is the combined 1.01; the thigh part 1.05.
- Cut volumes use the registration's height map as before (stretch below the hip-centre node, slope 1 above it), so the cut heights are in the sheet frame shifted to the mesh frame by the hip-centre node.
- v2's Statistics-height 169.90 is the OBJ's bounding box (1698.95 mm); the loaded mesh stature is 1699.0 mm.

## 9. My mistakes and defects

- The first region split (per-layer pieces on each mesh) was wrong for the posed mesh; replaced by vertex labels carried by index (section 3). The synthetic test mesh I first wrote for it had 8 vertices per box and could not exercise nearest-vertex labelling; I rebuilt the test body with vertex grids.
- A vertex on a horizontal face was first matched to a layer that does not contain the body there, and classified by its own height; fixed to use the matched layer's height. The tests caught it.
- Early drafts of the two data files held two things I could not source (an author list in `dumas2015_table1_female.json`, landmark names for Winter's thorax and trunk rows); I removed them before anything was run on them. The Dumas file now says "full citation to be added by Joe".
- I added `blender_volume_v2_m3` (your 0.0523331 m3 from the brief) to `data/envelope/body_density.json`, a file you author. The original `blender_volume_m3` is still v1's. The masses module picks the key from the mesh name.
- `fy envelope build` and `gates` default to v2 now (`cli.py`), so `data/envelope/*.yaml`, `*_sections.csv`, the silhouettes and `leg_R_trial.json` are v2 results; the ledgers' header names the mesh. The v1 trial of this code was run into a scratch directory and reproduces memo 30's gates (stretches 1.0683 / 0.9329 / 1.0007, volume 51.257 l); it is not committed.
- Defects carried: the Inspect envelope OBJ is still 27 MB and unthinned (you said thin only on your report); `Section.chebyshev()` centres are unstable on elongated sections (radius is fine); `sculpt_attribution.json` still reports 414 target files.
- A denominator subtlety, not a defect of this work: the volume share divides a conformed segment's volume by the unconformed whole-mesh volume. On v1 the conform added 0.47 l net (+0.9%), so v1's shares were about 0.9% low; on v2 it removes 0.11 l (-0.2%). It is why v1 and v2 ratios cannot be compared at 1%; I did not change it.

## 10. Tests and files

Tests: 1612 passed, 3 skipped, 1 failed (716 s). The failure is the known, out-of-scope `tests/test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce` (stale model hash in the run records). `fy state` ran the suite again and reports 1612/1616. New: `tests/test_envelope_dumas_cuts.py` (15: the two data files, the cut heights, the share rows, the diagnostic, the Dempster check, the region split including a posed arm lying against the trunk), `tests/test_makehuman_v2_check.py` (6, against the committed `v2_check.json`). Changed: one assertion in `tests/test_envelope_bundle.py` (the removed constants; the numbers are the same). `fy thread build` before the suite: 0 changed. Edited with the changes: `CONVENTIONS.md` (the layout rows for `tools/envelope/`, `data/makehuman/` and `data/envelope/`), `CLAUDE.md` (line 8). New code: `tools/envelope/decompose.py`, `analysis/makehuman_v2_check.py`; changed: `masses.py`, `cuts.py`, `gates.py`, `register.py` (`abdomen_length_mm`), `cli.py` (default mesh).

## Follow-ups

1. Dumas 2007a: confirm uniform density for the limbs, then the shank and foot raw ratios (0.954, 0.926) are the answer; if not uniform, the Dempster-normalised column is the one to read for them.
2. Decide the sculpt response to the 9% hip-and-thigh shortfall (a v3 with more hip and thigh volume, or accept it and carry the 9% as a known robot-versus-subject difference). I can quantify what a hip or thigh girth slider would do to the lumped ratio per cm using the attribution script; not done, not asked.
3. Whether to move the share denominator to the conformed whole-body volume. On v2 it changes shares by 0.2%; recommended: leave it.
4. Roadmap: `rm.v1-volume-extracted` stays pending ADR 0007; nothing in this memo signs it off.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v2.obj`; knee anchor `chords`; shear kept; voxel 2 mm; topology reference `base.obj` sha 8e761e66.... Running list: no such file exists in the repo.
