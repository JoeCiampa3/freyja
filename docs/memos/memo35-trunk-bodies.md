STATE: base f7c0fe1f7b9c | brief architecture sha256:3cf061256d79, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1661/1665 | dirty yes

# Memo 35: trunk bodies, joint zones, per-body design numbers (volume-extractor brief 5, items 2 to 8)

Brief: `docs/briefs/architecture/volume-extractor-brief5.md`, with your memo 34 decisions (ANSUR cervicale anchor, slope-1 map, head and neck at the sheet's length, shoulder plane through the SJC with a sphere zone, new share denominator for new rows only). All items done and no stop condition tripped: thorax and head stretch 1.0038 / 0.9754, no arm merges below the axilla (found at 1296 mm from the layer topology), the mesh is watertight, every gate passes.

## Decision summary

- **What it means for Freyja.** The four trunk bodies exist as whole-width voxel fields in the zero pose, with arms and shoulder girdle excluded, and an oracle that can say whether a box fits in the pelvis or thorax (feasible and infeasible placements both reproduced) and whether a rod fits across the LJC plane. The abdomen + pelvis pair must average **1.218 kg/l over its skin volume** (1.335 over a 5 mm inner shell) to carry the sheet's 12.155 kg. The thorax needs 1.085 kg/l and the head and neck 1.152 kg/l. Individual pelvis (1.715) and abdomen (0.599) numbers are not results: the frame planes are not the Dumas mass cuts, which is what the pair absorbs.

| Number | Value | Reference |
|---|---|---|
| Abdomen + pelvis required density, skin / inner t5 | 1.218 / 1.335 kg/l (9.982 l, 12.155 kg) | whole-body robot average 1.311 kg/l (memo 32) |
| Thorax / head and neck required density, skin | 1.085 / 1.152 kg/l (15.752 / 3.781 l) | water 1.0 |
| Thorax and head stretch | 1.0038 / 0.9754 | gate 8% |
| Closure: conformed bodies + remainder against mesh volume | 52.126 l vs 52.332 l, -0.392% | gate 0.5% |
| Neck pinch (head and neck, min inscribed radius) | 28.0 mm at station 170 mm (21 mm prominence) | |
| Thorax with / without the shoulder spheres | 15.765 / 15.702 l | sphere radius h = 25 mm |
| Shoulder girdle assigned to the arm side, right / left | 0.296 / 0.307 l | |
| Axilla (arm pieces merge with the core) | 1296 mm right, 1294 mm left (mesh, above the sole) | |

- **Decisions for you.**
  1. The Inspect envelope OBJ is now 94 MB (was 27 MB) because the four whole-width bodies are in it. You said to thin only if load exceeds 10 s or the frame rate drops under 20 fps; I did not open the viewer. Recommended: open it, and thin if it is slow.
  2. The SJC X coordinate was not given with Y and Z. The sphere centre uses the thorax's mean x at that height (17.2 mm in the mesh frame). It moves the thorax-with/without difference (0.063 l, 0.4%) and nothing else. Recommended: send Table 1's X when convenient; no rerun needed unless it differs by more than about 20 mm.
  3. Nothing else is open. The memo 32 and 33 share rows stay on the mesh-volume denominator as you decided.
- **What would change the conclusion.** A different CJC (a picked C7 vertex would move volume between the thorax and the head and neck at about 0.16 l per 10 mm (the section at the CJC plane is 15,700 mm2) and shift their stretches by about 3% per 10 mm); the arm rule (the vertex-label rule against the layer topology differs by 0.22% of the core volume, so it is not the sensitive part); the Dumas pelvis and abdomen mass cuts being brought into the frame bodies (the pair would then change; the thorax and head would not).

## 1. Gate table (v2, ANSUR cervicale CJC, slope-1 map, chords, 2 mm)

| Gate | Result | Numbers |
|---|---|---|
| 1 topology and watertight, pelvis / abdomen / thorax / head and neck | pass | identical to `base.obj`; boundary edges near each body 0; non-manifold 0; odd-parity columns 0 |
| 2 trunk stretch | pass | pelvis 1.0000, abdomen 1.0000 (slope 1 by the map), thorax 1.0038, head and neck 0.9754 |
| 3 matched-station areas against the raster layers (u = 0.1 to 0.9) | pass | worst 0.059% / 0.140% / 0.459% / 0.212% |
| 3b field volume against the raster accounting (my check) | pass | -0.29% / -0.55% / -0.08% / -0.09% (tolerance 1%) |
| 4 synthetic solids, 5 rod in thigh, 6 volume vs Blender | pass | unchanged: cylinder, box, cone within 2 mm; margins as in memo 32; 52.3315 vs 52.3331 l (-0.003%) |
| 5 pelvis box (100 x 160 x 50 mm at station 50) | pass | feasible +37.13 mm; infeasible (moved 70 mm left) -11.59 mm |
| 5 thorax box (120 x 180 x 100 mm at station 160) | pass | feasible +17.45 mm; infeasible -34.38 mm |
| 5 union query: rod OD 40 x 150 mm across the LJC plane | pass | feasible in the union +39.40 mm, overrun 0; the pelvis alone overruns by 75 mm; lowered 60 mm: overrun 37.32 mm |
| 7 closure | pass | -0.392%; remainder 3.700 l (arms 3.100, shoulder girdle 0.295 + 0.306); the conform itself changes the built volume by -0.143 l, the cell accounting closes to -0.0006 l |

The leg results are unchanged: the thigh, shank and foot ledgers are byte-identical and `leg_R_trial.json` changed only by the new diagnostic fields and the new gate rows.

## 2. Registration and planes

- CJC from ANSUR cervicale less the Dumas C7 offset (29.4 mm): 1426.5 mm mesh, 1424.6 mm sheet (memo 34's table). Mesh nodes (above the sole): HJC 874.2, TJC 1099.0, CJC 1426.5, vertex 1698.95. The map is slope 1 from the HJC to the TJC, then the thorax (x1.0038) and the head and neck (x0.9754); the head and neck keeps the sheet's length and the 9.66 mm to stature is not given to it (your decision 2). Conformed top of head: 1690.34 mm.
- **Orientation of the planes.** Horizontal in the zero pose. The template gives no trunk body a rotation and the sheet places the abdomen, thorax and head on the pelvis frame's vertical axis; the 12 degrees of `stand_pelvis_tilt_deg` is applied only in the design stance (record 0004, ADR 0038), where the pelvis tilts and the trunk stays plumb. That tilt is the 9.66 mm of memo 34.
- Bodies and stations: pelvis HJC (871.1) to LJC (968.8), 97.7 mm; abdomen to TJC (1095.8), 127.1 mm; thorax to CJC (1424.6), 328.8 mm; head and neck to the vertex (1690.3), 265.7 mm. A body's frame has its origin on the vertical line through the knee section's x and the midline, at its upper plane; stations are distances below it. A cell on a plane belongs to the body above it.

## 3. Arms

- Axilla, from the layer topology: the top of the highest layer with a separate arm piece of at least 500 mm2 on each side: right 1296 mm, left 1294 mm (2 mm apart, one layer). Arm pieces of at least 500 mm2 exist continuously from 968 mm (where the hand's piece first reaches that area) to the axilla on both sides: **no layer below the axilla has an arm merged with the trunk**, and none is missing a piece. Above the axilla arm and core are one piece up to the shoulder tops.
- Cut: the thorax, above the axilla, is cut at the vertical plane through the SJC, 178 x 1.0504 = 187.0 mm lateral of the midline (the SJC is 88.2 mm below the CJC, z = 1336.4 mm conformed). What lies beyond is shoulder girdle: right 0.296 l, left 0.307 l (3.5% apart), part of the unbuilt remainder with the arms.
- Shoulder zone: a sphere of radius h = 25 mm at each SJC, owned jointly. Right sphere: thorax-side 0.0308 l, arm-side 0.0307 l; left: 0.0321 and 0.0326 l. Thorax volume with the spheres 15.765 l, without them 15.702 l.
- Vertex-label rule (memo 32) against the layer topology: the core above the hip-centre plane is 30.207 l by label and 30.274 l by topology (-0.22%). Two clean-ups I added to the label rule, both reported: 0.0434 l of cells that the nearest-vertex rule left on the torso just below the axilla (arm cells whose nearest vertex lies on the torso side of the label boundary) are reclassified as arm, because below the axilla an arm is a separate piece of its layer; and 0.0164 l of cells inside the shoulder planes above the axilla whose nearest vertex is an arm vertex stay excluded from the thorax (0.1% of it). The voxel field drops the first set by itself (it is not connected to its seed), so field and accounting agree.

## 4. Joint zones (h = 25 mm, litres, conformed; with the zone / without the slab at each plane)

| Body | With | Without each plane | Without all |
|---|---|---|---|
| Pelvis | 5.549 | HJC 4.027; LJC 4.256 | 2.734 |
| Abdomen | 4.473 | LJC 3.315; TJC 3.775 | 2.617 |
| Thorax | 15.765 | TJC 15.008; CJC 15.120 | 14.363; without the shoulder spheres as well 14.300 |
| Head and neck | 3.784 | CJC 3.490 | 3.490 |
| Thighs (both) | 12.843 | HJC slab 1.508 below the plane | 11.335 |

Slabs on both sides of every plane are in `trunk_bodies.json` (`zone_planes_raw_l`). Volumes in this table are from the cell accounting (2 mm cells split by overlap at every plane); the voxel fields give 5.533, 4.449, 15.752 and 3.781 l.

## 5. Design numbers (t = 3, 5, 8, 10 mm inner shells)

| Body | Skin l | Inner l t3 / t5 / t8 / t10 | Sheet kg | Required kg/l: skin; t3 / t5 / t8 / t10 | Min inscribed radius (station) | Pinch |
|---|---|---|---|---|---|---|
| Pelvis | 5.533 | 5.271 / 5.096 / 4.839 / 4.672 | 9.490 | 1.715; 1.800 / 1.862 / 1.961 / 2.031 | 98.8 mm (97.7, the HJC plane) | none |
| Abdomen | 4.449 | 4.185 / 4.010 / 3.755 / 3.591 | 2.665 | 0.599; 0.637 / 0.665 / 0.710 / 0.742 | 81.8 mm (30) | none |
| Thorax | 15.752 | 14.895 / 14.318 / 13.471 / 12.921 | 17.095 | 1.085; 1.148 / 1.194 / 1.269 / 1.323 | 49.2 mm (0, the CJC plane) | none |
| Head and neck | 3.781 | 3.282 / 2.962 / 2.515 / 2.244 | 4.355 | 1.152; 1.327 / 1.470 / 1.731 / 1.940 | 28.0 mm (170, the neck) | 170 mm |
| Abdomen + pelvis | 9.982 | 9.456 / 9.106 / 8.595 / 8.264 | 12.155 | 1.218; 1.285 / 1.335 / 1.414 / 1.471 | | |

Volume shares of the conformed whole (denominator 52.126 l, the sum of the conformed bodies and the remainder; they sum to 1): pelvis 10.6%, abdomen 8.5%, thorax 30.2%, head and neck 7.3%, thighs 24.6%, shanks 9.5%, feet 2.2%, remainder 7.1%. Reported for the denominator, not as a verdict.

Notes: the head and neck minimum radius skips the crown (FREE_END_MM = 20 mm; its radius goes to 0 at the vertex by geometry). The thorax and pelvis minima sit on a cut plane, not inside the body. Pinch stations are interior local minima of the section's inscribed radius that stand out by 3 mm (named parameter); only the neck qualifies. Ledgers: `data/envelope/<body>.yaml` and `<body>_sections.csv` (every 10 mm, the thigh's columns with left/right where the thigh has medial/lateral), `_sagittal.png` and `_coronal.png`. Inspect bundle: the four bodies are further groups of `envelope_t5.obj`, with LJC, TJC, CJC and vertex planes, the axilla, the two SJCs and the trunk axis added to `inspect.json`; `conformed.obj` now uses the trunk map.

## 6. Tolerances and parameters I chose

H = 25 mm (yours); ARM_PIECE_MIN_MM2 = 500 mm2 (a hand section is several thousand, fingertips and slivers are below it); PINCH_PROMINENCE_MM = 3; FREE_END_MM = 20; FIELD_VS_RASTER_TOL = 1% (my cross-check, set before I saw a result; the first run gave the abdomen -1.1%, from the raster putting each plane on a 2 mm layer, and I fixed the accounting rather than the tolerance); gate 3 at 1% as for the legs; closure 0.5% (yours). No check tolerance or geometry value was changed.

## 7. My mistakes and defects

- Two edits to the code in one command were dropped by a shell quoting error (a heredoc inside a command); the first time nothing applied and I saw it from a `grep`, the second time a `\n` became a real newline and the file did not parse. Both caught by checking before running.
- The first accounting assigned each cell to a body by its centre, which puts every plane on a 2 mm layer: up to 1% of a 100 mm body. Replaced by an overlap split.
- The thorax first failed gate 3 at 6.8% at one station. Cause: arm cells just below the axilla that the vertex-label rule leaves on the torso, counted in the raster but not in the field. Fixed by the layer-piece clean-up of section 3, not by the tolerance.
- I wrote the union query and its tests in one step and so did not watch those three tests fail first.
- Defects carried: the Chebyshev centre is unstable on elongated sections (pelvis centres wander 55 mm in y; the radius is fine); the closure doubles the right leg (the left is its mirror to under 0.5% in area; the raster has the left thigh 0.16% below the right); `sculpt_attribution.json` still reports 414 target files.

## 8. Tests and files

Tests: 1661 passed, 1 failed (the known gait-extract test), 3 skipped; memo 34 closed at 1631, the baseline before this brief was 1616. The first full run of this work had a second failure, my own: `trunk_registration.json` carried the input hash from before the SJC entered the Dumas table; regenerated. New: `tests/test_envelope_bodies.py` (16, synthetic bodies with known answers), `tests/test_envelope_trunk_bodies.py` (11, the committed result, ledgers and the CLI), three union tests in `tests/test_envelope_oracle.py`, and the trunk registration tests now check your decisions. New code: `tools/envelope/bodies.py`, `bodies_report.py`, `oracle.clearance_union`, `fy envelope check --segment a,b`. Changed: `trunk.py` (primary anchor), `register.py` (`head_neck_mass_kg`), `ledger.py` and `plots.py` (a "trunk" side), `bundle.py`, `gates.py`, `cli.py`, `data/envelope/dumas2015_table1_female.json` (SJC [null, -84, 178] and a note, from your decision), `CONVENTIONS.md` (the layout rows, same commit). New data: the trunk ledgers, silhouettes, `trunk_bodies.json`, nine example files. `fy thread build` before the suite: 0 changed.

## Follow-ups

1. Open the Inspect viewer on the 94 MB bundle and say whether to thin it.
2. Table 1's SJC X, if you want the sphere centre exact.
3. The pelvis and abdomen planes against the Dumas mass cuts: a single pelvis or abdomen number is not a result until they are reconciled; I have not touched the sheet's masses.
4. Roadmap: `rm.v1-volume-extracted` stays pending ADR 0007; nothing here signs it off.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v2.obj`; knee anchor `chords`; CJC anchor `ansur_cervicale`; map `slope1`; shear kept; voxel 2 mm; topology reference `base.obj` sha 8e761e66.
