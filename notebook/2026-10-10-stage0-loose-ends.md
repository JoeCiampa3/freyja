---
origin: claude
---
# Stage 0 loose ends to revisit

Open questions left when Stage 0 closed. None blocks Stage 1. Delete a section when it is settled.

## 1. Pelvis and neck shapes (and the other geometry constants)

Joe may revisit the pelvis and neck. All shapes are tied to sheet lengths through `derive_keys()` in
`sim/scripts/pre_processor.py`, so a change is a constant or one template line plus a test:

- Radii and breadths are named design-choice constants there (`CAPSULE_RADII_M`, `PELVIS_RADIUS_M`,
  `NECK_RADIUS_M`, `HEAD_HALF_HEIGHT_M`, `SHOULDER_RADIUS_M`, `TRAPEZIUS_RADIUS_M`, `KNEE_SPHERE_RADIUS_M`,
  `CHEST_Z_FRACTION`, `CHEST_HALF_FRACTION`, `HANG_HALF_FACTOR`) and as literals marked
  `design choice, no sheet source` in `sim/models/freyja_template.xml` (ellipsoid breadths, foot box width).
- The pelvis is an ellipsoid plus a hip-girdle capsule; the neck is a short capsule from the cervical joint
  into the head. Both were judged "workable for the near future", not final.
- If the radii ever come from data (for example ANSUR circumferences), that data belongs in the sheet.
- Geoms are checked at neutral only (no body-to-body contact, soles on the floor). Behaviour under motion
  has not been checked.

## 2. Nine tracked archive CSVs in `sim/archive/`

`archive/` is gitignored, but 9 `freyja_params_*.csv` files were committed before the ignore applied, so git
still tracks them. `params/snapshot.csv` is now the tracked history, so the archive is redundant in git.
Either is fine; to untrack, `git rm -r --cached sim/archive` (the files stay on disk).

## 3. Housekeeping

- An empty `scripts/` folder at the repo root (only `__pycache__`).
- `log/chat.md` sits in `log/`; CONVENTIONS section 10 says `log/` should hold only events, so it probably
  belongs in `docs/memos/` or `notebook/`.
- Where the shared virtual environment lives: it is the root `.venv` today (`tools/fy/fy.cmd` assumes it);
  CONVENTIONS section 10 still lists this as open. Decide, then close the line there.

## Also still pending (already flagged by the tools)

- `checks/waivers.yaml`: the `check.mjcf.com_pct_stature` waiver is proposed (`confirmed: false`). Every build
  and watcher poll prints a reminder until it is confirmed or the CoM (55.26% against 55.36 to 56.40%) is fixed.
