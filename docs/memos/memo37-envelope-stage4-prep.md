STATE: base 8adbc6b4db26 | brief architecture sha256:302e28b3c0fc, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1742/1746 | dirty yes

# Memo 37: envelope preparation for Stage 4 (volume-extractor brief 7)

Brief: `docs/briefs/architecture/volume-extractor-brief7.md`. Items 1 to 4 done; ADR 0007 is drafted (`proposed`), not accepted. The shift was derived without ambiguity and no example margin moved. **Existing outputs did change in the ways listed in finding 2, which your stop rule names: the margins did not, the coordinates and the printed text did. Read that before accepting the commits.**

## Decision summary

- **What it means for Freyja.** The oracle and the registry now take every part in the frame of the MuJoCo model's body of that name (pelvis origin at the lumbosacral joint), so a Stage 4 part is placed where the sim puts it. The conversion to the oracle's built bodies is one computed constant, 56.719 mm (the model's HJC ahead of its pelvis origin), applied inside the oracle and printed in every trunk result. The five trunk-example margins are unchanged to the printed digit. The new report (item 2) found that the sim's trunk stack and the mesh trunk are not on the same line, and that in the zero pose the stack axis at the TJC is **outside the skin**.

| Number | Value | Reference |
|---|---|---|
| Mesh-to-model trunk shift: oracle = model + (-56.719, 0, 0) mm; mesh x of the model's trunk axis | 49.994 - 56.719 = -6.725 mm (conformed mesh frame) | `thigh_right_pos_x` 0.0567188 m; ADR 0004 "56.6 mm now" |
| Trunk example margins, feasible / infeasible: pelvis box; thorax box; union | +37.13 / -11.59; +17.50 / -34.40; +39.40 and overrun 37.32 | memo 36: +37.128 / -11.588; +17.497 / -34.405; +39.405 / 37.318 (limit 0.01 mm) |
| Sim stack minus mesh centre line, zero pose, x at LJC / TJC / CJC / SJC | -70.1 / -92.1 / -39.2 / -50.3 mm (mean of the two bodies at a plane) | design stance: -51.0 / -70.6 / -23.3 / -26.1 mm |
| Skin margin at the sim's stack axis, TJC (thorax section) | zero pose **-12.2 mm (outside)**; design stance +10.3 mm | LJC +24 / +41 mm, CJC +1 to +2 / +16.7 mm |
| Mesh centre-line y against the midline | at most 0.20 mm (at the SJC) | symmetric |
| Design stance rise of the stack | 9.658 mm | memo 34: 9.66 mm |
| Same stance with the lean about the ankle (stand_static's), CJC offset / skin margin at the stack | -6.0 mm / +32.9 mm (against -23.3 / +16.7 upright) | the lean is a sensitivity, section 3 |
| Sheet segment COM x in its body frame (abdomen / thorax / pelvis) | +31.0 / +6.9 / -1.0 mm | the mesh centroid sits 13 to 35 mm ahead of the hip line, the stack 57 (zero) or 35 mm (stance) behind it |

- **Decisions for you.**
  1. **Existing outputs that changed** (finding 2): `data/envelope/trunk_bodies.json` (the example points' x moved by +56.719 mm with the poses, a new `frame_offset_mm` on each example), `data/envelope/leg_R_trial.json` (the three example gate rows end with the frame line), and the six example pose files (migrated, with a comment line). Recommended: accept; the alternative (leave the points in the oracle frame) would print points in a frame the poses are no longer in. If you want them reverted, say so and I restore the oracle-frame reporting.
  2. **The stack against the skin.** In the zero pose the model's TJC axis is 12.2 mm behind the mesh's back surface, and the CJC axis is 1 to 2 mm inside it; the design stance brings them to +10.3 and +16.7 mm. The cause is in the sheet and the model (the abdomen, thorax and head are stacked at zero x offset above a pelvis origin 56.7 mm behind the hip, and the zero pose has no tilt), not in the mesh. Not mine to change. Recommended: for Stage 4 trunk placement use the design stance as the reference for any part that sits on the stack axis; decide whether the trunk's zero x offsets are still what you want.
  3. **The hip spacing.** The mesh's hip joint centres are 75.6 mm either side of its midline (conformed y: trunk origin -16.83, right hip -92.43); the sheet's are 92.43 mm. The shear moves the trunk, it does not widen the pelvis (cross-sections are unchanged by rule, ADR 0007 D2). It matters for a pelvis part near the hip. Recommended: leave, and put it in the contract's accuracy limits (done).
- **What would change the conclusion.** A different definition of the "centre line" (I used the area centroid of the section; a bounding-box midline or a spine line would move every x offset by tens of millimetres, but not the skin margin at the stack axis, which does not depend on it); the lean about the ankle (the stance as `stand_static` holds it moves the CJC offset from -23.3 to -6.0 mm; section 3); a trunk whose zero-pose stack is changed in the model.

## 1. Item 1: model body frames

- `tools/envelope/frames.py`. Model body frames for every segment; the trunk bodies' oracle frame is the model frame shifted by (-hjc_x, 0, 0), the head and neck by (-hjc_x, 0, -length) (its oracle origin is the vertex, the model's the CJC below it). Legs are unchanged.
- **How the shift is derived (and why it is unambiguous).** The mesh hip line is the vertical through the knee section, `reg.target_xy[0]` = 49.994 mm in the conformed mesh frame (the shear makes the hip section's centre sit on it); the oracle's thigh origin and every trunk body's origin are on it. The model's HJC is `thigh_right_pos_x` = 56.7188 mm ahead of its pelvis origin, read from the snapshot and checked against the MuJoCo model's forward kinematics (test, to 1e-6 mm). So the model's trunk axis is at 49.994 - 56.719 = -6.725 mm in the mesh frame, and oracle = model + (-56.719, 0, 0). The z of the origins agrees without a constant: the model's pelvis origin is at 968.75 mm (the sheet's LJC), the abdomen at +127.09 mm (TJC), the thorax at +328.76 mm (CJC), the head and neck at the thorax origin; test against the model's body positions, 1e-3 mm. The y of the model's pelvis is the midline: no shift.
- Stored at build time in each trunk body's cache meta (`model_to_segment_mm`, `mesh_hip_line_x_mm`, `model_hjc_x_mm`, `mesh_to_model_trunk_shift_mm`), applied by `oracle.clearance` and `clearance_union` (`frame_offset_mm`), by the registry (`Registry.frame_offset_mm`, so components, sweeps and foreign poses are all in the model frame) and printed as a `frame:` line in every trunk `check` and `free` (`fy envelope check` for a leg prints nothing new). A trunk cache built before this brief stops (exit 3) and says to rebuild. Reported points come back in the frame the poses were given in.
- The trunk examples' pose files are migrated by the constant (tx + 56.7188220965, with a comment line saying so). Margins: table above.
- Test (`tests/test_envelope_frames.py`, 11): the offsets by segment; the HJC x against MuJoCo; the oracle with and without the shift (a pose 56.7 mm off in x gives a different answer); the union; the CLI stop on an old cache, the frame line on a trunk check, no line on a leg; **the model's LSJ origin maps to the expected mesh position** (x and z against the MuJoCo model's own positions relative to the right hip centre, 1e-6 mm; y is the mesh midline), and the abdomen, thorax and head and neck origins likewise; the migrated examples' margins.
- Not done: nothing in the sim, the model, the sheet or the template was touched.

## 2. Existing outputs that changed (your stop rule)

`fy envelope build` regenerated every ledger, silhouette and result byte-identical (git shows no change under `data/envelope/` other than the files below). `fy envelope gates` changed:

| File | Change |
|---|---|
| `data/envelope/examples/{pelvis_box,thorax_box,trunk_union}_{feasible,infeasible}_poses.csv` | tx + 56.7188220965, one comment line |
| `data/envelope/trunk_bodies.json` | each example's `point_mm` x moved by exactly +56.7188 (e.g. 60.0 -> 116.7188), `frame_offset_mm` added; every margin, station, pose index, overrun and flag identical |
| `data/envelope/leg_R_trial.json` | the detail text of the three example gate rows ends with the `frame:` line; no number changed |
| `docs/STATE.md` | regenerated |

The thigh examples, the thigh's `.out` files and its free-space ledger are byte-identical (a test compares them). No tolerance was touched.

## 3. Item 2: the sim's trunk stack against the mesh trunk centre line

`fy envelope offsets` (new; `tools/envelope/offsets.py`, `data/envelope/trunk_offsets.json`, test `tests/test_envelope_offsets.py`, 4). Sim: MuJoCo forward kinematics of the lumbosacral joint, TJC, CJC and the SJC (the upper-arm origin) relative to the right hip joint centre; the zero pose is `qpos0`, the design stance is `leanpose.design_stance(model, 12.0, upright=True)` (pelvis tilted 12 degrees, hips flexed 12, lumbosacral extended 12; ADR 0004), called, not changed. Mesh: the area centroid (x, y) of the built body's section at the plane's height, relative to the hip line and the midline. Offset = sim - mesh. A plane bounds two bodies, so the zero pose lists both. All in mm:

| Plane | Pose | Plane height above HJC | Sim x | Body | Mesh centroid x | Offset x | Offset y | Skin margin at the stack |
|---|---|---|---|---|---|---|---|---|
| LJC | zero | 97.68 | -56.72 | pelvis / abdomen | 13.15 / 13.66 | -69.87 / -70.38 | 0.00 / 0.00 | +24.97 / +24.27 |
| TJC | zero | 224.78 | -56.72 | abdomen / thorax | 35.36 / 35.42 | -92.08 / -92.14 | 0.00 / -0.01 | -12.34 / -12.19 |
| CJC | zero | 553.53 | -56.72 | thorax / head and neck | -18.12 / -17.02 | -38.60 / -39.70 | -0.02 / 0.06 | +2.09 / +1.12 |
| SJC | zero | 475.96 | -56.72 (axis; the joint 13.81 ahead) | thorax | -6.41 | -50.31 | 0.20 | +30.60 |
| LJC | stance | 107.34 | -35.17 | abdomen | 15.79 | -50.96 | -0.02 | +41.05 |
| TJC | stance | 234.43 | -35.17 | thorax | 35.41 | -70.58 | 0.01 | +10.34 |
| CJC | stance | 563.19 | -35.17 | head and neck | -11.90 | -23.27 | 0.01 | +16.74 |
| SJC | stance | 485.62 | -35.17 | thorax | -9.07 | -26.10 | 0.18 | +50.32 |
| LJC | stance + lean | 108.40 | -31.76 | abdomen | 15.99 | -47.76 | 0.01 | +43.61 |
| TJC | stance + lean | 235.43 | -27.75 | thorax | 35.38 | -63.13 | 0.00 | +17.85 |
| CJC | stance + lean | 564.02 | -17.37 | head and neck | -11.38 | -5.99 | 0.04 | +32.94 |
| SJC | stance + lean | 486.06 | -19.83 | thorax | -9.19 | -10.64 | 0.18 | +64.87 |

The stack stands 9.658 mm higher in the stance (the tilt raises the lumbosacral joint) and 21.5 mm nearer the mesh centre line in x (-56.72 -> -35.17); the stance LSJ is 35.17 mm behind and 107.34 mm above the hip, ADR 0004's 34.3 and 107.5 at 12.43 degrees. In the stance the trunk is plumb, so the stack x is one number. Left-right: the mesh centroids are on the midline to 0.2 mm; the stack is on it.

**Reading it.** The centroid of a trunk section is ahead of the spine in a person, so a zero offset is not the target; the sheet's own segment COM x (abdomen +31.0 mm, thorax +6.9 mm, pelvis -1.0 mm in their body frames) is the nearest reference the repo has, and the mesh's offset at the TJC is 92 mm (zero) or 71 mm (stance), well beyond it. I draw no conclusion from that comparison (a section centroid at a plane is not a body COM). The skin margin at the stack axis is the number that does not depend on the definition: **-12.2 mm at the TJC in the zero pose** (the model's axis is behind the mesh's back), +10.3 mm in the stance.

Choices (mine, stated): "centre line" is the area centroid; the planes are sampled EDGE_MM = 1 mm inside each body at a boundary; the stance is the pure tilt without the CoM lean about the ankle (`design_stance(..., upright=True)`), and a third pose, the stance with the lean (`com_x_rel_ankle_m` 0.0, as `stand_static` holds it), is reported as a sensitivity in the last four rows of the table, in world axes: the lean tips the trunk forward with height (the CJC moves 17.9 mm forward, the TJC 7.4 mm, the LJC 3.4 mm) and takes the CJC offset from -23.3 to -6.0 mm. My first estimate of this effect in an earlier draft of this memo (11 mm at the CJC) was wrong by a factor of two; the figures are computed. The mesh is not moved with the stance: its section is taken at the stance plane's height above the hip, and the SJC row uses the thorax axis at the SJC's height (the line through the TJC and CJC origins). Values are rounded to 3 decimals in the file.

## 4. Items 3 and 4

- `docs/envelope-component-contract.md` (draft): the fields per component (id from the Ariadne scheme `part.<assembly>.<name>`, owner `seg.<name>` and side, model frame with the origin table, bounding primitive, optional watertight STL in the owner frame, status, clearance, mass, `sha256`, parameter-snapshot hash), right authoritative with the left by mirror (y negated; the rotation components rx and rz change sign, ry does not; mesh winding reversed), the accuracy limits (2 mm voxel, `marginal` under one voxel, 1 mm sampling, 1 mm mesh voxel and the exact distance for the binding pair, 96 facets, sweeps are rows, the sculpt is not a person, planes are accounting). Three fields (`revision`, `sha256`, `parameter_snapshot`) are not in the registry yet.
- `decisions/0007-envelope-extraction.md`: status `proposed`, D1 to D11 in your order with the wording tightened, a Context that cites memos 27 to 36 and the files, and a Consequences and a Rejected-options section (CONVENTIONS asks for it; the options are only those the list and the memos name). Not accepted; `rm.v1-volume-extracted` untouched.
- **Memo check against the list (your stop rule): no memo contradicts a decision.** Three places where the memos say less or something different, for you to see; I did not adjudicate any:
  1. D2 "arms a rigid rotation per segment": no memo from 27 to 36 registers or rotates the arms (they are the unbuilt remainder). Written as you gave it; it is a plan, not a result.
  2. D7: memo 33 section 4 presents the 9.0% as a context note and "draws no inference"; D7 states it as a finding. The numbers agree (raw ratio 1.099, 63.9 kg, 1.61 m, BMI 24.7 and 18.05).
  3. D1 "no other source": the mass base and the realism checks use Siri, Deurenberg, Hall, Winter and Dumas 2015 and 2007 (memos 29 to 33). The Context lists them as allowed for those two purposes, not for dimensions.

## 5. Gate table (`fy envelope gates`, v2, chords, 2 mm; all pass)

| Gate | Result | Numbers |
|---|---|---|
| 1 topology and watertight, thigh / shank / pelvis / abdomen / thorax / head and neck | pass | unchanged from memo 36 |
| 2 stretch within 8% | pass | thigh 0.9914, shank 1.0007, foot 0.9997, pelvis 1.0000, abdomen 1.0000, thorax 1.0038, head and neck 0.9754 |
| 3 matched-station areas within 1%; 3b field volume against the raster | pass | unchanged: worst 0.243% thigh, 0.178% shank, 0.059% pelvis, 0.140% abdomen, 0.653% thorax, 0.221% head and neck |
| 4 synthetic solids within 2 mm | pass | unchanged |
| 5 oracle: rod in the thigh; pelvis box; thorax box; trunk union | pass | rod +16.61 / -8.18 mm; pelvis +37.13 / -11.59; thorax +17.50 / -34.40; union +39.40, overrun 37.32 (unchanged; poses now in the model frame) |
| 6 volume against Blender | pass | -0.003% |
| 7 closure | pass | -0.389% |

## 6. Tolerances and parameters I chose

`EDGE_MM` = 1 mm (a plane on a body boundary is sampled this far inside each body); the example check 0.01 mm (yours); rounding of the offsets file to 3 decimals; the stance without the ankle lean; the area centroid as the centre line. No check tolerance or geometry value was changed, none was tuned toward a result.

## 7. My mistakes and defects

- Two edits through a shell heredoc turned `\n` into a real newline (once in `cli.py`, the same defect as memo 35); caught by the first run, fixed with the editor tool.
- I started `fy envelope gates` as a shell background job once and it produced nothing; I reran it as a background task. The numbers above are from the second run.
- Three of my own test expectations were wrong (a margin of 35 mm that is 25, an `sjc` x that I had defined as the axis, a pose file parsed with a header skip); the code was right each time and I changed the tests.
- I wrote the tests first and watched them fail at collection; the offsets test was written with the code in the same step, so I did not watch it fail on its own.
- The full suite ran once, after all four items, not once per commit as CLAUDE.md asks; the commits are cut from that one verified tree.
- Defect found, not fixed: in `check --segment a,b` with a registry on the second body, `component_skin_margins` (the "sticks out of the skin" warning) uses the union's frame without the body's offset; it affects only that warning, not the verdict or the margins.

## 8. Tests and files

STATE line above. Known failure: `test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce`. New: `tests/test_envelope_frames.py` (11), `tests/test_envelope_offsets.py` (4, the report test checks the lean variant and the skin margin against the body field); changed: `tests/test_envelope_occupancy_cli.py` (its synthetic trunk caches now declare a zero model frame). New code: `tools/envelope/frames.py`, `offsets.py`; changed: `oracle.py`, `registry.py`, `bodies.py`, `bodies_report.py`, `register.py` (`hjc_x_mm` on `SheetNodes`), `cli.py` (`offsets`, the frame lines), `CONVENTIONS.md` and `docs/schemas/envelope-oracle.md` (same commit). `fy thread build` before the suite: 0 changed.

## Follow-ups

1. Accept or revert the output changes in section 2.
2. Decide what the trunk's zero-pose x offsets should be, given the stack axis outside the skin at the TJC (a model/sheet question).
3. The Stage 4 connector's format; then `revision`, `sha256`, `parameter_snapshot` in the registry, and the left side's CAD frames.
4. The 16.8 mm hip-spacing difference between the mesh and the sheet.
5. Arms (D2's rotation) and reservations, the next briefs.
