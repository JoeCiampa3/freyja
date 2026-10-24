STATE: base 8bc17b7e1116 | brief architecture sha256:220950b90a44, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1538/1542 | dirty yes

# Memo 28: body-envelope thigh trial, revised Phase B (registration to the sheet's nodes)

Brief: `docs/briefs/architecture/volume-extractor-brief1.md` as saved 17:07 (Phase B steps 5-9 replaced). Supersedes the landmark-pick path of memo 27. All five gates pass on the committed mesh. Two of them pass narrowly, and the knee has no independent mesh measurement; read those before trusting the pass.

## Decision summary

- **What it means for Freyja:** the mesh's right thigh can be registered to the sheet's zero pose by a piecewise axial stretch (thigh x1.022, shank x0.970, foot x1.001, all inside the 8% gate) plus a horizontal shear of 64 mm (9.2 degrees) over the thigh. Cross-sections are untouched. The result is a voxel envelope with a 10 mm section ledger, silhouettes, and a working clearance oracle. The method is usable.
- **The finding that matters more than the gates: mass.** Skin volume of the conformed thigh is 6.31 l; the sheet's thigh mass is 9.49 kg. That is 1.50 kg/l against about 1.05 for soft tissue. Holding the sheet mass at tissue density needs about 9.0 l, 43% more than the sculpt. The sculpt is slim by design; its upper-thigh circumference matches ANSUR (see below), its lower thigh does not.
- **Numbers that matter** (reference beside each):

| Quantity | This trial | Reference |
|---|---|---|
| Stretch thigh / shank / foot | 1.022 / 0.970 / 1.001 | gate: within 8% of 1 |
| Shear thigh / shank | 64.5 mm (9.2 deg) / 44.9 mm (6.3 deg) | none; the A-pose legs are abducted |
| Min inscribed radius (outside hip zone) | 46.4 mm at station 390 (robust 5th pct 46.4) | gate: robust within 5 mm |
| Skin volume, nominal and 95% range | 6.30 l, 5.69-6.77 l (largest deviation 9.7%) | gate: within 10% |
| Implied density | 1.50 kg/l | soft tissue about 1.05 |
| Equivalent-circle circumference at station 0 / 350 mm | 617 / 331 mm | ANSUR female mean thigh 616 mm, lower thigh 401 mm (SD 56, 35) |

- **Decisions for you:**
  1. Is the sheet thigh mass (9.49 kg, 14.6% of 65 kg) or the slim sculpt the thing that gives? Recommended: keep the sculpt, treat the sheet mass as a lumped segment mass that includes soft tissue the envelope will not contain, and say so in ADR 0007. The lower thigh is the narrowest part against ANSUR (331 mm against 401 at the lower-thigh level), and that is where the knee actuators must live.
  2. Knee level: the mesh has no knee-breadth feature, so the KJC height is the ANSUR ratio. Recommended: place MakeHuman's Ruler vertex lists in the repo (`Ruler.Measures`, knee and ankle circumference) so the knee has a measured anchor.
  3. Whether the landmark picker, `landmarks.json` and the dead code stay. I removed the pelvis, provisional-landmark and landmark-sensitivity code (replaced by the revised Phase B). The picker page and the `landmarks/1` schema remain, unused by this trial.
- **What would change the conclusion:** a measured knee level more than about 20 mm from the ANSUR-ratio one (the shank stretch would leave 0.97 by that much), or a Ruler-based hip level that disagrees with crotch apex plus ANSUR offset.

## Findings

1. **Sheet nodes, read from the snapshot (no hardcoded Dumas values).** Ankle height 65.45 mm (ANSUR II malleolus 62.7 x 1700/1628.5, ADR 0038), KJC 472.99 mm, HJC 871.07 mm; the chain agrees with the model's own hip height (pelvis origin + thigh offset) to 1e-9 mm. HJC lateral offset 92.43 mm = 88 mm x k, k = 1.0503 (pelvis length 112.39 mm over the unscaled 107 mm you gave). The brief's B1 values (RASIS, MPSIS, HJC in ISB) are asserted from the snapshot's `source_landmark_*` keys and match exactly; a test changes one and sees the stop.
2. **Mesh features (heights above the sole, mesh stature 1697.3 mm).** Sole plane: lowest vertex, both feet within 0.0 mm of each other, 6 vertices within 1 mm. Midline 0.0 mm (feet symmetric). Crotch apex 809.1 mm (gap between the legs falls from 21.5 mm at 806 to 3.2 mm at 812; ANSUR-scaled crotch height 815.1). Knee: the right-leg breadth is 100-101 mm from 380 to 520 mm and rises to 102.7 mm at the band edge (535 mm); the peak is on the band edge with 2.8 mm prominence, so it is not a feature and the ANSUR ratio (485.5 mm) is used. If the weak breadth peak were used, the knee would sit 50 mm higher. Ruler polylines: not available in the repo, not done.
3. **Mesh nodes used:** AJC 65.4 mm (ANSUR ratio, nothing in the mesh stands for it), KJC 485.5 mm (ANSUR ratio), HJC 874.9 mm (measured crotch apex + the ANSUR trochanterion-above-crotch offset of 65.8 mm at this stature). Only the crotch is measured. Consequence: the stretches mix one measurement and two ratios, and the shank stretch (0.970) mostly says that the ANSUR knee ratio puts the mesh knee 12.5 mm above the sheet's.
4. **ANSUR diagnostics (sheet nodes against ANSUR means scaled to 1700 mm):** HJC is 11.4 mm below the scaled trochanterion (the flag is more than 20 mm); KJC is 13.4 mm below the scaled lateral epicondyle; AJC 0.05 mm from the scaled malleolus.
5. **Shear.** The mesh is an A-pose: right section centres run from y = -178 mm (ankle) through -134 (knee) to -73 (hip level) from the midplane. The brief's translate-not-deform shear straightens that, so the thigh's section centres move 64.5 mm relative to each other (9.2 degrees over 398 mm). Side effect: horizontal sections of a leg that leans 9 degrees are about 1.3% larger than sections normal to its axis (1/cos 9.2 degrees), so section areas and volume are slightly high. Not corrected.
6. **Envelope.** Skin volume 6.310 l; inner volume for t = 3, 5, 8, 10 mm: 5.805, 5.472, 4.993, 4.687 l (the sheet has no shell thickness, so the brief's sweep). Smallest in-plane inscribed radius outside the hip zone: 46.4 mm at station 390 (the knee end); for t = 3, 5, 8, 10 mm: 43.7, 41.6, 38.5, 36.5 mm. Hip zone (s < 40 mm): the section is the full right half of the pelvis plane, 30,300 mm2 at station 0; not meaningful as a thigh and reported apart in the ledger.
7. **Worked example** (`data/envelope/examples/`): a 60 mm OD rod, 150 mm long, centred at station 200 mm, lateral sweep. Feasible poses 0-15 mm lateral: worst margin 13.08 mm; infeasible poses 25-40 mm lateral: worst margin -11.52 mm. Both bind at station 275 mm (the rod's lower end, where the thigh narrows). `fy envelope check` prints margin, binding pose, station and point and exits 0 or 1.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| 1 topology, watertight | pass (topology tautological) | the reference is the exported file itself; boundary edges 0 (whole body 0), non-manifold 0, odd columns 0; HJC, KJC, AJC nodes inside the body |
| 2 stretch, robust envelope | pass, narrow | stretches above; robust radius diff 0.07 mm (gate 5); robust volume deviation 9.7% (gate 10%) |
| 3 conform | pass, narrow | length 398.082 mm = sheet (diff 0.0000); worst area change 0.84% at u = 0.1, all others under 0.07% (gate 1%) |
| 4 synthetic solids | pass | cylinder V 0.051, A 0.044, r 0.739 mm; box 0.000, 0.007, 0.250; cone 0.002, 0.106, 0.832 (gate 2 mm) |
| 5 oracle CLI | pass | as in finding 7 |

## Monte Carlo (N = 200, seed 0)

Mesh node heights drawn normal with the ANSUR SD of the ratio times the mesh stature: AJC 4.8 mm, KJC 17.3 mm, HJC 17.1 mm (ANSUR trochanterion-above-crotch SD, combined with 2 mm for the apex). Section-centre offsets drawn uniform +-10 mm. Result: thigh stretch SD 0.066, shank 0.042, foot 0.078 (the foot node has a 4.8 mm SD on a 65 mm height); skin volume 95% range 5.69-6.77 l. The section-centre offsets change none of the envelope outputs (sections only translate); they widen the thigh shear to 49-79 mm (95%). Per-station section areas and every t are in `data/envelope/thigh_R_trial.json`.

## Method choices and tolerances (mine)

- Piecewise-linear heights through sole, AJC, KJC, HJC; slope 1 outside. Shear linear between the three node heights, constant outside. The shear target is the sheet's lateral hip offset (y) and the knee section's own x. Section centre = area centroid of the largest piece of the right-of-midplane section (2 mm raster).
- Knee search band: ANSUR epicondyle estimate +-50 mm; a breadth peak counts as a feature only with prominence >= 3 mm and off the band edge. Crotch: first level above an open start where the gap between leg surfaces is below 5 mm.
- Monte Carlo remaps an unconformed section profile (2 mm steps), which is exact for area and radius because stretch and shear do not change a horizontal section; volume is stretch times the integral of area. Gate 2's "robust" values: 5th percentile of the minimum radius; the 2.5-97.5% volume range.
- The conform is applied to the mesh's vertices, so triangles that span a node are interpolated linearly between their moved ends. The mesh's 5-10 mm edge length bounds that error; I did not measure it separately, the synthetic slanted-tube test (a ring every 8.6 mm) checks the principle.
- Voxel field, band, sampling, sections: as memo 27.
- Pelvis length 107 mm is a named constant in `register.py` citing your message and ADR 0038 (no snapshot key holds it).

## My mistakes and defects

- I first read `base.obj` as missing; you resolved that. I also earlier killed processes that were not mine (memo 27).
- Two scripted edits wrote a broken string into `cli.py` because a heredoc dropped my escape; I fixed them with the editor and added a CLI test. The full run was delayed by this.
- Defect found along the way, not fixed: `Section.chebyshev()` returns an arbitrary point on the ridge when a section is elongated (an ellipse has no unique largest circle), so the centre columns of the ledger are not stable for elongated sections; the radius is. Hip-zone rows are the affected ones.
- Test files for the landmark path (pelvis frame, sensitivity, provisional landmarks) and `thigh.py`, `pelvis.py`, `provisional.py` are deleted, not kept (their function is gone). `sheet.py` still holds the B1-pull loader; nothing calls it now.

## Test suite

1538 passed, 3 skipped, 1 failed. The failure, `tests/test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce`, is not from this work: your pre_processor commit `d379525` rebuilt the model (model_sha256 now 1ceee245..., the three tracked run records still carry cfa2e074...), so `ENVELOPE.md` regenerates as "included: none". It needs the scenarios re-run and the digest and envelope regenerated; I did not touch it.

## Questions for Joe

1. The density gap: which gives, the sheet mass or the sculpt (above)?
2. Ruler vertex lists: can you place them (for example `data/makehuman/ruler_measures.json`)?
3. Should the shear be replaced by a rotation for the A-pose legs? It would keep sections normal to the axis (removes the 1.3%) but violates the brief's "sections translated, not deformed".
4. Delete `sheet.py`'s B1 loader, the landmark picker and `landmarks.py`, or keep them for the segments that follow?
5. Where is the "running list" the brief mentions? None exists in the repo. Results above used: mesh `data/makehuman/freyja-body-v1.obj`, ANSUR ratios `data/ansur2/ratios.json` (sha 12 in the JSON), no landmark file; KJC source: ANSUR ratio.

## Follow-ups (not done)

- Use of the unconformed ledger in the oracle is untested at the hip end beyond the example. The oracle takes a rod whose points beyond the slab ends report `slab_overrun_mm`; a margin at those ends comes from the extended solid.
- The in-plane Chebyshev radius in the ledger differs from the 3-D sd maximum used by the oracle on sloped skin.
- `fy envelope gates` takes about 4 minutes; `fy test` about 10.

Landmark file used: none. k variant: single (the sheet's pelvis factor 1.0503, used only for the lateral hip offset).
