---
schema: roadmap-node/2
id: rm.v1-upper-arm-char-file
title: "Upper-arm characterization file generated, schema-valid and stamped current in the thread"
short: UA char file
parent: rm.v1-upper-arm-characterized
blocked_by: [rm.v1-upper-arm-loads-computed, rm.v1-upper-arm-geometry-extracted, rm.v1-bridge-tooling]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: work
  work: work.upper-arm-characterization
  status: current
---
Delegate. Assembles the geometry and loads outputs into the one characterization file, validates it against the contract's schema, and stamps its work item against the addresses it consumed, so a changed snapshot, anchor or case marks it stale. The criterion evaluates `unknown`, with a criterion-unknown warning, until the work item exists; that is expected. Gates are in the brief.
