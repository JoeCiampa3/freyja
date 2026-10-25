STATE: base 481d0d4936c3 | brief architecture sha256:missing, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1563/1568 | dirty yes

# Memo 29: shank trial, mass base, inspect bundle (volume-extractor brief 2)

Brief: `docs/briefs/architecture/volume-extractor-brief-2.md` (CLAUDE.md names it `volume-extractor-brief2.md`; no such file exists, the saved name has a hyphen before the 2). Decisions of yours applied: the shear stays, the picker, `landmarks.py` and the sheet loader stay, no re-sculpt.

**Stop condition reached.** With the brief's anchor (the Ruler knee loop plus the ANSUR offset) the thigh stretches +10.5% and the shank -9.3%, both past the 8% gate. Everything else in the brief is built and run; the artifacts in the repo are the Ruler-anchor run. Which anchor to carry forward is yours.

## Decision summary

- **What it means for Freyja.** The sculpt's knee sits higher against its stature than the sheet's. MakeHuman's own knee loop puts it 29 mm above the ANSUR-ratio estimate, and 42 mm above the sheet's KJC after scaling; the thigh is about 10% short and the shank 9% long relative to the sheet. The conform absorbs this without touching a cross-section, but the stretches are larger than the brief allows.
- **The mass base says the thigh, not the whole body, is the odd segment.** The sculpt is slim overall (BMI 18.9 at 15% body fat, 18.2 at 35%; the sheet's 64.9 kg at 1.70 m is 22.5), but the whole-body mass is set from the mesh volume, so that cancels. What is left is the distribution: the sheet gives the thigh 14.6% of body mass, the sculpt's thigh holds 12.3-12.8% of its volume.

| Quantity | This trial | Reference |
|---|---|---|
| Stretch thigh / shank / foot, Ruler anchor | 1.105 / 0.907 / 1.001 | gate: within 8% of 1 |
| Same, chords anchor / ANSUR-ratio anchor | 1.068 / 0.933; 1.022 / 0.970 | same gate (both pass) |
| Mesh volume | 51.257 l | Joe's Blender 51.2605 l (-0.007%; gate 0.5%) |
| M_mesh at 15% / 35% body fat | 54.6 / 52.3 kg | sheet total 64.9 kg (robot needs 1.267 kg/l average) |
| Thigh relative density (sheet mass share / sculpt volume share) | 1.14-1.19 | 1.0 if the sculpt matched the sheet; Dempster thigh/body about 1.0 |
| Shank / foot relative density | 0.93-0.95 / 0.91 | same |
| Thigh implied density, hip zone in / out (15% fat) | 1.22 / 1.49 kg/l | Dempster-type 1.05 |

- **Decisions for you, with my recommendation:**
  1. Knee anchor. Recommended: `chords` (the mean of MakeHuman's own upper-leg and lower-leg chord ends at the knee, 502.2 mm). It is a MakeHuman-internal knee, needs no assumption about where the Ruler loop sits, and both stretches pass (+6.8%, -6.7%). The Ruler-loop anchor assumes the loop is at the midpatella, which I could not verify. Alternatively keep the Ruler anchor and widen the gate for this mesh; that is a change to a tolerance because a result looks wrong, which I will not do myself.
  2. BODY_FAT_FRACTION and V_LUNG_L with sources. Not supplied; `data/envelope/body_density.json` holds null for both and the report carries the f = 0.15 / 0.35 bracket only. Lung gas is not subtracted anywhere yet (it would raise the implied densities by the lung share of 51 l).
  3. An ANSUR source for the Ruler ankle-loop offset. ANSUR II gives the minimum ankle circumference but not its height, so the ankle loop cannot anchor the AJC; the AJC stays on the ANSUR malleolus ratio (65.4 mm; sheet 65.5). The loop sits 57 mm above that.
  4. Whether the sheet's thigh mass share (14.6%, Dumas female) is what you want the envelope to carry. The sculpt's thigh is 12-15% light against it at every knee anchor.
- **What would change the conclusion:** a measured midpatella height for the Ruler loop (moves the Ruler-anchor knee by its offset, 17.6 mm), or an ANSUR-independent source for the knee joint centre.

## Gate table (Ruler anchor, 2 mm voxels, N = 200)

| Gate | Result | Numbers |
|---|---|---|
| 1 thigh, shank: topology, watertight | pass (topology tautological) | boundary edges 0, non-manifold 0, odd columns 0; HJC, KJC, AJC inside the body |
| 2 thigh | **FAIL** | stretch 1.1052 (+10.5%); min inscribed radius 47.59 mm at station 390, robust 46.71 (diff 0.87, gate 5); volume 6.55 l, 95% range 5.99-6.96 l (max diff 8.6%, gate 10%) |
| 2 shank | **FAIL** | stretch 0.9071 (-9.3%); min inscribed radius 24.69 mm at station 370, robust 24.66; volume 2.49 l, 95% range 2.46-2.53 l (1.6%) |
| 2 foot | pass | stretch 1.0007 |
| 3 thigh, shank | pass | lengths equal the sheet's (398.082 and 407.535 mm, diff 0.0000); worst area change 0.18% and 0.15% over u = 0.1-0.9 (gate 1%) |
| 4 synthetic solids | pass | cylinder V 0.051, A 0.044, r 0.739 mm; box 0.000, 0.007, 0.250; cone 0.002, 0.106, 0.832 (gate 2 mm) |
| 5 oracle CLI | pass | feasible margin 17.03 mm, infeasible -7.83 mm, both at station 275 mm |
| 6 mesh volume vs Blender | pass | 51.2570 l against 51.2605 l (-0.0068%) |

## 1-2. Anchors and the shank

Mesh heights above the sole, mm, against the sheet (sheet KJC 473.0, HJC 871.1, AJC 65.5):

| Node | ANSUR ratio x mesh stature | Ruler | Other |
|---|---|---|---|
| KJC | 485.5 | knee loop 497.0 + ANSUR offset 17.7 = 514.7 | chords 499.0 and 505.5, mean 502.2; breadth peak: none |
| HJC | trochanterion 880.9 | upper-leg chord top 871.5 | crotch apex 809.1 + ANSUR offset 65.8 = 874.9 (used) |
| AJC | 65.4 (used) | ankle loop 122.6 | lower-leg chord bottom 9.1 (the sole) |

- Knee-loop offset: ANSUR II female, lateral femoral epicondyle height minus midpatella height, per subject, n = 1,986: mean 16.9 mm, SD 8.6 mm (as a fraction of stature 0.0104, SD 0.0053). **Assumption: the Ruler knee loop is at the midpatella.** The loop's own 478-506 mm spread (14 degree tilt) is larger than the offset's SD. Mesh node SDs for the Monte Carlo: KJC 9.5 mm (offset SD with 3 mm of loop scatter), HJC 17.1, AJC 4.8.
- The upper-leg chord's top vertex is at 871.5 mm, on the sheet's HJC (871.07); three hip estimates (871.5, 874.9, 880.9) agree within 10 mm, so the hip is not the problem. The two MakeHuman-based knee estimates are 17 and 29 mm above the ANSUR-ratio one and 29 and 42 mm above the sheet's KJC (the ANSUR ratio itself is 12.5 mm above it).
- Stretches by anchor and the shears that go with them: Ruler 1.105 / 0.907, shear thigh 61.6 mm, shank 51.4 mm; chords 1.068 / 0.933, 62.8, 48.9 mm; ANSUR ratio 1.022 / 0.970, 64.5, 44.9 mm. Section-centre offsets do not change any envelope output; they widen the Ruler-anchor thigh shear to 47-77 mm (95%) and the shank's to 37-66 mm. The 1/cos bias you estimated (0.6% on the shank) is not corrected.
- Shank envelope (Ruler anchor): skin 2.491 l; t = 3, 5, 8, 10 mm: 2.165, 1.956, 1.665, 1.485 l; smallest in-plane inscribed radius 24.7 mm at station 370 (the ankle end), 19.8 mm at t = 5.
- Ledgers: `data/envelope/{thigh,shank,foot}_R.yaml` and `_sections.csv`, now with the true section perimeter and the equivalent-circle value as columns; silhouettes for thigh and shank.

## 3-4. Mass base and the thigh restated

- Constants: Siri 1956 (UCRL-3349 eq. 10), BODY_DENSITY = 4.950 / (f + 4.500): 1.0645 kg/l at f = 0.15, 1.0206 at 0.35. V_LUNG_L not supplied (treated as 0, flagged). M_mesh = 54.56 / 52.31 kg. Sculpt BMI 18.94 / 18.16 (mesh stature 1.6973 m). Sheet total 64.935 kg (the sum of the snapshot's segment masses; target 65). Robot required average density: sheet total over the mesh volume, 1.267 kg/l; as a mass ratio sheet total / M_mesh it is 1.19 / 1.24.
- Segments, Ruler anchor, conformed skin volumes:

| Segment | Skin l (t=3 / 5 / 8 / 10) | Sheet mass share | Sculpt volume share | Relative density | Expected mass 15% / 35% | Implied density 15% / 35% | Reference |
|---|---|---|---|---|---|---|---|
| Thigh | 6.559 (6.045 / 5.706 / 5.218 / 4.906) | 14.61% | 12.80% | 1.14 | 7.97 / 7.65 kg | 1.216 / 1.166 | 1.05 |
| Shank | 2.491 (2.165 / 1.956 / 1.665 / 1.485) | 4.50% | 4.86% | 0.93 | 2.46 / 2.36 kg | 0.987 / 0.946 | 1.09 |
| Foot | 0.563 (0.439 / 0.365 / 0.273 / 0.221) | 1.00% | 1.10% | 0.91 | 0.55 / 0.52 kg | 0.969 / 0.929 | 1.10 |

- Thigh with the hip zone (s < 40 mm) excluded: 5.368 l instead of 6.559 l, implied density 1.485 / 1.424 kg/l. That uses the whole thigh mass against less volume, as the brief asked; the zone holds 1.19 l (18%) of the thigh volume, the cut-plane's reach into the pelvis.
- **Interpretation grid.** Global slimness (the whole sculpt thinner than the 65 kg design) is already removed by taking the mass from the mesh volume; it shows up only as the 19-24% gap between M_mesh and the sheet total. The pattern left is segment-specific: thigh dense, shank and foot light, at every knee anchor (thigh implied density 1.17-1.27 across the three anchors and both fat fractions, shank 0.95-1.01; see `knee_anchor_mass_sensitivity` in `leg_R_trial.json`). A cut-plane artefact would move volume between thigh and shank as the knee moves; it does, by 0.25 l thigh and 0.06 l shank across the three anchors, against a thigh shortfall of about 1 l (7.97 kg at 1.05 kg/l is 7.6 l; the sculpt has 6.55 l). So this reads as thigh definition: the sculpt's thigh is slim against the sheet's BSIP thigh share, and its lower leg is not. It could also be that Dumas's thigh share is high for this build; the sheet is not mine to judge.
- Memo 28's girth line compared a station-0 equivalent circle with an ANSUR mean. **Withdrawn**: station 0 is the hip plane, not a girth, and the equivalent circle undershoots the true perimeter.

## 5. Cut sensitivity (shank, +-15 mm of each cut plane in the sheet frame)

| Shift | Skin volume | Change | t = 5 mm |
|---|---|---|---|
| KJC plane +15 | 2.618 l | +5.1% | +5.3% |
| KJC plane -15 | 2.369 l | -4.9% | -5.1% |
| AJC plane +15 | 2.431 l | -2.4% | -2.2% |
| AJC plane -15 | 2.573 l | +3.3% | +3.0% |

The knee plane matters twice as much as the ankle plane; a knee anchor 30 mm out is a 10% shank volume.

## 6. Girth check on the unconformed mesh

Ruler loops are on the left leg; the mesh is symmetric to 0.5% in section area, so the right leg's sections stand in for them. Perimeters are true contour lengths with the equivalent-circle value beside them:

| Loop | Ruler loop length | Section perimeter (equiv. circle) at loop height | Difference | Loop tilt | Flag (2%) |
|---|---|---|---|---|---|
| Thigh, z = 737 | 475 mm | 462 (453) | -2.8% | 24 deg | **flag** |
| Knee, z = 497 | 324 | 326 (319) | +0.6% | 14 deg | no |
| Calf, z = 350 | 332 | 324 (321) | -2.4% | 27 deg | **flag** |
| Ankle, z = 123 | 191 | 192 (186) | +0.2% | 10 deg | no |

The two flagged loops are the two most tilted. A tilted loop is longer than the horizontal section at its mean height; the sign and size are what tilt predicts. Not a ledger fault, but the ledger's horizontal perimeters are not Ruler-equivalent on a leaning leg.
Indicative against ANSUR II female (true perimeter, equivalent circle in brackets): calf maximum 325 mm (322) against 373 +- 29 (z = -1.7); ankle minimum 191 (186) against 216 +- 15 (z = -1.7). Thigh and lower thigh are not compared: ANSUR measures them at the gluteal furrow and at the suprapatella, whose heights on the mesh are not known.

## 7. Inspect bundle and picker

`fy envelope build` writes `data/envelope/cache/inspect/`: `original.obj`, `conformed.obj` (the 13,380 vertices moved by the registration, original quads), `envelope_t5.obj` (thigh, shank, foot as groups, 5 mm shell) and `inspect.json` (`inspect-bundle/1`: joint centres and axes for the original and the conformed leg, the three cut planes, the hip zone, feature levels, ANSUR mean +- SD slabs, the worked-example rod at every pose of both pose files). All in MakeHuman axes and decimetres. The folder is gitignored (the files are large and regenerate).
- **Marching cubes was replaced by marching tetrahedra**, the same iso-surface, because scikit-image is not a dependency and the brief says to ask before adding one. Tested on a sphere (area and volume within 2%, watertight, outward normals).
- The envelope file is 26.9 MB, about 0.8 million triangles (tetrahedra give about three times the triangles of cubes). If the page is slow, say so and I will thin it by meshing every second voxel (about 7 MB).
- Inspect mode in `tools/landmark-picker/index.html`: a button and drag-and-drop for the four files; layer checkboxes (original, conformed, envelope, joint centres, cut planes, hip zone, feature levels, ANSUR slabs, oracle rods); the clipping plane now has an axis choice (sagittal, coronal, horizontal) and acts on every layer. `landmarks.json` load, save and picking are untouched.
- Checked in headless Edge with software GL: the page renders the original and conformed meshes overlaid, loads all 13 layers, applies the clip to all 51 materials, and shows the registration summary. **The check used a one-triangle stand-in for the envelope file because the real one did not finish loading inside the headless time budget; I have not seen the real envelope in a browser.** Mouse interaction was not exercised. The page screenshot shows the gizmo labels overlapping at the lower right (cosmetic, not fixed).

## Method choices and tolerances (mine)

- Foot segment: the slab from the sole to the AJC plane, right of the midplane, connected to the foot. No Monte Carlo for it (stretch only).
- `BLENDER_TOLERANCE` 0.5%, `GIRTH_FLAG` 2%, `CUT_SHIFT_MM` 15, `LOOP_SD_MM` 3.0 (scatter of the Ruler loop's height about its mean; the loop's vertices span 10-64 mm in height), Monte Carlo as in memo 28 with the shank and foot added.
- Total sheet mass is the sum of the snapshot's segment masses (64.935 kg), not the 65 kg target; the toe is not added to the foot.
- Girth perimeters come from the zero contour of the signed-distance field at 0.5 mm; on a box this under-reads 1% (corners are rounded), on a cylinder 0.06%.
- Pelvis length 107 mm, ANSUR handling and the voxel field: as memo 28.

## My mistakes and defects

- Three syntax errors from escaped newlines in scripted edits (two in `cli.py`, one in a test). Each stopped a run; each is fixed with the editor, and every file now parses. I also did not run my syntax check in the foreground the second time, so one background run failed silently; that cost about 25 minutes.
- Memo 28's station-0 girth comparison (withdrawn above).
- CLAUDE.md points at `volume-extractor-brief2.md`; the file is `volume-extractor-brief-2.md`. I read the right file by listing the directory. Joe owns CLAUDE.md; not edited.
- Defect carried over: `Section.chebyshev()` centres are unstable on elongated sections; the radius is fine.
- `sheet.py` still holds the B1 loader (kept at your request); nothing calls it.

## Test suite

1563 passed, 3 skipped, 2 failed. Neither failure is from this work. `tests/test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce`: your pre_processor commit `d379525` rebuilt the model (hash 1ceee245...), the tracked run records still carry cfa2e074..., so `ENVELOPE.md` regenerates as "included: none"; the scenarios need re-running. `tests/test_stage2b_housekeeping.py::test_claude_md_names_the_current_brief_of_each_track_and_each_exists`: CLAUDE.md names `volume-extractor-brief2.md`, the file is `volume-extractor-brief-2.md` (the STATE line shows the architecture brief hash as missing for the same reason). A third failure in my last full run was mine (a fixture CSV lacking the new girth columns) and is fixed. I touched neither of the two.

## Questions for Joe

1. The knee anchor (above; I recommend `chords`).
2. BODY_FAT_FRACTION and V_LUNG_L, each with a demographic source; fill `data/envelope/body_density.json`.
3. An ANSUR (or other) source for the height of the minimum ankle circumference above the malleolus, if the ankle loop is to anchor the AJC.
4. Whether the sheet's 14.6% thigh share stands (finding above).
5. Is a thinned envelope OBJ acceptable for the browser?

Landmark file used: none. Mesh `data/makehuman/freyja-body-v1.obj`; ANSUR `data/ansur2/ratios.json`; knee anchor `ruler`; shear kept; voxel 2 mm.
