# Brief 7: envelope preparation for Stage 4 (volume-extractor-brief7.md)

Tag: Delegate. Read first: CLAUDE.md, CONVENTIONS.md, memos 35-36, ADR 0004, the Stage 4 docs.
Step 0. Save verbatim as docs/briefs/architecture/volume-extractor-brief7.md; repoint CLAUDE.md (one line); `fy state`. Known failure: gait-extract.

Decided by Joe: the model's pelvis origin (the lumbosacral joint) is the standard; arms and reservations are later briefs; ADR 0007 is drafted, not accepted.

1. Frames. The registry and the oracle use the model body frames for every segment (pelvis origin at the LSJ; abdomen at TJC; thorax and head and neck at CJC; legs as now). The mesh-to-model shift is a named parameter, computed (the mesh hip line x minus the model's HJC x relative to the LSJ) and not typed, applied inside the oracle and printed in every result. Migrate the trunk examples' pose files by the constant; margins must be unchanged to 0.01 mm. Test: the model's LSJ origin maps to the expected mesh position.
2. Report, no sim changes: the offset between the sim's trunk stack and the mesh trunk centre line at the LJC, TJC, CJC and SJC planes, at zero pose and in the design stance (12 degree pelvis tilt, lumbosacral extension 12 degrees, ADR 0004).
3. docs/envelope-component-contract.md: what the Stage 4 connector must emit per component (id from the Ariadne scheme, owner segment, model frame, bounding primitive, optional watertight mesh in the segment frame, status, clearance, mass, sha256, parameter-snapshot hash), right side authoritative with left by mirror (y negated), and the oracle's accuracy limits (voxel size, confidence). Draft only.

4. ADR 0007, decisions/0007-envelope-extraction.md, format as decisions/0004 (frontmatter id adr-0007, status proposed, date, links; sections Context, Decision, Consequences). The Decision section is the list below, in this order, wording tightened only. Context cites memos 27-36 and the sources; every number is copied from a committed file or memo, named in the text. If a memo disagrees with the list, stop and report; do not adjudicate. Do not accept it.
D1 Authority: the sheet (Dumas via the sheet) sets every dimension and mass; the v2 sculpt (data/makehuman/freyja-body-v2.obj, unposed, 13,380 body vertices, topology identical to base.obj's body) supplies shape only; ANSUR II (already in data/) only places mesh features and cross-checks; no other source.
D2 Registration: piecewise axial stretch onto the sheet's joint-centre nodes, never uniform scale; cross-sections unchanged; legs get a horizontal shear, arms a rigid rotation per segment; 8% stretch gate per sub-segment. Anchors: knee chords; hip crotch apex + ANSUR (Dumas GT +8 mm check); CJC ANSUR cervicale less the Dumas C7 offset; ankle on the ANSUR malleolus ratio (unmeasured); trunk map slope 1; head and neck keeps the sheet length.
D3 Uncertainty: anchor SDs from ANSUR, Monte Carlo N = 200, results nominal and robust, volume range gate 10%; thorax and head stretches known to about +-4%.
D4 Available volume: signed distance to the skin on a 2 mm grid; inner envelope = skin offset by the shell thickness t, a design parameter (default 5 mm, the sheet has none); margins under one voxel are "marginal".
D5 Bodies: frame cuts at joint-centre planes (horizontal in the zero pose for the trunk, normal to the axis for limbs); a plane is accounting, hardware may straddle it; neutral-pose containment uses the union of adjacent bodies; ROM interference belongs to the sim; joint zones (hip, LSJ, TJC, CJC, shoulder, h = 25 mm) are owned jointly.
D6 Mass cuts: realism checks use the source's tissue boundaries (Dumas 2015 Table 1: MSR10, iliocristale) and the uniform-density reading (Dumas 2007 section 2.1: sheet masses are volume shares). Results are the lumped abdomen-to-thigh region, shank and foot (later segments with two known cuts); pelvis, abdomen and thigh alone are not results; abdomen + pelvis share one budget (12.155 kg).
D7 Realism finding: against the reference women (63.9 kg, 1.61 m, BMI 24.7) the sculpt (BMI 18) carries about 9% less volume share in the abdomen-to-thigh region; no re-sculpt; revisit when all segments are in.
D8 Mass base: Siri 1956 density, fat fraction 0.207 (Deurenberg), lung gas removed (Hall); comparators 1.24 kg/l (robot, skin volume) and 1.31 kg/l (tissue basis).
D9 Oracle and registry: component registry per segment; check, free, foreign; model body frames everywhere (pelvis origin at the LSJ), the mesh-to-model trunk shift a named design parameter; foreign parts from MuJoCo forward kinematics; fine fits belong to CAD.
D10 Gates: topology and watertight; stretch within 8%; area change within 1%; synthetic solids within 2 mm; oracle examples; volume against Blender and closure within 0.5%.
D11 Open: arms, reservations, left side, discrete hip sweeps, single sculpt, no structural check.

5. Memo: gate table, the offsets, follow-ups.

Stop and ask Joe: the shift cannot be derived unambiguously; any trunk example margin changes; any existing output changes.
