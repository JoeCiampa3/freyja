Brief 11: BodyRaster grid phase. Context: memo 53, question 2; memo 52 (C2 margin); adr-0042 C1 to C4.

Step 0. Save this prompt verbatim as docs/briefs/architecture/volume-extractor-brief11.md, repoint CLAUDE.md's architecture brief line to it, and commit those two alone before anything else. No memo unless a stop condition fires or something unexpected turns up; otherwise report in your final reply.

Thresholds, set by Joe before any result. S1: if C2 varies by more than 0.035 points across the grid phases below, or any phase fails any of C1 to C4 or any gate, STOP after reporting; commit nothing further, because C2 may be measuring raster phase and that needs a decision from Joe.

Part A. Diagnostic, read-only. Write nothing under data/, tools/ or checks/. Find BodyRaster and how it takes its grid origin from the mesh bounding box. Rebuild the envelope and run the gates on v3 four times in scratch, with the origin shifted by 0, 0.5, 1.0 and 1.5 mm along all three axes (run them in parallel as memo 52 did). For each phase report in one table: C2 closure (signed, points), the worst C4 body, C1's two stretches, the sum of leg volumes and the sum of arm volumes, and any gate that fails. Then the spread (max minus min) of C2 against S1.

Part B. Only if S1 does not fire.
1. Tests first, each watched failing. (a) Displacing or scaling the arm vertices leaves every leg output (thigh, shank and foot volumes, the ankle section centroid, the thigh rod example) bit-identical. (b) A mutation test: the old bounding-box origin fails (a).
2. Snap the origin per axis to floor(bbox_min / voxel) * voxel in world coordinates, keeping any padding BodyRaster already has, so grid phase no longer depends on the sculpt's extent.
3. Rebuild every envelope output (CONVENTIONS rule 10; nothing stale afterwards) and rerun the gates. Update pinned test values only to measured values, and list every changed pin with old and new in your reply. Stop before committing if any of C1 to C4 or any gate fails.
4. The offsets test tolerance memo 53 set to 1.6e-3 is justified as 3 x 0.0005, which is 1.5e-3. State whether the bound has another term; if not, tighten it to the derived bound.
5. One commit for the code and tests, one for the rebuilt outputs. fy test --quick before the first commit; the full suite once at the end.

Reply with: the Part A table and the S1 verdict; if Part B ran, the new C1 to C4 values against memo 53's, the list of changed pins, and the tolerance answer.
