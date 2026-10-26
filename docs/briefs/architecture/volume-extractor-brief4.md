# Brief 4: Phase B on v2, sourced densities, Dumas-landmark mass cuts (volume-extractor-brief4.md)

Tag: Delegate
Roadmap: rm.v1-volume-extracted (ADR 0007 pending). Read first: CLAUDE.md, CONVENTIONS.md, memo31, volume-extractor-brief3 (its Phase B items 6-9 are superseded by this brief), memo30, data/envelope/body_density.json.

Step 0. Save this brief verbatim as docs/briefs/architecture/volume-extractor-brief4.md and repoint CLAUDE.md's volume-extractor entry (one line). Do not edit older briefs. Run `fy state`. Verify the MakeHuman target cache with `python analysis/makehuman_fetch.py --verify` and fetch if missing. Known out-of-scope failure: gait-extract.

Decided by Joe (do not reopen)
- Chords knee anchor, 8% gate, shear kept, ankle on the ANSUR malleolus ratio (unmeasured, recorded), Dumas masses and shares unchanged (thigh 14.6%). Anthropometry stays Dumas-via-sheet; ANSUR II (in data/) is the exception, used only where already used.
- v2 (freyja-body-v2.obj, unposed) is the baseline from now on; v1 results are historical.
- Mass-cut boundaries come from Dumas 2015 Table 1 (female), not ANSUR. Pelvis top = right iliocristale (RI); abdomen top and the lumped region's top = MSR10. ANSUR iliocristale and tenth-rib heights are cross-checks only. Frame cuts (joint-center planes, envelope, oracle) are unchanged, including the lumbosacral plane.
- Dumas 2015 p.116: segment masses are expressed "assuming a uniform density of 1 g.cm-3", so the sheet's shares are volume shares of the reference women. The PRIMARY shares test is the raw ratio = sheet mass share / sculpt volume share (1.00 = same distribution; the sculpt's volume includes lung gas, as does the reference). The Dempster-normalised ratio is a secondary column. (Joe will confirm the same assumption for the limbs in Dumas 2007a; do not wait for it.)
- Inspect envelope: thin only if Joe reports load > 10 s or < 20 fps.

Inputs from Joe
- MakeHuman check on v2 complete: Measure and Statistics readouts matched the memo-31 table exactly (0.1 cm), including torso and arm boxes. freyja-body-v2.obj is committed.
- Blender volume of v2 = 0.0523331 m3 (52.3331 l). v1 was 51.2605 l (+1.0726 l, +2.09%).
- Dumas 2015 checked: p.117 defines the abdomen as below the 10th ribs (L1) and above the iliocristales (L4); p.116 Table 2 matches the sheet's thorax and abdomen rows. Table 1, female, abdomen SCS (origin TJC, mm; X anterior, Y up, Z right; negative Y is below TJC): MSR10 (-53, -1, 0); RR10 (32, -21, 134); RI (17, -75, 153); RASIS (72, -172, 119); LJC (0, -121, 0). Thorax SCS (origin CJC): C7 (-61, 28, 0); SUP (49, -35, 0); TJC (0, -313, 0). Table 2 reference lengths: thorax 313, abdomen 121.
- Winter, Biomechanics and Motor Control of Human Movement, Table 4.1 (after Dempster 1955); edition and page left blank for Joe. Rows: thigh (greater trochanter / femoral condyles) 0.100, density 1.05; leg (femoral condyles / medial malleolus) 0.0465, 1.09; foot (lateral malleolus / head of metatarsal II) 0.0145, 1.10; abdomen (T12-L1 / L4-L5) 0.139, none; pelvis (L4-L5 / greater trochanter) 0.142, none; abdomen and pelvis (T12-L1 / greater trochanter) 0.281, 1.01; thorax 0.216, 0.92; trunk 0.497, 1.03.

Items (supersede brief 3 items 6-9)
1. Gate 1 on v2 against base.obj. Compare the whole v2 body to the rebuild; report max and mean deviation for legs, torso, arms and head separately (torso is now unposed; flag anything over 0.1 mm).
2. Volume attribution. Compare v2's computed volume with Blender 52.3331 l (gate 6, 0.5%). Using the rebuild, produce v1 posed (committed OBJ), v1 at rest and v2, and split the +1.07 l into the pose effect (v1 posed to v1 at rest) and the leg-slider effect (v1 at rest to v2), by region (head, arms, trunk above the tenth rib, abdomen and pelvis, thighs, shanks, feet). Do not read any v2-v1 change in a ratio as geometry before this is done.
3. Re-run the trial on v2 (chords, 2 mm, N = 200), all gates. Expect stretches within +/-1% and conformed segment volumes within 1% of v1's; report any difference.
4. Data files (locations per CONVENTIONS): (a) reference_densities.json from the Winter rows above, with a blank edition/page field; replace the "recalled" constants and wording; the abdomen and pelvis individual densities are the combined 1.01 applied to each, and the lumped rows use the combined value directly. (b) dumas2015_table1_female.json with the landmarks above and the source and page.
5. Mass base on v2 for the design numbers (not the shares test): M_mesh = BODY_DENSITY x (V - V_LUNG_L) with v2's volume (Blender as cross-check; about 52.1 kg expected). Recompute the robot's required average density and BMI; show v1 beside v2.
6. Cut heights. s_a = sheet abdomen length / 121 (read both from the snapshot / Table 2). Above the LJC plane: TJC = L_abd; MSR10 = (121 - 1) s_a (about +126 mm); RR10 = (121 - 21) s_a (about +105); RI = (121 - 75) s_a (about +48). Expected mesh-frame values with the LJC plane at 972.5 mm: MSR10 about 1098.5, RR10 about 1077.5, RI about 1020.8. Report the ANSUR heights beside them (tenth rib 1100.7, iliocristale 1037.5 +/- 21.8) and the differences. Primary: pelvis top = RI, lumped top = MSR10. Sensitivities: RR10 top, ANSUR heights, the lumbosacral top, and +/-10 mm on each cut.
7. Share rows on v2: abdomen (MSR10 to RI, about a 78 mm slab; report volume change per 10 mm of either cut and label it a diagnostic), pelvis (RI to the hip-centre cut and to the crotch cut), thigh x2 + pelvis, lumped (MSR10 to the KJC planes), shank, foot. For each: sculpt volume share, sheet mass share, raw ratio (primary), Dempster-normalised (secondary), sheet mass / skin volume. Report, do not pass/fail.
8. Independent cross-check: Dempster's lumped share (0.281 + 2 x 0.100) against the sheet's (abdomen + pelvis + 2 thighs).
9. Girth check: the Ruler loops on v2 against the memo-31 predictions.
10. Memo: gate table; v1 vs v2; the volume decomposition; the share rows on both bases; one plain paragraph on what the Dumas-landmark cuts and the uniform-density basis change; follow-ups.

Stop and ask Joe: any gate failing; whole-body deviation from the rebuild over 1 mm anywhere; v2 chord stretches over 2%; more than 0.3 l of the v2-v1 volume change unexplained; computed volume more than 0.5% from Blender; Table 1 coordinates that cannot be placed along the standing model's abdomen axis; anything needing a change to the sheet or the Dumas shares.
