# fy

Thin command-line glue: wrappers only, no domain logic. It finds the repo root by walking up to
`CONVENTIONS.md`, so it works from any directory.

```
fy build [options]            build freyja.xml and params/snapshot.* (pre_processor options: --dry-run, --xlsx FILE ...)
fy watch [options]            rebuild whenever the sheet or template changes
fy test [pytest options]      pytest over tests/ and checks/
fy check [--tier gate|advisory]   the model checks on the committed model and snapshot; exit 1 on a gate failure
```

Run it as `python tools/fy <command>`, or put `tools\fy` on your PATH and use `fy <command>` (Windows,
`fy.cmd` picks the repo `.venv` when it exists).
