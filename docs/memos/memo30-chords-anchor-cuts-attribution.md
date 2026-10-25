STATE: base e2eb3cc0c485 | brief architecture sha256:b8c8769f5bd3, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1577/1582 | dirty yes

# Memo 30: chords anchor, topology against base.obj, thigh cut variants, tissue-ratio shares, .mhm attribution

Follows memo 29 and your six instructions. All gates pass with the chords anchor. One file is missing from the repo and one gate input came from outside it (below).

## Decision summary

- **What it means for Freyja.** The knee anchor is settled (chords) and the 8% gate holds: stretches thigh +6.8%, shank -6.7%, foot +0.07%. The real topology check against MakeHuman's `base.obj` passes: the exported body has the same 13,380 vertices and the same 13,378 faces in the same order. The `.mhm` shows the knee-height excess is not an accident of this sculpt but the base mesh plus its macro sliders, and it can be removed with three sliders.
- **The mass finding survives every cut.** Once the pelvis is cut, the thigh+pelvis total is the same wherever the cut goes (18.44 l with the cut at the hip centre, 18.41 l at the crotch apex). Against the sheet's mass shares and Dempster-type densities that region is 17% light in the sculpt; the shank and foot are 15-18% heavy. The sculpt is slimmer at the hips and thighs than the sheet's segment masses assume, and not slimmer in the lower leg.

| Quantity | This trial | Reference |
|---|---|---|
| Stretch thigh / shank / foot (chords) | 1.068 / 0.933 / 1.001 | gate: within 8% of 1 |
| Thigh+pelvis normalised ratio, cut at hip centre / at crotch apex | 1.169 / 1.171 | 1.00 if the sculpt matched the sheet |
| Shank / foot normalised ratio | 0.854 / 0.823 | same |
| Thigh normalised ratio: hip zone in / out / cut at crotch | 1.10 / 1.35 / 1.59 | same (moves with the cut) |
| Sculpt knee height, fraction of stature | 0.2956 (committed OBJ 0.2959) | sheet 0.2782; base.obj 0.2775 |
| Three-slider change that lands knee and hip on the sheet | Height +0.002, upper-leg height +0.269, lower-leg height -0.515 | stature unchanged at 1698.9 mm |
| Mesh mass at f = 0.207, lung gas out | 50.97 kg (BMI 17.7) | sheet 64.94 kg; robot needs 1.340 kg/l average |

- **Decisions for you:**
  1. Place `base.obj` at `data/makehuman/base.obj` (MakeHuman master, `makehuman/data/3dobjs/base.obj`, CC0 by its own header; sha256 8e761e66...). Gate 1 stops without it. I used a scratch copy, the result file records its hash, and I did not add it to the repo. I recommend you commit it.
  2. Whether you want the three-slider change tried in MakeHuman. Report only, as you said; recommended, because it also removes the 6.8% / -6.7% stretches the registration has to absorb.
  3. A Dempster-type density for the pelvis: the brief gives none. I used 1.01 kg/l (Dempster's abdomen-pelvis value as I recall it); please confirm or replace it (`PELVIS_REFERENCE_DENSITY` in `masses.py`). It moves only the pelvis and lumped normalised ratios (by 1% per 0.01 kg/l).
  4. An ANSUR source for the minimum-ankle-circumference height, if the ankle loop is ever to anchor the AJC (still open from memo 29).
- **What would change the conclusion:** the pelvis reference density, if far from 1.01, would move the lumped 1.17 by about its own ratio; a different Dumas thigh share would move all thigh numbers.

## 1. Anchor

`chords` is the default (`fy envelope build`, `gates`, the inspect bundle). Mesh KJC 502.25 mm above the sole (mean of 499.0 and 505.5), Monte Carlo SD 17.3 mm (ANSUR lateral-epicondyle ratio SD x mesh stature) centred on the anchor. The Ruler and ANSUR-ratio anchors remain options and their stretches are still tabulated in `leg_R_trial.json`.

## 2. Gate table (chords, 2 mm voxels, N = 200)

| Gate | Result | Numbers |
|---|---|---|
| 1 thigh, shank | pass | 13,380 vertices and 13,378 faces identical to `base.obj`'s body (reference sha 8e761e66...); boundary edges 0, non-manifold 0, odd columns 0 |
| 2 thigh | pass, narrow | stretch +6.8%; min inscribed radius 46.75 mm at station 390, robust 46.36 (diff 0.39 mm, gate 5); volume 6.44 l, 95% range 5.80-6.93 l (max diff **9.9%**, gate 10%) |
| 2 shank | pass | stretch -6.7%; radius 24.66 mm at station 370, robust 24.66; volume 2.467 l, 95% 2.41-2.54 l (2.9%) |
| 2 foot | pass | +0.07% |
| 3 thigh, shank | pass | lengths exact; worst area change 0.32% and 0.31% over u = 0.1-0.9 (gate 1%) |
| 4 synthetic solids | pass | worst 0.83 mm (gate 2 mm) |
| 5 oracle CLI | pass | feasible margin 15.58 mm, infeasible -9.21 mm, both at station 275 mm |
| 6 mesh volume vs Blender | pass | 51.2570 l against 51.2605 l (-0.007%) |

The thigh volume gate is the close one: the wider knee SD you asked for puts 9.9% of the volume range against a 10% limit.

## 3-4. Mass base: variants, shares and the tissue ratio

Constants (yours, `data/envelope/body_density.json`): f = 0.207 (Deurenberg 1991, age 22), V_lung 2.787 l (Hall 2021, FRC), Siri 1956. BODY_DENSITY 1.0516 kg/l; M_mesh = 1.0516 x (51.257 - 2.787) = 50.97 kg; mean mesh density M_mesh / V_mesh = 0.9944 kg/l. (At f = 0.15 / 0.35: 51.60 / 49.47 kg.) Your 20.7% is self-consistent: Deurenberg applied to the sculpt's own BMI of 17.7 gives 20.9%.

Definitions: mass share = sheet segment mass over the sheet total (64.935 kg, the sum of the snapshot's segment masses); volume share = skin volume over the whole mesh volume (lung gas included); ratio = mass share / volume share; expected tissue ratio = Dempster-type density / mean mesh density; **normalised = ratio / expected**. 1.00 means the sculpt's share matches the sheet's at that tissue density.

| Row | Cut | Volume l | Vol. share | Mass share | Ratio | Expected | Normalised | Implied density kg/l (nominal; 15% / 35%) |
|---|---|---|---|---|---|---|---|---|
| Thigh, hip zone in | from the hip-centre plane | 6.449 | 12.58% | 14.61% | 1.162 | 1.056 | **1.100** | 1.155 (1.169 / 1.121) |
| Thigh, hip zone out | s > 40 mm | 5.260 | 10.26% | 14.61% | 1.424 | 1.056 | **1.349** | 1.416 (1.434 / 1.375) |
| Thigh, cut at crotch apex | s > 70.3 mm | 4.461 | 8.70% | 14.61% | 1.679 | 1.056 | **1.590** | 1.670 (1.690 / 1.621) |
| Pelvis, hip-centre cut | hip-centre to lumbosacral plane | 5.543 | 10.81% | 14.61% | 1.351 | 1.016 | 1.331 | 1.344 (1.360 / 1.304) |
| Pelvis, crotch cut | crotch apex to lumbosacral plane | 9.491 | 18.52% | 14.61% | 0.789 | 1.016 | 0.777 | 0.785 (0.794 / 0.762) |
| **Thigh x2 + pelvis, hip-centre cut** | | 18.440 | 35.98% | 43.84% | 1.219 | 1.042 | **1.169** | 1.212 (1.227 / 1.176) |
| **Thigh x2 + pelvis, crotch cut** | | 18.414 | 35.92% | 43.84% | 1.220 | 1.042 | **1.171** | 1.214 (1.229 / 1.178) |
| Shank | KJC to AJC plane | 2.467 | 4.81% | 4.50% | 0.936 | 1.096 | **0.854** | 0.931 (0.942 / 0.903) |
| Foot | sole to AJC plane | 0.563 | 1.10% | 1.00% | 0.911 | 1.106 | **0.823** | 0.905 (0.917 / 0.879) |

- The pelvis here is the whole-width body slab (arms excluded as separate pieces) from its lower plane up to the lumbosacral plane at 968.75 mm (the pelvis body's origin in the snapshot), stretched by the same height map: slope 1 above the hip-centre node. The lumbosacral plane sits 972.5 mm above the sole in the mesh. Both thighs are twice the right one (the mesh is symmetric to 0.5% in section area).
- **Interpretation grid.** Thigh alone swings from 1.10 to 1.59 as the cut drops, and the pelvis swings the other way (1.33 to 0.78): the cut location is trading volume between them, so neither number means anything alone. The sum does not move (1.169 against 1.171). So the discrepancy is real and is about where the sculpt carries its volume: the hip-and-thigh region holds 36% of the mesh volume against the 44% of mass the sheet gives it (17% light at tissue density), and the lower leg holds 5.9% of volume against 5.5% of mass (15-18% heavy). It is not global slimness: that is divided out by taking the mass from the mesh.
- Sculpt BMI 17.7 (f = 0.207); 17.9 at 15% and 17.2 at 35% (lung gas out). The sheet's 64.9 kg at 1.70 m is BMI 22.5; the robot needs an average density of 1.340 kg/l over the mesh's tissue volume (sheet total / (V - V_lung)), against about 1.05 for tissue.
- Inner volumes (t = 3, 5, 8, 10 mm): thigh 5.939, 5.603, 5.118, 4.810 l; shank 2.143, 1.935, 1.645, 1.467 l; foot 0.439, 0.365, 0.273, 0.221 l.
- Girths on the unconformed mesh (true perimeter, equivalent circle beside it): thigh loop 462 mm (453) against the Ruler loop 475, -2.7%, flagged; knee 326 (319) against 324, +0.7%; calf 324 (321) against 332, -2.3%, flagged; ankle 192 (186) against 191, +0.2%. ANSUR II female: calf maximum 326 mm against 373 +- 29 (z = -1.66); ankle minimum 191 against 216 +- 15 (z = -1.64). Station 0 is not compared.
- Shank cut sensitivity (+-15 mm): KJC plane +5.0% / -4.9%, AJC plane -2.5% / +3.3%.

## 5. .mhm attribution of the knee-height shift (report only)

Script `analysis/makehuman_attribution.py`, output `data/envelope/sculpt_attribution.json`. MakeHuman's `base.obj`, the target files and the weight rules (from MakeHuman's own `human.py` and `humanmodifier.py`) rebuild the mesh as base plus weighted targets. Check: **the rebuilt legs match the committed OBJ to 0.009 mm at most** (mean 0.005 mm) once the exporter's translation is removed, and the knee height agrees to 0.05 mm (502.2 mm both). The torso and head do not match (mean 29 mm, up to 262 mm) because the OBJ is exported in the `.mhm`'s pose (`standing02`); the legs are not moved by that pose, so the knee numbers stand, and the rebuilt stature is 1698.9 mm against the OBJ's 1697.3.

Knee height as a fraction of stature, with the knee the chord mean the trial uses:

| Mesh | Knee mm | Stature mm | Fraction |
|---|---|---|---|
| `base.obj`, no targets | 462.2 | 1665.9 | 0.2775 |
| Default human (every macro at its default) | 502.4 | 1659.4 | 0.3027 |
| This sculpt (`.mhm`) | 502.2 | 1698.9 | 0.2956 |
| Sheet (KJC / stature) | 473.0 | 1700 | 0.2782 |

The sculpt sits +18.2 per mille above `base.obj` (+30.9 mm at the sculpt's stature). Most of that, +25.3 per mille, is what MakeHuman's macro targets do to any human at their default weights, before any slider here is moved; the sculpt's own sliders then take back 7.1 per mille. Per modifier, from the default human (a modifier alone) and by leaving it out of the sculpt:

| Modifier (value) | Alone, per mille | Left out, per mille |
|---|---|---|
| Gender (0.0, female) | -10.1 | -7.0 |
| Height (0.623) | +2.5 | +3.9 |
| BodyProportions (0.546) | +1.1 | +1.6 |
| Ethnicity (Caucasian 1) | -1.5 | -0.7 |
| Age (0.44) | -1.3 | -0.2 |
| Weight (0.232) | -0.9 | -1.5 |
| Muscle (0.396) | 0.0 | -0.7 |
| Body shapes, pelvis bulge, breast, bust / underbust / waist / hips measures | 0.0 | 0.0 |
| Interaction (macro targets multiply) | +3.0 | |

Slider changes that remove the shift (the sculpt's other sliders held):
- **Each slider alone** can reach the sheet's 0.2782 or `base.obj`'s 0.2775 in only two cases, both unusable: lower-leg height to -0.69 (-0.72 for `base.obj`), which leaves a 1,658 mm stature, and Height down to 0.157 (0.141), a 1,290 mm stature. Age, Weight, Muscle and BodyProportions cannot reach it; the upper-leg height measure gets to 0.2786 at +1, just short of the sheet's 0.2782 and of `base.obj`'s 0.2775.
- **Three sliders together**, keeping the stature at 1698.9 mm: Height 0.623 to 0.625 (+0.002), upper-leg height measure 0 to **+0.269**, lower-leg height measure 0 to **-0.515**. Result: knee 472.7 mm (fraction 0.27823, the sheet's), hip (top of the Ruler upper-leg chord) 870.5 mm (0.51239, the sheet's), residuals below 1e-9. This is the same correction the registration applies by stretching, as sliders: thigh +6.8%, shank -6.7%. Not applied to the `.mhm`; what it does to thigh and calf girth is not checked.
- The cause, in one line: the default macro targets put the knee high, and gender 0 is the only big slider that pulls it back. Tabulated for completeness: both leg-height measure sliders at their extremes are in the JSON.

## Method choices and tolerances (mine)

- Variants: `in` = the conformed slab from the hip-centre plane; `out` = stations beyond 40 mm; `crotch` = beyond the crotch-apex plane, 70.3 mm below the hip-centre plane after the stretch. Volumes by the ramp method of memo 28.
- Pelvis area profile from the 2 mm body raster (largest connected piece per layer), 2 mm steps, integrated with the registration's height map. The lumbosacral plane is horizontal (the zero pose has the pelvis upright).
- Knee anchor sigma 17.3 mm (yours). The Ruler-loop offset (ANSUR epicondyle minus midpatella, 16.9 +- 8.6 mm) is unused now.
- Attribution: product weights as in MakeHuman; ethnic values normalised to sum to 1; only the target folders the `.mhm` touches (macrodetails for female and male, child and young; breast; measure; bodyshapes; pelvis) were fetched; age sliders below 0.1875 are not explored. Single-slider roots by sampling 41 points and interpolating; the combined solve is `scipy.optimize.least_squares`.
- `BODY_FAT_FRACTION` and `V_LUNG_L` are read from your file as they stand; nothing here edits it.

## My mistakes and defects

- Gate 1 compared the file to itself in memos 28 and 29. It could not fail. Now it compares to MakeHuman's own faces, and the result (identical) was not guaranteed.
- The committed ledgers, silhouettes and `leg_R_trial.json` were produced with `--base` pointing at a scratch copy of `base.obj`, because the file is not in the repo; they name it by file name and hash only.
- The envelope OBJ for Inspect mode is still 27 MB; not thinned, you did not ask. Inspect mode with the real envelope has still not been viewed in a browser by me.
- Defects carried: `Section.chebyshev()` centres are unstable on elongated sections (radius is fine); the hip zone's cut through the pelvis is why `thigh_in` is not a clean "thigh".

## Test suite

1577 passed, 3 skipped, 2 failed; neither failure is from this work and I touched neither. `tests/test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce` (the model hash changed in `d379525`; the three tracked run records still carry the old one; the scenarios need re-running). `tests/test_stage2b_housekeeping.py::test_claude_md_names_the_current_brief_of_each_track_and_each_exists`: CLAUDE.md now names `volume-extractor-brief-2.md`, which exists, but the test requires a name ending `-brief<digits>.md`, and `brief-2.md` does not match. Either rename the brief to `volume-extractor-brief2.md` or relax the test's pattern; both are yours (the test says it takes no per-stage edits).

## Questions for Joe

1. Commit `data/makehuman/base.obj`? (items above)
2. Pelvis reference density (1.01 assumed).
3. Try the three-slider change in MakeHuman?
4. Still open: an ANSUR source for the ankle-loop height; the Dumas thigh share (14.6%); whether to thin the envelope OBJ.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v1.obj`; knee anchor `chords`; shear kept; voxel 2 mm; topology reference `base.obj` sha 8e761e66.... Running list: no such file exists in the repo.
