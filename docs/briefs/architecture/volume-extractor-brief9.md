Read-only diagnostic for rm.v1-arm-joint-anchors-decision (ADR 0042, not yet written). Context: memo 43, memo 45, ADR 0007 D2 and D11, the leaf roadmap/nodes/rm.v1-arm-joint-anchors-decision.md.

Step 0. Save this prompt verbatim under docs/briefs/architecture/ (next free volume-extractor brief number) and commit it alone, before computing anything. Leave CLAUDE.md's current-brief lines as they are.

Thresholds, set by Joe before any result:
T1. B's error bar. If either cross-check in item 2 puts a joint centre more than 5 mm from the B node, B is reopened.
T2. One-shot definition. If a second iteration moves a node more than 1 mm, the one-shot definition is reopened.
T3. Forearm roll. The styloid-line construction is used only if the line direction agrees within 5 degrees across the clean distal stations; otherwise the anterior-preserving twist (after the shortest-arc rotation, the twist about the segment axis that maps the mesh's +x, projected onto the section plane, to the frame's +x).

Definition. A B node is the proximal segment's skin-section centre line (fitted on clean, cap-free stations as in memo 43 section 2), extrapolated to the joint station and computed once in the current Ruler-chord frame. Elbow: the upper arm's centre line. Wrist: the forearm's centre line.

Hard limit. Do not report or print any segment length or stretch between moved nodes; report node positions and offsets only. Write nothing to data/envelope (tracked or cache), the registration, tools/ or checks/.

1. Script move. git mv the two memo 43 diagnostics (sim/scripts/diag_elbow_anchor_build.py, sim/scripts/diag_elbow_anchor.py) to analysis/ (CONVENTIONS section 2: read-only envelope diagnostics) and fix their paths. Own commit.
2. B and its cross-checks, right side. Give the B elbow and wrist nodes in the current frames.
   (a) The gap at the elbow station between the upper arm's and the forearm's extrapolated centre lines, and at the wrist station between the forearm's and the hand's. Say so if the hand's sections don't fit a line cleanly.
   (b) The midpoint of the mediolateral skin extremes at the nearest clean station to each joint (-230 mm at the elbow; choose the wrist's and say why), and its distance from the B node.
   Report each against T1.
3. Second iteration. Rebuild the frames on the B nodes, refit the centre lines, and report how far each node moves, against T2.
4. Forearm roll.
   (a) For each clean station in the distal third of the forearm, the direction of the line through the mediolateral skin extremes in the section plane, and their spread against T3.
   (b) The angle between the x axis this implies and the anterior-preserving x (the sculpt's pronation offset).
   (c) From sim/models/freyja_template.xml, whether the model has a forearm pronation-supination joint and what its zero means.
5. Re-sculpt blast radius. Using MakeHuman's targets as analysis/makehuman_attribution.py does, find the targets that set upper-arm and forearm length. For each one at full weight, report:
   - the vertices moved more than 0.1 mm, grouped by segment label (flag any outside the arm);
   - the volume change;
   - the change in the current Ruler-chord node-to-node length of each arm segment, in mm and %;
   - whether full weight covers the current shortfalls (about 12% per segment, memo 38) with margin, and the maximum lengthening available.
   If the targets aren't reachable from this machine, say what's needed and skip.

Tests: fy test --quick once before your first commit and once at the end. No full suite unless you touch tools/, checks/ or tests/ (you shouldn't). Use fy state --no-run for the memo's STATE line.
Timebox: about 40 minutes. If an item would run long, report what it needs and move on.
Output: a memo (next free number) with the numbers against T1 to T3, what would change each conclusion, your mistakes, and questions. No recommendation on the arm gate.
