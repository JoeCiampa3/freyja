STATE: base 75b1c8b71dcf | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests not run (--no-run; quick suite 900 passed, 4 skipped) | dirty no (before this memo)

# Memo 51: memo 50's answers carried out

## Decision summary

- **Memo 50 needed no commit:** it was already in as 6e0d188, and it stays as it was. Your T1, Q1 and Q2 answers are for ADR 0042; nothing else was changed for them.
- **`.venv` is reinstalled from `requirements.txt`:** 0 version mismatches, mujoco 3.10.0 (it was 3.14.0), pytest 9.1.1. `fy test --quick` under it: 900 passed, 4 skipped, 28 deselected, 285 s. No full suite, as you said.
- **No committed record shows a mujoco other than 3.10.0**, but only the runs can be checked. All 15 tracked `sim/runs/*/summary.json` say 3.10.0. Gait and sweep records could not be checked: their JSON is not tracked and not on this machine, and no tracked gait or sweep file carries a version.
- **The arm targets are pinned** (75b1c8b): the manifest goes from 161 to 165 files, add-only, with the hashes of memo 50 section 5. `fetch --verify` reports 0 missing, 0 changed.
- **`isb_to_segment` assumes no forearm reference posture.** It is one fixed axis relabel for every segment. In effect a forearm part inherits the model's zero, which memo 50 inferred to be neutral. CAD text that reads "z lateral" as the radial side would assume a supinated forearm and sit about 90 degrees from the model's hand. No forearm part is bound yet (only `part.arm.upper_member`), so nothing is wrong today.
- **Decisions for you:** (1) whether the zero in ADR 0042 is stated as neutral, which would make this implicit behaviour explicit (recommended, since it needs no code change); (2) the manifest wording below.
- **What would change this:** a forearm CAD binding authored against a supinated frame, or a `gait.json` from another machine stamped with a different mujoco.

## Q3. Records against mujoco 3.10.0

Scanned every JSON under `sim/`, on disk, for a `mujoco` version key, and the tracked `.md`, `.yaml` and `.csv` files under `sim/` for a mujoco version string.

| Records | Found | Result |
|---|---|---|
| `sim/runs/*/summary.json` (tracked) | 15 with `env.mujoco` | all 3.10.0, **0 hits** |
| `sim/gait/*/gait.json` | none: gitignored (`.gitignore:45`), never committed, none on this machine | **not checkable** |
| `sim/gait/*/GAIT*.md` (tracked) | no version in the text | not checkable |
| `sim/benchmarks/gait_extract.json`, `walk_reference.json` (tracked) | no `env` key (stamped with commit, snapshot and model hashes) | not checkable |
| `sim/sweeps/` | `SWEEP.md` tracked; no JSON on disk, no version in the text | not checkable |

`sim/scripts/gait.py:681` and `sim/scripts/sweep.py:195` do write `env`, into records that are not kept. Gait and sweep results therefore have no surviving version stamp here. I can't date the drift: the reinstall replaced the evidence. The newest tracked run in the scan is from the 2026-10-28 16:53 to 16:54 batch, and it says 3.10.0.

## Q4. Pin

`--pin` rewrites the whole manifest from a folder, so I first fetched the 161 pinned files into the gitignored `data/makehuman/cache/targets`, added the four arm targets, and pinned the 165. The commit, license and note fields are unchanged.

`target_weights` ignores the extra files unless a modifier sets them, and the `.mhm`s do not, so they don't affect `makehuman_attribution.py`.

Two statements are now out of date, and I left them because you asked only for the pin:

- The manifest's `note` says the list is what `makehuman_attribution.py` and `makehuman_v2.py` read.
- `data/makehuman/SOURCE.md` says "161 files read".

Also, `retrieved` still says 2026-10-25; the arm targets were fetched on 2026-10-29. Recommended: a one-line wording fix to each, if you want it.

## Q5. `isb_to_segment` and the forearm (read-only)

**It assumes neither neutral nor supinated.**

- `tools/envelope/registry.py:263`: `ISB_TO_SEGMENT`, one constant matrix (oracle x = a, y = -c, z = b).
- `tools/envelope/registry.py:266-271`: `isb_to_segment(points, side="right")` takes no segment argument and has no forearm branch. Right side only; left raises `NotImplementedError`.
- `tools/envelope/registry.py:21`, `docs/schemas/envelope-oracle.md:18`: the same rule, with no posture.
- `tools/cad/frames.py:16,20`: the only callers' wrapper, passing no segment.
- A search of `registry.py` and `cad/frames.py` for forearm, elbow, neutral, supination and pronation finds nothing.
- `CONVENTIONS.md:89`: x anterior, y proximal "(up in the neutral pose)", z lateral. Its only segment-specific clause is the humerus. "Neutral pose" there means the upright zero pose; the text says nothing about forearm rotation.

**What it does in effect.** The CAD frame's x is the forearm body's x at q = 0, and CAD z is the body's -y. So the posture is whatever the model's zero is. If that zero is neutral (memo 50 section 4c, inferred, undocumented), the radius-ulna line lies along x, not along CAD z. "z lateral" stays true of the zero pose in space, but it is not the radial direction of the forearm.

## My mistakes

None new. Memo 50 said the drift "matters for every sim result". That overstated it: the checkable records are all 3.10.0, and the rest can't be checked.

## Questions for Joe

1. Should `gait.json` or the extract carry `env`, so that a gait result keeps its mujoco version? `gait_extract.json` is tracked and stamped, and it is the natural home. That is a schema change, so I have made none.
2. Fix the wording of the manifest `note`, `retrieved` and `SOURCE.md`?
