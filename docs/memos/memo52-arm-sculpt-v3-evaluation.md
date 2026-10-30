STATE: base 92dd91836b52 | brief architecture sha256:46970f1eb762, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests not run (--no-run; quick suite 904 passed) | dirty yes (the script, its test and this memo, uncommitted when generated)

# Memo 52: ADR 0042 committed; v3 generated and evaluated in memory against C1 to C4

Brief: `docs/briefs/architecture/volume-extractor-brief10.md` (sha256 46970f1eb762, committed alone as 2b8ac27). Phases 1 and 2 are done; Phase 3 is not started.

## Decision summary

- **v3 with both targets meets all four adr-0042 criteria, so the forearm-only fallback was not evaluated.** On D3's terms it qualifies as the baseline, subject to your MakeHuman look and Blender volume.
- **C1:** stretches 1.00001 (upper arm) and 0.99997 (forearm), against 8%. This one holds by construction, because the weights solve for it.
- **C2:** closure -0.430%, against 0.5% (v2 on the D1 nodes: +0.325%). **This is the tight one: 0.070 points of margin.** It flipped sign because the 0.387 l of arm stretch volume that sat in v2's closure is gone.
- **C3:** the SJC moves 0.007 mm, against 2 mm.
- **C4:** worst trunk body, the thorax, -0.026%, against 0.5%.
- **Weights:** upper arm 0.381365, forearm 0.512871, residuals 0.00003 mm or less on the solve and 0.007 mm or less on the written OBJ. The forearm weight is above the ADR's approximate 0.43 because that figure was on the skin nodes: the D1 forearm is 226.6 mm long on v2, not 231.7 mm.
- **v2 on the D1 nodes:** upper arm 1.1147 (matches ADR D3's figure), forearm **1.1449**. Without v3 the forearm would be over 8% and also over the retired 1.133 gate.
- **The elbow placeholder is now inside the skin:** 10.97 mm proud on v2 today, +14.32 mm inside on v2 with D1, **+13.93 mm inside on v3**. The elbow node's 7 mm error bar (D2) applies to that figure.
- **Mass and share:** mesh volume 52.33 to 52.72 l (+0.384 l), sculpt mass 52.10 to 52.51 kg, the robot comparator 1.241 to 1.232 kg/l, the tissue comparator 1.311 to 1.301 kg/l. D7's ratios move by 0.003 or less, except the forearm (1.082 to 1.090).
- **Finding: the three arm oracle examples fail on the D1 nodes, on v2 and v3 alike.** Their poses are authored around the old off-centre axis. Phase 3 cannot pass gate 5 by rebuilding alone (question 2).
- **Decisions for you:** (1) open the candidate in MakeHuman and enter its Blender volume, then say "proceed to Phase 3" or not; (2) approve re-placing the arm examples on the D1 axis (recommended, since they are test articles for the oracle, not design data); (3) how to file v3's Blender volume (question 3).
- **What would change this:** the Blender volume is the live risk. Closure is measured against the computed mesh volume, but if MakeHuman's result differs from the scripted OBJ, C2 has only 0.037 l of margin (0.070% of 52.7 l).

## Phase 1

| Item | Commit | Result |
|---|---|---|
| Step 0: brief and CLAUDE.md | 2b8ac27 | Two files alone |
| 1.1: ADR 0042, ADR 0007 (Amendments and D11), CONVENTIONS section 3 | 4bcf094 | One coupled commit. ADR text extracted from the brief's markers, byte for byte |
| 1.2: `rm.v1-arm-sculpt-v3`, blocked_by, `rm.v1-volume-extracted` text | 1f77e0b | `fy roadmap validate`: 0 errors, 0 warnings, 184 nodes |
| 1.3: wording fixes | 92dd918 | Hashes and file list unchanged |

`fy test --quick` after Phase 1: 904 passed, 28 deselected, 257 s.

Item 1.3 diffs:

```diff
--- data/makehuman/mhm_sources.json
- "note": "Pins what analysis/makehuman_attribution.py and analysis/makehuman_v2.py read. 'files' are paths ...
+ "note": "Pins what analysis/makehuman_attribution.py and analysis/makehuman_v2.py read, and also lists the four arm-length targets (measure-upperarm-length-incr and -decr, measure-lowerarm-length-incr and -decr; pinned for adr-0042). 'files' are paths ...
- "retrieved": "2026-10-25",
+ "retrieved": "2026-10-25 for the 161 files, 2026-10-29 for the four arm targets",
--- data/makehuman/SOURCE.md
-The target files themselves (33 MB for the 161 files read) are not committed.
+The target files themselves (the 165 files read: 33 MB for the original 161, plus the four arm-length targets `measure-upperarm-length-incr`, `-decr` and `measure-lowerarm-length-incr`, `-decr`, pinned for adr-0042) are not committed.
```

The 33 MB figure is kept for the original 161 only. I did not recompute a total for 165.

## Method

- **`analysis/makehuman_v3.py`** (new) has four commands: `solve`, `write`, `evaluate`, `compare`.
- **`evaluate` runs the real `fy envelope gates` code** (`gates.run`), with `arms.registration` and `arms.rotation_to_down` patched for the length of the call and the three result files sent to the scratchpad. So the numbers come from the production path, not a second implementation. Nothing changed under `data/envelope`, `tools/` or `checks/` (`git diff --stat` is empty there).
- **Harness checks:**
  - The placeholder measurement reproduces -10.97 mm on the committed `upper_arm_R` field (`occupancy.component_skin_margins`, the call behind `fy envelope check`).
  - The v2 trunk volumes equal the committed ones to the printed digits. On v2 the trunk does not depend on the arm nodes.
  - D1 nodes on v2 reproduce memo 50's B nodes: elbow (25.8, -326.3, 1163.8), wrist (172.8, -449.3, 1043.0).
  - The D4 roll left in both frames is under 1e-14 degrees, on v2 and v3.
- **Base for C3 and C4:** v2 evaluated the same way (v2 with D1 and D4), so every difference is the sculpt's alone.

**Choices I made** (none tuned toward a result):

| Choice | Value | Why |
|---|---|---|
| Solver tolerance | 0.001 mm, Newton, 2 by 2 | Well inside D3's 0.1 mm; the weights couple through the elbow node, so they are solved together |
| Weight precision | 6 decimals, rounded before writing | v2's `.mhm` format; the OBJ and `.mhm` carry the same numbers |
| Vertices with no delta | v2's line kept byte for byte | "Same OBJ conventions" |
| SJC during the solve | The committed one; no second pass | The rerun moved it 0.007 mm |
| Skin sampling | 0.5 mm | Memo 43's value |

## 2.1 Full B on v2, right side

| Quantity | Skin nodes (committed) | D1 nodes, D4 roll |
|---|---|---|
| Upper-arm length, stretch | 227.0 mm, 1.1244 | 228.975 mm, **1.1147** |
| Forearm length, stretch | 231.7 mm, 1.1198 | 226.607 mm, **1.1449** |
| Closure | +0.333% | **+0.325%** |
| Elbow node to nearest skin | 4.0 mm (field) | **28.03 mm** exact; 28.17 mm field |
| Wrist node to nearest skin | 0.07 mm (field) | **13.86 mm** exact; 13.93 mm field |
| Placeholder, least skin distance (positive inside) | **-10.97 mm** | **+14.32 mm** |

- Sheet lengths: 255.235 and 259.436 mm.
- Both nodes are inside the skin (`field.contains`).
- Elbow bend 38.86 degrees. The left side matches the right to the digits shown.
- ADR 0042 quotes 28.6 mm for the elbow from memo 43. I measure 28.03 mm on the exact skin. Memo 43's point was slightly different (it is the same node to about 0.3 mm), and I have not reconciled the 0.6 mm. It does not touch a criterion.

## 2.2 Weights

| Target | w | D1 length on v2 | Sheet | Residual |
|---|---|---|---|---|
| `measure-upperarm-length-incr` | **0.381365** | 228.975 mm | 255.235 mm | -0.00003 mm |
| `measure-lowerarm-length-incr` | **0.512871** | 226.607 mm | 259.436 mm | +0.00002 mm |

Both are in [0, 1], and the D1 nodes were recomputed at every step. The weights reported here are the ones in `V3_WEIGHTS`.

## 2.3 Candidate

Files in `data/makehuman/cache/v3-candidate/` (gitignored):

| File | sha256 (first 12) |
|---|---|
| `freyja-body-v3.obj` | 8627b0490678 |
| `freyja-body-v3.mhm` | 29f54e0062ad |

- 4,146 of 13,380 vertices move, by at most 53.7 mm.
- `topology_difference` against v2: none. Rewriting the files gives the same two hashes.
- The `.mhm` differs from v2's by exactly the two modifier lines.
- **Cross-check of `.mhm` against `.obj`:** the attribution script's rule (base plus weighted targets) rebuilt from the two `.mhm`s gives the same v2-to-v3 delta as the OBJs to 0.008 mm at worst, about the 0.01 mm of the OBJ's four-decimal format. That is the repo's own arithmetic, not MakeHuman's. Your look in MakeHuman is the independent test.
- The four arm targets were missing from the cache at the start of the session (`--verify`: 4 missing, 0 changed). I fetched them from the pinned commit with `makehuman_fetch.py`; afterwards 165 files, 0 missing, 0 changed.

## 2.4 Evaluation against adr-0042 D3

| Criterion | Measured | Limit | Result |
|---|---|---|---|
| C1 arm stretches | Upper arm 1.00001, forearm 0.99997 (worst 0.003%, both sides) | 8% | **pass** |
| C2 closure | -0.430% (52.4888 l against 52.7155 l) | 0.5% | **pass** |
| C3 SJC move | 0.007 mm | 2 mm | **pass** |
| C4 trunk volume | Pelvis -0.0005%, abdomen 0.0000%, thorax -0.026%, head and neck -0.008% | 0.5% | **pass** |

The fallback's condition (C3 or C4 failing) did not arise, so it was not run.

**Why closure flipped.** Sum of bodies minus mesh, l:

| | v2 on D1 | v3 |
|---|---|---|
| Sum of bodies | 52.5013 | 52.4888 |
| Mesh | 52.3315 | 52.7155 |
| Sum minus mesh | +0.170 | -0.227 |
| Conform effect, arms | +0.387 | 0.000 |
| Conform effect, everything else | -0.143 | -0.143 |
| Remainder (sum minus mesh, less the conform effect) | -0.074 | -0.084 |

The mesh grew by 0.384 l, while the built arms stayed about the same size (conformed, they were already at the sheet's length). v2's positive closure was the arm stretch offsetting the trunk and legs' negative conform effect. v3's -0.43% is that same trunk and leg term with nothing left to offset it. Its remainder is 0.010 l worse than v2's, and `arms_built_minus_raster_l` went from -0.014 to -0.023 l.

### Reported, no criterion

| Quantity | v2 (D1) | v3 |
|---|---|---|
| Thighs, l | 12.8395 | 12.8414 (+0.014%) |
| Shanks, l | 4.9408 | 4.9408 (-0.0006%) |
| Feet, l | 1.1315 | 1.1315 (0.0000%) |
| Upper arms, l | 2.2119 | 2.2104 |
| Forearms, l | 1.2625 | 1.2536 |
| Hands, l | 0.5109 | 0.5113 |
| Sculpt volume, l | 52.331 | 52.715 (+0.384; the ADR expected about +0.4) |
| Sculpt mass, nominal, kg | 52.10 | 52.51 |
| Sculpt BMI, nominal | 18.05 | 18.19 |
| D8 robot comparator, kg/l | 1.2408 | 1.2318 |
| D8 tissue comparator, kg/l | 1.3106 | 1.3006 |
| Elbow placeholder (positive inside), mm | +14.32 | **+13.93** |
| Elbow, wrist node to skin, mm | 28.03, 13.86 | 28.29, 14.25 |
| Elbow bend, degrees | 38.86 | 40.79 |

D7 share table, raw ratio (mass share over volume share):

| Row | Role | v2 (D1) | v3 |
|---|---|---|---|
| Head and neck | result | 0.931 | 0.931 |
| Thorax | result | 0.872 | 0.872 |
| Forearms | result | 1.082 | 1.090 |
| Hands | result | 1.029 | 1.028 |
| Whole arms | result | 1.055 | 1.057 |
| Lumped abdomen to thigh | result | 1.103 | 1.103 |
| Shanks | result | 0.957 | 0.957 |
| Feet | result | 0.929 | 0.929 |
| Upper arms | diagnostic | 1.045 | 1.046 |
| Abdomen | diagnostic | 0.484 | 0.484 |
| Pelvis | diagnostic | 1.387 | 1.387 |
| Thighs | diagnostic | 1.195 | 1.195 |

### Other findings from the same run

1. **Arm oracle examples: all three fail gate 5 on the D1 nodes, on v2 and on v3.** v3 "feasible" margins: `upper_arm_cylinder` -14.04 mm, `forearm_box` -14.98 mm, `arm_union` -13.09 mm. Those examples are authored around the old axis: the cylinder's YAML says it sits at y = +24 mm because the section's centre was about 20 mm medial of the axis. With the axis on the centre line, that placement is about 20 mm off-centre. This follows from D1, not v3.
2. **Elbow interface sections.** The area step across the elbow, -0.7% committed, is -5.2% on v2 with D1 and -3.6% on v3. The moved bisector and the frames change where the two bodies meet. It is not gated.
3. **The forearm is now longer than ANSUR scaled to stature:** 259.4 mm against radiale-stylion 251.7 mm (+3.1%). On v2's skin nodes it was 8% short by this comparison (231.7 mm). That is the sheet's length, which D3 conforms to, so this is context only. Radiale-stylion is a surface-landmark distance, not a joint-centre one.
4. **Gate failures in the v3 log that are artefacts of the candidate:** gate 6 compares against the v1 Blender key, because `masses.blender_volume_m3` has no v3 key (52.7155 l against 51.2605 l, +2.84%, meaningless). The v2 run's gate 2 failure is the expected 8% on 1.1147 and 1.1449. The printed arm gate label still says "2 x 17.3" in these logs because `tools/` is unchanged. No other gate failed on v3.
5. **Left and right:** the arm volume difference is -0.47% on v2 and +0.01% on v3. I have not explained that change.

## What would change each conclusion

- **C1.** Only a change to the D1 rule or the sheet's lengths, and then the weights would be re-solved. If a sheet edit moved a length, v3 would need regenerating.
- **C2.** A 0.037 l shift in the difference between the sum and the mesh, which is 0.070 of a point. Sources: MakeHuman disagreeing with the scripted mesh, the rebuilt arm bodies differing from these (Phase 3 uses the same code path, so it should not), or a sheet change.
- **C3.** Margin 1.99 mm; the trunk registration's inputs do not depend on the arms, to first order.
- **C4.** Margin 0.47 points on the thorax. A wider axilla reach is the only route, and it scales with the upper-arm weight.
- **The elbow placeholder's +13.93 mm.** D2's 7 mm error bar leaves it inside the skin even at the far end, but it is a test article, not a design.

## My mistakes

- **The roadmap state in 4bcf094 is one commit ahead.** I extracted the ADR and the node file in one step before committing 1.1, so the hook rebuilt `roadmap/STATUS.md` and `state.json` with 184 nodes and folded them into 1.1, while the node file itself landed in 1f77e0b. The two commits are adjacent and the tree is consistent from 1f77e0b on.
- **The timebox slipped.** Two parallel evaluations took 11 and 16 minutes, and the session's reading and writing added more; the whole of Phases 1 and 2 took longer than the 45 minutes planned. I estimated the `gates` pass too low, and did not time one before running both. No item was cut.
- **Scope addition:** `tests/test_makehuman_v3.py` (9 tests, watched failing first) is committed beside the script, per CLAUDE.md rule 1. The brief lists only the script and the memo for this commit. `fy test --quick` does not collect it (904 passed, as before), so I ran it directly: 9 passed.
- **Memo 51's cache statement did not hold here.** It says the 161 and the four were fetched into the cache, but the four were absent today. I don't know why; the manifest was never wrong.

## Questions for Joe

1. **Phase 3:** after your MakeHuman look and Blender volume, proceed? The candidate is at `data/makehuman/cache/v3-candidate/freyja-body-v3.mhm`. Note that the `.mhm` still carries v2's `name` and camera lines unchanged, as the brief says.
2. **Arm examples:** may Phase 3 re-place the authored poses of `upper_arm_cylinder`, `forearm_box` and `arm_union` on the D1 axis? "Rebuild" in the brief does not cover an authored edit, and gate 5 fails without one. Recommended: yes, with the new placements in the Phase 3 memo.
3. **Blender key:** `masses.blender_volume_m3` chooses between v1 and v2 keys by label, and anything else falls back to v1 silently. That is how the meaningless gate 6 above arose. Phase 3 needs a `blender_volume_v3_m3` key, and I recommend the fallback becoming a stop rather than a silent v1 comparison.
4. **ADR 0042's 28.6 mm and 0.43:** the record is accepted, so I have changed nothing. Should the measured 28.03 mm and 0.512871 go in with the Phase 3 Amendments line?
