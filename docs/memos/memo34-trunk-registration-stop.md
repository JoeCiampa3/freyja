STATE: base ea93880770a9 | brief architecture sha256:3cf061256d79, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1631/1635 | dirty yes

# Memo 34: trunk registration (volume-extractor brief 5, item 1) stopped at the 8% rule

Brief: `docs/briefs/architecture/volume-extractor-brief5.md` (saved verbatim; CLAUDE.md names it). Done: step 0 and item 1. **Stopped before items 2 to 8**, because the brief's own anchor puts the thorax and the head beyond 8% (stop condition 1). No body, voxel field, ledger, oracle example or closure was built, so nothing downstream rests on an anchor I chose.

## Decision summary

- **What it means for Freyja.** The brief's CJC anchor (nape vertex 1491 as a C7 proxy, less the Dumas C7 offset) puts the mesh CJC 30 mm below the sheet's CJC. Making the mesh fit the sheet then needs the thorax stretched +10.1% and the head and neck compressed -11.8%. Three other estimates of the CJC, one of them the mesh's own nape vertex read as the CJC itself, agree with the sheet to within 4 mm and need 0.2% to 1.2% (thorax) and 2.3% to 3.4% (head and neck). So the problem is the +28 mm C7 offset applied to a vertex that already sits at CJC height, not the sheet or the sculpt.
- Numbers (v2, chords knee, slope-1 map above the HJC as in the memo 32 cuts, MC N = 200 seed 0):

| Number | Value | Reference |
|---|---|---|
| CJC from nape 1491 less Dumas C7 offset (29.4 mm) | 1397.5 mm, 30.2 mm below the sheet's CJC | sheet CJC in the mesh frame 1427.8 |
| Thorax / head-and-neck stretch, brief anchor | 1.1013 / 0.8816 | gate 8% (0.92 to 1.08) |
| Same, ANSUR cervicale less C7 offset (CJC 1426.5) | 1.0038 / 0.9754 | |
| Same, ANSUR suprasternale plus SUP offset (CJC 1423.8) | 1.0121 / 0.9660 | |
| Same, nape vertex taken as the CJC (1426.9) | 1.0025 / 0.9769 | |
| Zero-pose chain top vs stature | 1690.34 vs 1700 mm: 9.66 mm short | LJC-HJC drop 107.34 mm at 12 deg vs 97.68 mm upright |

- **Decisions for you.**
  1. Which CJC anchor. Recommended: ANSUR II cervicale less the Dumas C7 offset (`ansur_cervicale`), because it is population data independent of this mesh and of the sheet, and the suprasternale route agrees with it (2.7 mm apart); keep the nape vertex as a reported cross-check. Alternative: the nape vertex as the CJC (offset zero), which needs no ANSUR input. Not recommended: the brief's nape-minus-offset, whose result is outside the gate.
  2. Where LJC and TJC sit in the mesh. I reported two maps. `slope1` (pelvis and abdomen unstretched, the map under the memo 32 cuts, so those results do not move) and `uniform` (HJC to CJC stretched evenly: +0.2% on the recommended anchor). Recommended: `slope1`.
  3. Whether the thorax's arm-bearing layers above the axilla are to be handled as memo 32 did (item 2, not started). Needs your word only if an arm merges with the trunk in a layer below the shoulder.
- **What would change the conclusion.** A mesh landmark for C7 that is not the nape vertex (a vertex you pick in the landmark picker at the C7 spinous process): the three cross-checks put C7 about 29 mm above vertex 1491, and the posterior contour has no visible bump to confirm by eye (the nape slope is monotonic from z = 1340 to 1550 mm).

## 1. What was done

- **Step 0.** Brief saved, CLAUDE.md repointed. Baseline `fy state`: tests 1616/1620, the one failure being the known gait-extract test.
- **Hip diagnostic.** Expected trochanterion-above-HJC offset is Dumas 2007 Table 1B female GT Y = +8 mm times the pelvis scale (`register.DUMAS_GT_ABOVE_HJC_MM`; k = 1.05035, so 8.403 mm). On v2: scaled ANSUR trochanterion 882.5 mm, HJC 871.1, expected offset 8.40, residual +3.01 mm; flag at 10 mm, so no flag. I made the flag two-sided (`abs(residual) > 10`); the old one was one-sided. The old figure (HJC minus trochanterion, -11.41 mm) is still reported. `leg_R_trial.json` still carries the old diagnostic fields: I did not rerun `fy envelope gates` (it is not part of this checkpoint), so the next gates run rewrites them.
- **Trunk nodes** (sheet, zero pose, mm above floor): HJC 871.07, LJC 968.75 (+97.68), TJC 1095.84 (+127.09), CJC 1424.60 (+328.76), vertex 1690.34 (+265.74). These come from `thorax_length` and `head_neck_length` in the snapshot (`SheetNodes` gained both).
- **Mesh side.** HJC 874.25 (registration's crotch-apex anchor, SD 17.2), top 1698.95, nape vertex 1491 at 1426.94, narrowest neck plane 1475.0 (memo 32's method). Dumas 2015 Table 1 offsets scaled by 328.76/313 = 1.0504: C7 +29.4 mm above the CJC, SUP 36.8 mm below it.
- **ANSUR cross-checks.** The raw female CSV in `data/ansur2/raw` has cervicale and suprasternale, so I added both to `anthro.COLUMNS` and regenerated `data/ansur2/ratios.json` (22 lines added, nothing else moved). Cervicale 1395.7 mm mean, ratio 0.85695 (SD 0.00682, 11.6 mm at this stature); suprasternale 1329.7 mm, 0.81644 (12.1 mm). Suprasternale is my addition beyond the brief.

## 2. Standing head top (item 1)

The zero-pose chain tops out 9.66 mm below the 1700 mm stature. That equals the pelvis non-verticality: k times (54 sin 12 + 93 cos 12) = 107.34 mm is the vertical LJC-HJC drop at the design tilt that ADR 0038 closes the stack on, against 97.68 mm with the pelvis upright. The difference checks to 0.01 mm (`standing_head_top` in the result). The planes of the bodies are therefore horizontal in the zero pose (upright pelvis; the 12 degree tilt exists only in the design stance and in the thigh and trunk chain), which answers item 2's orientation question without building anything.

In the mesh, the HJC-to-vertex span is 824.7 mm against 819.3 mm in the zero-pose sheet, so the trunk above the HJC must shrink 5.4 mm (0.66%) overall. On the recommended anchor the head and neck takes it and more (-2.5%, -6.7 mm) while the thorax takes +0.4% (+1.3 mm). If the head sub-segment were instead closed to the stature (sheet length plus the 9.66 mm), its stretch would be 1.011 on the recommended anchor and 0.914 on the brief's.

## 3. Monte Carlo spread (item 1)

Independent normal draws of the mesh HJC (SD 17.2 mm) and CJC (the ANSUR SD of the landmark's height ratio times the mesh stature, 11.6 to 12.1 mm, the convention of the leg anchors; for the nape candidate I used the cervicale SD, an assumption since nothing gives the proxy's own error); the top is fixed. 95% ranges of the stretch, slope-1 map: thorax 0.898-1.147 and head 0.909-1.068 on the cervicale anchor. The spread is wide because the thorax and head spans are only 300 mm, so 12 mm of CJC SD is 4%. Fraction of draws beyond 8% (slope-1 map), thorax / head: cervicale 0.23 / 0.10, suprasternale 0.25 / 0.14, nape as CJC 0.23 / 0.08, brief anchor 0.62 / 0.89. The nominal value is what the rule tests, as for the legs; a quarter of draws outside the gate on the good anchors says the thorax and head stretches are only known to about +-4% whichever anchor is used.

## 4. Tolerances and choices (mine)

- 8% is the registration's `MAX_STRETCH_DEVIATION`, applied to the thorax and head as the brief says. The stop test is on the nominal primary stretch.
- The CJC SDs (above), N = 200, seed 0: from the brief and convention, none tuned to a result.
- The `slope1` map is the memo 32 cut map; `uniform` is my alternative. Neither was picked to help a result.
- `nape_as_cjc` and `ansur_suprasternale` are diagnostics I added to show what the C7 offset costs and to give a third independent estimate.

## 5. My mistakes

None found. One exploratory finding to state: before coding I computed these numbers in a scratch script with the old LJC (HJC node 870.6 instead of the registration's 874.25) and got thorax 1.088; the committed code uses the registration's node and gives 1.1013. The committed JSON is what the tests compare against a fresh run.

## 6. Tests and files

Tests: 15 new in `tests/test_envelope_trunk.py` (diagnostic offset and flag, trunk nodes, non-verticality, C7 and SUP offsets, both maps, the 8% rule, MC, ANSUR landmarks, the committed result and its fresh-run equality). Full suite: 1631 passed, 1 failed (the known gait-extract test), 3 skipped; baseline before the work was 1616/1620. New: `tools/envelope/trunk.py`, `fy envelope trunk`, `data/envelope/trunk_registration.json`. Changed: `register.py` (diagnostic, `SheetNodes` lengths), `anthro.py`, `cli.py`, `data/ansur2/ratios.json`, `CONVENTIONS.md` (the layout rows for `tools/envelope/` and `data/envelope/`, same commit), `CLAUDE.md` (line 8). Not started: items 2 to 8.

## Follow-ups

1. Your answer on the anchor and the map; then items 2 to 8 run as written (whole-width bodies with arms by vertex label, joint zones at h = 25 mm, design numbers, closure, oracle union query and the pelvis and thorax box examples).
2. Closure and denominators: the new sum-of-conformed-volumes denominator will apply to the new rows; I will leave the memo 32 and 33 share rows on the mesh-volume denominator (0.2% on v2) unless you say to switch them.
3. Optionally pick C7 in the landmark picker on the mesh, so the anchor does not depend on ANSUR proportions.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v2.obj`; knee anchor `chords`; shear kept; voxel not used in this checkpoint.
