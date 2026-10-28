# The clearance oracle: shapes, poses, component registry, free-space ledger

Authored reference for `fy envelope check` and `fy envelope free` (volume-extractor briefs 1, 5 and 6). Code: `tools/envelope/oracle.py` (shapes, poses, skin margin), `registry.py`
(`components/1`), `occupancy.py` (margin to components, free field). Tests: `tests/test_envelope_oracle.py`, `test_envelope_registry.py`, `test_envelope_occupancy.py`.

## Frame

The segment frame of a built segment: x anterior, y left, z up, origin at the proximal joint centre on the vertical axis (a trunk body: at its upper plane, on the midline). A station is
the distance below the origin plane. Units: millimetres and degrees. Every shape, pose and component below is in this frame.

**Model body frames (brief 7).** The oracle and the registry take every pose and component in the frame of the MuJoCo model's body of that name: the pelvis origin is the lumbosacral joint, the
abdomen's the TJC, the thorax's and the head and neck's the CJC; the legs as above. The built trunk bodies keep their own frame; `frames.py` converts: oracle = model + (-hjc_x, 0, 0) (the
head and neck also (0, 0, -length), its oracle origin being the vertex), hjc_x being the model's HJC x relative to its pelvis origin (`thigh_right_pos_x`). The mesh-to-model trunk shift (the
mesh hip line x less hjc_x) is computed at build time, stored in the cache, applied inside `oracle.clearance` / `clearance_union` (`frame_offset_mm`) and printed as a `frame:` line in every trunk
`check` and `free`. A trunk cache without it (built before brief 7) stops with an instruction to rebuild; a leg prints no such line (its frame is unchanged). A point the oracle reports back is in the
frame the poses were given in.

An ISB/CAD segment frame has x anterior, y up, z right. `registry.isb_to_segment` is the fixed rotation, right side: (a, b, c) -> (a, -c, b), a proper rotation (determinant +1). The hip
joint centre stays at the origin and the knee joint centre at (0, 0, -L). The left side is not defined (the function raises).

## Shapes (`shapes.yaml`)

```yaml
shapes:                          # a list, or the same list at the top level
  - name: rod                    # optional, default shape<i>
    type: cylinder               # cylinder | capsule | box
    diameter: 60                 # or radius; cylinder and capsule: length along the local z axis (a capsule's length is the straight part, the caps add one radius each end)
    length: 150
    # box: half: [hx, hy, hz]    # half extents along the local axes
    offset: [0, 0, 0]            # optional: the shape's centre in the pose's frame
    rpy_deg: [0, 0, 0]           # optional: the shape's own rotation, same convention as a pose
```

The shape is centred on its local origin with its axis along local z. A surface sample (spacing `SAMPLE_MM` = 1 mm) is rotated by `rpy_deg`, moved by `offset`, then posed.

## Poses (`poses.csv`)

Columns `tx,ty,tz` (required, mm) and `rx,ry,rz` (optional, degrees, default 0); lines starting with `#` are comments. One row is one candidate placement; the check reports the least
margin over rows and names the binding row (the pose index counts rows from 0). A pose maps the shape's frame to the segment frame: `p_segment = R p + t`, with `R = Rz(rz) Ry(ry) Rx(rx)`:
extrinsic rotations about the fixed segment axes, x first (`scipy ... from_euler("xyz")` in lower case), right-handed (positive is counter-clockwise seen from the positive end of the axis). Rotations are
supported by the oracle (`oracle.pose_points`) and pinned by tests: `ry = 90` lays a shape's z axis along the segment's x axis.

## Margins

* Skin: the signed distance from the sampled surface of every shape to the skin (positive inside), the least over rows and shapes. Not a distance to a cut plane. The slab ends are reported
  apart as `slab_overrun_mm`. `--required t` is the margin demanded of the skin.
* Component (brief 6): the signed distance between the candidate's surface and the component's surface, positive when separate, minus the component's `clearance_mm`. It is the smaller of
  (the component's signed distance at the candidate's surface samples) and (the candidate's signed distance at the component's surface samples), so an overlap is caught whichever solid is
  inside; an overlap is reported as the depth of the deepest sample. It is exact to the sample spacing (about 0.5 mm on curved faces) for analytic solids; for a mesh it is exact to
  the mesh's 1 mm voxel field, and the exact mesh-to-mesh distance is computed for the binding pair only (triangle distance on the candidate shape's facets, 96 around a cylinder).
* A feasible placement has skin margin >= `--required`, no slab overrun, and every component margin >= 0.
* `confidence: clear` when the binding slack (its margin less what it must reach: `--required` for the skin, 0 for a component) is at least the segment's voxel size in absolute value,
  else `marginal`.

## Component registry (`data/envelope/components/<segment>.yaml`, `components/1`)

Authored, one file per segment (the segment names of the cache: `thigh_R`, `shank_R`, `foot_R`, `pelvis`, `abdomen`, `thorax`, `head_neck`, `upper_arm_R`, ...). `fy envelope check` loads it when the file is
beside the cache (`<cache-dir>/../components/<segment>.yaml`, or `--components-dir`) unless `--no-occupied`. Beside it the CAD bridge writes `components/cad/<segment>.yaml` (generated by `fy cad pull`, same schema);
the loader merges the two, authored components first, and a duplicate `id` or `name` across them is an error naming both files. Relative mesh paths in the generated file resolve against its own directory.

| Field | Meaning |
|---|---|
| `schema` | `components/1` |
| `segment` | the segment frame all geometry is in |
| `components[].id` | a part id (`part.<assembly>.<name>`) in the bridge's file, free text in an authored file (`docs/envelope-component-contract.md`) |
| `name` | unique in the file; what reports call the component |
| `status` | `designed`, `reserved` (both take space), `candidate` (a proposal: takes no space), `foreign` (another segment's component, swept into this frame) |
| `owner` | the owning segment; equal to `segment` unless `foreign` |
| `primitive` | required unless `kind: flexible`: an oracle shape dict (cylinder, capsule, box; `offset` and `rpy_deg` allowed) in the component frame |
| `mesh` | optional STL (binary or ASCII), path relative to the registry file, vertices in the component frame in mm; used instead of the primitive when present |
| `pose` | static pose, component frame to segment frame, `{tx,ty,tz,rx,ry,rz}` (a mesh exported in the segment frame has the identity pose) |
| `poses_file` | optional sweep: an oracle pose CSV in the segment frame, replacing `pose`; required for `foreign`. The rows are the sweep: no interpolation between rows |
| `clearance_mm` | the margin kept around the component, default 0 |
| `mass_kg`, `source` | optional mass; where the geometry came from |
| `revision`, `sha256`, `parameter_inputs` | the CAD bridge's fields (Stage 3b): the part's revision, the canonical hash of its mesh and the hash of the addresses its CAD state consumed. Optional in an authored file; required per component in the bridge's file |
| `kind: flexible` | cables and hoses: `polyline` (component frame), `radius_mm`, `bend_radius_mm` instead of `primitive`; checked as a capsule chain; a polyline vertex tighter than `bend_radius_mm` is reported |

## Free field and free-space ledger (`fy envelope free`)

Free field = `{skin sd >= t}` minus every `designed`, `reserved` and `foreign` component dilated by its clearance and swept over its poses (and, with `--union`, over the union of the
adjacent bodies by brief 5's union query). The field's value is the distance to the skin (less `t`) and to the components, so its maximum is the radius of the largest free sphere;
cut planes never limit it. `data/envelope/free/<segment>.yaml` holds the header (free, occupied and skin volume, the largest free sphere with its centre and station, the components used) and
`rows`, the section ledger of the free field at 10 mm stations in the schema of `ledger.rows_for` (area, perimeter, largest inscribed circle, half-widths, inner shells). It is generated and
carries the banner of CONVENTIONS section 4.

## Foreign components and their poses (`fy envelope foreign`)

A foreign component belongs to another segment (owner) and moves relative to this one (host). Its registry entry has `status: foreign`, `owner: pelvis` and a `poses_file` already in the
host segment's frame. `foreign.foreign_poses` (`tools/envelope/foreign.py`) builds that file from the MuJoCo model (`sim/models/freyja.xml`, the file the sim runs):

* Inputs: the owner body (`pelvis`), the host (`thigh_R`, the model's `thigh_right`), a static placement of the part in the **owner's model body frame** (6-DOF in the pose convention
  above) and joint-angle samples: a CSV with one column per model joint name (`hip_fe_right`, ...), degrees, unlisted joints neutral. Without a CSV the default sampling is, for the
  three hip hinges, a single-axis sweep of each over its full range at 5 degree steps (the others neutral) plus the three-axis grid at 15 degree steps over the model's limits
  (the sheet's "MuJoCo limit - FINAL" ranges, as the model holds them), the range endpoints included: 590 distinct poses for either side.
* For each sample the model is set to `qpos0` with the sampled hinges, `mj_kinematics` runs, and the part's pose in the host frame is `inv(T_world_host) T_world_owner T_placement`;
  rotations are written as the pose convention's `rx, ry, rz`. Joint names, axes, order and ranges are read from the model (MuJoCo composes the hinges of one body in the order the
  model lists them); nothing is assumed about the hip's. Angles are in the clinical sign of `checks/joint_polarity.yaml` (flexion, adduction and internal rotation positive): the model's
  own sign is measured with that file's probe and the sample is flipped when they disagree.
* Stops (StopAndAsk, exit 3): the hip is not three serial hinges, their anchors are not at the body origin, or the host body is rotated against its parent at q = 0.
* Frames. The host thigh's model body frame is the oracle's thigh frame (origin at the HJC, axes parallel to the world at q = 0). The owner's is **not** always the oracle's: the model's
  pelvis origin is the lumbosacral joint, `thigh_<side>_pos_x` (56.7 mm) behind the hip, whereas the oracle's pelvis body has its origin on the knee's vertical line. The helper takes
  placements in the model's pelvis frame, which since brief 7 is also the frame a pelvis registry is authored in (no conversion is needed; the oracle applies the shift itself).
* Right side only. The left side's convention is an open item (the helper raises; the default sampling exists for both).
* Trajectories from the sim replace the default sampling by passing a samples CSV. **A part driven by a linkage rather than by joint angles enters only as a poses CSV from the user's
  linkage solver** (the oracle's pose schema, in the host segment's frame, named as the entry's `poses_file`); linkages are not modelled here.

