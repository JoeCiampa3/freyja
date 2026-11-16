---
origin: claude
---

# Joe's rulings on memo 65 (2026-11-16)

Recorded from Joe's reply in session ("yes, accept, yes, keep 180 s"). Each answers the question of the same number in `docs/memos/memo65-elbow-clearance-close-out.md`.

1. **Sign-off of `rm.v1-upper-arm-geometry-extracted`: yes.** Joe sets `signed_off: true` in the node file; Code never does.
2. **The sculpt's 4.69 deg forearm twist: accepted.** The zero-twist posing convention stands for this leaf. Revisit at the elbow part, where a twist-corrected sensitivity row may be added if its clearance design comes within a few mm.
3. **The M3 keep-out goes into `data/characterization/upper_arm.json` at Group F:** a reported constraint, never subtracted from any volume.
4. **Headless-browser timeout: keep 180 s** (`tests/test_roadmap_viewer.py`, `BROWSER_TIMEOUT_S`). No serial phase in `fy test`.

Open: rulings 3 and 4 need no work now; ruling 3 applies when Group F runs, and the brief's G-F text does not yet name the keep-out, so the Group F brief revision should.
