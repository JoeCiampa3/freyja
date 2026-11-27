STATE: base 8f528de273fd | brief architecture sha256:bd2d997fe5e8, ariadne sha256:31a88eef7b85 | snapshot sha256:492fe816e6d8 | tests 2548/2551 | dirty yes (the uncommitted files are this memo and the timing figures in `CLAUDE.md`; full suite on this tree with `PYTEST_XDIST_AUTO_NUM_WORKERS=12`, 171 s: 0 failed, 3 skipped, 26 `inputs` tests not run again)

# Memo 68: shoulder room, Group B: stopped at T0, the model's SJC sits 37.8 mm behind the envelope's shoulder joint

Brief: `docs/briefs/ariadne/shoulder-room-brief.md`, Group B. sha256 `31a88eef7b857d5b…` matches the prompt's prefix 31a88eef7b85 (LF, no mismatch). Your prompt signed off Checkpoint A (memo 67). It kept B1 as the basis, left B1T and S4 untyped and named u1 = `data/shoulder/axis_search.json#/basins/1/u1` = (-0.43809, -0.57088, 0.69439). It also said to run M4 with the three c rows only. T0 ran. It found that the SJC the brief fixes (the model's `upper_arm_right`) is not where the body envelope's shoulder joint is. Every Group B measure is centred on the SJC, so I stopped before T3 (CLAUDE.md rule 4). No script, test or output was written. The one commit holds this memo, `docs/STATE.md` and the full-suite timing figures in `CLAUDE.md` (205 s, then 171 s, at 12 workers; 83 s quick). CLAUDE.md lets Code update those when a memo measures new ones, and the next session needs the worker note (finding 4). The Camargo tests that failed in memo 66 (its finding 6) pass on this clone. Nothing in the model, template, `pre_processor`, sheet, `tools/envelope/`, `data/envelope/`, decision records, roadmap nodes or thread records changed. Nothing stamped, nothing pushed.

## Decision summary

- **What this means for Freyja:** the body envelope's shoulder joint is **37.8 mm further forward** than the sim model's. The envelope's joint is where the arm actually hangs from the skin: the mesh SJC carried through the trunk registration. The model's joint is `upper_arm_right`. Their y and z agree to 0.01 mm. Centred on the model's SJC, the shoulder room is cut off by the **back of the shoulder 8.5 mm behind the joint**, and the arm's envelope pokes 38 mm out behind the thorax's (figure below). That is not a body. Centred on the envelope's SJC, the thorax and arm fields measure the same skin: 46.0 mm in front and 46.5 mm behind in both. The brief's frame rule, the gate G-B1 and every measure use the model's point, so I stopped and need your ruling on the centre.
- **The numbers that matter:**
  - Envelope SJC in the thorax model frame: **(51.60, -192.33, -77.57) mm**, against the model's (13.81, -192.33, -77.57). Difference **37.79 mm in x**, 0.00 in y and z.
  - Depth to skin from the SJC, thorax field, back / front: **8.5 / 83.5 mm** at the model SJC, against **46.5 / 46.0 mm** at the envelope SJC. The arm field gives 46.5 / 46.0 at the envelope SJC.
  - Cause, already on file: the trunk registration shifts the mesh +29.39 mm in x above the hip. The model's trunk stack stands on the lumbosacral joint, 56.72 mm behind the hip. In the zero pose, `data/envelope/trunk_offsets.json` puts the model stack **50.3 mm behind** the thorax section's centroid at SJC height (26.1 mm in stance).
  - G-B1's lateral check is unaffected: the arm skin along -y at station 40 is at y = -226.6 mm, against memo 59's 226.63.
  - Disk at T0: 171 GB free (stop line 10 GB).
- **Decisions for you:**
  1. Centre Group B on the **envelope's SJC** (recommended). That is the arm ledger's `mesh_nodes_mm.sjc` mapped through `bodies.trunk_map`, computed and not typed. The arm field sits at its own origin there. u1 is unchanged: it is a direction. G-B1 becomes: SJC equals that point to 0.01 mm, with its y and z equal to `upper_arm_right`'s and the 37.79 mm x difference reported. M4's sternal node takes the same rule: Dumas SUP measured from the mesh's thorax centre line at the CJC, as `trunk_bodies.json`'s shoulder plane already does.
  2. Or keep the **model's SJC** literally. Then the measures describe a joint 8.5 mm from the back skin and an arm displaced 38 mm behind the shoulder. I would not use those numbers for adr-0025.
  3. Or fix the offset at its source: re-register the trunk, or move the model's trunk stack. Both are outside this brief.
- **What would change this:** a ruling that the hardware's joint must sit at the model's SJC, whatever the skin does. Then the question becomes 3, not a room measure.

## Findings

1. **The model's SJC is 37.79 mm posterior to the envelope's shoulder joint** (CLAUDE.md rule 4; it contradicts the brief's premise that the model SJC is the centre of the union). Measured on the cached fields (`data/envelope/cache/thorax.npz`, inputs 01a6e055b4a5; `upper_arm_R.npz`, 770c1272e683). The thorax field is placed in the model frame by `frames.segment_offset_mm` (oracle = model + (-56.72, 0, 0)). The arm field is centred on its own origin.
   - The arm field's origin is `upper_arm_R.yaml#/mesh_nodes_mm/sjc` = (15.51, -192.33, 1349.24) in the mesh frame. Mapped by `bodies.trunk_map(...).apply`, with the shear above the hip (dx, dy) = (+29.39, -16.48) mm, and less the thorax `origin_xyz`, it lands at thorax oracle (-5.12, -192.33, -77.57). That is model (51.60, -192.33, -77.57).
   - Cross-check of the map: vertex 1671 maps to (-36.51, -223.19, -84.76), memo 59's thorax-ledger coordinates of that vertex, exactly.
   - Rays from each candidate centre to the zero level of each field (0.5 mm step):

   | Centre (model frame) | field | +x ant | -x post | +z up | -y lat |
   |---|---|---|---|---|---|
   | model SJC (13.81, -192.33, -77.57) | thorax | 83.5 | **8.5** | 26.0 | 16.5 |
   | model SJC | arm at model SJC | 46.0 | 46.5 | 82.5 | 34.5 |
   | envelope SJC (51.60, -192.33, -77.57) | thorax | 46.0 | 46.5 | 47.0 | 46.5 |
   | envelope SJC | arm at envelope SJC | 46.0 | 46.5 | 82.5 | 34.5 |

   The thorax's -y figures (16.5 and 46.5) are not skin. Its grid ends 15 mm beyond the shoulder plane (y = -207.33), and past the edge `field.Segment.signed_distance` returns the edge value less the distance. Signed distance at the point: thorax 8.13 mm at the model SJC, 36.52 at the envelope SJC; arm 34.42 at its own origin.
   - Figure: `data/shoulder/map/sjc_placement.png` (gitignored; made by a scratch script, not committed). It shows the transverse section at SJC height and the sagittal section through the shoulder plane: thorax skin, the arm's skin at each placement, and both centres.
   - The source is the documented trunk offset (`fy envelope offsets`, zero pose: SJC height sim x -56.72, mesh centroid -6.42 from the hip line, offset -50.30 mm). `frames.py` places model-frame points against the mesh by the hip line alone. `trunk_bodies.json`'s shoulder plane and the arm bodies place the SJC from the mesh's thorax centre line at the CJC (`x_note`). The two conventions meet nowhere else in Group B, but they meet at the shoulder.
2. **Shoulder plane: a cut, not skin, in both fields** (T0, brief's report-and-stop item; it is not the blocking one).
   - In both fields, `sd` is the signed distance to the skin of the extended solid, the whole conformed mesh. The plane exists only in `region`. Thorax: `bodies.build`'s region clips |y| > 192.33 above the axilla; the grid itself ends at y = -207.33. Upper arm: its region takes the girdle beyond the plane.
   - On a lateral scan 4 mm below the model SJC, the thorax region holds y >= -192 and the arm region holds -190 to -228, with sd zero at -226.6. The arm region also has holes just medial of its origin (y -178 to -188 at that placement), the A-pose mesh rotated 37 deg. A region-based union covers them with the thorax.
   - For the next session: `oracle.clearance_union` holds a point by z-slab only and ignores `region`, whereas `occupancy.skin_field`, which `free --union` uses, holds by region. At the shoulder the thorax and arm slabs overlap over the whole z range, so `clearance_union` would credit the thorax field's extended-solid flesh beyond the cut. Example: at y = -200, thorax region 0 but thorax sd 5.4 mm. I recommend skin_field's rule for N (question 2). Placed at the envelope SJC, the two fields agree at the skin, so the difference should be small. Not measured.
3. **Memo 59's "mesh SJC x" rows omit the trunk shear.** `analysis/fall_room.py` takes the mesh SJC's x as `mesh_nodes_mm.sjc[0]` less the pelvis origin, -34.52 mm in the thorax ledger frame. Through the trunk map it is -5.12 mm, 29.39 mm further forward. The two inboard rows labelled "mesh SJC x" in `data/falls/room.json` (146.23 mm to m1; 192.33 with modules elsewhere) were therefore measured at the wrong x. Memo 59 drafted no cap on them ("I report them and draft nothing on them"), so no decision rests on them. The vertex-based shoulder row (226.63 mm) is correct.
4. **`fy test` with `-n auto` crashes this machine.** It now reports **32 logical CPUs**; memo 66 measured on 14. `tools/testkit.PARALLEL` is `-n auto --dist loadfile`, so xdist started 32 workers. They died at spawn with `MemoryError` and `OSError: [WinError 8] Not enough memory resources are available to process this command`: "no tests ran", exit 3. Memory at the time was 13.8 GB free of 33.5 GB physical and 26.0 GB of commit, with WSL's vmmem resident. This took down my first session (you resumed it). I changed no code. I set xdist's own `PYTEST_XDIST_AUTO_NUM_WORKERS=12` for every suite run after that, an environment variable only. Recommended: cap the workers in `testkit` (for example min(cpu_count, 12)), or size them by free memory. This is a follow-up for you to approve, not done.

## T0 baseline

- HEAD 8f528de, tree clean. `df` on C: 464 GB, 171 GB free (stop line 10 GB): go.
- `fy thread build`: 70 files, 0 changed, 34 records, 1 work item, rework 0, errors 0, warnings 0 (2.0 s).
- `fy test --quick`: with `-n auto` (32 workers) INTERNALERROR, no tests ran (24.4 s; finding 4). With `PYTEST_XDIST_AUTO_NUM_WORKERS=12`: **1129 passed in 83.3 s**.
- Cache present and current: `thorax.npz` inputs 01a6e055b4a5 = `thorax.yaml` and `thorax_sections.csv`; `upper_arm_R.npz` 770c1272e683 = `upper_arm_R.yaml` and `upper_arm_R_sections.csv`.
- Model: `upper_arm_right` is a child of `thorax`, pos (13.814, -192.329, -77.569) mm, quat identity; the thorax frame is the world's at q = 0.
- u1 by address: `data/shoulder/axis_search.json#/basins/1/u1` = (-0.43808827, -0.57087653, 0.69439086), norm 1 - 7.7e-14. G-B1 asks for 1e-12; the file prints 12 significant digits, so the script will have to normalise it and report the residual.
- Spine modules (`data/envelope/reserved/thorax.yaml`): m1, m2 and m3, cylinders 90 x 81.5 mm, clearance 5, centres at model (32.66, -2.33), (68.66, -92.33) and (68.66, 87.67), tz -119.
- `part.arm.upper_member` (`components/cad/upper_arm_R.yaml`): box 29.96 x 29.98 x 255.23 mm, hanging from the arm origin, clearance 0. It is the CAD placeholder, reported and not subtracted (brief, Decisions 4).

## Gates

| Gate | Result | Numbers |
|---|---|---|
| G-B1 frames | not run (T3 not reached) | Seen at T0: the arm skin along -y at station 40 is at y = -226.6 mm by linear interpolation of the 2 mm scan (memo 59: 226.63). The SJC part is the open question (finding 1) |
| G-B2 synthetic | not run | — |
| G-B3 ball | not run | — |
| G-B4 bound order | not run | — |
| G-B5 determinism | not run | — |

## Tolerances and parameters I chose

None that touch a result. The scan steps above (0.5 mm rays, 1 mm figure raster, 2 mm lateral scan) are for reading only, and nothing is gated on them. The worker cap of 12 is an execution setting, the largest count I had seen run cleanly on this machine. It is not a test tolerance.

## My mistakes

1. I ran the quick suite with `-n auto` without first checking the CPU count, after two memos in a row had environment trouble (66: missing xdist; 67: full disk). It started 32 workers and took the session down. A `nproc` and a memory check first would have cost five seconds.
2. My first conversion of the arm's mesh origin into the thorax frame subtracted the thorax's `origin_xyz` directly. That is the same omission as memo 59's (finding 3), and it put the mesh SJC at -34.52 mm. I caught it only when vertex 1671 did not reproduce memo 59's coordinates. Then I used `bodies.trunk_map` itself.

## Open follow-ups (approved, not this session's work)

- Memo 67 finding 4: `fy state` should error on a `Current <track> brief:` line without a backticked path. Open.
- Memo 66 finding 5: `fy test` should print a line when it falls back to serial because xdist is missing. Open.

## Questions for Joe

1. Which SJC centres Group B: the envelope's (51.60, -192.33, -77.57), recommended, with G-B1 restated as in the decision summary; the model's (13.81, ...); or neither until the trunk offset is fixed at its source?
2. For N: the union by region (`occupancy.skin_field`'s rule), recommended, or by z-slab (`oracle.clearance_union` as written; it credits flesh beyond the shoulder cut)?
3. Finding 4: cap `fy test`'s workers in `tools/testkit`? Until then every suite run on this machine needs `PYTEST_XDIST_AUTO_NUM_WORKERS` set, or fails.
4. Finding 3: correct memo 59's two "mesh SJC x" rows in `analysis/fall_room.py` (a fall-room follow-up), or leave them as history, since nothing rests on them?
5. Still none: a source for the sternoclavicular offset c (M4 runs the three sensitivity rows, as you said).
