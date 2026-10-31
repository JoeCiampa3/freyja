Brief 12: groin labelling fix, then Part B of brief 11. Supersedes brief 11's Part B ordering; brief 11 Part A stands. Context: memo 54; tools/envelope/decompose.py (vertex_regions, _class_areas).

Step 0. Save this prompt verbatim as docs/briefs/architecture/volume-extractor-brief12.md, repoint CLAUDE.md's architecture brief line, and commit those two alone. Then commit memo 54 as written, alone (S1 told you to hold it; Joe releases it). A short memo at the end (memo 55, under a page, decision summary first) is wanted, because this changes a label rule.

Thresholds, set by Joe before any result.
S2. Stop and commit nothing further if, after the fix, at any scanned phase: the arm-labelled vertex set (arms against not-arms) differs from phase 0's, or any of the 35 gates fails, or any of C1 to C4 fails, or C2's spread across the full-gate phases exceeds 0.035 points. Torso, legs and head labels may vary with phase; only the arm set must not.

1. Mechanism first, read-only. For one flipped groin vertex at phase 1.5 and at phase 0, print the layer it matches: layer centre, the apex, and every piece's area, centroid y and "big" flag, and the classification branch taken. Say whether the above-apex "not big -> arm" branch is the cause, and whether the lobes are still unmerged in the raster there. My reading is that at 1.5 the layer centre (808.5) is above the apex (808.4), so a rule limited to pieces at or below the apex would not fire. If the pieces contradict that, say so and propose the rule from what you see.

2. Test first, watched failing. A phase scan on v3, labels only: z-only shifts 0 to 1.75 mm in 0.25 steps, x-only and y-only at 0.5, 1.0 and 1.5, the four diagonal phases of brief 11, and Part B's snap phase. Assert the arm-labelled set is identical at every phase. It must fail at diagonal 1.5 before the fix. Add a mutation test that fails if the fix is reverted. Keep the scan fast enough to live in the quick suite, or mark it slow and say so.

3. The fix. Preferred: topology. Above the apex, a piece that overlaps in xy a leg piece in the layer below is a leg lobe, repeated upward until it merges into the core; keep the existing below-apex centroid rule (|y| > LEG_Y_MM_MAX is an arm). Do not use a height cutoff, which depends on this sculpt's A-pose. If the mechanism in step 1 differs, choose the rule from the evidence and say why. Choose between candidate rules by the scan, not preference.

4. Verify. Full gates on the four diagonal phases, the snap phase and the two phases with the most label differences from phase 0 (before the fix). Report one table: C2, C4 worst, C1's two stretches, gates failing, as in memo 54. Check S2.

5. Part B of brief 11, as written there (tests first including the arm-displacement invariance test for legs and its mutation, the world-lattice snap, rebuild every output per CONVENTIONS rule 10, the offsets-tolerance question). Update pins to measured values only and list each with old and new.

6. Append to adr-0042's Amendments (kind (1)): "2026-10-30. C3's SJC value of 0.007 mm in the outcome line is a difference at one raster phase; the SJC moves about 0.26 mm across raster phases (memo 54), so C3 reads as under about 0.3 mm. It passes against 2 mm."

7. Commits: the fix and its tests; the snap and its tests; the rebuilt outputs; the ADR line; each separate. fy test --quick before the first, the full suite once at the end.

Memo 55: S2 verdict and the phase table; the mechanism; the rule chosen and why; C1 to C4 and gates against memo 53's; the changed pins; the tolerance answer. Record the neck-plane phase sensitivity (4.5 mm; C4 thorax -0.016% to -0.058%) as an observation, not a fix.
