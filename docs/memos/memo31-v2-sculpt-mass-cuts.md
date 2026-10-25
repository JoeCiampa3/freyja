STATE: base e1cbc34a846e | brief architecture sha256:3fd62592ecb1, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1591/1595 | dirty yes

# Memo 31: base.obj committed, v2 sculpt prepared, iliocristale and tenth-rib mass cuts (volume-extractor brief 3, Phase A)

Brief: `docs/briefs/architecture/volume-extractor-brief3.md` (saved verbatim; CLAUDE.md now names it). Phase A is done and I have stopped at the handoff. Phase B waits for `freyja-body-v2.obj`.

## Decision summary

- **What it means for Freyja.** The thigh/pelvis mass question no longer has one answer, and it should not be forced to. Put the pelvis top at the iliocristale instead of the lumbosacral plane and the thigh x2 + pelvis normalised ratio falls from 1.17 to 1.02 (band 0.99-1.06 for +/-1 SD of iliocristale height). The lumped abdomen + pelvis + 2 thighs region, which depends on no internal cut, gives 1.03 (band 1.01-1.06). So the earlier "sculpt is 17% light in the hip-and-thigh region" is mostly the lumbosacral top excluding the iliac volume that the sheet's pelvis mass plausibly includes. The shank (0.85) and foot (0.82) findings are untouched by any of this.
- **v2 is ready to open.** `freyja-body-v2.mhm` differs from v1 by 2 removed and 3 added lines. Predicted: every Measure box within 0.3 cm of v1 at rest except the two leg-height boxes it is meant to move (+2.91 and -2.94 cm); girths move by at most 0.21 cm (calf). Nothing near the 1 cm stop.

| Number | This work | Reference |
|---|---|---|
| Thigh x2 + pelvis, normalised, top at lumbosacral plane (972.5 mm) | 1.169 | 1.00 = sheet matches (memo 30: 1.169) |
| Same, top at iliocristale mean 1037.5 mm / -1 SD / +1 SD | 1.021 / 1.060 / 0.990 | 1.00 |
| Lumped, tenth rib mean 1100.7 mm / -1 SD / +1 SD | 1.031 / 1.055 / 1.006 | 1.00 |
| Sheet mass / skin volume: thigh x2 + pelvis (lumbosacral top); same (iliocristale top); lumped; shank; foot, kg/l | 1.544; 1.348; 1.359; 1.186; 1.154 | tissue about 1.0-1.1 |
| Predicted v2 knee / hip fraction of stature | 0.27824 / 0.51241 | sheet 0.2782 / 0.5124 |
| Predicted Statistics Height, v2 (unposed) | 169.90 cm | v1 posed showed 169.73 cm; v1 at rest 169.89 |

- **Decisions for you.**
  1. Do the v2 check below and export. Recommended; the sheet-matching knee and hip come from sliders, not from a 6.8% / -6.7% stretch.
  2. Pelvis top: I report both and do not choose (your instruction). One fact bearing on it: the sheet's abdomen body runs 127 mm above the lumbosacral plane, i.e. to about 1100 mm in the sheet frame, level with the tenth-rib mean, and the iliocristale mean (1037.5) lies inside it. With the pelvis top at the iliocristale the abdomen would own only the part above it, but its sheet mass (2.665 kg) is not reduced in this arithmetic.
  3. A cited source for the reference densities (list below).
- **What would change the conclusion.** The tenth-rib and iliocristale SDs are ANSUR whole-population SDs in stature ratio (1.1% and 1.3%); a sculpt whose waist-to-hip proportions are far from the ANSUR mean moves the lumped number by 1.2% of volume per 10 mm of rib height. A different abdomen reference density than 1.01 moves the lumped ratio by under 0.3%.

## Step 0, baseline

- Brief saved; CLAUDE.md line 8 now names `volume-extractor-brief3.md` (the repo rules allow it; the brief files themselves I did not touch).
- Brief-name test: not run in isolation; it is in the full-suite result below.
- `docs/STATE.md` still said `volume-extractor-brief-2.md` (generated, from the previous commit). `fy state` regenerates it.
- Known out of scope: the gait-extract test failure.

## 1. base.obj and the pins

- `data/makehuman/base.obj` committed, sha256 `8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c`, 1,749,303 bytes, CC0 header in the file, retrieved 2026-10-25 from upstream commit `a8bc2d54ff0a...` (master, 2024-06-26). Marked `-text` in `.gitattributes`, because `* text=auto eol=lf` could otherwise rewrite it and change the hash. Source note: `data/makehuman/SOURCE.md`.
- `data/makehuman/mhm_sources.json` pins the commit and, for the 161 target files the scripts actually read, sha256 and size (33.3 MB, over the 5 MB limit, so the cache `data/makehuman/cache/` is gitignored). `python analysis/makehuman_fetch.py` downloads from the pinned commit, refuses any hash mismatch and never overwrites with a bad download; `--verify` is offline. Tested: a clean download of all 161 files verified.
- License of the targets folder: no license file of its own. Every file read carries the CC0 header (checked for all 486 I had fetched: 0 without), and `LICENSE.ASSETS.md` at the pinned commit is CC0 1.0. Recorded in the manifest.
- The memo-30 attribution ran on a 414-file folder fetched from master on 2026-10-24. My folder was 486 files; rerunning on it reproduces `sculpt_attribution.json` to 1e-9 in every number, only `inputs.target_files` differs (486 against 414). I did not rewrite the committed attribution JSON. The 161-file pin is the set read by the attribution run plus the v2 prediction.
- Gate 1 against the committed file: pass. Identical 13,380 vertices and faces in the same order, boundary edges 0, non-manifold 0, odd columns 0. The full gates run (`fy envelope gates`, chords, 2 mm, N = 200) passes all of gates 1-6 with numbers identical to memo 30 (thigh +6.8%, shank -6.7%, foot +0.07%, volume 51.2570 l against Blender 51.2605 l). `leg_R_trial.json` changed only by the added cut rows and by now naming `data/makehuman/base.obj`.

## 2. v2 sculpt

`data/makehuman/freyja-body-v2.mhm` is `v2_mhm_text(v1)` in `analysis/makehuman_v2.py` (write with `python analysis/makehuman_v2.py write-mhm`; a test checks the committed file equals the function's output and that v1's LF-form hash is unchanged, `a6c2ba83452d`). Against v1:

- **Changed:** `modifier macrodetails-height/Height 0.623000` -> `0.625000`.
- **Added** (v1 had no line, i.e. 0): `modifier measure/measure-upperleg-height-decr|incr 0.269000` and `modifier measure/measure-lowerleg-height-decr|incr -0.515000`, placed after the hips measure line.
- **Removed:** `pose standing02.bvh`.
- Nothing else. v1 is untouched. The values are the memo-30 solution rounded to the 3 decimals the file holds.

### Predicted readouts (MakeHuman's own arithmetic: `Ruler.getMeasure`, summed distances between consecutive listed vertices x10, not closed unless the list repeats its first vertex; Statistics height = body bounding box in y)

| Box (cm) | v1 as MakeHuman showed it (posed, from the committed OBJ) | v1 at rest | v2 predicted (unposed) | v2 - v1 at rest |
|---|---|---|---|---|
| Statistics: Height | 169.73 | 169.89 | **169.90** | +0.01 |
| Statistics: Chest (= bust-circ) | 89.00 | 89.30 | 89.39 | +0.09 |
| Statistics: Waist (= waist-circ) | 64.13 | 64.10 | 64.17 | +0.07 |
| Statistics: Hips (= hips-circ) | 94.30 | 94.30 | 94.39 | +0.09 |
| neck-circ | 30.55 | 30.58 | 30.61 | +0.03 |
| neck-height | 10.03 | 9.91 | 9.92 | +0.01 |
| upperarm-circ | 22.47 | 22.24 | 22.27 | +0.03 |
| upperarm-length | 26.58 | 26.71 | 26.76 | +0.05 |
| lowerarm-length | 22.47 | 22.32 | 22.35 | +0.03 |
| wrist-circ | 12.92 | 12.91 | 12.93 | +0.02 |
| frontchest-dist | 27.94 | 28.86 | 28.89 | +0.03 |
| bust-circ | 89.00 | 89.30 | 89.39 | +0.09 |
| underbust-circ | 72.16 | 72.18 | 72.25 | +0.07 |
| waist-circ | 64.13 | 64.10 | 64.17 | +0.07 |
| napetowaist-dist | 38.80 | 38.95 | 38.99 | +0.05 |
| waisttohip-dist | 19.30 | 19.28 | 19.30 | +0.02 |
| shoulder-dist | 16.30 | 14.74 | 14.75 | +0.01 |
| hips-circ | 94.30 | 94.30 | 94.39 | +0.09 |
| **upperleg-height** | 37.43 | 37.43 | **40.34** | **+2.91** |
| thigh-circ | 47.50 | 47.50 | 47.60 | +0.10 |
| **lowerleg-height** | 49.79 | 49.79 | **46.85** | **-2.94** |
| calf-circ | 33.19 | 33.19 | 32.98 | -0.21 |
| ankle-circ | 19.12 | 19.12 | 19.15 | +0.03 |
| knee-circ | 32.39 | 32.39 | 32.42 | +0.03 |

- **Which stature the Statistics Height should show.** v2 has no pose, so the unposed one: **169.90 cm** (1699.0 mm). v1 as exported (posed, standing02) showed 169.73 cm (1697.3 mm, the OBJ's); v1 at rest is 169.89. The pose costs 0.16 cm of height. Compare v2's box against the third column, not the first: the torso and arm boxes of the first column carry the pose (shoulder-dist 16.30 posed against 14.74 at rest).
- **Girths, memo 30's unchecked item.** v1 at rest to v2: thigh 47.50 -> 47.60 (+0.10), knee 32.39 -> 32.42 (+0.03), calf 33.19 -> 32.98 (-0.21), ankle 19.12 -> 19.15 (+0.03) cm. These are the Ruler polylines, which are what the four boxes show. The loops are fixed vertex sets that ride with the legs: mean loop height moves thigh 737.5 -> 732.6 mm, knee 497.0 -> 467.5, calf 349.9 -> 327.3, ankle 122.6 -> 122.7; tilt from horizontal 24.4/25.1, 14.1/14.0, 27.3/25.6, 9.8/9.6 degrees (v1/v2). The largest shift is 0.21 cm, far below the brief's 1 cm stop.
- **Knee and hip.** v2 predicted knee 472.7 mm (0.27824 of stature; sheet 0.2782) and hip 870.6 mm (0.51241; sheet 0.5124), stature 1699.0 mm against 1698.9 (v1 at rest).
- **Limits of the prediction.** The legs are verified against a real export to 0.009 mm (memo 30); the torso at rest has never been compared with a real MakeHuman export (v1's torso is posed), so the chest, waist, hips and arm boxes rest on the same weight rules but without a check. The thigh +0.10 sits exactly on your 0.1 cm tolerance. Data in `data/envelope/v2_prediction.json`.

## 3-4. Mass cuts on v1 (additions only; frame cuts unchanged)

ANSUR II female (n = 1,986) ratios were already in `data/ansur2/ratios.json`; nothing missing. Iliocristale 0.6113 +/- 0.0129 of stature, tenth rib 0.6485 +/- 0.0111. Times the mesh stature 1697.3 mm: iliocristale 1037.5 mm (band 1015.7-1059.4, SD 21.8), tenth rib 1100.7 mm (1081.9-1119.5, SD 18.8). For comparison the lumbosacral plane is 972.5 mm. Heights are mesh heights above the sole and map to the conformed frame with slope 1 (above the hip-centre node), as the pelvis top did.

Same definitions as memo 30. Normalised = mass share / volume share / (reference density / mean mesh density 0.9944). Sheet mass / skin volume uses the sheet's own masses, not the mesh-derived ones.

| Row | Volume l | Sheet mass kg | Sheet mass / skin vol. kg/l | Normalised |
|---|---|---|---|---|
| Pelvis, hip-centre cut, top lumbosacral (as before) | 5.543 | 9.49 | 1.712 | 1.331 |
| Pelvis, hip-centre cut, top iliocristale mean | 8.217 | 9.49 | 1.155 | 0.898 |
| ... top -1 SD / +1 SD | 7.443 / 8.887 | 9.49 | 1.275 / 1.068 | 0.991 / 0.830 |
| Pelvis, crotch cut, top lumbosacral | 9.491 | 9.49 | 1.000 | 0.777 |
| Pelvis, crotch cut, top iliocristale mean (-1 / +1 SD) | 12.165 (11.391 / 12.836) | 9.49 | 0.780 (0.833 / 0.739) | 0.606 (0.647 / 0.575) |
| **Thigh x2 + pelvis, hip-centre cut, top lumbosacral** | 18.440 | 28.47 | **1.544** | 1.169 |
| **Thigh x2 + pelvis, hip-centre cut, top iliocristale** (-1 / +1 SD) | 21.114 (20.340 / 21.785) | 28.47 | **1.348** (1.400 / 1.307) | 1.021 (1.060 / 0.990) |
| Thigh x2 + pelvis, crotch cut, top lumbosacral | 18.414 | 28.47 | 1.546 | 1.171 |
| Thigh x2 + pelvis, crotch cut, top iliocristale (-1 / +1 SD) | 21.088 (20.314 / 21.758) | 28.47 | 1.350 (1.402 / 1.308) | 1.022 (1.061 / 0.991) |
| **Lumped: abdomen + pelvis + 2 thighs, tenth rib to KJC planes** (-1 / +1 SD) | 22.915 (22.389 / 23.476) | 31.135 | **1.359** (1.391 / 1.326) | 1.031 (1.055 / 1.006) |
| Shank | 2.467 | 2.925 | **1.186** | 0.854 |
| Foot | 0.563 | 0.650 | **1.154** | 0.823 |

(The snapshot gives the pelvis 9.49 kg and each thigh 9.49 kg, 14.61% of 64.935 kg each. As in memo 30 the pelvis and thigh rows move opposite ways with the cut: it trades volume between them.)

- **Lumped region.** Connected-body slab from the crotch apex (mesh 809.1 mm) up to the tenth-rib height, plus two right-thigh volumes below the crotch-apex plane (4.461 l each, KJC to apex), so it contains no thigh/pelvis cut and no pelvis/abdomen cut. Mass = abdomen 2.665 + pelvis 9.49 + 2 x 9.49 = 31.135 kg (47.95% of the sheet total). Reference density = mass-weighted mean of abdomen 1.01, pelvis 1.01, thigh 1.05 = 1.034. The abdomen value 1.01 is mine (the brief gave none); same recalled source as the pelvis.
- **Plausibility of the slab.** The area profile (largest connected piece, 2 mm steps) has no jump above the crotch apex: area 515 cm2 at 819 mm, 610 at 879, 477 at 979, 324 at 1039, 276 at 1079 (waist), 312 at 1119. The only large layer step (105%) is the first layer, below the crotch apex where one leg is the largest piece; the slab starts at the apex, so it is outside. No arm merged with the trunk to the height of the tenth-rib +1 SD. The rise from 276 to 312 cm2 above the waist is the chest widening.
- **Reading.** Normalised near 1.00 means the sculpt's share matches the sheet's at the recalled tissue densities. The lumped region is 3% (band 1-6%) heavy in the sheet's favour: the sculpt's volume is within the sheet's expectations once the iliac volume is inside the region. The 1.17 of memo 30 depended on the lumbosacral top. Whether the lumbosacral top or the iliocristale is the better model of the sheet's pelvis body is not chosen here.

## 5. Reference densities: recalled and unverified

All need a cited source before they carry weight in a decision. They are Dempster-type values as I recall them from Winter's tabulation, not checked against the primary table:

- Thigh 1.05 kg/l (brief's figure; `REFERENCE_DENSITY["thigh"]`)
- Shank ("leg") 1.09 kg/l (brief's figure)
- Foot 1.10 kg/l (brief's figure)
- Pelvis 1.01 kg/l (`PELVIS_REFERENCE_DENSITY`, Dempster's abdomen-pelvis value as I recall it; accepted by you in the brief but still unsourced)
- Abdomen 1.01 kg/l (`ABDOMEN_REFERENCE_DENSITY`, new in this work, same recalled value as the pelvis)

## Method choices and tolerances (mine)

- No new tolerance is chosen to fit a result. The 0.1 cm and 1 cm figures are the brief's.
- The lumped top uses the same slope-1 height map above the hip-centre node as the pelvis; tops at +/-1 SD use the ANSUR SD in stature ratio times mesh stature.
- The raster for the slab reaches the largest of lumbosacral, iliocristale +1 SD and tenth-rib +1 SD, plus 20 mm.
- The predicted readouts use the weights from `analysis/makehuman_attribution.py` (unchanged); the 3-decimal slider values as written.

## My mistakes and defects

- I wrote the tests for the new modules before the code but did not run them against missing modules to watch them fail; they would have failed on import. The cuts tests I did watch fail (3 failures) before implementing.
- My first `predict` run read an empty targets folder and failed with a KeyError that blamed the modifier; I added an explicit error when the folder is missing.
- The first background run of `fy envelope gates` produced no output and I re-ran it; no tracked file was affected.
- `SheetNodes` gained a trailing `abdomen_mass_kg` field (default NaN) so existing constructors keep working; the snapshot loader requires the key.
- Carried: v1's committed `sculpt_attribution.json` still reports 414 target files; `Section.chebyshev()` instability on elongated sections; the envelope OBJ is still 27 MB and unthinned (you said thin only on your report of load time).

## Test suite

1591 passed, 3 skipped, 1 failed (685 s). The failure is the known, out-of-scope `tests/test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce` (stale model hash in the run records; the scenarios need re-running in a separate session). The CLAUDE.md brief-name test now passes after the rename to `brief2` and the repoint to `brief3`. New tests: `tests/test_makehuman_v2.py` (10) and three in `tests/test_envelope_bundle.py`. `fy thread build` run before the suite: 0 changed.

## Joe's check

1. Open `data/makehuman/freyja-body-v2.mhm` in MakeHuman. In **Pose/Animate** confirm no pose is applied (the v1 file loaded standing02).
2. Compare the **Measure** tab boxes and the **Statistics** box to the third column of the table above (tolerance 0.1 cm). Statistics Height should read **169.90 cm** (unposed). Pay particular attention to upperleg-height 40.34, lowerleg-height 46.85, and the four girth boxes: thigh 47.60, knee 32.42, calf 32.98, ankle 19.15 (v1 at rest: 47.50, 32.39, 33.19, 19.12). Torso and arm boxes are the least verified (no unposed comparison exists).
3. Eyeball the legs: the thigh should be longer and the shank shorter than in v1 by about 29 mm each, with no kink at the knee.
4. Export with v1's dialog settings (Wavefront obj, helper geometry off, decimeter, feet on ground, normals off) as `data/makehuman/freyja-body-v2.obj` and commit it. Optional: run your Blender volume on v2 and send me the number for gate 6.

Then tell me; Phase B (items 6-9) starts from there. If a box disagrees by more than 0.1 cm, send me the readout before exporting: the cause would be in the rebuild, and I would rather know before Phase B.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v1.obj`; knee anchor `chords`; shear kept; voxel 2 mm; topology reference `base.obj` sha 8e761e66.... v1 `.mhm` LF sha `a6c2ba83452d`.
