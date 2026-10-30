# Freyja

Freyja is a solo, multi-decade project to design and build a biomimetic humanoid android, 170 cm and 65 kg. This repository is the engineering record: the parametric model, the simulations, the decisions and the tooling that connects them. 

Freyja is currently in the design and simulation stage.

## v1

v1 is deliberately less ambitious than the long-term aim. Its goal, from the [roadmap root](roadmap/nodes/rm.freyja-v1.md):

> Freyja v1 stands, balances and walks 10 m indoors untethered at 0.5 m/s

- **Acceptance:** a trial against a protocol recorded before the attempt, with power and compute onboard. Trials run with a safety catch rig fitted ([ADR 0036](decisions/0036-fall-intent.md)).
- **Sizing:** the acceptance test needs only slow walking, but actuators and structure are sized for walking at 1.4 to 1.6 m/s, sit-to-stand and stairs. Every v1 interface is final, so later gains are control work, not redesign.
- **Deferred to v2:** Actuated hands, with their mass, volume and routing reserved now. Unlocked spine during gait. Running is out of scope. 
- **Open:** how much of the spine is actuated in v1 is not yet decided.
- **Hard constraint:** the body's outer form. Mechanisms must fit inside it and do not get to reshape it.

## Status

The sheet-to-model pipeline, load simulations, body envelope, system model and CAD bridge exist and run. Load results are provisional and are not yet a complete sizing basis; the model's masses are still human anthropometry, not hardware. Live state:

- [roadmap/STATUS.md](roadmap/STATUS.md): counts and what is workable now. `python tools/fy roadmap serve` opens the local viewer.
- [docs/memos/](docs/memos/): numbered checkpoint reports. The highest number is the latest.
- [sim/runs/ENVELOPE.md](sim/runs/ENVELOPE.md): worst-case load per joint, with what it does not cover.

## Method

- **Phase-gated, part by part.** Work passes through spec, simulation, design, fabrication, bench and integration. Dependencies are explicit, and each roadmap leaf has a completion criterion, machine-evaluated wherever the evidence allows. The pipeline must be proven on one part, the upper arm, before other parts go through it.
- **Simulate before fabricating.** Derive loads and envelopes, select actuators, then build CAD parametrically around the results.
- **Every number carries provenance.** A value has one home and a citation or a script that reproduces it. Results are reproducible from a commit, and a model is never validated against the data it was built from.
- **Checks can fail.** Claims of correctness are named, executable checks, and each has a mutation test. A failure is a finding, never a tolerance to adjust.
- **Decisions are recorded.** ADRs in [decisions/](decisions/) include the rejected options and why each was rejected.
- **Briefs and memos.** Task specs are committed to [docs/briefs/](docs/briefs/). Claude Code executes them, and results come back as memos for human review. Decisions stay with the project owner.

## Ariadne, the digital thread

Ariadne is the pipeline that keeps one set of authoritative numbers and derives everything else by code. An anthropometric reference spreadsheet produces a hashed parameter snapshot and a generated MuJoCo model. Checks gate that model, and simulations turn it into load envelopes. The system model in `thread/` records segments, joints, parts and load cases, and marks stamped work stale when an input it consumed changes. A bridge carries parameters to Fusion and mass properties and meshes back. FEA is planned.

## Layout

| Path | Holds |
|---|---|
| `sim/` | model template and generated model, scenarios, controllers, solvers, run records |
| `params/` | generated parameter snapshot |
| `checks/` | executable model, run and thread checks; waivers |
| `thread/` | system model: authored records, stamps, generated dossiers |
| `roadmap/` | v1 roadmap: one file per node, generated status |
| `cad/` | Fusion bridge: add-in, bindings, sidecars, exports |
| `data/` | gait dataset metadata, body mesh, body-envelope results, reference literature |
| `analysis/` | scripts that produce numbers, and read-only diagnostics |
| `decisions/` | architecture decision records |
| `docs/` | overview, briefs, memos, schemas, generated state |
| `notebook/` | dated working notes |
| `log/` | project log |
| `tools/` | the `fy` CLI and its libraries, viewer, landmark picker |
| `tests/` | offline pytest suite |
| `requirements/`, `catalog/`, `fea/`, `reports/` | reserved; not populated yet |

## Build and run

Tested on Windows with Python 3.11. On Windows, clone with `git -c core.longpaths=true clone`, because some tracked file names are long.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run from the repo root:

```
python tools/fy test                # full offline suite, about 15 minutes
python tools/fy test --quick        # subset, about 4 minutes
python tools/fy check               # model checks on the committed model
python tools/fy run stand_static    # one simulation; writes a run record
python tools/fy runs digest         # rewrite sim/runs/DIGEST.md
python tools/fy runs envelope       # rewrite sim/runs/ENVELOPE.md
python tools/fy roadmap frontier    # what is workable now
python tools/fy thread show seg.thigh    # one record of the system model
```

Some commands need things that are not in the repo. `fy build` needs the source sheet (`--xlsx FILE` takes an exported workbook). `fy gait` needs the processed [Camargo et al. 2021](data/camargo2021/ATTRIBUTION.md) dataset (CC BY 4.0), and without it two tests in the full suite fail with a missing-file error. `fy cad` writes need Fusion with its MCP server.

## Further reading

- [docs/OVERVIEW.md](docs/OVERVIEW.md): project orientation and glossary
- [CONVENTIONS.md](CONVENTIONS.md): the contract for names, file kinds, schemas and checks
- [roadmap/README.md](roadmap/README.md): how the roadmap works and how v1 is structured
- [decisions/](decisions/): the ADRs
