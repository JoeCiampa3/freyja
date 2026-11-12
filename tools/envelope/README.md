# tools/envelope

The body-envelope library (volume-extractor brief 1 onward). Authored. `fy envelope` calls it; `tools/envelope/cli.py` documents each command. The schemas of the shapes, poses, registry and free ledger are in `docs/schemas/envelope-oracle.md`. What the library writes is listed in `data/envelope/README.md`.

This list was one cell of the layout table in `CONVENTIONS.md` section 2 until 2026-11-11 (memo 61). The wording is that cell's; each module's own docstring is the detail.

- Landmarks schema (`landmarks.py`), MakeHuman mesh and frame map (`meshio.py`), ANSUR heights (`anthro.py`), mesh features (`features.py`).
- Registration to the sheet's nodes (`register.py`): piecewise axial stretch plus horizontal shear.
- Voxel signed-distance field (`field.py`), section ledger (`ledger.py`), clearance oracle (`oracle.py`).
- Mass cuts (`cuts.py`): the Dumas 2015 Table 1 landmarks scaled to the sheet's abdomen. The mass base (`masses.py`).
- The region split of a mesh's volume (`decompose.py`).
- The trunk registration (`trunk.py`): the sheet's LJC, TJC, CJC and vertex nodes against the mesh, CJC anchor candidates, stretch per sub-segment.
- The trunk bodies (`bodies.py`): the trunk map above the hip, the axilla from the layer topology, the cell accounting with joint zones and shoulder planes, the voxel bodies, design numbers, closure. `bodies_report.py`: the assembled result and the oracle examples.
- The oracle's union query (`oracle.clearance_union`).
- The model body frames of every segment and the computed mesh-to-model trunk shift (`frames.py`): the oracle takes poses and registries in the model frames, pelvis origin at the lumbosacral joint (brief 7).
- The offset of the sim's trunk stack from the mesh centre line (`offsets.py`).
- Foreign components' poses from the MuJoCo model and joint-angle samples (`foreign.py`).
- The component registry (`registry.py`): `components/1`, the ISB to segment rotation, the STL reader.
- The occupancy of a segment (`occupancy.py`): margin to the registry's components, the exact mesh distance of the binding pair, the free field.
- The arm bodies (`arms.py`, `arms_report.py`, brief 8): each arm segment is the mesh rotated rigidly about its proximal joint centre onto the zero-pose axis, anterior preserved, and stretched along it, on the adr-0042 nodes (the proximal segment's section centre line at the joint station), gate 8%; the hand rotated with the forearm, no stretch; the closure with every body built, the final share table.
- The spine reservations (`reserve.py`): the placement search and the reserved registries.
- The corridor sweep (`corridor.py`) and the hip registration check (`hipcheck.py`, report only).
- Gates (`gates.py`).
- Not named in the old cell: the leg trial (`trial.py`), the sheet inputs (`sheet.py`), the Ruler measures (`ruler.py`), the inspect bundle (`bundle.py`), silhouette plots (`plots.py`), synthetic test meshes (`synthetic.py`).

`reserve`, `corridor` and `hip` are brief 8's commands.
