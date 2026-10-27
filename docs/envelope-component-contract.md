# Envelope component contract (DRAFT)

Status: draft from volume-extractor brief 7, item 3. Not agreed with Stage 4: no Stage 4 document or ADR exists yet (memo 36, finding 3; `cad/*/README.md` are empty, the only roadmap
node is `rm.v1-ariadne-cad-bridge`). Everything below is what the envelope tooling can read today plus what the connector would have to add. When the connector's format is decided,
this file and `id` / pose fields of the registry are aligned in one edit. Nothing here changes the oracle's behaviour.

## What the connector emits

One record per component, per owner segment. The envelope reads them as a component registry (`data/envelope/components/<segment>.yaml`, schema `components/1`, documented in
`docs/schemas/envelope-oracle.md`); the connector writes that file, or a file that converts to it without loss.

| Field | Rule | Registry field |
|---|---|---|
| `id` | the Ariadne identifier of the part, `part.<assembly>.<name>` (CONVENTIONS section 3; the revision is a field, not part of the id). Permanent, never reused | `id` (free text today) |
| `revision` | the part's revision, a string | not yet in the registry (to add with the alignment) |
| `name` | unique within the segment file; what reports call the component | `name` |
| owner segment | the thread segment record, `seg.<name>` (`seg.pelvis`, `seg.abdomen`, `seg.thorax`, `seg.head_neck`, `seg.thigh`, `seg.shank`, `seg.foot`), and the side for the limbs. The registry's `segment` / `owner` are the oracle's names (`pelvis`, ..., `thigh_R`) | `owner`, `segment` |
| frame | the **model body frame of the owner** (next section), axes parallel to the world at q = 0: x anterior, y left, z up. Not the oracle's own frame and not an ISB/CAD frame; a CAD frame in ISB axes is converted by the connector (`registry.isb_to_segment`, right side: (a, b, c) -> (a, -c, b)) | `pose`, `poses_file`, `primitive`, `mesh` |
| bounding primitive | required: `cylinder`, `capsule` or `box` (with optional `offset`, `rpy_deg`) enclosing the part; it is what the oracle checks when no mesh is given | `primitive` |
| mesh | optional: a watertight STL, millimetres, vertices already in the owner's frame (identity pose), consistent winding, no self-intersection. Used instead of the primitive. A flexible part (cable, hose) is a polyline with `radius_mm` and `bend_radius_mm` instead | `mesh`, `kind: flexible` |
| `status` | `designed`, `reserved` (both take space), `candidate` (a proposal, takes no space), `foreign` (belongs to another segment; needs its poses in this segment's frame) | `status` |
| `clearance_mm` | the margin kept around the part, default 0 | `clearance_mm` |
| `mass_kg` | the part's mass | `mass_kg` |
| `sha256` | the hash of the geometry the oracle used: of the STL bytes when there is a mesh, else of the canonical JSON of `primitive`, `offset`, `rpy_deg` and `pose` (sorted keys, no whitespace). 64 hex | not yet in the registry (to add) |
| `parameter_snapshot` | the `snapshot sha256` (12 hex, the STATE line, `params/snapshot.meta.json`) of the parameter set the part was designed against, so a changed sheet makes the part stale rather than silently valid | not yet in the registry (to add) |
| `source` | where the geometry came from (CAD file and revision) | `source` |

Two fields the registry cannot hold today (`revision`, `sha256`, `parameter_snapshot`) are the additions this contract asks for; the oracle would carry them through to its outputs and
hash them into the free-space ledger's inputs hash.

## Frames: where each owner's origin is

Model body frames (brief 7, item 1), origins as in `sim/models/freyja.xml`:

| Owner | Origin | Body extends |
|---|---|---|
| pelvis | the lumbosacral joint (LSJ), on the midline | below the origin, to the hip-centre plane |
| abdomen | the TJC | below, to the LJC plane |
| thorax | the CJC | below, to the TJC plane |
| head_neck | the CJC | above, to the vertex |
| thigh (R) | the hip joint centre | below, to the knee |
| shank (R) | the knee joint centre | below, to the ankle |
| foot (R) | the ankle joint centre | as the model's foot |

The trunk examples and every trunk registry are in these frames. The oracle's built trunk body has its own origin (on the vertical through the hip joint centre at the body's upper plane, the
head and neck at the vertex); the oracle converts with the **mesh-to-model trunk shift**, a computed parameter (the mesh hip line x less the model's hip joint centre x relative to the pelvis
origin, `thigh_right_pos_x` in the snapshot), applied inside the oracle and printed in every trunk result (`frames:` line). The connector does not apply it.

The model's trunk stack and the mesh's trunk centre line are not the same line: memo 37 reports the offset at the LJC, TJC, CJC and SJC planes in the zero pose and in the design stance. A
trunk part placed in the model frame is where the simulation puts it; whether the mesh's soft tissue is there is what the oracle's margin says.

## Sides

The **right** side is authoritative. The left is the mirror in the sagittal plane: y negated. For a pose that is `ty -> -ty`, `rx -> -rx`, `rz -> -rz` (`ry` unchanged); for a primitive its
`offset` and `rpy_deg` transform the same way; for a mesh, vertices `y -> -y` and the triangle winding reversed. The trunk bodies are whole-width (they hold both sides): a trunk part is placed
at its signed y, and a bilateral pair is two records, the left the mirror of the right. The oracle builds the right legs only today and refuses a left-side frame helper
(`registry.isb_to_segment("left")` raises) until Joe defines the left CAD frames (brief 6, open item; ADR 0007 D11).

## What the oracle can and cannot say (accuracy limits)

* **Voxel size.** The skin is a signed-distance field on a 2 mm grid (`trial.VOXEL_MM`), sampled trilinearly. A margin is exact to about the voxel; a candidate whose binding slack is smaller than
  the segment's voxel size is reported `confidence: marginal`, otherwise `clear` (`slack` = the margin less what is required: `--required` for the skin, 0 for a component).
* **Component margins.** Analytic parts are sampled at 1 mm on their surfaces (`oracle.SAMPLE_MM`; about 0.5 mm on curved faces); a mesh part is voxelised at 1 mm (`occupancy.MESH_VOXEL_MM`) and
  the exact triangle-to-triangle distance is computed for the binding pair only; a candidate cylinder has 96 facets (0.02 mm short at 35 mm radius).
* **Sweeps are rows.** A foreign part's travel is the list of poses given (the default hip sampling is 590 distinct poses); nothing is interpolated between rows, so the free field between rows is
  optimistic. Linkage-driven parts enter only as a poses file from the connector's own solver.
* **The skin is a sculpt, not a person.** The envelope is the v2 sculpt registered to the sheet by a piecewise axial stretch (stretch gate 8%; the thorax and the head and neck are known to about
  +-4%). Against the reference women the sculpt (BMI 18) carries about 9% less volume share in the abdomen-to-thigh region (ADR 0007 D7, memo 32). Single-sculpt shape and the anchor
  uncertainty are not in a margin; a tight fit needs the Monte Carlo ranges or a margin of a few millimetres on top.
* **Planes are accounting.** A part may straddle a joint-centre plane; the union query holds a part in the adjacent bodies in the neutral pose. Interference across the range of motion belongs
  to the simulation, not to the oracle (ADR 0007 D5).
* **Fine fits belong to CAD.** The oracle answers "does it fit, where does it bind"; it does not replace a CAD interference check, and it is not a structural check.
* **A mesh component trusts its frame.** The registry trusts the STL it is given; a mesh exported in the wrong frame is a wrong answer, not an error. The component's own `inside_skin_mm` (a
  component sticking out of the skin is a registry fault, reported as a warning) is the only guard.

## Open for Stage 4

1. The connector's format (this document's fields against whatever CAD exports); `revision`, `sha256`, `parameter_snapshot` in the registry.
2. The left side's CAD frames.
3. Whether a component's pose may depend on joint angles in the registry itself (today only through `poses_file`).
4. Who regenerates the registry when the snapshot hash changes.
