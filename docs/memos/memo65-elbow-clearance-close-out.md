STATE: base a1798d23ffbb | brief architecture sha256:bd2d997fe5e8, ariadne sha256:49f2b1e12196 | snapshot sha256:492fe816e6d8 | tests 2517/2520 | dirty no (0 failed, 3 skipped, 25 `inputs` tests not run again on unchanged inputs; reported by `fy state` from the full run on this tree, key c16d37cad2cd)

# Memo 65: upper-arm characterization, Group G close-out (Amendment 1: T7a to T7d)

Brief: `docs/briefs/ariadne/upper-arm-characterization-brief.md`, Amendment 1. Its sha256 prefix `49f2b1e12196` matched the prompt's 49F2B1E12196. Commits: e514364 (T7a and T7b), 304b791 (T7c), a1798d2 (T7d), then this memo with `docs/STATE.md`. Checkpoint G reached. Group L not started. Nothing pushed, nothing stamped.

## Decision summary

- **What this means for Freyja:** every Group G gate now passes, as amended. The measure works: it reassembles the sculpt to within a voxel and reads the zero pose at exactly 50 mm. It says something the old measure could not: **the 5 mm inner shells of the two segments, outside the elbow's 25 mm joint zones, collide from 78 degrees of flexion**, far short of the 157 degree mechanism end. The upper arm's anterior distal third and the forearm's proximal half give up about 0.1 l each to the elbow's travel. That is a design constraint for the part, not a characterization failure.
- **Numbers, each against its reference:**
  - First contact of the 5 mm inner shells, 25 mm zones excluded (M1): **78 deg**, against the mechanism's 157 deg (adr-0008 D4) and the anatomical 150 deg (snapshot).
  - Sensitivity, not basis: 91 deg with 35 mm zones and 120 deg with 50 mm. Even 50 mm zones touch 37 deg before the mechanism's end.
  - Inner separation at 0 / 90 / 157 deg: +50.00 / -8.51 / -40.66 mm. Memo 64's literal measure (no exclusion) gave -0.77 / -22.63 / -45.97, and the `no_exclusion` block reproduces that table at every angle.
  - V2, sculpt reassembly: m = 0.95 mm (skin) and 0.91 mm (inner), against 0 within one 2 mm voxel. V3, zero pose: 50.00 mm against 2 x 25 = 50.
  - Keep-out (M3): upper arm 0.097 l, 12% of its 0.8346 l inner volume, stations 163 to 265, 63% anterior. Forearm 0.098 l, 23% of its 0.4253 l, stations 25 to 133. Deepest 26.5 mm inside each inner shell.
  - Sculpt (T7b): flexion 40.52 deg about the model's hinge, carrying angle 5.09 deg (forearm lateral), **axial twist 4.69 deg**. The axes are 40.78 deg apart, which reproduces memo 64's 40.78.
- **Decisions for Joe:**
  1. Sign off `rm.v1-upper-arm-geometry-extracted`. Recommended: **yes**. G-G1 to G-G8 (V1 to V4) pass. First contact at 78 deg is the finding the amendment anticipated, not a fail.
  2. The 4.69 deg twist (finding 2, memo 64 finding 3). It is above the 2 deg line, and I did not change the posing convention. Recommended: accept the convention for this leaf. It moves a skin point at 35 mm radius by about 2.9 mm, under 1.5 voxels. Add a twist-corrected sensitivity row if the elbow part's clearance design comes within a few mm.
  3. The 78 deg contact (finding 1). Recommended: carry it forward unchanged. The elbow part's concept decides whether the cubital hardware is cut back (the M3 keep-out tells it where), not this leaf.
  4. T7d (finding 4). Recommended: keep the 180 s timeout. Add a serial phase to `fy test` only if the test fails again under the `inputs` load.
- **What would change this:** a joint zone that the elbow concept defines differently from `ZONE_H_MM` (the 35 and 50 mm rows show how strongly first contact depends on it). A rebuilt envelope (the ledgers' inputs hash moves, so the file goes stale). A corrected twist convention, if the twist turns out to be the sculpt's error and not anatomy.

## Gate table (amended G-G8 as V1 to V4)

| Gate | Result | Numbers |
|---|---|---|
| G-G1 provenance | Pass (memo 63, unchanged) | both ledgers `data/makehuman/freyja-body-v3.obj`, inputs `770c1272e683`. The cache's own inputs hash equals the ledgers' (the script checks this) |
| G-G2 frames | Pass (memo 63) | orthonormal to 0.0, det +1; elbow 255.2347 mm along -y |
| G-G3 bars | Pass (memo 63) | 7 mm AP, 5 mm, unstated; tilt 1.5710 deg against 1.6 (gate 0.05) |
| G-G4 interface sections, amended labelling clause | **Pass** | No ray is labelled `skin` where `Section.ray` ended it on a region boundary or outside: 0 of 372. Skin rays labelled `cut_plane`: 11 of 372, listed below. At the interfaces: 1 of 48 (station 40 `hw_post` 45.75). The station 40 `hw_lat` 34.30 matches memo 59 |
| G-G5 elbow room, `hw_` rays | **Pass** | station 270, 21.23 mm above the elbow: hw_ant 36.97, hw_post 33.18, hw_med 33.58, hw_lat 32.51, all positive; ant-post 3.79, med-lat 1.07 (bar 7). The `r_` rays beside them: 31.64 to 40.24 |
| G-G6 ROM | Pass (memo 63) | -4.7 to 150 anatomical, -4.7 to 157 mechanism |
| G-G7 volume | Pass (memo 63) | 0.8346 l read |
| G-G8 / V1 synthetic | **Pass** | 20 cache-free tests, each within 2 mm: cylinders side by side (10 and 20 mm gaps) and overlapping, axial gaps 0 / 6 / 20 mm across slab planes, a cut solid reassembled (0), zone exclusion at 0 (50 and 70 mm), a hinged pair at 90 deg (the measure's analytic -10 mm), symmetry, and the sign mutation through the sweep (forward hits the block, reversed reads -10) |
| G-G8 / V2 sculpt reassembly | **Pass** | m = +0.95 mm (t = 0), +0.91 mm (t = 5), tolerance 2 mm |
| G-G8 / V3 zero pose, zones excluded | **Pass** | 50.00 mm against 50, tolerance 2 mm |
| G-G8 / V4 determinism | **Pass** | `test_a_fresh_build_equals_the_committed_file_byte_for_byte`: an in-process build equals the file a separate run wrote |
| M1 hardware clearance | Reported; **finding** | first contact 78 deg (at or below 157) |

The 11 skin rays labelled `cut_plane` are a diagnostic, recomputed from `data/envelope/cache/upper_arm_R.npz` by `Section.ray`'s own branches. They appear in this memo only, as ruled on memo 64 Q5. Each is listed as station, column, value: 40 hw_post 45.75; 70 r_post 46.0; 130 hw_post 36.0; 130 hw_med 44.75; 140 r_post_med 40.0; 180 hw_ant 39.0; 180 hw_med 39.25; 210 r_ant 40.75; 220 r_ant_lat 37.0; 240 hw_lat 30.25; 260 hw_med 34.25. Each is a skin crossing that rounded to a multiple of 0.25 mm. Memo 63's count was the same, 361 agreeing and 0 overstated.

## M1: inner separation at the 5 mm shell, 25 mm zones excluded (mm; negative = overlap), with M2 skin interpenetration

| deg | inner | skin | | deg | inner | skin | | deg | inner | skin |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 50.00 | 0.00 | | 132 | -26.04 | 32.65 | | 145 | -32.73 | 40.65 |
| 30 | 25.11 | 0.00 | | 133 | -26.52 | 33.26 | | 146 | -33.41 | 41.04 |
| 60 | 8.63 | 0.00 | | 134 | -27.06 | 33.91 | | 147 | -34.18 | 41.77 |
| 90 | -8.51 | 13.06 | | 135 | -27.50 | 34.72 | | 148 | -34.95 | 42.57 |
| 120 | -19.68 | 25.77 | | 136 | -28.01 | 35.18 | | 149 | -35.39 | 43.27 |
| 121 | -20.22 | 26.53 | | 137 | -28.67 | 35.58 | | 150 | -36.17 | 43.93 |
| 122 | -20.70 | 27.13 | | 138 | -28.94 | 36.21 | | 151 | -36.75 | 44.48 |
| 123 | -21.22 | 27.49 | | 139 | -29.45 | 36.69 | | 152 | -37.14 | 45.09 |
| 124 | -21.66 | 28.09 | | 140 | -29.99 | 37.40 | | 153 | -37.90 | 45.89 |
| 125 | -22.18 | 28.96 | | 141 | -30.63 | 38.09 | | 154 | -38.66 | 46.67 |
| 126 | -22.79 | 29.31 | | 142 | -31.23 | 38.80 | | 155 | -39.38 | 47.30 |
| 127 | -23.25 | 29.71 | | 143 | -31.73 | 39.30 | | 156 | -40.09 | 47.98 |
| 128 | -23.83 | 30.38 | | 144 | -32.27 | 39.98 | | 157 | -40.66 | 48.48 |
| 129 | -24.31 | 31.00 | | | | | | | | |
| 130 | -24.87 | 31.33 | | | | | | | | |
| 131 | -25.53 | 31.97 | | | | | | | | |

- First contact (1 deg scan from 0): **78 deg**.
- Sensitivity (first contact only; labelled sensitivity, not basis): zones of 35 mm, 91 deg; 50 mm, 120 deg.
- Binding points (upper arm frame, mm): at 90 deg (13.0, -1.9, -209.1), station 245, 46 mm above the elbow plane. At 157 deg (14.6, -3.9, -210.4). The contact is the two bodies' anterior distal and proximal masses meeting, well clear of the zones.

## M3: keep-out over 0 to 157 deg (1 deg steps)

| Body | Volume l | Share of its t5 inner volume | Deepest mm | Stations (own ledger) | ant / med / post / lat l |
|---|---|---|---|---|---|
| upper_arm_R | 0.0970 | 11.6% of 0.8346 | 26.49 | 163.0 to 265.0 | 0.0606 / 0.0119 / 0.0033 / 0.0212 |
| forearm_R | 0.0984 | 23.1% of 0.4253 | 26.45 | 25.0 to 133.0 | 0.0474 / 0.0192 / 0.0066 / 0.0251 |

- Volume is the voxel count times 8 mm^3. Deepest is the largest sd - 5 among the keep-out voxels.
- A side is the hw_ quadrant of the voxel's direction from the body's axis, ±45 deg.
- The upper arm's range ends at 265.0, which is 291.23 - 25 to within a voxel: the zone boundary. The forearm's starts at 25.0, its zone boundary.
- None of this is subtracted from G-G7's volume.

## T7b: the sculpt

- **Decomposition.** R_rel = R_u R_f^T, with each R from `arms.ArmFrame`, rebuilt from the cache's origin, axis and stretch. Each equals the cache's rotation to 1e-9, and the script checks that. The intrinsic decomposition R = R_hinge(flexion) R_x(carry) R_z(twist) gives: flexion **40.5176 deg** (positive, forward); carrying **-5.0942 deg**, forearm distal end lateral (valgus); twist **+4.6924 deg** about the forearm's long axis.
- **Against memo 64.** The angle between the axes is 40.7817 deg, against memo 64's 40.78 and the ledger's `mesh_nodes_mm` bend of 40.78.
- **Stretches.** The axial stretches are 1.0000045 (upper arm) and 0.9999683 (forearm), so the sculpt transform is affine to 3e-5.
- **Test.** `test_decomposition_recovers_flexion_carrying_angle_and_twist` recovers four constructed rotations to 1e-9.
- **The twist is above 2 deg: finding 2.** The posing convention is unchanged.

## Findings

1. **Inner shells first touch at 78 deg of flexion, with the elbow's 25 mm zones excluded.**
   - Contact is 79 deg below the mechanism's 157 deg.
   - It is not a zone artefact. At 90 deg the binding point is 46 mm above the elbow plane, and doubling the zone only delays contact to 120 deg.
   - In a human, this volume is soft tissue (biceps belly against the forearm flexor mass) that compresses.
   - For Freyja it means no rigid hardware may sit in the M3 keep-out: 0.097 l of the upper arm's distal anterior, stations 163 to 265, and 0.098 l of the forearm's proximal half, stations 25 to 133. Otherwise the cover there must yield.
   - The brief calls this a finding for Joe, not a fail.
2. **The sculpt's forearm is twisted 4.69 deg about its own axis relative to the upper arm, against the 2 deg line.**
   - The model's zero pose assumes 0. So the posed forearm field is rotated 4.69 deg about its axis from where the sculpt's hinge would put it.
   - At a skin radius of 35 mm that is 2.9 mm of arc, under 1.5 voxels. On M1 the effect is probably a few degrees of first-contact angle. I have not measured it, because that would change the posing convention, which the brief forbids.
   - Whether 4.69 deg is anatomy (forearm pronation in the A-pose) or a frame artefact (adr-0042 D4 projects each segment's +x separately) is not decidable from this data.
   - Carrying angle 5.09 deg lateral, also unmodelled by the hinge, is reported.
3. **The measure reads closer than the Euclidean distance at a convex corner, never farther.**
   - S is a minimum of constraint distances. For the hinged pair at 90 deg the measure gives 10 mm where the Euclidean corner-to-corner gap is 14.1 mm (tested).
   - So M1's separations are conservative (towards contact), and first contact could be a few degrees late in reality, not early.
   - For parallel faces the measure is exact (V3: 50.00).
4. **T7d took the fallback, a 180 s timeout, not a serial run.**
   - `fy test` distributes files with xdist `--dist loadfile`, which cannot reserve CPUs for one file.
   - A serial phase means changing `tools/fy` and `tools/testkit`. `tools/testkit` is in every `inputs` key, so the change would rerun the 48 minutes of `inputs` tests.
   - This session's full runs skipped the `inputs` tests (none of their inputs changed). The 180 s is therefore unproven under the load that caused memo 64's failure.
5. **T7c needed a schema field the brief's "no other file changes" did not allow for.**
   - `segment-characterization/1`'s `flexion_clearance` has `additionalProperties: false` and no place for the zone height that T7c asks it to carry.
   - I added a required `zone_h_mm` (number > 0), the fixture value and two mutations (missing, zero), and printed it in `cli.py`.
   - Field names are mine, as at Checkpoint S. No convention mentions them, so `CONVENTIONS.md` is untouched.
   - Files beyond `geometry.py`: the schema, `tests/fixtures/characterization/minimal.json`, `cli.py`, and the two test files.

## What every number is

- **Read:**
  - The shell (5 mm) and mechanism end (157 deg) from the T5 inputs.
  - The zone height (25 mm) from both ledgers' `joint_zone_volumes_l.zone_h_mm`. They are equal, as the script requires. `arms.zone_numbers` writes it from `bodies.ZONE_H_MM`, and the output's provenance says so.
  - The fields from `data/envelope/cache/{upper_arm_R,forearm_R}.npz`. They are recorded by sha256 (`d05153baaee7...`, `cb4c985d6127...`) and size (6275744, 4710821 bytes). Their meta inputs hash equals the ledgers'.
  - The hinge and its sign from the model and the polarity file.
- **Computed** (`analysis/elbow_flexion_clearance.py`):
  - `Clipped`: S.
  - `measure`: m and the binding point.
  - `poses`, `sweep_inner`: the hinge poses.
  - `keep_out`: M3.
  - `arm_frame` and `sculpt_transform`: V2's pose.
  - `decompose`: T7b.
- **Stamp.** Inputs `sha256:23355616cd86` over the two ledger headers, the T5 inputs, the model, the polarity file and the snapshot. It is the same hash memo 64's draft printed, and so are the cache hashes.
- **The characterization** (`tools/characterization/geometry.py`, `Segment.flexion_clearance`) reads four addresses of the clearance file: `#/hardware_clearance/rows`, `/first_contact_deg`, `/zone_h_mm` and `#/skin/rows`. Consumes went from 32 to 36. It does not read the sensitivity, keep-out or no-exclusion blocks.

## Tolerances and choices

- `VOXEL` = 2 mm: the V gates' tolerance, as written in the brief (one voxel, the cache's `h`).
- `FRAME_TOL_MM` = 0.01: memo 64's tolerance on the cache's forearm origin against the model's; measured 0.0000.
- `FRAME_ROT_TOL` = 1e-9: the cached rotation against `arms.rotation_to_frame` of its own axis.
- `TWIST_FINDING_DEG` = 2: the brief's.
- Touch is inner separation <= 0, as in memo 64. The step is 1 deg, so first contact is resolved to 1 deg. Between 60 and 90 deg the separation runs from +8.63 to -8.51 mm, about 0.57 mm per degree.
- Choice: the zone is an analytic plane in S, not a voxel mask, so V3 is exact for parallel faces.
- Choice: M3's step is 1 deg. Within 100 mm of the hinge a step moves a point at most 1.7 mm, under a voxel.
- Choice: sensitivity scans stop at first contact.

## Timings

- Clearance build: 67 s (1.3 s load, 158 + 158 + 2 x up to 158 + 3 x 42 measures and the 158-step keep-out).
- Its test file: 72.7 s (24 tests; the cache rebuild is about 68 s of that, marked `slow`).
- Full suite: 530 s (T7a/b), 504 s (T7c), 495 s (T7d), each with the 28 `inputs` tests skipped.
- Quick suite (T0): 188 s, 1129 passed.
- `fy thread build`: 0 errors, 0 warnings throughout.
- The full suite's 495 to 530 s against CLAUDE.md's 488 s now includes the 73 s clearance file. I left CLAUDE.md's figures alone (within 9%).

## My mistakes

- My first sign-mutation test excluded no zone. The reversed pose touched the shared end plane and read +10 instead of negative. I corrected the test, not the code, by excluding the owner's zone. Its docstring states why.
- My first keep-out test swept to 180 deg, where the analytic claim "anterior only" is false. I fixed it before the first run, at zone 10 and 0 to 90 deg, with the derivation in the docstring.
- My manual V4 `cmp` failed, because the scratchpad directory did not exist yet. V4 rests on the byte-equality test instead, which compares an in-process build with the file a separate process wrote.
- The hinged-pair test's first docstring was garbled; I rewrote it before running.

## Questions for Joe

1. Sign off `rm.v1-upper-arm-geometry-extracted`? Recommended yes (the gate table above).
2. The 4.69 deg sculpt twist (finding 2): accept the zero-twist posing for this leaf, or add a twist-corrected sensitivity row in a later brief? Recommended accept, revisit at the elbow part.
3. Should the M3 keep-out be carried into `data/characterization/upper_arm.json` at Group F (it is in the clearance file now, not read by the characterization)? Recommended yes, as a reported constraint, never subtracted.
4. T7d: is the 180 s fallback enough, or do you want a serial phase in `fy test` despite the one-time `inputs` rerun it costs (finding 4)?
