# Brief: body-envelope thigh trial (landmark picker + conform + envelope oracle)

Tag: Delegate (build), Pair (Joe's landmark picks)
Roadmap: rm.v1-envelope-method (ADR 0007, pending) → rm.v1-volume-extracted
Read first: CONVENTIONS.md, CLAUDE.md, the roadmap nodes above. Follow repo conventions for paths, tests and memos.

## Goal
Run one non-trivial segment (right thigh) through the full chain: MakeHuman sculpt → landmark-derived Dumas joint centers → conform to the sheet → skin-offset envelope → prompt-facing section ledger + a clearance oracle. The trial decides whether this method becomes ADR 0007. Do not write the ADR.

## Principles (non-negotiable)
- The sheet is authoritative for dimensions. MakeHuman supplies shape only. Read every number from the sheet pull or params snapshot; never hardcode Dumas values. If a needed cell is missing, stop and tell Joe which one.
- No uniform scaling anywhere. Conforming is an axial stretch along the segment axis only; cross-sections must be unchanged.
- Distances are measured to the skin, never to cut planes. Compute the distance field on an extended solid, then mask to the segment. Cut caps must not shrink the inscribed radius near segment ends.
- Report numbers, not code. Joe will not read the code; give a gate table and plots.

## Inputs
- The committed "Project Freyja v3" OBJ + .mhm (find them in the repo; units are decimeters, helper geometry off).
- MakeHuman base mesh `base.obj` (makehuman repo, `makehuman/data/3dobjs/base.obj`): body = first 13,380 vertices. If it is not in the repo, ask Joe to place it at `data/mesh/base.obj`. Do not proceed without it.
- Frames: MakeHuman OBJ is x = subject's LEFT, y = up, z = anterior. The sheet's MuJoCo frame is x anterior, y left, z up. Map (x_mh, y_mh, z_mh) → (z_mh, x_mh, y_mh) (a proper rotation; assert det = +1). Verify "left = +x" on base.obj via the `joint-l-*` face groups. Convert dm → mm (×100).
- Sheet values: thigh length and mass, and the B1 table rows RASIS, LASIS, MPSIS, "HJC (Dumas)". Assert B1 = RASIS (87, −13, 119), MPSIS (−108, −13, 0), HJC (54, −93, 88) mm in ISB; stop if they differ.

## Phase A: build and hand off
1. Topology check: the exported mesh must have 13,380 body vertices and faces identical to base.obj. If not, stop and report the first difference.
2. Landmark picker: one self-contained HTML page under `tools/landmark-picker/` (vendor three.js locally, pinned version, no CDN at runtime). Drag-and-drop OBJ; orbit/zoom/pan; wireframe toggle; clipping-plane slider; click snaps to the nearest vertex of the hit face and shows ID and mm coordinates; ordered checklist; markers; undo; axis gizmo labelled with subject left (+x); export and re-import `landmarks.json`. Checklist for this trial: ASIS_R, ASIS_L, SACRAL_MID (midline skin point at PSIS level, standing in for MPSIS), EPI_MED_R, EPI_LAT_R. Schema: `{schema, topology: 13380, landmarks: {name: {vertex: id}}}`.
3. Python schema test for landmarks.json (IDs < 13380, required names present).
4. Develop Phase B against provisional landmarks from a simple geometric heuristic, clearly marked `provisional`. When Phase A is done, tell Joe the picker is ready and wait for the committed `data/mesh/landmarks.json`.

## Phase B: the trial (needs real picks)
5. Pelvis frame (ISB/Dumas): Z = ASIS_L → ASIS_R; X anterior, perpendicular to Z in the plane of the ASISs and SACRAL_MID; Y = Z × X. Scale k = mesh inter-ASIS / 238 mm (parameter; also run with the sheet's pelvis factor and report the difference). LJC = ASIS midpoint − R·(87, −13, 0)·k. HJC_R = LJC + R·(54, −93, 88)·k. Unit-test by round-tripping the B1 numbers through a synthetic pelvis.
6. KJC = midpoint of EPI_MED_R and EPI_LAT_R. L_mesh = |HJC − KJC|; required stretch s = L_sheet / L_mesh.
7. Thigh region: slab between planes through HJC and KJC (normal = thigh axis; the full method will use the bisector with the shank axis, which is out of scope here), clipped to the right of the sagittal midplane, keeping the connected component containing the mid-axis point. Note that the proximal end is the hip zone; report stats separately for s < 40 mm.
8. Sensitivity: perturb each landmark ±5 mm one at a time, then Monte Carlo (N = 200, 5 mm sigma). Report the spread of s.
9. Conform: stretch the thigh along its axis in the segment frame by s. Segment frame = MJC convention, origin HJC, axis down to KJC at (0, 0, −L), x anterior.
10. Envelope: 2 mm voxels, signed distance (positive inside) to the skin. Inner envelope = {sd ≥ t}; shell thickness t is a parameter (look in the sheet's Design Inputs; otherwise report t ∈ {0, 3, 5, 8, 10} mm). Report skin volume, inner volume per t, and implied density = sheet thigh mass / skin volume.
11. Section ledger at 10 mm stations (`data/envelope/thigh_R.yaml` plus a CSV or equivalent): header scalars (length, volumes, min inscribed radius and its station, mass budget, landmark file used, k, s); per row s_mm, area_mm2, Chebyshev circle (cx, cy, r) relative to the axis, half-widths ant/post/med/lat from the axis, and 8 directional radii from the Chebyshev center. Side-aware: for the right thigh, lateral = −y. Also render sagittal and coronal silhouette PNGs with a scale grid, with the inner envelope overlaid.
12. Oracle (`fy envelope`): load a segment; `signed_distance(points)`; `section(s)`; `clearance(shapes, poses)` where shapes are capsules, cylinders and boxes (sampled surfaces are fine) and poses are rigid transforms in the segment frame; returns min margin, pose index, station and point where it binds. CLI: `fy envelope check --segment thigh_R --shapes shapes.yaml --poses poses.csv`. Include a worked example: a straight cylinder of OD D and length 150 mm at s0, with a lateral offset sweep, one feasible and one infeasible case.

## Gates (report pass/fail with the numbers)
1. Topology matches base; the thigh solid is watertight.
2. Required stretch |s − 1| < 8%, and moves < 1.5% under 5 mm landmark perturbation.
3. Conformed length = sheet length within 0.5 mm; section areas at matched normalized stations unchanged within 1%.
4. Oracle reproduces synthetic cylinder, box and tapered cone within one voxel (2 mm) on volume, section area and inscribed radius.
5. Oracle CLI returns margin and binding station for the worked example, feasible and infeasible. (Joe and Claude run the real hip/knee placement in chat afterwards.)

## Stop and ask Joe
Topology mismatch; missing or changed sheet cell; thigh not watertight; |s − 1| > 8%; any landmark that falls outside the mesh's plausible region (e.g. HJC outside the body).

## Deliverables
Picker, pipeline, tests, data artifacts per conventions, and a memo in `docs/memos/` with the gate table, the sensitivity spread, the volume and density numbers, and the plots. Include a follow-ups section for anything Joe should decide. Add to the running list: note which landmark file and k variant each result used.