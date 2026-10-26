# Brief 5: trunk bodies, joint zones, per-body design numbers (volume-extractor-brief5.md)

Tag: Delegate
Roadmap: rm.v1-volume-extracted (ADR 0007 pending). Read first: CLAUDE.md, CONVENTIONS.md, memos 31-33, volume-extractor-brief4, data/envelope/reference_densities.json.

Step 0. Save this brief verbatim as docs/briefs/architecture/volume-extractor-brief5.md; repoint CLAUDE.md (one line); `fy state`. Known out-of-scope failure: gait-extract. Add one housekeeping change: the hip diagnostic's expected HJC-to-trochanterion offset is Dumas 2007 Table 1B (female) GT Y = +8 mm unscaled (thigh frame, up) times the pelvis scale; report HJC against the ANSUR trochanterion with that offset (flag beyond 10 mm; the old 20 mm flag assumed zero offset).

Decided by Joe (do not reopen)
- v2 is the baseline; chords knee; shear kept; Dumas masses and shares unchanged; all anthropometry stays Dumas-via-sheet plus ANSUR II already in data/.
- Frame cuts (joint-center planes) define the bodies and envelopes. Mass-cut shares (memos 32-33) are done and not repeated. Do not add per-body share verdicts. Pelvis, abdomen and thigh alone are not results.
- Abdomen + pelvis carry one combined budget (sheet abdomen + pelvis mass); report them as a pair as well as individually.

Items
1. Trunk registration. Sheet nodes (snapshot): HJC (existing), LJC = HJC + sheet LJC offset (existing), TJC = LJC + abdomen length, CJC = TJC + thorax length, head vertex = CJC + head-and-neck length. Mesh anchors: the existing ones, plus a measured top: the nape vertex (Ruler neck-height / nape-to-waist end, id 1491) as a C7 proxy, with the Dumas 2015 Table 1 C7 offset above the CJC, scaled; cross-check against the narrowest neck plane (found in memo 32) and ANSUR cervicale if present in data/ansur2. Report the required axial stretch per sub-segment (abdomen, thorax, head and neck) and the MC spread. Report the sheet's standing head top (below stature by the pelvis non-verticality) and how the head sub-segment absorbs it. Do not choose an anchor silently if the thorax or head stretch exceeds 8%; stop and ask.
2. Bodies. Pelvis (LJC plane down to the hip-centre node), abdomen (LJC to TJC), thorax (TJC to CJC), head and neck (CJC to vertex). Arms are excluded using the vertex-label method of memo 32; report any layer where an arm merges with the trunk. State which orientation the cut planes follow in the zero pose (check the snapshot's pelvis tilt convention).
3. Joint zones at LJC, TJC, CJC and the hip: ownership at the joint-center plane (accounting only); report each body's volume with and without a slab of +/- h around each plane (h a named parameter, default 25 mm). Extend the oracle with a union query across adjacent bodies (neutral pose containment) while interference across ROM stays in the sim.
4. Per-body design numbers, for pelvis, abdomen, thorax, head and neck and the abdomen + pelvis pair: skin volume, inner volume (t = 3, 5, 8, 10 mm), sheet mass, required average density (sheet mass / skin volume and / inner volume), minimum inscribed radius and station, pinch stations. Section ledgers at 10 mm in the thigh schema, silhouettes, and an inspect bundle with the new layers.
5. Closure. Sum of conformed segment volumes (all bodies built so far) plus the unbuilt remainder (arms, hands) equals the mesh volume within 0.5%. From here shares use the sum of conformed segment volumes as the denominator, so they sum to 1 (this fixes the 1% v1/v2 inconsistency from memo 32).
6. Oracle examples on the new bodies: one box-shaped example in the pelvis and one in the thorax with feasible and infeasible placements, via `fy envelope check`.
7. Gates: topology and watertight per body; stretches within 8%; conformed area change under 1%; synthetic solids; oracle examples; volume against Blender 52.3331 l; closure.
8. Memo: gate table, trunk stretches and the CJC anchor used, per-body design table, pair budget, follow-ups.

Stop and ask Joe: thorax or head stretch over 8%; an arm merging into the trunk raster; a watertightness failure at the axilla or neck; a needed sheet cell missing; anything needing a change to the sheet or the Dumas shares.
