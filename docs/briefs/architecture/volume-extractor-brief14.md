Brief 14: two documentation corrections. Docs only: no rebuild, no fy test, no full suite. Timebox 5 minutes. No memo; report in your final reply.

Step 0. Save this prompt verbatim as docs/briefs/architecture/volume-extractor-brief14.md, repoint CLAUDE.md's architecture brief line to it, and commit those two alone.

1. ADR 0007 D8 (CONVENTIONS section 8, kind (1): correct in place, log in Amendments). The comparators are whole-mesh values and moved when D1's baseline moved to v3. Read the committed v3 values from the committed outputs (expected 1.232 and 1.301 kg/l). Replace
"Comparators: 1.24 kg/l (robot, skin volume) and 1.31 kg/l (tissue basis)."
with
"Comparators: 1.23 kg/l (robot, skin volume) and 1.30 kg/l (tissue basis), on the v3 baseline (adr-0042; memos 52 and 53); on v2 they were 1.24 and 1.31."
If the committed values differ from the expected ones, use the committed values at two decimals and say so in your reply. Append to ADR 0007's Amendments:
"- 2026-10-31. D8: comparators corrected in place to the v3 baseline's values (1.232 and 1.301 kg/l); they are whole-mesh quantities and moved when D1's baseline did. D7's share ratios were checked against the committed share table and stand (brief 13)."
Change nothing else in ADR 0007.

2. roadmap/nodes/rm.v1-upper-arm-characterized.md. Keep the front matter, including stub: true, exactly as it is. Add this body:
"Elbow-position quantities in the file (the elbow node, anything measured from it, interface positions at the elbow) carry adr-0042 D2's error bar of 7 mm, mostly anteroposterior, and the wrist node's 5 mm; results quote it, and a clearance or position stated more finely than that is inside the anchor's uncertainty. The arms are on the adr-0042 D1 nodes with the D4 roll, the sculpt is v3, and the arm stretch gate is 8% (adr-0042 D3)."
Validate the roadmap the way brief 10 did; it must show 0 errors.

Commits: one for ADR 0007, one for the roadmap node. fy state --no-run only.
