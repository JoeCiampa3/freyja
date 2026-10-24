STATE: base f2defa491c98 | brief architecture sha256:bea77718dbaa, ariadne sha256:155afbaa35f6 | snapshot sha256:cf4fdfe08804 | tests 1551/1554 | dirty yes

# Memo 27: body-envelope thigh trial, Phase A handoff and provisional dry run

Brief: `docs/briefs/architecture/volume-extractor-brief1.md`. Status: **Phase A done, Phase B built and run on provisional landmarks only. Waiting on two things from Joe: the committed `data/mesh/landmarks.json`, and the sheet's B1 table.** Nothing below about the thigh is a trial result.

## Decision summary

- The picker, the pipeline, the oracle and `fy envelope` are built and tested. Every gate passes on a dry run with heuristic landmarks, so the machinery works; it says nothing yet about whether the method deserves ADR 0007.
- Two inputs the brief assumes are not what the brief says. The sheet's B1 table (RASIS, LASIS, MPSIS, HJC) is not in `params/snapshot.csv` or in any named range `pre_processor` pulls, and `base.obj` is byte-identical to the exported body, so the topology gate cannot fail. Details below.
- One early warning, provisional and to be confirmed with your picks: the dry-run thigh has a skin volume of 6.0 l; the sheet's thigh mass is 9.49 kg. That is an implied density of 1.58 kg/l against about 1.05 for soft tissue. If it survives real picks, the sheet's thigh mass and the slim-leg sculpt cannot both stand (the mesh would need about 9 l).
- Numbers that matter (provisional landmarks): required stretch s = 1.066 (gate: |s-1| < 8%; sheet pelvis factor variant 1.071); worst 5 mm landmark move changes s by 0.94% (gate 1.5%); Monte Carlo sigma 5 mm gives s = 1.067 +- 0.018; conformed length 398.082 mm vs sheet 398.082; section areas move 0.06% under the stretch (gate 1%); synthetic solids within 0.83 mm (gate 2 mm).
- Decisions for Joe: (1) supply the B1 pull. Recommended: add a named range for B1 and the 107 mm Dumas pelvis length so `pre_processor` can snapshot them (needs your say-so, it changes what `pre_processor` reads), or hand me `data/envelope/sheet_b1.json` in the format in `tools/envelope/sheet.py`. (2) Do the picks (`tools/landmark-picker/index.html`, open it in a browser, drag in `data/makehuman/freyja-body-v1.obj`). (3) If a real topology gate matters, place MakeHuman's own `base.obj`; recommended, cheap.
- What would change the conclusion: real picks giving |s-1| above 8%, or the density gap persisting. The first stops the trial; the second is a finding about the sheet, not about the method.

## Findings

1. **B1 is not in the repo's sheet pull.** Searched `params/snapshot.csv` and `pre_processor`: only the six BSIP/position/ROM/design named ranges are read. Needed and absent: RASIS, LASIS, MPSIS, HJC (Dumas) rows, and Dumas's 107 mm pelvis length (the denominator of the sheet's pelvis factor; the snapshot only has the scaled `pelvis_length`, 112.387 mm). Shell thickness is not in the Design Inputs keys either, so the trial reports t in {0, 3, 5, 8, 10} mm. Thigh length (398.082 mm) and mass (9.49 kg) are in the snapshot and are read from it.
   The pipeline loads B1 from `data/envelope/sheet_b1.json` and asserts the brief's numbers before anything runs (`sheet.assert_b1`, tested). For the dry run I used a file holding the values quoted in the brief, outside the repo, labelled DEV ONLY in its `source` field. Nothing in `data/envelope/` was built from it.
2. **`base.obj` and the exported body are the same file** (sha256 0b8c6853..., 13,380 vertices, 13,378 quad faces, one group named `base.obj`). Gate 1's topology comparison therefore passes by construction; it only protects against a future re-export that changes faces. A real check needs MakeHuman's own `base.obj`.
3. **"Left = +x" cannot be verified from `joint-l-*` groups**: helper geometry is off, so the file has one group. Phase B will assert from the picks that ASIS_L has the larger MakeHuman x than ASIS_R, which is the same statement.
4. **`data/mesh/freyja-body-v1.obj` and `data/makehuman/freyja-body-v1.obj` are both tracked and identical.** One home per quantity says one should go. I used `data/makehuman/` as the mesh and `data/mesh/` as the topology reference.
5. **Mesh facts:** height 1697 mm, extent in x 578 mm (arms out, A-pose), watertight everywhere (0 boundary edges, 0 non-manifold edges, 0 odd-parity columns).

## Provisional dry run (heuristic landmarks, DEV B1)

`tools/envelope/provisional.py` takes extremal vertices in fixed height bands. Inter-ASIS 245 mm (k = 1.028 against the sheet's 1.050), sacral point 128 mm behind the ASIS plane.

| Gate | Result | Numbers |
|---|---|---|
| 1 topology, watertight | pass (topology tautological, finding 2) | boundary edges near thigh 0, odd columns 0 |
| 2 s and sensitivity | pass | s = 1.0663 (6.63% from 1); worst one-at-a-time 0.94% (ASIS_R z, 5 mm); MC N=200: 1.0670 +- 0.0178, 5-95% 1.0376-1.0953 |
| 3 conform | pass | length 398.082 vs 398.082 mm; worst area change 0.056% at u 0.1-0.9 |
| 4 synthetic solids | pass | cylinder V 0.051, A 0.044, r 0.739 mm; box 0.000, 0.007, 0.250; cone 0.002, 0.106, 0.832 (limit 2.0) |
| 5 oracle CLI | pass | feasible: margin 8.44 mm at station 275 mm; infeasible: -16.33 mm at station 275 mm (pose 3) |

k variants: mesh inter-ASIS k 1.0284, s 1.0663, skin volume 5.999 l; sheet factor k 1.0503, s 1.0714, 5.971 l; the two hip centres differ by 2.71 mm. The sheet-factor variant uses 107 mm from the dev B1 file.
Volumes (l): skin 5.999; inner t = 3, 5, 8, 10 mm: 5.496, 5.164, 4.688, 4.385. Density: 9.49 kg / 5.999 l = 1.58 kg/l. Smallest in-plane inscribed radius outside the hip zone: 46.1 mm at station 380 mm (36.3 mm for t = 10).
Sensitivity worst case is a single ASIS because k follows the inter-ASIS distance.

## What was built

- `tools/landmark-picker/index.html` (+ `vendor/three.min.js`, r160, LICENSE): drag and drop OBJ, orbit/zoom/pan, wireframe, sagittal clipping slider, click snaps to the nearest corner of the hit face and shows id and mm in both frames, ordered checklist, markers, undo (button and Ctrl+Z), axis gizmo labelled "+x subject LEFT", export and import `landmarks.json`. Checked headlessly in Edge: the page loads, parses the 13,380-vertex OBJ, imports a landmarks file and places markers, no script errors. **Not checked: clicking, dragging and rendering with a real GPU and mouse.** Expect the console to print a three.js deprecation notice (the classic build is used so the page works from `file://`).
- `tools/envelope/`: `landmarks` (schema), `meshio` (OBJ, topology, frame map), `sheet`, `pelvis`, `thigh`, `field` (voxel field), `ledger`, `plots`, `oracle`, `trial`, `gates`, `synthetic`, `provisional`, `cli`. `python tools/fy envelope build | gates | check`.
- `data/envelope/examples/`: the worked example (rod OD 60 mm, 150 mm long, centre at station 200 mm, lateral sweep 0-15 mm feasible, 25-40 mm infeasible). **Tuned on the provisional thigh; I will retune it on the real one.**
- `CONVENTIONS.md` section 2: rows for `tools/envelope/`, `tools/landmark-picker/`, `data/mesh/`, `data/envelope/`, with the `landmarks/1` schema (same commit).
- Tests: 6 new test files (landmarks, pelvis, thigh, field, ledger, oracle).

## Method choices and tolerances (all mine; the brief fixes only the gates)

- Voxel 2 mm (brief). Signed distance: voxel EDT to classify, exact nearest-sample distance within 10 mm of the skin (skin sampled so that every point is within 1 mm of a sample), deeper cells carried inward from the band's inner edge. A direct query for every cell took minutes because the nearest skin on the medial axis is equidistant from thousands of samples. The first version of this hung my session for several minutes.
- Inside/outside by x-ray parity on the extended solid; the slab, the right-of-midplane clip and the connected component containing the mid-axis point only mask the result. Cut planes never enter a distance (tested: radius at s = 0 and s = L equals the cylinder radius).
- Volumes use a one-voxel linear ramp on sd instead of a hard threshold (removes the staircase bias).
- Sections are sampled at 0.5 mm; Chebyshev circle from a 2-D EDT of that raster (about 0.25 mm bias).
- Gate 4 "within one voxel" is read as surface displacement: |dV|/surface area, |dA|/perimeter, |dr| all below 2 mm.
- Gate 3 compares the stretched and the unstretched build at the same normalised stations u = 0.1..0.9 (hip zone excluded). The stretch cannot change a cross-section by construction; the gate checks the voxel pipeline does not either.
- Hip zone: s < 40 mm (brief); the ledger header reports its inscribed radius apart.
- Half-widths are measured from the axis, not the Chebyshev centre; the 8 directional radii from the Chebyshev centre. Rays stop at the midplane, so touching thighs do not read through each other.
- SACRAL_MID is a skin point standing in for MPSIS (bone). It is 20-odd mm off, which tilts the pelvis X axis; the ±5 mm sensitivity does not cover that bias.
- Landmark perturbations are along the sheet axes, one landmark, one axis, one sign at a time (30 runs).

## My mistakes

- I stopped every `python` process on the machine while clearing my own hung test runs. Two of them (started 13:40, before this session) were not mine; I do not know what they were (possibly the editor's language server). If something of yours died, that was me.
- A scatter of first drafts failed before they worked: a skin-sampling scheme that produced 10 million points, and a test whose expectation was symmetric and could not have passed. Both fixed; neither affects results.

## Questions for Joe

1. B1 pull: named range in the sheet (changes what `pre_processor` reads, so your call) or a hand-made `data/envelope/sheet_b1.json`? Also the Dumas pelvis length (107 mm) for the sheet-factor variant.
2. Picks: ASIS_R, ASIS_L, SACRAL_MID, EPI_MED_R, EPI_LAT_R into `data/mesh/landmarks.json`.
3. MakeHuman's own `base.obj` for a real topology gate?
4. Which of the two tracked copies of the OBJ stays?
5. The density gap (1.58 kg/l, provisional). Is the sheet's 9.49 kg the Dumas segment mass of 65 kg x 14.6%, and is the slim-leg aesthetic allowed to give?

## Follow-ups (not done)

- Real-picks run, final gate table, the sagittal/coronal plots, worked example retuned: next session, after the picks and B1 arrive.
- The ledger header's `min_inscribed_radius` is the 2-D in-plane Chebyshev radius, not the 3-D sd maximum; the oracle uses 3-D distance to the skin. The two agree on prismatic stretches and differ on the sloped skin of a cone; say if you want the 3-D value in the ledger as well.
- `fy envelope` tests take about 90 s together; the rest of the suite is unaffected.

Landmark file and k variant used: provisional heuristic, both variants reported above; no committed landmark file yet. The brief asks for an entry on a "running list"; I found no such file in the repo, so this line is the record until you say where the list lives.
