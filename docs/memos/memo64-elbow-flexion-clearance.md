STATE: base 29de47281749 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:a44cd65d62e9 | snapshot sha256:492fe816e6d8 | tests 2489/2493 | dirty no (1 failed: the headless-browser timeout of finding 4; reported by `fy state` from the full run on this tree, key 5d078a5b3214)

# Memo 64: upper-arm characterization, Group G, T7 (elbow flexion clearance, G-G8)

Brief: `docs/briefs/ariadne/upper-arm-characterization-brief.md`, sha256 prefix `a44cd65d62e9` (matched the prompt's). Prompt: T7 only, under Joe's rulings of 2026-11-14 (points 1 to 8). Commits: 29de472 (the pose module), then this memo with `docs/STATE.md`. **T7 stopped at G-G8's 0 degree check.** Group L not started. Nothing pushed. Sign-off of `rm.v1-upper-arm-geometry-extracted` is Joe's.

**Point 2, answered first: case (a).** `foreign.py`'s convention and frame helpers (`clinical_factor`, `joints_of`, `_body_id`, `_transforms`, `_T`, `POLARITY_ROWS`, `body_name`) are module-level and do not depend on `check_hip_chain`, which only `default_samples` and `foreign_poses` call. They import as they are. `foreign.py` is untouched (`git diff HEAD -- tools/envelope/foreign.py` is empty), so the hip regression guard (point 3) was skipped.

## Decision summary

- **What this means for Freyja:** the elbow pose machinery exists and is tested: the forearm is posed in the upper arm's frame over the model's elbow hinge, signed by the polarity file and carried to 157 degrees. G-G8, as written, cannot pass. Adjacent envelope segments share the elbow plane, so their 5 mm inner shells touch at 0 degrees by construction, not because tissue collides. The flexion clearance is not yet a number Freyja can use.
- **Numbers, each against its reference:**
  - Inner shells at 0 deg: **-0.77 mm** (touching within a 2 mm voxel), against G-G8's "separated". The binding point is posterior, 1 mm below the elbow plane, 9.6 mm inside the upper arm's skin and 7.8 mm inside the forearm's: the two cut faces, not skin.
  - Inner overlap at 90 / 150 / 157 deg: -22.63 / -44.28 / -45.97 mm. The binding point is about 30 mm from the elbow node, deep in both bodies.
  - Skin interpenetration at 0 / 90 / 157 deg: 0.77 / 26.02 / 54.96 mm (reported, not gated).
  - The measure against analytic cylinders: within 0.12 mm (tests allow one voxel, 2 mm).
  - Two builds byte-identical (12.7 s each). The ledgers' inputs hash is `770c1272e683`, the same as memo 63.
  - The mesh's elbow is bent 40.78 deg between the two axes (ledger `mesh_nodes_mm`); the model's zero is straight.
- **Decisions for Joe:**
  1. The G-G8 measure (finding 1). Recommended: exclude the elbow's joint zone from both sets. Use the ledger's own joint-zone slabs (`bodies.ZONE_H_MM` = 25 mm, already behind `joint_zone_volumes_l.slab_l.elbow`): the upper arm's last 25 mm and the forearm's first 25 mm. That is an existing repo constant, not a tuned one. Expect first contact far below 157 deg even then (finding 2).
  2. What to do with the draft analysis script (in the session scratchpad, described below). Recommended: commit it with the ruled measure in the next session.
  3. Sign-off of `rm.v1-upper-arm-geometry-extracted`: not yet (G-G4's ray and G-G8 open).
- **What would change this:** a joint-zone definition that removes the overlap at 90 deg would make first contact a real flexion limit. A rebuilt envelope with segments that do not share the elbow plane would let the literal G-G8 run.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G-G8 flexion clearance | **Stopped** at "at 0 degrees the inner shells are separated" | 0 deg: inner separation -0.77 mm, skin 0.77 mm. Under the literal definition, first contact is at 0 deg. Two runs byte-identical. Table below. Output not committed (Joe, in session) |

## Findings

1. **G-G8's literal measure reads contact at 0 deg, by construction (the stop).**
   - `arms.py` cuts each arm segment at its own distal plane. The upper arm's slab ends at z = -L_upper arm. The forearm's begins at its z = 0, which the model places exactly there at zero (cache `origin_xyz` against the model: equal within 0.01 mm). The elbow's bisector rule then gives each overlapping cell to one body.
   - So at 0 deg the posterior faces of the two regions coincide. The inner sets {sd >= 5} within each region reach right up to those faces: sd is the distance to the skin of the extended solid, so the faces are 8 to 10 mm deep inside the tissue.
   - The measured binding point at 0 deg is upper arm frame (-23.9, -5.9, -254.2) mm, 24.6 mm from the elbow node.
   - Any set-based measure of two adjacent segments gives contact at the shared plane. G-G8 names no exclusion, so it cannot be met.
2. **Away from the shared plane, the rigid envelopes still overlap through most of the flexion range.**
   - At 90 deg the binding point is 30.5 mm from the node, 21.1 mm inside the upper arm's skin and 12.1 mm inside the forearm's. At 157 deg: 31.2 mm from the node, 25.1 and 30.9 mm deep.
   - This is the forearm's proximal mass turning rigidly into the upper arm's distal mass. The mesh is posed with the elbow bent 40.78 deg, and the cut faces fit together only near that pose. Rigid segments of a soft-tissue joint must interpenetrate in deep flexion; a human compresses that tissue.
   - I ran one diagnostic, excluding a 40 mm sphere about the node. Under ruling 1 its numbers are kept out of every file except T7's output, which does not exist. In words: it does not remove the overlap at 90 or 157 deg. So with the recommended 25 mm slabs I expect inner first contact well below the mechanism's 157 deg. Your ruling says that is a finding for you, not a failure.
3. **The forearm's twist at zero is the envelope build's convention, not checked here.** Each arm field's +x is the mesh's +x projected onto its section plane (adr-0042 D4). Posing the forearm field parallel to the upper arm's at the model's zero assumes those two "anteriors" agree when the elbow is straightened. The origins agree (finding 1); the twist is not tested by this task.
4. **The headless-browser test is flaky under full parallel load (rule 9).** In this session's full suite, `tests/test_landmark_picker.py::test_only_faces_whose_vertices_are_all_in_the_body_are_kept` timed out: Edge did not finish within 90 s while the `inputs` tests ran beside it. Run alone, the file passes 2 of 2 in 21.5 s. Nothing in this change touches it. `fy state` therefore records 1 failure for this tree. A longer timeout, or serialising the browser tests, is a change I did not make.
5. **`joint_poses.py` imports two underscore-private names from `foreign.py`** (`_body_id`, `_T`, `_transforms`). Ruling 2 forbids extracting them, so they stay. A later extraction commit could make them public.

## G-G8 table (literal definition; draft script, output not committed)

The measures (from the draft's docstring, unchanged):
- Each body's set is {sd >= t} within its region. S = min(sd - t, the signed distance to the region's voxel boundary).
- m = max over the forearm's voxel centres p of S_upper(T p) + S_fore(p), with T the model's pose.
- Inner separation = -m at t = 5 mm (T5 shell). Skin interpenetration = max(m at t = 0, 0).
- For two parallel faces, m is exactly their overlap. Resolution is about one voxel (2 mm).

| deg | inner sep. mm | skin mm | | deg | inner sep. mm | skin mm |
|---|---|---|---|---|---|---|
| 0 | -0.77 | 0.77 | | 139 | -40.12 | 46.85 |
| 30 | -2.09 | 2.17 | | 140 | -40.40 | 47.27 |
| 60 | -9.37 | 11.16 | | 141 | -40.74 | 47.75 |
| 90 | -22.63 | 26.02 | | 142 | -41.10 | 48.24 |
| 120 | -32.37 | 37.91 | | 143 | -41.44 | 48.72 |
| 121 | -32.86 | 38.44 | | 144 | -41.80 | 49.17 |
| 122 | -33.27 | 39.05 | | 145 | -42.18 | 49.69 |
| 123 | -33.72 | 39.52 | | 146 | -42.58 | 50.32 |
| 124 | -34.16 | 39.95 | | 147 | -42.92 | 50.85 |
| 125 | -34.61 | 40.45 | | 148 | -43.37 | 51.31 |
| 126 | -35.09 | 40.93 | | 149 | -43.85 | 51.68 |
| 127 | -35.53 | 41.53 | | 150 | -44.28 | 52.10 |
| 128 | -35.81 | 41.92 | | 151 | -44.51 | 52.58 |
| 129 | -36.09 | 42.27 | | 152 | -44.73 | 53.05 |
| 130 | -36.54 | 42.83 | | 153 | -44.98 | 53.53 |
| 131 | -37.03 | 43.41 | | 154 | -45.29 | 53.97 |
| 132 | -37.40 | 43.75 | | 155 | -45.60 | 54.35 |
| 133 | -37.73 | 44.15 | | 156 | -45.82 | 54.54 |
| 134 | -38.11 | 44.58 | | 157 | -45.97 | 54.96 |
| 135 | -38.55 | 45.15 | | | | |
| 136 | -39.05 | 45.63 | | | | |
| 137 | -39.54 | 46.09 | | | | |
| 138 | -39.89 | 46.43 | | | | |

Both measures grow monotonically. Stamp of the draft's output, as `room.json`: inputs `sha256:23355616cd86` over the two ledger headers, the T5 inputs file, the model, the polarity file and the snapshot. Ledger hashes: `upper_arm_R` and `forearm_R` both `770c1272e683`. Cache files by sha256 prefix: `upper_arm_R.npz` `d05153baaee7`, `forearm_R.npz` `cb4c985d6127`. The draft records the full 64-hex hash and the byte size.

## What was built

- **Committed (29de472): `tools/envelope/joint_poses.py`** and 14 tests (`tests/test_envelope_joint_poses.py`, no cache).
  - `hinge_chain` reads the hinges between host and owner from the model tree. Upper arm to forearm gives [`elbow_right`], axis (0, -1, 0), range -4.7 to 150. Upper arm to hand adds `wrist_right`. A host below the owner, or no hinge, stops.
  - `relative_transforms` gives T_host_owner in mm with `foreign.clinical_factor`'s sign. It is not clamped: 157 deg is posed 7.000 deg past 150 (tested).
  - `check_probe_direction` checks the polarity file's probe on the posed transform, independently of the sign the pose used.
  - Mutations: polarity `elbow_right: -1` must fail the probe check (it does). A model copy with the elbow axis reversed still flexes forward, because the model's sign is measured.
  - Right side only. A README line was added.
- **Not committed (Joe, in session), kept in the session scratchpad:** `analysis/elbow_flexion_clearance.py` (draft) and `tests/test_elbow_flexion_clearance.py` (16 synthetic tests plus the two output tests).
  - The draft writes the file per G-G8 and point 5, stamped per point 6: ledger hashes, cache sha256 and bytes, and a tracked-inputs hash.
  - It checks the cache's forearm origin against the model's to 0.01 mm, and every positive angle against the probe.
  - Its synthetic tests (parallel cylinders, an axial gap across slab planes, a hinged pair, symmetry, the sign mutation through the sweep) pass. The two output tests: the committed JSON's ledger hashes against the current ledgers (no cache needed), and a fresh build compared byte for byte (skips without the cache, saying so).
  - Joe: the scratchpad does not survive the session. If you want it, the next session rewrites it from this description, or I can paste it on request.

## Timings

- Pose tests 1.07 s. Synthetic distance tests 12.5 s. A G-G8 build is 12.7 s (1.3 s to load the cache, about 0.25 s per angle).
- Full suite 2571 s (42:51), with the `inputs` tests rerun because `tools/envelope/` is in their input set: 2486 passed, 1 failed (finding 4), 6 skipped. Memo 63's comparable run was 2485 s.
- Quick suite 177 s, 1129 passed (CLAUDE.md: 174 s). `fy thread build`: 0 errors, 0 warnings.
- CLAUDE.md's figures are left alone: the full run with `inputs` skipped was not measured this session.

## Tolerances and choices

- `PROBE_MIN_MM` = 1.0 mm: the polarity file's own threshold (`foreign._probe_sign`).
- `FRAME_TOL_MM` = 0.01 mm (draft): the cache's forearm origin against the model's, the sheet length's printed precision.
- Touch = inner separation <= 0, with no margin. The reading is good to about a voxel (2 mm): the synthetic cylinders read within 0.12 mm. Not tuned: the stop is decided by -0.77 mm, which is under any margin up to one voxel.
- Choice: the measure is symmetric (a sum of both bodies' depths), so it does not depend on which body is host.
- Choice: the sets are bounded by their regions, so a cut face is a boundary. This is the oracle's convention (margin to skin, slabs reported apart), and it is what causes finding 1.

## My mistakes

- My first draft of the pose test held a meaningless assertion (`... or True`). I removed it before the first run.
- The distance tests "failed first" only by import error, since the script did not exist yet. That is weaker than a behavioural failure.
- I ran the 40 mm exclusion diagnostic (finding 2) before deciding how ruling 1 treats a memo. Its numbers are kept out of the repo.

## Questions for Joe

1. The G-G8 measure (finding 1). Should it exclude the ledger's 25 mm elbow joint-zone slabs (recommended), a sphere about the node of a radius you set, or only the anterior skin surfaces? Or should G-G8 be recast?
2. With any exclusion, I expect inner first contact below 157 deg (finding 2). Is skin compression part of the clearance question (the brief: "a design question"), or should G-G8 report the overlap only?
3. The forearm twist convention at zero (finding 3): accept it, or add a check?
4. The headless-browser timeout (finding 4): raise it, or serialise those tests?
5. Does ruling 1's "no cache-derived number in any file other than T7's output" cover memos? I read it as yes, apart from the G-G8 table you asked for.
