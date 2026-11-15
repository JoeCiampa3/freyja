STATE: base 1970fef122e3 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:a44cd65d62e9 | snapshot sha256:492fe816e6d8 | tests 2476/2479 | dirty no (2473 run and passed at T6, 3 not run again on unchanged inputs, 3 skipped, 0 failed; reported by `fy state` from the full run on this tree, key c332a6bfcbdb)

# Memo 63: upper-arm characterization, Group G (rm.v1-upper-arm-geometry-extracted)

Brief: `docs/briefs/ariadne/upper-arm-characterization-brief.md`, sha256 prefix `a44cd65d62e9` (matched the prompt's A44CD65D62E9). Commits: 4668e30 (memo 62 answer 2), ed9dd2e (answer 5), 9c8ff6f (T5), 1970fef (T6), then this memo. T7 not run: it hit the brief's stop-and-ask, and Joe ruled in session to hold it. Checkpoint G reached with G-G8 open; stopped. Group L not started. Nothing pushed.

## Decision summary

- **What this means for Freyja:** the upper arm now has its frames, its anchors with their error bars, the envelope sections at the shoulder and elbow, the elbow's range and its available volume, all read by address and computed by committed code (`tools/characterization/geometry.py`, `fy characterize upper_arm --dry-run`). The room around the D1 elbow node is no longer one-sided: memo 43's problem is gone. The flexion clearance (G-G8) is not measured: no tool can sweep the forearm envelope against the upper arm's.
- **Numbers, each against its reference:**
  - Elbow origin 255.2347 mm below the shoulder along -y; the ledger's own lengths are 255.23 (field length less joint station) and 255.234 (mesh node to node), against the sheet's 255.2347 and a 0.1 mm gate.
  - Axis tilt bound 1.5710 deg against adr-0045 D6(a)'s 1.6 deg (gate 0.05; off by 0.029).
  - Shoulder lateral skin ray at station 40: 34.30 mm against memo 59's 34.30 mm.
  - Room at the last full row above the elbow (station 270, 21.2 mm above it): eight `r_` rays 31.64 to 40.24 mm, all positive. Anterior less posterior is 4.16 mm and medial less lateral 0.64 mm, both inside the 7 mm bar. Memo 43, on the old anchor, had a placeholder 10.97 mm proud of the skin.
  - Inner volume at the 5 mm shell 0.8346 l, the ledger's value read exactly. Range -4.7 to 150 deg anatomical (snapshot) and -4.7 to 157 deg mechanism.
  - Ray labels: 47 of 48 interface rays carry the label the ledger's own code gives. Over the whole ledger it is 361 of 372, and every miss is a skin ray labelled `cut_plane`.
- **Gates:** G-G1, G2, G3, G5, G6 and G7 pass. **G-G4 fails on one ray** (finding 2). **G-G8 not run** (finding 1).
- **Decisions for Joe:**
  1. T7 route, for the brief's revision (finding 1). Recommended: extend `foreign.py` to the hinges between host and owner, and write `analysis/elbow_flexion_clearance.py` comparing the posed forearm inner shell with the upper arm's signed-distance field from the cache. Its test is skipped where the cache is absent, and it says so.
  2. Ray labels (finding 2). Recommended: have `fy envelope build` write each ray's end (skin, region, outside) into the ledger at the next envelope rebuild. Until then accept the conservative CSV rule, which never calls a cut plane skin.
  3. Sign-off of `rm.v1-upper-arm-geometry-extracted`. Recommended: not yet. Wait for G-G8 and the label route, since the leaf's gates include both.
- **What would change this:** a cut-plane ray labelled skin would overstate room. The rule cannot produce one (proof below, and tested). A rebuilt envelope that moves the ledger's inputs hash moves every section number here, and the file will go stale on it by address.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G-G1 provenance | Pass | `upper_arm_R.yaml` and `forearm_R.yaml` both name `data/makehuman/freyja-body-v3.obj`; inputs hash `770c1272e683` for both, the value memo 59 read for the upper arm |
| G-G2 frames | Pass | The CAD axes from the transpose of `registry.isb_to_segment`: orthonormal to 0.0 (gate 1e-9), determinant +1; the shoulder and elbow frames share axes (identity in the file frame). The elbow origin is 255.2347 mm from the shoulder along (0, -1, 0). That holds by construction, because the ledger frame puts the distal plane at z = -sheet length (`arms.py`). The ledger's own numbers: `length_mm` less `joint_station_mm` = 255.23 (0.0047 short) and `mesh_length_mm` = 255.234 (0.0007 short), both against the sheet's 255.2347 and the 0.1 mm gate |
| G-G3 bars | Pass | elbow 7 mm anteroposterior, wrist 5 mm (adr-0042 D2), shoulder `unstated` (adr-0045 D6(b)); tilt atan(7 / 255.2347) = 1.5710 deg against 1.6 deg, difference 0.029 (gate 0.05) |
| G-G4 interface sections | **Fail, one ray** | Bracketing rows, uninterpolated: shoulder (station 36.0) rows 30.0 (+6.0 mm) and 40.0 (-4.0 mm); elbow (station 291.2347) rows 290.0 (+1.2347 mm) and 291.2 (+0.0347 mm, the field's end plane, finding 4). Values equal the CSV's cells (tested). The first row with a lateral skin ray is station 40, `hw_lat_mm` 34.30 (memo 59: 34.30, difference 0.00). Labels: 47 of 48 match the ledger's definition. Station 40 `hw_post_mm` = 45.75 is labelled `cut_plane`, but the ledger's code ends it on skin (finding 2) |
| G-G5 elbow room on the D1 node | Pass | Last row above the elbow with every ray on skin: station 270, 21.23 mm above the joint; rows 280 and 290 have anterior rays ending on the elbow's bisector cut. Eight `r_` rays (from the Chebyshev centre (-0.34, 0.23), 0.41 mm off the axis): ant 37.15, ant_med 31.64, med 33.34, post_med 36.15, post 32.99, post_lat 32.07, lat 32.70, ant_lat 40.24, all positive. Ant less post 4.16, med less lat 0.64. The four `hw_` rays from the axis: ant 36.97, post 33.18, med 33.58, lat 32.51; ant less post 3.79, med less lat 1.07. Each difference is under the 7 mm bar (finding 3 on the gate's wording) |
| G-G6 ROM | Pass | anatomical -4.7 to 150.0 deg, equal to `snapshot#/elbow_extension` and `elbow_flexion`; mechanism -4.7 (snapshot) to 157 deg (T5, adr-0008 D4); flexion positive, extension negative (`checks/joint_polarity.yaml` `elbow_right`: sign 1, positive flexion); loaded arc null, source needed |
| G-G7 volume | Pass | 0.8346 l = `data/envelope/upper_arm_R.yaml#/inner_volume_l/t5`, read; 31 station rows, each CSV row unchanged in value, CAD y = 36.0 - s |
| G-G8 flexion clearance | **Not run** | Blocked at T7 (finding 1); Joe held T7 in session |

## Findings

1. **T7 cannot run on the existing tools (G-G8 blocked).** I measured this rather than assuming it:
   - `foreign.foreign_poses(model, "forearm_R", "upper_arm_R", ...)` raises `KeyError: the model has no body 'upper_arm_R'` (`BODY_NAMES` has no arm entries).
   - With the model names it raises `StopAndAsk: upper_arm_right carries the hinges ['shoulder_fe_right', 'shoulder_aa_right', 'shoulder_ier_right'], not the three serial hip rotations`. `check_hip_chain` runs on the host, while the elbow hinge (`elbow_right`, axis (0, -1, 0), range -4.7 to 150) sits on the owner.
   - The oracle sweeps primitive or mesh components against a segment's skin. It has no envelope-against-envelope query and no inner-shell-against-inner-shell distance.
   - Any route reads `data/envelope/cache/*.npz` (gitignored). No `analysis/` script does that today: `fall_room.py` works from ledgers, registries and mesh vertices. So a committed `upper_arm_flexion_clearance.json` would reproduce only where the cache exists.

   I asked; Joe held T7. Nothing was built.
2. **The ray label cannot be read exactly from the CSV (G-G4 fails on one ray).** The ledger's definition is `Section.ray` (`tools/envelope/field.py:258-273`). A ray leaving on the skin is interpolated across the crossing (line 273). One leaving the region first (an end plane, the elbow bisector, the arm-thorax membership boundary) returns the last 0.25 mm step inside (lines 271-272). One whose origin is outside returns 0 (lines 265-266). The CSV keeps only the distance, rounded to 0.01 mm.
   - The rule I implemented (`geometry.ray_label`): a value that is not a multiple of 0.25 mm is `skin`, which is certain because only line 273 can produce it. A multiple is `cut_plane`.
   - Cross-check, memo only and not in any file: I reran `Section.ray`'s own code on `data/envelope/cache/upper_arm_R.npz`, recording which branch ended each ray. All 372 rays reproduce the CSV to 0.01 mm, so the cache is the ledger's.
   - The rule agrees with the branch on 361 of 372. All 11 misses are skin rays whose crossing fell within 0.005 mm of a step (about 4% of skin rays expected from the rounding; 11 of 372 observed), labelled `cut_plane`. No cut-plane ray is labelled skin. At the interface rows the one miss is station 40 `hw_post_mm` = 45.75.
   - Exact labels need either the cache in the generator (the brief's stop-and-ask) or a label column written by the ledger build (extending it, also stop-and-ask, plus an envelope rebuild).
3. **G-G5's wording mixes two ray families.** "Every `r_` ray from the node's axis": in the ledger, `r_` rays start at the section's Chebyshev centre and the `hw_` rays start on the segment axis, where the D1 node lies. I report both. At station 270 the centre is 0.41 mm from the axis, so they agree to about that.
4. **The elbow's lower bracketing row is the field's end plane.** Its printed station is 291.2 against the joint's 291.2347. `ledger.py:56` rounds `s_mm` to 0.1 mm, and the last station is the field's length by construction (`ledger.stations`).
   - I treat a row within 0.05 mm (half that precision) as at the station and carry its offset as printed, +0.0347 mm.
   - Its four `hw_` rays are 0: the axis is outside the region on the end face (branch `outside`). So the axis-based room at the elbow station itself is not in this ledger.
   - Over the last 21 mm above the elbow, the anterior rays end on the bisector cut, not skin: `hw_ant` 32.75 at row 280 and 4.75 at row 290.
5. **At the shoulder, the medial side of the section is the arm-thorax boundary, not skin.** At station 40, `hw_med` = 3.0 (branch `region`), and `r_ant_med`, `r_med` and `r_post_med` are cut as well. At station 30 every `hw_` ray is 0: the axis is outside the section above the SJC. That is consistent with memo 59 finding 7 and with adr-0045 D3's frame-only shoulder.
6. **The characterization reads the forearm ledger** (`#/mesh_file`, `#/inputs_sha256_12`) for G-G1. Once the file exists, a forearm-only ledger rebuild will mark it stale. That is correct for provenance; I flag it so it is not a surprise at F.
7. **No `fy characterize` write path exists yet.** Without `--dry-run` it refuses (exit 2) until L and F give it loads and a work item.

## T5: authored inputs against their clauses

`data/characterization/inputs/upper_arm.yaml`. Each row is checked in `tests/test_characterization_inputs.py`, which reads the clause text out of the decision file at test time.

| Entry | Value | Clause, as read | Equal |
|---|---|---|---|
| shell | 5 mm | adr-0007 D4: "default 5 mm" | yes |
| anchor_bars.elbow | 7 mm, anteroposterior | adr-0042 D2: "an error bar of 7 mm, mostly anteroposterior" | yes |
| anchor_bars.wrist | 5 mm | adr-0042 D2: "the wrist node 5 mm" | yes |
| anchor_bars.shoulder | unstated | adr-0045 D6(b): 'quoted with the bar "unstated", never zero' | yes |
| rom.mechanism_ends.flexion | 157 deg | adr-0008 D4: "to 157° of flexion" | yes |
| rom.loaded_arc | null, source_needed | adr-0008 D2: "[source needed: ...]" | yes |
| payloads.design | 1.0 kg, hand CoM | adr-0008 D2: "Payloads are 1.0 kg design" | yes |
| payloads.nominal | 0.5 kg, hand CoM | adr-0008 D2: "0.5 kg nominal" | yes |
| swing S1 | 90 deg, 1.0 s, 0 kg | adr-0008 D3: "S1 gesture, no payload, 90° in 1.0 s" | yes |
| swing S2 | 90 deg, 2.0 s, 1.0 kg | D3: "S2 grasp transport at the design payload, 90° in 2.0 s"; D2: "1.0 kg design" | yes |
| swing S3 | 90 deg, 1.0 s, 1.0 kg | D3: "design payload at gesture speed"; D7: "Swing S3: 1.0 kg at gesture speed \| 90° in 1.0 s" | yes |
| bsip_spread | 3 % | adr-0008 D2: "carry about 3%" | yes |
| fall_contact_points.lc.fall-hand-arm.contact | wrist | adr-0008 D5: "0.515 m, the wrist, is the design case" | yes |
| fall_contact_points.lc.fall-hand-arm.rating | 30 kN axial | adr-0008 D6(f): "rated 1.5 × 20 = 30 kN" | yes |
| fall_flags.lc.fall-hand-arm | structural | adr-0045 D5(e): "lc.fall-hand-arm is structural (0008 D6f)" | yes |
| fall_flags.lc.fall-shoulder-lateral | clearance, provisional | adr-0045 D5(e): "a clearance constraint (0037 D5 ...). This is provisional" | yes |

All 21 checked entries are equal. S3 cites D7 as well as D3, because D3 names "gesture speed" and "design payload" while D7's row writes the numbers. The 0.515 m reach is not typed: the wrist anchor is the snapshot's two lengths, 514.6708 mm below the shoulder at the zero pose. No flag is typed for `lc.fall-hand-arm-backward`, which is not recorded (brief, stop-and-ask).

## Interface sections (CAD frame, mm; `(cut)` = `cut_plane`)

- **Shoulder**, station 36.0 (`stations.joint_station_mm`), y = 0.
  - Row 30.0 (y +6.0, offset +6.0; area 1948.4, area_t5 1412.4, cheb_r_t5 12.25): hw_ant/post/med/lat 0.0 (cut, origin outside); r_ant 39.29, r_ant_lat 19.79, r_lat 14.61, r_post_lat 16.94, r_post 30.46; r_ant_med 20.75 (cut), r_med 14.75 (cut), r_post_med 22.25 (cut).
  - Row 40.0 (y -4.0, offset -4.0; area 2685.5, area_t5 2070.9, cheb_r_t5 16.25): hw_ant 45.68, hw_lat 34.30, hw_post 45.75 (cut; skin by the field, finding 2), hw_med 3.0 (cut); r_ant 41.41, r_ant_lat 23.28, r_lat 18.56, r_post_lat 22.24, r_post 34.80; r_ant_med 26.5 (cut), r_med 18.75 (cut), r_post_med 26.5 (cut).
- **Elbow**, station 291.2347 (36.0 + the sheet's 255.2347), y = -255.2347.
  - Row 290.0 (y -254.0, offset +1.2347; area 1958.4, area_t5 1423.1, cheb_r_t5 16.04): hw_ant 4.75 (cut), hw_post 33.81, hw_med 30.71, hw_lat 35.04; r_med 26.96, r_post_med 19.94, r_post 19.89, r_post_lat 22.41, r_lat 29.82; r_ant 18.75 (cut), r_ant_med 32.0 (cut), r_ant_lat 23.5 (cut).
  - Row 291.2 (y -255.2, offset +0.0347; area 1648.3, area_t5 1168.3, cheb_r_t5 14.05): hw_* 0.0 (cut, origin outside); r_med 28.64, r_post_med 18.29, r_post 17.31, r_post_lat 17.86, r_lat 24.93; r_ant 16.5 (cut), r_ant_med 29.0 (cut), r_ant_lat 20.5 (cut).

Every one of these cut labels is the field's own `region` or `outside` branch, except station 40 `hw_post`.

## Flexion table

Not produced (G-G8, finding 1).

## What every number is (brief: read, computed, or T5)

- **Read by address** (32 addresses, listed by `Reader.consumes`): the snapshot's `upper_arm_right_length`, `forearm_right_length`, `elbow_extension` and `elbow_flexion`; the ledger's `stations/joint_station_mm`, `stations/top_z_mm`, `length_mm`, `mesh_length_mm`, `inner_volume_l/t5`, `mesh_file`, `inputs_sha256_12`, `sections_csv`; the whole sections CSV; the forearm ledger's `mesh_file` and hash; `checks/joint_polarity.yaml#/joints/elbow_right`; `jnt.elbow#/hinges` and `#/rom_keys`; and the derived `body`, `joints_as_child`, `joints_as_parent` and `child_segments` that make the code segment-generic.
- **Computed** (`tools/characterization/geometry.py`):
  - `to_cad`: positions, CAD y of each station, and the axes.
  - `Segment.anchors`: elbow at -255.2347 and wrist at -514.6708 mm.
  - `Segment.tilt_bound`: 1.5710 deg.
  - `Segment.bracket` and `Segment.section_row`: rows, offsets and labels, with labels from `ray_label`.
  - `Segment.distal_room`: station 270 and the differences.
  - `Segment.rom`: signs and ranges.
  - `Segment.frame_checks`: the G-G2 numbers.
- **T5:** the shell, the bars, the 157 deg end and the loaded arc.

## T0 baseline

- `fy thread build`: 34 records, 1 work item, rework 0, 0 errors, 0 warnings, 0.81 s (after commits A and B).
- `fy test --quick`: 1128 passed, 188 s.
- adr-0045, 0008, 0042, 0037 and 0007 are `accepted`. `fy roadmap`: `rm.v1-upper-arm-geometry-extracted` is `ready`; loads-computed and char-file are `blocked`; char-schema is `done`.
- Ledger origin and axis against adr-0042 D1:
  - The upper arm's origin is the SJC computed in `arms.registration` as "the sheet's, through the trunk registration" (`arms.py:196-208`). The header's phrase "the mesh's own SJC" means that point in the mesh frame.
  - The axis runs from it to the D1 elbow node (`d1_nodes`, the section centre line at the joint station).
  - The model puts `forearm_right` at (0, 0, -0.255235) under `upper_arm_right`, unrotated.
  - Neither of the brief's first two findings fires: the joint centres are 255.234 mm apart in the mesh against 255.2347 (0.0007 mm).
- `foreign.py`'s stops are as in finding 1. It cannot take the elbow without change.

## Commits before T5 (memo 62 answers)

- **4668e30, answer 2.** An interface's `wrenches` items require `governs` (force_x .. moment_z, force_magnitude, moment_magnitude), the component whose largest absolute value over the case that wrench is. A fall case's per-interface wrench forbids it. The descriptions say the sweeps live only in `load_cases`. There are 3 new mutations. No convention mentions the wrenches, so CONVENTIONS is untouched.
- **ed9dd2e, answer 5.** New build error `csv-unparsable`: a record or a stamp addressing a CSV that does not parse. It names the record or stamp, the address, the file and the key. A missing row or column stays `address-unresolved`. Two invalid fixtures and three new cases; CONVENTIONS section 3 changed in the commit.

## Timings

- `fy thread build`: 0.81 s.
- Quick suite: 188 s.
- Full suite: 475 s (answer 2), 455 s (answer 5), 463 s (T5), 2485 s, with the `inputs` tests run because `tools/fy` is in their input set (T6).
- These agree with CLAUDE.md's 488 s and 174 s to within 8%, so I left its figures alone.

## Tolerances and choices

- `STATION_HALF_PRECISION_MM` = 0.05 mm: half the CSV's 0.1 mm station rounding (`ledger.py:56`). It decides only that row 291.2 is at the elbow station (finding 4). It was not tuned: the alternative, strict inequality, finds no row at or below the station and no bracket.
- `RAY_STEP` = 0.25 mm: `Section.ray`'s default step, which a region exit returns multiples of.
- 1e-9 on the axes: the brief's.
- Choice: the interface frames' axes are the CAD axes in the file frame (identity), computed as the round trip through `isb_to_segment`.
- Choice: the wrist anchor sits at the model's zero pose (every joint 0 deg). Group L places it at other elbow angles.
- Choice: the generator resolves the whole sections CSV as one address (`...csv#`), since the volume carries every row. Any CSV edit will mark the file stale.
- Choice: "full section" in G-G5 means every one of the row's 12 rays labelled skin.

## My mistakes

- I ran the label cross-check, which reads the cache, while answer 2's full suite was running. It wrote nothing, but it shared the CPUs, so that suite's 475 s is slightly inflated.
- T5's two new files were written while the T0 quick suite was running. They are outside the quick globs, so its 1128 count is unaffected, but the baseline was not of an untouched tree.
- My first T6 draft put the ledger's axes, not the CAD axes, into the interface frames. I caught it before anything entered the repo.

## Questions for Joe

1. T7: which route for the revised brief? Recommended: extend `foreign.py` to the hinge chain between host and owner, and write a cache-reading analysis script whose test skips without the cache (finding 1).
2. Ray labels: write the branch into the ledger at the next envelope build, accept the conservative CSV rule, or let the generator read the cache (finding 2)? Recommended: the ledger column, and the rule until then.
3. Sign off `rm.v1-upper-arm-geometry-extracted` now with G-G4 and G-G8 open, or after? Recommended: after.
4. G-G5's wording: should the room check use the `hw_` rays from the axis or the `r_` rays from the centre (finding 3)? Both are reported.
