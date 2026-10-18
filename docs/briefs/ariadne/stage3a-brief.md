# Stage 3a brief (for Claude Code): the system model

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`. This brief belongs to the Ariadne track.

## Purpose

Ariadne traces every v1 part from the anthropometry sheet through simulated loads to a validated CAD model. Stage 3a builds the data layer that trace runs on: a small system model of Freyja's segments, joints, parts, interfaces, load cases and harness runs. The relations between them are stored once, on the record that owns them. Every per-item document (a **dossier**) is generated from the records, the model and the snapshot, never written by hand. A dependency graph says which pieces of manual or tool-assisted work went stale when an input changed, and exactly which values moved.

The test of the design is a reallocation. Moving an actuator from the thigh to the pelvis must be a one-line edit to one record, after which every consequence (which dossiers change, which budgets move, which work is now stale) is computed, and nothing unrelated changes by a single byte.

Stage 3b (the CAD bridge, the upper arm) writes into this model, so 3a comes first. 3a builds no bridge, computes no loads and adds no hardware to the real store.

Two parts, two checkpoints. Part A (T0 to T4) builds the contract, the library and a fixture, and ends at Checkpoint A. Part B (T5 to T8) renders, adds the CLI, seeds the real store and wires it into the hook and `fy state`, and ends at Checkpoint B. Do not start Part B until the prompt says so: Joe answers the Checkpoint A questions first, and may give the Ariadne track to Stage 2 work in between.

## Concepts

**Record.** One authored YAML file in `thread/records/`, the filename stem equal to the id, the kind given by the id prefix.

| Kind | Id form | What it is | Binds to |
|---|---|---|---|
| segment | `seg.<pre_processor segment name>`, e.g. `seg.upper_arm` | An anatomical body: a space with a mass target, inertia and, later, a volume envelope | Its model body or bodies, and through `pre_processor`'s naming the snapshot keys of that segment |
| joint | `jnt.<anatomical joint>`, e.g. `jnt.elbow` | A kinematic joint: its hinges and their ROM | Its model hinges and the ROM keys |
| part | `part.<assembly>.<n>` (CONVENTIONS section 3) | Hardware | A catalog entry, optionally |
| interface | `if.<slug>` | A contract between two parts, or a part and a segment: mechanical, electrical, thermal | |
| load case | `lc.<slug>` | A named design condition | A scenario or gait condition |
| harness run | `hn.<slug>` | A cable run | An ordered path of segments |
| work item | `work.<slug>` | Assisted or manual work whose output depends on inputs (a CAD model, an FEA study, a fabricated part) | The addresses it consumes |

Every record carries `schema: thread-record/1`, `id`, `kind`, `status` (`proposed`, `active` or `superseded`), `superseded_by` when superseded, and `purpose`: one or two sentences of intent that no relation captures. `notes` is optional. Proposed records are loaded, rendered and visibly flagged. Ids are permanent (CONVENTIONS section 3): a retired record is superseded, never deleted.

**Topology and values live in the model and the snapshot.** Records never restate them. A segment record names its body, a joint record its hinges. A joint's parent and child segments are derived from the model's body tree. Masses, lengths, centres of mass, inertias and ROM are read from `params/snapshot.csv` with their `sheet_source`. A typed copy of any of them in a record is a bug (CONVENTIONS section 1). The root free joint is not a joint record.

**Relations.** Each is stored once, on the record that owns it:

- part: `housed_in` (a segment); `acts_across` (a joint, optional); `reacts_into` (a segment, required with `acts_across`: where the reaction torque goes, which sets the load path); `harness` (harness run ids); `mass` as `{kg, source, reserved}`, where `reserved: true` means a claim with no hardware yet; `category` (free text); `catalog` (a path, optional); `sides` for a bilateral part.
- interface: `between` (exactly two ids, each a part or a segment); `carries_cut_of` (a joint, optional: the joint whose cut wrench passes through it); `mechanical`, `electrical` and `thermal`, each `{status: open | defined, notes}`.
- harness run: `path` (ordered segment ids); `carries` (free text).
- load case: `source` as `{scenario: <name>}` or `{gait_spec: <name>, condition: <text>}`; `independent_source_required` (a boolean: true means simulation alone may not size from this case, as for fall impact).
- work item: `of` (the owner's id); `mode` (`assisted` or `manual`); `consumes` (a list of addresses); `output` (a repo path, optional).

Inverse relations are derived, never authored: what a segment houses, which harness runs cross it, which parts act across a joint, which interfaces touch a record, which work items consume it. The home of a decision-to-record link is the decision record's `links:` front matter (CONVENTIONS section 8). A record never lists its decisions.

**Bilateral.** `pre_processor.BILATERAL` is the authority. A bilateral segment, joint or part is one record with `sides: [left, right]`, checked against `BILATERAL`. Values are read from the right side, since `pre_processor` mirrors the left. A bilateral part claims mass on each side's segment.

**Address.** `<source>#<pointer>`, where the pointer is a JSON pointer (RFC 6901). An empty pointer means the whole source. Sources:

- `snapshot`, with pointer `/<placeholder>`. The value is the string exactly as written in `snapshot.csv`.
- A record id of any kind above, or a `req.` id resolving to `requirements/<id>.yaml`.
- The repo-relative path of a tracked JSON or YAML file.

An address into one of the thread's own generated outputs resolves against a fresh in-memory build, never the file on disk. In every generated JSON value the banner keys `generated_by` and `inputs` are excluded before hashing. The hash of an address is the sha256 of the canonical JSON of its value (sorted keys, no whitespace, non-ASCII kept), as 12 hex. Examples: `part.hip.m2#/housed_in`, `snapshot#/upper_arm_right_mass`, `thread/derived/seg.thigh.json#/houses`.

**Stamp.** An event record, like a run record (CONVENTIONS section 6), stored at `thread/stamps/<work id>/<YYYYMMDD-HHMM>.json`. It says that this work item's output was produced or checked against these values. It holds the consumed addresses with their hashes, and each value itself when its canonical JSON is at most 2 KB (otherwise null beside the hash). It also holds a note, `pinned` (a boolean) and `by` (who or what stamped it). It is written only by `fy thread stamp` and never edited. The newest stamp by name is the baseline.

**Work status.** Derived on every build, never stored:

| Status | Meaning |
|---|---|
| `unstamped` | No stamp yet. Normal for future work; no warning. |
| `current` | Every address in the baseline stamp hashes as it did when stamped. |
| `stale` | At least one differs and the baseline is not pinned: rework. |
| `drifted` | At least one differs and the baseline is pinned: a disposition for Joe (accept by re-stamping, or open a change). |
| `unknown` | An address in the baseline no longer resolves. Warns `address-unresolved`. |
| `reverified` | Reserved for margin-aware re-verification in a later stage. Never computed. |

Status follows the addresses in the stamp, which are what the work actually consumed. If the record's `consumes` list no longer matches the baseline's, warn `consumes-changed`.

**Rework queue.** Every stale, drifted and unknown work item, each with the addresses that moved, showing the stamped value against the current one.

**Impact.** For a given address: the work items whose consumed addresses overlap it (one pointer is a prefix of the other), and the generated outputs whose content depends on its source. `--edit <address>=<YAML value>` applies the edit in memory, rebuilds in memory, and reports the outputs that would change and the work items that would change status. It writes nothing.

**Budget.** A comparison of what a segment provides against what the parts housed in it claim. 3a builds the mechanism and one budget, mass. A segment's target is `<segment>_mass` from the snapshot (the right side for a bilateral segment). Its claims are the `mass` of every active or proposed part housed in it. The whole body is compared against `target_mass` when the snapshot has it. An over-claim warns `budget-over`. Volume, heat and harness-channel budgets come later, on the same mechanism.

**Edge types.** A registry in the library, the one place each relationship is documented. Each type has a name, its from-kinds and to-kinds, whether it is authored or derived, and a docstring saying what the relation means and what is derived from it. `thread/graph.json` carries the registry, so the future viewer can show "how this relationship works" without anyone writing documentation per edge.

## Layout

| Path | Holds | Kind |
|---|---|---|
| `thread/records/` | one YAML file per record | authored |
| `thread/stamps/<work id>/` | stamp event records | event records, tracked |
| `thread/derived/<id>.json` | per record: everything derived about it (bindings resolved, values with sources, inverse relations, budgets, work statuses) | generated |
| `thread/dossiers/<id>.md` | per record: the human-readable view of the same | generated |
| `thread/graph.json` | nodes, edges, the edge-type registry, work statuses | generated |
| `thread/STATUS.md` | counts, rework queue with diffs, budgets, proposed records, problems | generated |
| `tools/thread/` | the library; `fy thread` calls it | authored |

Every generated file carries the CONVENTIONS section 4 banner with the snapshot hash (dossiers show snapshot values) and the hash of its other inputs.

## Out of scope

- **Stage 3b work.** The CAD bridge, sidecars and Fusion; cut wrenches and any load number; characterization files; the roadmap `done_when` type that reads a work item's status (it lands with the first real work item, in 3b).
- **Later budgets and methods.** Volume, heat and harness-channel budgets, the body envelope, and margin-aware re-verification.
- **Interfaces to other tracks.** Any viewer or UI (that is `rm.v1-thread-viewer`), the weekly report, and a GitHub workflow for the thread.
- **Real hardware records.** Real part, interface, harness and work records. They exist only in fixtures; the real store gets segments, joints and load cases (T7).
- **Inputs owned elsewhere.** Any edit to the model, the template, `pre_processor` or the sheet.
- **The roadmap.** Any edit under `roadmap/nodes/` or `tools/roadmap/`, except importing `tools/roadmap`'s reference search read-only.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, including rule 10 on coupled tasks.

- **Dependencies.** None new; `pyyaml` and `jsonschema` are present.
- **Reading the model.** Read it with `xml.etree` from `sim/models/freyja.xml`. `tools/thread/` must not import `mujoco`, so that it runs anywhere the roadmap does.
- **Segment names.** Use `pre_processor`'s own names (`EXPECTED_SEGMENTS`, `BILATERAL` and its key-building rules) by import, never as a copied list. If they cannot be imported without side effects, stop and report.
- **Determinism.** Sorted keys and ids, LF endings, repo-relative paths, no timestamps anywhere except a stamp's id.
- **Conflicts.** Where this brief and `CONVENTIONS.md` disagree on anything not listed under Amendments, `CONVENTIONS.md` wins and you report it.
- **New tests' cost.** Keep the new tests under about 20 s of the full suite's time, and report what they add.

Stop and ask before:
- adding a record kind, relation or address source not in this brief;
- changing the address grammar or the hashing rule;
- making any check a gate;
- creating any record as `active`, other than the seeded segments and joints of T7;
- stamping any real work item.

## Amendments to CONVENTIONS (land with T1)

1. **Section 2.** Add a `thread/` row (mixed: records authored; stamps are event records, tracked; `derived/`, `dossiers/`, `graph.json` and `STATUS.md` generated) and a `tools/thread/` row (authored library).
2. **Section 3.** Add id rows for `seg.`, `jnt.`, `if.`, `lc.`, `hn.` and `work.`, and the address grammar in one sentence. Add a **Thread terms** paragraph beside Track terms and Roadmap terms, defining: record, binding, relation, address, work item, stamp, pinned, the six work statuses, rework queue, impact and budget.
3. **Section 6.** Stamps are event records: the stamp id encodes the time, and nothing else in a stamp is time-dependent.
4. **Section 8.** Add the record format, with one short example per kind, and the stamp format.
5. **Section 9.** Claude Code creates thread records only as `proposed`, never sets `active`, and never stamps a manual work item unless the prompt tells it to.

## Part A

**T0. Baseline and inventory.** Run `fy test`. Then inventory:

- `pre_processor`'s segment names and `BILATERAL`;
- every body and hinge in `freyja.xml`, with each one's parent body;
- the snapshot keys grouped by the segment or joint they belong to under `pre_processor`'s naming, plus the keys nothing claims and any key two records would both claim;
- the scenario files and gait specs, and the scenario classes `sim/runs/ENVELOPE.md` lists as covered.

From that, propose the real record set: one segment record per segment and one joint record per anatomical joint, with every hinge mapped to exactly one joint. State the rule that derives side-specific body and hinge names from one binding. Nothing is committed in T0; the inventory goes into the Checkpoint A memo.

Anything that does not fit one record cleanly becomes a numbered question for Joe at Checkpoint A, not a guess. Examples: a body that is no segment; a hinge that belongs to no anatomical joint; a fixed body pair such as the trunk segments above the lumbosacral joint; bilateral names that follow no single rule. Part A continues on fixtures regardless.

**T1. Contract.** Write three schemas in `docs/schemas/`:

- `thread-record-1.schema.json`: one schema, with a branch per kind selected by `kind`, so there is a single validator.
- `thread-stamp-1.schema.json`.
- `thread-graph-1.schema.json`.

Apply the amendments in the same commit. Tests: each schema accepts one valid example per kind, and rejects one example of each schema-level error.

**T2. Library.** In `tools/thread/`: load, validate, bind, resolve addresses, derive inverse relations and budgets, derive work status, compute impact and the in-memory what-if. Errors stop generation; warnings are listed in the outputs.

Errors:
- id and filename stem differ;
- duplicate id;
- schema error;
- a reference that does not resolve;
- a reference to the wrong kind (`housed_in` naming a joint);
- a `superseded_by` that does not resolve or points at a superseded record;
- a binding to a body or hinge the model lacks;
- a body or hinge bound twice;
- a snapshot key bound to two records;
- `sides` that disagree with `BILATERAL`;
- a stamp for an unknown work item;
- a stamp that fails its schema.

Warnings:
- `address-unresolved`;
- `consumes-changed`;
- `budget-over`;
- an active record referencing a proposed or superseded one;
- `unbound-body` and `unbound-hinge` (a body or hinge with no record).

Commit one hand-authored invalid fixture per error class, each containing exactly that error, as the roadmap's are. A tiny hand-written model (a few bodies and hinges) is fine for unit tests. Tests: every error and warning; status derivation for each status; address resolution for each source kind, including the empty pointer and the banner-key exclusion; prefix overlap in impact.

**T3. Fixture.** Write a deterministic, seeded generator, `fy thread fixture --out DIR [--seed N]`. It writes a repo-shaped root holding:

- copies of the tracked `freyja.xml` and `snapshot.csv`;
- segment and joint records covering every body and hinge;
- synthetic parts, interfaces, harness runs, load cases, work items, stamps and decision records.

The fixture must include:
- every work status except `reverified`;
- a bilateral part;
- a pinned stamp;
- a decision record whose `links` name a part;
- a harness run crossing three segments;
- a part housed in each of at least four segments.

It writes the status it intended for each work item to an intent file, and a test requires that derived equals intended. Fixtures are generated into temporary directories and never committed.

**T4. The reallocation acceptance test.** In a fixture built for it:

- `part.hip.m1` is housed in the pelvis, acts across the hip and reacts into the pelvis.
- `part.hip.m2` is housed in the thigh, acts across the hip and reacts into the thigh.
- `hn.leg-power` runs pelvis to thigh to shank.
- Work items consume, among other things, the thigh's and the pelvis's `houses`, `part.hip.m2#/housed_in`, the pelvis mass budget (one of these is pinned), and only shank facts.
- The masses are chosen so that moving M2 overfills the pelvis budget.

The test then runs this sequence:

1. Build, and stamp every work item.
2. Edit M2's `housed_in` and `reacts_into` to `seg.pelvis`, and rebuild.

After the rebuild it asserts:

- The set of generated files that changed is exactly the expected set, stated explicitly in the test. It includes M2's, the thigh's and the pelvis's derived and dossier files, `graph.json` and `STATUS.md`, plus any others the test names with a reason. Every other generated file is byte-identical, the shank's among them.
- Work items consuming the moved facts are `stale`, and their diffs name each moved address with both values. The pinned one is `drifted`. The shank-only item stays `current`.
- The thigh's claimed mass falls by M2's mass and the pelvis's rises by it, and `budget-over` fires for the pelvis.

Two further checks on the same fixture:

- Before the edit, `fy thread impact --edit part.hip.m2#/housed_in=seg.pelvis` (with the matching `reacts_into` edit) reports the same changed outputs and the same status changes as the real edit, and leaves the root byte-identical.
- Reverting the edit returns every status to `current`, and every output to bytes identical to the first build.

Two builds from the same inputs are byte-identical.

**Checkpoint A.** Write the memo per `CLAUDE.md` rule 6, numbered one above the highest in `docs/memos/`. Include:

- what was built;
- the T0 inventory and the proposed real record set, with its numbered questions;
- the acceptance test's result;
- timings (a fixture build, an impact what-if);
- the tests added and their runtime;
- every finding.

Run `fy state` and stop.

## Part B

**T5. Render.** Produce the four kinds of generated output.

`thread/derived/<id>.json` and `thread/dossiers/<id>.md` are written for every record. Dossier sections, in order:

1. **Header.** Id, kind, status and purpose, with the proposed or superseded flag.
2. **Binding and values.** Each bound snapshot key with its value and `sheet_source`, read from the snapshot, so the dossier is its own provenance table.
3. **Relations.** Authored and derived, each linking to the other record's dossier with a relative link.
4. **Budgets.**
5. **Work.** Work items owned by the record or consuming any address in it, with status.
6. **Decisions.** Decisions whose `links` name it, with their status.
7. **References.** From `tools/roadmap`'s reference search over `roadmap/nodes/`, `docs/memos/`, `notebook/` and `log/`, files only. Commit messages are left out, because a generated file must not depend on git history.
8. **Neighbourhood.** A one-hop Mermaid graph, capped at 25 nodes, falling back to a list above the cap.

`thread/graph.json` is validated against its schema. `thread/STATUS.md` opens with a one-line summary of counts, followed by the rework queue with diffs, the budgets table, the proposed records and the problems.

Tests:
- each section for each kind on the fixture;
- every link in every dossier resolves;
- the Mermaid cap;
- banners;
- determinism.

**T6. CLI.** Add these commands, each taking `--root DIR` (repo root by default). `tools/fy` gets a thin wrapper only.

| Command | Does |
|---|---|
| `fy thread validate` | Errors and warnings; exit 1 on errors. |
| `fy thread build` | Writes the generated outputs; on errors writes nothing and exits 1. |
| `fy thread show <query>` | One record's derived view in the terminal, using the roadmap's query rules. |
| `fy thread impact <address> [--edit <address>=<value> ...]` | Impact, or the what-if. Writes nothing. |
| `fy thread why <work id>` | Status and, for each moved address, stamped against current value. |
| `fy thread stamp <work id> [--note TEXT] [--pin] [--by NAME]` | Writes a stamp and prints what it consumed. Refuses when the work item is unknown, any address fails to resolve, or the thread has errors. |
| `fy thread fixture --out DIR [--seed N]` | T3's generator. |

Tests: each command on the fixture, including each refusal of `stamp`.

**T7. Seed the real store.** Following the T0 inventory as Joe answered it at Checkpoint A, write:

- one segment record per segment and one joint record per anatomical joint, `status: active`, each with a one-sentence purpose saying what the segment or joint is anatomically, and nothing about design (what a segment houses is derived later);
- one load-case record per scenario class that `sim/runs/ENVELOPE.md` treats as a load source, `status: proposed`, each with `independent_source_required` set and its reason in `notes`.

No part, interface, harness or work records.

Add the advisory check `check.thread.coverage` in a new `checks/thread_checks.py`. It requires that every model body maps to exactly one segment record and every hinge to exactly one joint record. Give it a mutation test: removing a record, or adding a body to a copy of the model, makes it fail. `fy check` and pytest run it; the model build gate does not (the gate checks the model, and the thread has its own build).

Run `fy thread build`, and commit the records and outputs.

**T8. Integration.**

- **Hook.** `.githooks/pre-commit` runs `fy thread build` after the roadmap build and stages the thread's generated outputs. A thread error blocks the commit with the error text, as a roadmap error does. Test it in a throwaway repository, as the roadmap hook test does.
- **State.** `fy state` gains one line after the Roadmap line: `Thread: <n> records | <n> work items | rework <n> | errors <n>`.

**Checkpoint B.** Write the memo per `CLAUDE.md` rule 6. Include:

- what changed;
- the real store's counts;
- timings (a real-store build, the hook's added time per commit);
- the lines you propose for the `CLAUDE.md` command list, and the glossary terms for `docs/OVERVIEW.md` (you edit neither file);
- every finding;
- the questions for Joe.

Run `fy state` and stop.

## Performance

A warm `fy thread build` on the real store takes under 2 s. An impact what-if on the T4 fixture takes under 3 s. The hook adds under 2 s per commit. Report measured times either way.

## Decisions this brief makes (Joe approves them by committing it)

1. Flat YAML records in `thread/records/`, with the kind given by the id prefix, as the roadmap keeps flat node files.
2. Topology and values come from the model and the snapshot; records carry bindings, relations and purpose only.
3. Address = source + JSON pointer. Hashes are taken over canonical JSON, and snapshot values are hashed as their written strings.
4. Stamps are event records and status is derived. `reverified` is reserved.
5. Segment and joint records are seeded `active`, since they mirror the model and a check proves it. Load cases are seeded `proposed`.
6. `check.thread.coverage` starts advisory.
7. The pre-commit hook builds the thread as it builds the roadmap.

## Prerequisites for Joe

- Commit this brief and point the "Current Ariadne brief" line in `CLAUDE.md` at it. Committing it approves the amendments and the decisions above.
- Answer the Checkpoint A questions before Part B starts.
