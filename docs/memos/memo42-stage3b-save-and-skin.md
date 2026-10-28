STATE: STATEPLACEHOLDER

# Memo 42: Stage 3b, the guarded save and the joint centres against the skin

## Decision summary

- **Q2 is done.** `fy cad push` now saves a bound document that had no unsaved changes, after a healthy recompute that changed something, with a version description naming the pushed addresses. A document with unsaved changes gets its parameters set and is not saved. The sidecar's `document.unsaved_changes` records the state at pull, and `fy cad stamp` refuses when it is true. Tests for both paths run on the live fixture and on the fake.
- **A defect in the push-and-save design, found and handled:** Fusion shows the new version number about 1.4 s after the save (measured: 10 at 0.1 s, 11 at 1.4 s). Without a wait the sidecar would pin the old version. `push` now polls for the new number for up to 20 s and reports "not confirmed" instead of guessing.
- **Q3: the 10.97 mm is not mostly a lateral offset, it is the elbow end.** In the upper arm's frame the signed skin distance (positive inside) is **34.5 mm at the SJC** and **4.0 mm at the EJC**. The EJC is inside your 5 mm line, so by your rule it is a registration finding: reported, envelope unchanged.
- The model and the mesh agree on both anchors to 0.000000 mm (stretch 1.12437 maps the mesh's native 227.0 mm SJC-EJC to the model's 255.2347 mm). The 4.0 mm is a property of where the registration puts the EJC against the skin, not a CAD or model-frame disagreement.
- The tube (radius 15.0 mm) goes outside the skin from about z = -150 mm on and the protrusion grows to **10.97 mm at the distal end**, at model-frame point (-7.8, -12.8, -255.2) mm. The skin's inscribed radius at the EJC section is 12.8 mm, smaller than the tube.
- **Decisions for you.** (1) Look at the EJC registration: 4.0 mm from the skin at a joint centre is where the elbow's housing will have no room; the envelope's elbow section is what to check, not the placeholder. Recommended: a separate brief item on the upper arm's distal registration before the real design. (2) Save `Upper Arm v0`, then `fy cad pull part.arm.upper_member`, then `stamp`-eligibility returns. It is unsaved now, so the committed sidecar says `unsaved_changes: true` and doc v1. (3) Q1 and Q4 are applied as written below.
- **What would change the conclusion:** a different EJC section in a rebuilt envelope cache (this is the cache with inputs `e255f8e9c931`), or a placement of the real upper arm that is not on the model axis.

## Q2: what changed

| Item | Result |
|---|---|
| `bridge.save_document(description)` | new verb; refuses a never-saved document, an unhealthy timeline and an unmodified document; not read-only |
| `push` | records `unsaved_before`; saves only if clean, ok, and Fusion reports the document modified; returns `saved`, `version`, `save_skipped`, `save_note` |
| Version lag | `_new_version` polls `doc_info` every 0.5 s up to 20 s (`VERSION_WAIT_S`, `VERSION_POLL_S`); a timeout gives `version: None` and the note "not confirmed" |
| Sidecar | `document.unsaved_changes` (boolean, required) in the schema and CONVENTIONS section 8; `stamp` refuses; `fy cad status` shows `UNSAVED` |
| CONVENTIONS rule 12 | "never saves a document it was not told to save" replaced by the exact scope: through `push` only, bound or fixture document only, clean only, healthy only |

Live fixture results (`tests/test_cad_fusion.py --fusion`, 28 passed in 51 s before the last three edits, the three new ones 3 passed in 22 s): a clean fixture gains exactly one version on push and the pull records it with `unsaved_changes` false; a fixture with an unsaved edit gains none and the pull records `unsaved_changes` true and `stamp` refuses; `save_document` on an unmodified document saves nothing. The fake adds: a lagging version number is waited for; a version that never shows is reported, not guessed; a failed push saves nothing; a failed save is reported.

The fixture accumulates versions (about three per run). I tolerate that; it is a scratch document.

Tolerances chosen: `VERSION_WAIT_S` 20 s is about 14 times the measured lag, chosen from that measurement, not tuned to a result.

## Q3: joint centres against the skin, upper_arm_R frame

The field is `data/envelope/cache/upper_arm_R.npz` (voxel 2.0 mm, `z_top` 36.0 mm, length 291.235 mm, so the distal plane is z = -255.2347 mm, the model's elbow). Signed distance is the field's, positive inside, error about the 2 mm voxel.

| Point | Model frame (snapshot) | Mesh's own anchor | Signed skin distance |
|---|---|---|---|
| SJC | (0, 0, 0) | (0, 0, 0) (station 36.0 mm) | **+34.52 mm** |
| EJC | (0, 0, -255.2347) (`forearm_right_pos_z`) | (0, 0, -255.2347) (distal plane) | **+4.03 mm** |

Distance between the model's and the mesh's anchors: 0.000000 mm at both. This follows from the construction (the segment frame origin is the mesh's SJC and the upper arm is cut at the EJC), so it confirms the frame, it does not test it independently.

The placeholder's skin distance by station (tube radius 15.0 mm, ring points): z = 0: +19.6; -50: +11.6; -100: +3.5; -150: -3.0; -200: -8.4; -230: -9.6; -255.2: **-10.98** mm. The 581 mesh vertices give -10.97 mm at (-7.8, -12.8, -255.2) mm (station 291.2 mm), the distal end ring, which is the binding point. 17% of the vertices are outside the skin. My memo 41 explanation (the axis runs near the lateral skin) was incomplete: the axis is 12.1 mm inside the skin at z = -150 and 4.0 mm at the EJC, and a 15 mm tube cannot fit a skin that narrows to a 12.8 mm inscribed radius at the elbow.

Not done: I did not change the envelope, the cache or the registration. The 4.0 mm is below your 5 mm line, so it goes to you as a registration finding.

## Q1 and Q4

- `rm.v1-bridge-tooling` is a leaf: `estimate_days: 3.0`, `done_when: {type: manual}`; `signed_off` not set. `roadmap/state.json` and `STATUS.md` regenerated (182 nodes, errors 0).
- `CLAUDE.md`: the `fy test --quick` and `fy cad` commands, and rule 1, as proposed in memo 41. The `fy cad` bullet also says what `push` saves. The full suite measured 1068 s (17 min 49 s), so CLAUDE.md says "about 18 minutes: 1068 s at memo 42", not the proposed 17. `tests/test_state.py::test_the_documented_suite_time_matches_claude_md` and the `sim/scripts/state.py` docstring still said "about six minutes"; I updated both to the measured figure (a documentation number, not a tolerance).
- `docs/OVERVIEW.md` glossary: five bullets for the CAD terms (bound document/binding/sidecar, parameter classes, push/pull/drift, CAD frame/canonical mesh, chord bound/guarantee).
- No roadmap node's `done_when` changed. Adoption of the `work` criterion waits for the real upper arm's work item (`work.upper-arm-cad` is `current` on the placeholder).
- Q5: the fixture stays open. `Upper Arm v0` is active again.

## My own mistakes

- I ran the fusion tests twice with an unfinished test edit; the first run left the fixture at `in_fixture_length` 299 mm and the next run refused to start ("not in its committed state"). I restored it by hand with the `restore` verb.
- A test I wrote for the unsaved path created a thread directory inside a `pytest.raises` block; replaced by the plain call.

## Finding: Fusion's stdout capture

During this task `print` inside any script raised `RecursionError` in Fusion's own wrapper (a script `print('hello')` failed). The result file written before the print still carried every result. I made the print in the generated script best-effort (`except RecursionError: pass`), so the file channel is the result and the printed line is a bonus. Both channels did not fail together (the file always arrived), so I did not stop; this is the second sighting of a stdout capture fault after memo 40. Recommended: restart Fusion when convenient; I have not tested whether that clears it.

## Questions for Joe

1. Save `Upper Arm v0` and pull again, or tell me to leave the sidecar at `unsaved_changes: true`?
2. The EJC at 4.03 mm from the skin: a brief item for the upper arm's distal registration?
3. Restart Fusion to clear the stdout fault?

## Tests

`fy test --quick`: 904 passed in 271 s. Full suite before the commits: 2027 passed, 2 failed, 3 skipped in 1068 s; the failures were the known stale `test_gait_extract` envelope test (deselected before, left alone, not fixed) and the suite-time doc test fixed above. Live Fusion tests: 28 passed. Commits `6487449` (Q2) and `0b4964c` (Q1, Q4).
