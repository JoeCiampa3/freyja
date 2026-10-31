Brief 13: close out memo 55's two documentation gaps. Docs only: no rebuild, no raster work, no fy test, no full suite. If anything below would need a computation, list it in your reply and skip it.

Step 0. Save this prompt verbatim as docs/briefs/architecture/volume-extractor-brief13.md, repoint CLAUDE.md's architecture brief line to it, and commit those two alone. No memo; report in your final reply.

1. ADR 0042 Amendments (CONVENTIONS section 8, kind (1): append only, edit nothing above). The outcome line quotes pre-brief-12 values. Check the numbers against memo 55 and the committed outputs, then append, with date 2026-10-31:
"Final values after the arm-label and raster-origin changes (brief 12, memo 55): C1 1.0000045 and 0.9999683; C2 -0.425%; C3 0.058 mm; C4 worst thorax -0.049%. The outcome line above quotes the values before those changes. The arm label is now mesh-based (decompose.arm_vertices, no raster) and the ears belong to head_neck."
If any figure differs from the committed outputs, use the committed value and say so in your reply.

2. ADR 0007. Search D7, D8 and the Amendments for quoted arm or head_neck volumes or shares, and for thorax volumes, that the new arm label or the ears' move changes (memo 55: head_neck +0.0008 l, thorax -0.011 l). For each hit, read the new value from the committed outputs and correct it in place, kind (1), logging the change in ADR 0007's Amendments. If a value is not in a committed output, do not compute it: list it in your reply with where it is quoted. If there are no hits, say so.

3. Report in your reply, reading from committed outputs only, the current gate 3 thorax value on v3, with its limit. No rebuild.

Commits: one for the ADR 0042 line, one for any ADR 0007 corrections. Run fy state --no-run only; skip the tests, since only .md files change. Timebox: 10 minutes.
