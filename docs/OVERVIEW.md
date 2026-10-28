# Freyja: orientation for a reader with no prior context

Authored. Owner: Joe. Written 2026-10-11, updated 2026-10-18 (Stage 3a), for a Claude session that has never seen this project. Where this file and `CONVENTIONS.md` disagree, `CONVENTIONS.md` wins. This file describes what is stable; for where the repo is right now, read `docs/STATE.md` and the highest-numbered file in `docs/memos/`. Items marked **(confirm)** are my reading of Joe's intent and should be checked with him before anything depends on them.

## 1. What Freyja is

Freyja is a biomimetic humanoid android, 170 cm and 65 kg, built by one person (Joe) over a multi-decade horizon. The long-term aim is a machine that is hard to tell from a person. Version 1 is a reduced scope: facial actuators and actuated hands are deferred to v2, but their mass, volume and routing budgets are reserved now. The spine plan is not final: v1 builds a multi-DOF spine for articulation and locks it during gait, with the lumbosacral joint possibly left unlocked and actuated for basic balance, and a fully rigid torso as the fallback if control complexity balloons. Stage 2's trunk modes bracket exactly these options (section 7).

Two things shape every engineering decision:

- **The aesthetic envelope is a hard constraint.** Slim legs, specific pelvic dimensions and a 0.68 waist-to-hip ratio are design invariants, more foundational than any single subsystem choice. Mechanisms must fit inside the form; they do not get to reshape it.
- **Locomotion target:** brisk indoor walking, 1.4 to 1.6 m/s. Running is out of scope. The design envelope also covers sit-to-stand and stair ascent and descent; excess range of motion beyond these is for articulation only. v1's acceptance trial walks at 0.5 m/s, but the hardware is sized to the 1.4 to 1.6 m/s target so that v1 does not underbuild the structure.

Joe is a physicist by training and is learning CAD, machining and controls through this project. He is rigorous, checks claims, and has caught real errors (cable tension physics, strain estimates, which load case governs the ankle). Give numbers and sources, say how sure you are, and expect to be verified.

## 2. What this repository is for

The repo is meant to be a **digital thread**: one set of authoritative numbers, with everything else derived from them by code and nothing transcribed by hand.

```
Freyja Anthropometric Reference (Google Sheet, ground truth)
   -> sim/scripts/pre_processor.py   (the only code that reads the live sheet)
   -> params/snapshot.csv + snapshot.meta.json   and   sim/models/freyja.xml  (generated)
   -> checks/            (gate the build; named, executable, each with a mutation test)
   -> sim/ scenarios     -> sim/runs/*/summary.json -> DIGEST.md, ENVELOPE.md
   -> sim/ gait          -> sim/gait/<id>/GAIT.md      (Stage 2)
   -> thread/            (system model: one record per segment, joint, load case and, later, part,
                          interface and work item; generated dossiers; stale work)   (Stage 3a)
   -> [planned] CAD parameters (Stage 3b bridge), actuator sizing, FEA
```

Three goals, in order of maturity:

1. **Documented, traceable, rigorous.** `CONVENTIONS.md` fixes naming, IDs, file kinds and checks so that a file or variable named today is unambiguous in ten years. Every number has a citation or a script that reproduces it.
2. **A pipeline that feeds itself.** A value changed in the sheet propagates to the model, the sims, the load envelopes and, later, CAD and FEA, with no retyping. Sim results become actuator and part requirements.
3. **More agency for Claude.** Joe used to be the copy-paste bridge between a chat assistant and his tools. The intended workflow now: a brief is written, committed under `docs/briefs/`, and Claude Code executes it using everything in the repo (run sims, tests, benchmarks) with little supervision, then reports in a memo. The system model in `thread/` (Stage 3a) is the data layer for the next step: every segment, joint and load case is a record, relations are stored once, and every per-record document (a dossier) is generated, so moving a part between segments is a one-line edit whose consequences are computed. Planned extension: per part, the pipeline adds loads from sim and spatial limits from CAD to what the model derives, Claude reads it and hands back CAD briefs and parameters, and the Stage 3b bridge records what each CAD export consumed so a changed input marks it stale. Fusion 360 has a scripting API (`cad/fusion_addin/`, `cad/sidecars/*.json` in the layout); whether CAD and FEA can be automated beyond parameters and export is an open question, not an assumption.

The simulation-first build order: **simulate to derive loads and envelopes, then select actuators, then build CAD parametrically around the results.** The earlier habit of working the hardware passively is deliberately replaced by this.

## 3. How work flows, and who does what

- **Joe** owns every decision and every check that needs a human. He edits the sheet, `local_config.json`, credentials and `CONVENTIONS.md` rulings.
- **A Claude chat session (the planning and review side)** discusses, analyses reports and writes briefs. It sees the repo only through a Project copy that Joe refreshes by hand, so it can be stale. `docs/STATE.md` exists so it can tell.
- **Claude Code (you, probably)** executes a brief: tests first, one commit per task, evidence in the commit message, a memo at each checkpoint.

The loop: Joe and the planning session write `docs/briefs/<track>/<name>-brief.md`; Joe points Code at it; Code works and stops at the stated checkpoint; Code writes `docs/memos/memoN-<slug>.md` opening with the STATE line from `fy state`; Joe and the planning session review; the brief is revised and overwritten; repeat. Joe should never have to paste a report into chat. Put it in the repo.

Different Claude accounts may do this work. Nothing carries between sessions except what is in the repo. If something you need is not in a file, it is not known: check the memos and `notebook/`, then ask Joe.

## 4. The principles that matter most

These are in `CONVENTIONS.md` section 1; the ones that bite in practice:

- **One home per quantity.** A hand-typed copy of a value that lives elsewhere is a bug even when it is currently right.
- **Authored or generated, never both.** Generated files carry a banner and are never edited by hand.
- **Downstream reads the snapshot, not the sheet.** Any result must be reproducible from a commit.
- **Checks can fail, and a failure is a finding.** If a check fails on the current model, report the measured number and stop. Do not adjust a tolerance or a geometry value to make it pass.
- **No circular validation.** A model is never validated against the data it was built from. Method A in Stage 2 reproducing the dataset's own joint moments verifies the pipeline; it does not validate Freyja's loads.
- **Determinism.** Same inputs, byte-identical output. Time lives in the log, not in artifacts.

## 5. Repository map

Full table: `CONVENTIONS.md` section 2. Where you will spend time:

| Path | What |
|---|---|
| `CONVENTIONS.md` | the contract |
| `CLAUDE.md` | session-start instructions for Code |
| `docs/briefs/` | task specs for Code; Joe overwrites them between rounds |
| `docs/memos/` | numbered checkpoint reports; the project's narrative |
| `docs/STATE.md` | generated snapshot of the repo (commit, tests, checks, waivers); `fy state` |
| `docs/schemas/` | JSON Schemas for run, sweep, gait, roadmap and thread records |
| `params/` | generated parameter snapshot |
| `sim/models/` | `freyja_template.xml` (authored), `freyja.xml` (generated) |
| `sim/scripts/` | pre-processor, runner, solvers, gait pipeline |
| `sim/scenarios/` | authored scenario and sweep specs; `scenarios/gait/` for the gait spec and dataset mapping |
| `sim/runs/`, `sim/sweeps/`, `sim/gait/` | records; `DIGEST.md`, `ENVELOPE.md` and `GAIT.md` are what to read |
| `thread/` | the system model: authored records in `thread/records/`, stamps in `thread/stamps/`; generated dossiers, derived JSON, `graph.json` and `STATUS.md` (read `STATUS.md` and the dossiers) |
| `roadmap/` | the v1 roadmap: authored node files in `roadmap/nodes/`, the rest generated; `fy roadmap` |
| `checks/` | executable checks, joint polarity file, waivers |
| `analysis/` | scripts that produce numbers entering the sheet or the records |
| `data/camargo2021/` | the open gait dataset (CC BY 4.0): manifest, audit, attribution; raw files stay outside the repo |
| `tools/fy/` | the CLI; wrappers only |
| `notebook/` | dated notes with `origin: me | source | claude` |
| `decisions/` | decision records (`adr-NNNN`) with a "rejected options" section |
| `cad/` | Fusion add-in and sidecars (early) |

`fy` is run as `python tools/fy <command>` (on Windows `tools/fy/fy.cmd` uses the repo `.venv` when present). Commands: `build`, `watch`, `test`, `check`, `run`, `sweep`, `gait`, `view`, `runs list|show|compare|digest|envelope`, `roadmap`, `thread`, `state`.

## 6. How we got here (stable history)

- **Stage 0** (memo 2): the sheet-to-MJCF pipeline made reproducible, tracked and checked; the snapshot and the gate checks; the `fy` CLI.
- **Stage 1, 1b, 1c** (memo 3): every sim run leaves a stamped machine-readable record; a standing pose that actually balances; a gain-independent static solve; posture sweeps; the digest and the envelope.
- **Stage 2** (memos 4 to 6, `docs/briefs/stage2-brief.md`, closed): walking loads at 1.4 and 1.6 m/s on Freyja's mass distribution, driven by measured human kinematics from the Camargo et al. 2021 dataset, computed three ways (B Freyja's own dynamics, A measured ground force, H a hybrid) and compared with the dataset's own joint moments. Only A with the filtered force meets the agreement band, so the envelope's gait rows rest on it, flagged provisional. B's failure stands as a finding whose cause is unattributed. The brief and the memos are the record of what worked and what did not; read them rather than trusting any summary here.
- **Stage 2b** (`docs/briefs/stage2b-brief.md`): two checks on numbers from memo 6 that are not yet believed (hip extension, the ankle torque), a tracked gait extract so the envelope reproduces from a clean clone, and wording clean-up.
- **Stage 3a** (memos 18 and 19, `docs/briefs/ariadne/stage3a-brief.md`): the system model in `thread/`. Records for the 10 segments and 9 joints, each bound to its model bodies or hinges and read from the snapshot, plus proposed load cases; a dependency graph that marks stamped work stale when an input it consumed changes; mass budgets per segment; generated dossiers, rebuilt by the pre-commit hook. Proven on a fixture in which moving a hip actuator from the thigh to the pelvis changes exactly the outputs that depend on it.

## 7. Hard-won lessons

Each of these cost real time. Do not relearn them.

- **Never run `mj_inverse` on a prescribed trajectory with contacts on.** The contact force it returns is a soft-constraint artefact, not the force that balances the motion. Disable contacts and joint limits for inverse dynamics and supply the ground wrench explicitly.
- **Joint torque is about the model's own hinge axes** (the decoupled hip). It is not actuator torque for the coupled hip differential; the mapping to actuator space happens later.
- **Mirrored joints have flipped axes.** A mirror-symmetric load gives the same scalar torque on both sides; only the world-frame vectors are mirror images.
- **Dataset names are not model names.** In the Camargo lab frame the ground z axis is the walking direction, so `pelvis_tilt` is roll, `pelvis_list` is sagittal pitch, `pelvis_rotation` is yaw. Model-side code uses anatomical names; dataset names appear only in ingestion and `camargo_mapping.yaml`.
- **Reference the root to the hip-centre midpoint, not the pelvis origin.** Freyja's pelvis origin is the lumbosacral joint; her hip centres sit about 57 mm ahead of it and 97.5 mm below. The dataset's sit behind its pelvis origin. Mixing the two silently wrecks the sagittal moments.
- **The foot is a rigid, flat, toeless box.** It cannot represent late-stance push-off, so the late-stance failures of the contact-polygon test are a limit of the foot model (`decisions/0001-toe-joint.md`). That is separate from B's unexplained 66 mm backward CoP offset, which also appears with the heel on the ground.
- **Trunk modes bracket the spine options.** `rigid` is a locked spine; `counter_rotate` is an actuated lumbosacral roll and yaw cancelling the pelvis's by feed-forward; `first_harmonic` is a human-like reference from the trunk IMU (diagnostic only). Joints above the pelvis depend only on kinematics and the mode, not on the method. Balance feedback through the trunk is the controller project's. No mode is the v1 headline until Joe decides.
- **The dataset's foot is toeless and B's failure is unattributed.** `mtp_angle` is exactly 0 in the dataset, so it carries no toe loads, and a force-plate proxy would be dominated by an assumed joint position. B's 66 mm backward CoP offset is explained only in part (masses about 18 mm, trunk placement none); do not attribute it to Freyja's mass distribution, foot or the controller project.
- **Freyja's mass data is human-based for now.** Agreement between methods is a soft check on the pipeline; once CAD masses replace the anthropometry, disagreement will be legitimate.
- **Units:** SI in the snapshot and the records (the sheet gives some lengths in mm). Torques N m, speeds rad/s, powers W.
- **Missing data are flagged, not invented.** Seven sheet range-of-motion values are still missing, so those joints are unlimited and every build warns. Do not make up a limit.

## 8. How Joe wants to be talked to

Blunt, technically dense, peer to peer. Findings first, with the measured number and an honest error bar. If something you did was wrong, say so plainly in the memo and show the fix; `memo5` is the model for this. Do not soften a result, bury a contradiction of the brief, or re-argue a recommendation he has declined. If a brief's reasoning is contradicted by what you measure, report both and stop; do not quietly follow either.

## 9. Glossary

- **BSIP / anthropometry:** body segment inertial parameters (masses, centres of mass, inertias); here Dumas 2007 female, scaled to 170 cm and 65 kg.
- **MJCF:** MuJoCo's XML model format. **ISB:** the International Society of Biomechanics joint conventions (Wu 2002, 2005).
- **CoM, CoP, ZMP:** centre of mass; centre of pressure on the ground; zero-moment point (the CoP for a rigid body on flat ground).
- **GRF:** ground reaction force. **Inverse dynamics:** the joint torques that produce a prescribed motion.
- **ROM:** range of motion. **HAT:** head, arms and trunk; about two thirds of body mass rides above the hips.
- **QDD:** quasi-direct-drive actuator. The hip uses a pair of AKH70 modules in a differential; the knee a frameless motor with a ballscrew.
- **Snapshot:** the parameter set a model was built from, hashed. **Envelope:** the worst-case load per joint across scenarios.
- **Gate / advisory check, waiver:** a gate check blocks a build; an advisory prints; a waiver records a known deviation and takes effect only when `confirmed: true`.
- **rigid / counter_rotate / first_harmonic:** the three trunk modes of Stage 2, modelling a locked spine, an actuated lumbosacral roll and yaw, and a human-like reference.
- **Method A / B / H:** the three Stage 2 ways of computing gait joint loads (measured force at measured CoP; Freyja's own dynamics with a solved CoP; Freyja's force at the measured CoP).
- **Brief, memo, STATE, ADR:** a task spec for Code; a checkpoint report; the generated repo snapshot; a decision record.
- **Thread / system model:** the records of Freyja's segments, joints, parts, interfaces, load cases, harness runs and work items, with the relations between them stored once and everything else derived (`thread/`).
- **Record, binding:** one authored YAML file; a binding ties a segment to its model body and a joint to its hinges and ROM keys.
- **Load case:** a named design condition (`lc.`), bound to the scenario or gait condition that computes it. `independent_source_required: true` marks a case whose simulation physics is itself untrusted (impacts and other contact transients), so it cannot size anything on simulation alone.
- **Address:** `<source>#<JSON pointer>`; its hash is 12 hex of the canonical JSON of its value.
- **Work item, stamp, pinned:** assisted or manual work whose output depends on addresses; a stamp records the hashes it was made against; a pinned stamp makes a difference `drifted` instead of `stale`.
- **Work status:** `unstamped`, `current`, `stale`, `drifted`, `unknown` (`reverified` is reserved).
- **Bound document, binding, sidecar:** a Fusion design with a binding; `cad/bindings/<part>.yaml`, the document's name and id, the side and the parameter list; `cad/sidecars/<part>.json`, the one home of CAD-derived quantities (generated).
- **Parameter classes:** `in_` inherited from a thread address, never edited in Fusion; `dv_` design, authored in Fusion; `dr_` derived.
- **Push / pull / drift:** the repo's values out to Fusion by expression (a clean document is then saved); Fusion's parameters, mass properties and meshes back; an inherited parameter that no longer equals its address.
- **CAD frame, canonical mesh:** right-side ISB, mm, converted to the model body frame on pull; the STL the bridge writes, with a hash independent of Fusion's ordering.
- **Chord bound / guarantee:** the achieved worst-case chord error of the tessellation, and whether it covers every face.
- **Rework queue, impact, budget, dossier:** the stale, drifted and unknown work items with the values that moved; what an address touches; a segment's provision against its claims (mass first); the generated per-record document.

## 10. Your first session

1. Read `CLAUDE.md`, `CONVENTIONS.md`, `docs/STATE.md`, this file, then the newest memo and the current brief.
2. `git status`, then `python tools/fy test` and `python tools/fy check`; compare `git rev-parse HEAD` with the base commit in `STATE.md`.
3. Raw dataset files live outside the repo, found through `CAMARGO_RAW_DIR` or a `camargo_raw_dir` key in `sim/local_config.json`. Never edit that file; ask Joe. The sheet needs credentials you may not have; `python tools/fy build --xlsx FILE` works offline.
4. Do what the brief says, in its order, and stop where it says stop.
