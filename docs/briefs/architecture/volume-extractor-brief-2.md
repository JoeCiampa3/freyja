## Shank trial (rm.v1-volume-extracted)
1. Anchors: use data/makehuman/ruler_measures.json (knee-circ and ankle-circ loops: height and centroid) as mesh features; report each against the ANSUR-ratio estimate. Offsets from loop to KJC/AJC from ANSUR (report source and SD); no landmark picks.
2. Segment: KJC plane to AJC plane (normal = shank axis); same conform (axial stretch + shear, sections translated not deformed). Report stretch per sub-segment.
3. Mass base. M_mesh = whole-body mesh volume x BODY_DENSITY, a named constant in data/ (value and source supplied by Joe; Joe's Blender volume supplied as a cross-check, and the computed volume must match within 0.5%). For shank, thigh and foot: skin volume, inner volume (t = 3, 5, 8, 10 mm), sheet mass fraction from the snapshot, expected mass = fraction x M_mesh, implied density = expected mass / skin volume. Repeat the thigh with the hip zone excluded. Report beside each the Dempster-type reference density (thigh 1.05, leg 1.09, foot 1.10; eyeballing only), sculpt BMI = M_mesh / stature^2, and the robot's required average density = sheet total mass / M_mesh.
BODY_FAT_FRACTION (Joe: value and demographic source)
BODY_DENSITY = 4.950 / (BODY_FAT_FRACTION + 4.500)   # Siri 1956, UCRL-3349 eq. (10)
V_LUNG_L (Joe: assumed lung gas volume in l; Siri densities exclude lung gas)
M_mesh = BODY_DENSITY * (V_mesh_l - V_LUNG_L)
Report M_mesh at f = 0.15 and 0.35 as a sensitivity bracket.
4. Thigh restated: recompute thigh volume and density with the hip zone (s < 40 mm) excluded and included; report both. Report the true section perimeter alongside the equivalent-circle value everywhere a girth is compared. Do not compare station 0 to ANSUR.
5. Cut sensitivity: shank volume for +/-15 mm shifts of each cut plane.
6. Girth check: ledger perimeter on the UNCONFORMED mesh at the Ruler thigh, knee, calf and ankle loop heights vs the loop's own perimeter (Ruler method); flag if > 2%.
7. Inspect bundle: write conformed.obj, original.obj, envelope_t5.obj (marching cubes), inspect.json (joint centers and axes in mesh coordinates, cut planes, hip-zone range, feature levels, ANSUR mean +/- SD slabs, oracle shapes). Add an Inspect mode to tools/landmark-picker that loads the bundle with the layers and clipping plane described above; keep landmarks.json load/save.
8. Memo: gate table, plus a short table of the density and fraction numbers with the interpretation grid (global slimness vs thigh definition).

blender whole body volume for this mesh: 0.0512605m^3