# Brief 3: mass cuts, v2 sculpt, base.obj (volume-extractor-brief3.md)

Tag: Delegate (Phase A), Pair (Joe's MakeHuman check at the pause), Delegate (Phase B)
Roadmap: rm.v1-volume-extracted (ADR 0007 pending). Read first: CLAUDE.md, CONVENTIONS.md, memos 28-30, volume-extractor-brief2, data/envelope/body_density.json.

Step 0. Save this brief verbatim as docs/briefs/architecture/volume-extractor-brief3.md and point CLAUDE.md's volume-extractor entry at it (one line; if the repo rules forbid that edit, say so and leave it). Baseline: the gait-extract failure is known and out of scope (scenarios need re-running in a separate session). The CLAUDE.md brief-name test should now pass after Joe's rename to brief2; report if not.

Decided by Joe (do not reopen): chords knee anchor and the 8% gate; Dumas masses and shares unchanged (thigh 14.6%); ankle stays on the ANSUR malleolus ratio, recorded as unmeasured, no new source (all anthropometry stays Dumas-via-sheet plus the ANSUR II data already in data/); PELVIS_REFERENCE_DENSITY 1.01 accepted; shear kept; v1 is not re-sculpted. Inspect envelope: thin only if Joe reports load > 10 s or < 20 fps; decimate to <= ~8 MB within one voxel and keep the full distance field for the oracle.

## Phase A (no new mesh needed; do all of it, then stop)
1. base.obj: commit data/makehuman/base.obj with a source note (repo path, retrieval date, CC0 header, sha256 8e761e66...). Pin the MakeHuman target files that analysis/makehuman_attribution.py fetches by hash in a manifest, with a fetch script; cache gitignored unless the total is under ~5 MB. Record the license of the targets folder in the manifest. Re-run Gate 1 against the committed file.
2. v2 sculpt: write data/makehuman/freyja-body-v2.mhm from the committed v1 .mhm, changing only Height 0.623 -> 0.625, measure upper-leg-height 0 -> +0.269, measure lower-leg-height 0 -> -0.515, and removing the pose (v1's OBJ was exported in standing02; v2 is exported unposed so the whole body can be verified against the rebuild). State exactly which lines changed. Leave v1 untouched. Rebuild v2 with the attribution script and give Joe a table: v1 vs predicted v2 for every Measure-tab box and the Statistics box (Height, Chest, Waist, Hips), saying which stature (posed or unposed) the Statistics Height should show. Also predict the change in thigh, knee, calf and ankle circumferences (the tilted loops may shift); that is the unchecked item from memo 30.
3. Mass cuts, on v1 (additions only; frame cuts for the envelope stay exactly as they are): add ANSUR II iliocristale-height and tenth-rib-height ratios with SDs from the data already in data/ansur2. Report the pelvis row with its top at the lumbosacral plane (as now) and at the iliocristale height (mean and +/-1 SD). Add the lumped region from the tenth-rib height down to the KJC planes (abdomen + pelvis + 2 thighs, abdomen mass share from the sheet); it does not depend on the thigh/pelvis or pelvis/abdomen cuts. Do not choose which pelvis top is right; report both.
4. Report sheet mass / skin volume (kg/l) for thigh x2 + pelvis, abdomen + pelvis + 2 thighs, shank and foot.
5. In the memo, list the Dempster-type densities used (thigh, shank, foot, pelvis 1.01) as recalled and unverified, needing a cited source.

## Handoff (stop here)
Write the memo (next memo number, usual STATE line) ending with "Joe's check": (a) open freyja-body-v2.mhm in MakeHuman and confirm Pose/Animate shows no pose; (b) compare the Measure and Statistics readouts to your predicted table (tolerance 0.1 cm) and the four girth boxes to your predicted change; (c) eyeball the legs; (d) export with v1's dialog settings (Wavefront obj, helper geometry off, decimeter, feet on ground, normals off) as data/makehuman/freyja-body-v2.obj and commit. Optional: Joe runs his Blender volume on v2 and gives you the number for gate 6. Then stop and wait.

## Phase B (after Joe says freyja-body-v2.obj is committed)
6. Gate 1 on v2 (13,380 vertices, 13,378 faces vs base.obj). Compare the whole v2 body to the rebuild; report max and mean deviation for legs and torso separately.
7. Re-run the full trial on v2 with chords. Expect thigh, shank and foot stretches within +/-1% and conformed volumes within 1% of v1's; report any difference and v2's whole-mesh volume vs v1's. Gate 6 against Joe's Blender number if given, otherwise record "not run".
8. Re-run items 3-4 on v2. Girth check on the Ruler loops.
9. Memo: gate table, v1 vs v2 table, the lumped ratios at both pelvis tops with the +/-1 SD band, follow-ups.

## Stop and ask Joe
v2 chord-anchor stretches > 2%, or Measure-tab girths shifting > 1 cm; any gate failing; a needed landmark ratio missing from data/ansur2; network failure fetching MakeHuman files; anything requiring a change to the sheet or to the Dumas shares.
