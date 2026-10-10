# Stage 0 recap

Date: 2026-10-10. Brief: `docs/briefs/stage0-brief.md`. Contract: `CONVENTIONS.md`.

Stage 0 made the sheet-to-MJCF pipeline tracked, reproducible and checked. The pipeline itself (what `pre_processor` reads, the meaning of every placeholder) is unchanged.

## What exists now

| Piece | Where | What it does |
|---|---|---|
| Snapshot | `params/snapshot.csv`, `params/snapshot.meta.json` | Every value the model used, with its sheet cell, plus `target_mass` (kg) and `target_stature` (m) from the sheet's `targets` range. Installed together with `sim/models/freyja.xml`, or not at all. The model banner carries the snapshot hash. |
| Template geometry | `sim/models/freyja_template.xml`, `derive_keys()` in `sim/scripts/pre_processor.py` | Every geom is tied to a sheet length. Capsule tips touch both joints, the knee sphere is centred on the knee, the head top is the vertex, the soles are on the floor at neutral. Radii and breadths are named design-choice constants. `site_vertex` and `site_sole_right/left` exist for the checks. |
| Checks | `checks/checklib.py`, `checks/mjcf_checks.py`, `checks/joint_polarity.yaml`, `checks/waivers.yaml` | Six checks with IDs, tiers, named tolerances and mutation tests. Waivers per CONVENTIONS section 7, with a `confirmed` field. |
| Gate | `post_checks` hook in `build_model()` | A failing gate check parks the new XML as `freyja_FAILED.xml`, keeps the last good model, snapshot and metadata, and prints the check IDs. Advisory results print and go to `checks/last_run.json` (gitignored). `--no-checks` skips it. |
| `fy` | `tools/fy/` | `fy build`, `fy watch`, `fy test`, `fy check [--tier]`. Wrappers only. Run `python tools/fy <command>` from anywhere in the repo. |

Test command: `python tools/fy test` (172 tests, offline, about 4 s). Model checks only: `python tools/fy check`.

## Measured numbers (committed model)

| Check | Tier | Measured |
|---|---|---|
| `check.mjcf.mass_closure` | gate | 64.935 kg, equal to the snapshot segment sum |
| `check.mjcf.mass_closure.target` | advisory | 0.100% from 65 kg (limit 0.15%; Dumas' rounded mass fractions) |
| `check.mjcf.mirror` | gate | 6 body pairs, 11 joint pairs, largest difference 1.9e-18 |
| `check.mjcf.joint_signs` | gate | 31 hinges, all as expected (polarity file approved) |
| `check.mjcf.floor_contact` | advisory | lowest point -1.3e-12 m |
| `check.mjcf.stature_chain` | advisory | vertex 1685.3 mm against 1700 mm, offset -14.684 mm (the sheet's own definitional offset) |
| `check.mjcf.com_pct_stature` | advisory | 55.26% of stature, 0.10% below the 55.36 to 56.40% band: FAILS |
| `check.mjcf.com_lateral` | advisory | -0.163 mm |

## Decisions and findings worth remembering

- **Foot box.** The old box left the sole 17 mm below the floor. Its height is now the ankle height (pelvis, thigh, shank and foot heights summed), so the sole is at z = 0 and `floor_contact` passes with no waiver.
- **Spine and neck flexion axes were wrong.** The moving segment is above those joints, so the hip-style axis `0 -1 0` bent the trunk and head backward for a positive angle (measured -12.7, -32.8 and -15.0 mm at 0.1 rad). They are now `0 1 0`. Wu 2005 section 2.4.1 confirms the lateral bending (right positive) and axial rotation (left positive) signs. It makes flexion negative, which the model does not follow because its ranges are written `-extension flexion`.
- **Targets are SI.** The sheet gives stature in mm; the snapshot stores 1.7 m.
- **Waiver.** `com_pct_stature` is proposed with `confirmed: false`. Every build prints a reminder until it is confirmed or the CoM is brought into the band.
- **PyYAML and pytest** were added and pinned in `requirements.txt` with approval.

## Not done, on purpose

Listed in `notebook/2026-10-10-stage0-loose-ends.md`: the pelvis and neck shapes, the 9 tracked archive CSVs, repo housekeeping and the virtual-environment location. Seven sheet ROM values are still missing (lumbosacral flexion, extension, lateral bending and axial rotation; shoulder adduction and internal/external rotation), so those joints are unlimited and each build warns.

## Starting Stage 1

Open a new session, point it at `CLAUDE.md`, update the "current brief" line there, and begin with the baseline: `python tools/fy test`, `python tools/fy check`, and `python tools/fy build --dry-run`.
