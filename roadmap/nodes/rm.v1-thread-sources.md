---
schema: roadmap-node/2
id: rm.v1-thread-sources
title: "Load cases carry checked evidence (an accepted decision clause, a verified literature row or an admitted test record), and the thread refuses to stamp active work that consumes a flagged load case without it"
short: Thread sources
parent: rm.v1-ariadne-system-model
blocked_by: [rm.v1-fall-design-basis]
estimate_days: 2.0
tags: ["stage3"]
done_when:
  type: manual
signed_off: true
---
Brief: `docs/briefs/ariadne/thread-sources-brief.md`. A schema bump (thread-record/2) and one rule. Evidence on a load case is resolved and graded by the build from the cited source's own status, never from a grade typed into the record. Stamping is refused for an active work item that consumes a flagged case with no admissible evidence, and warned on every build for anything else. The rule sits in `build.write_stamp`, so `fy thread stamp` and `fy cad stamp` both enforce it. The bump also carries the energy-defined load-case form adr-0037 D1(a) specifies, so rm.v1-fall-load-cases needs no further bump.

Retitled 2026-10-31. The first title admitted literature or test sources only. adr-0037 sizes fall cases from the energy bound, a derivation inside the decision; the literature only calibrates, only a Verified row may lower a reservation, and no drop test exists. Under the old title no v1 fall case could have been sourced, and the rule would have refused all active work that consumed one. Test records count only against an admitted schema, and none is admitted yet. Estimate raised from 1.5 to 2.0 days for the energy-defined form and the migration.

Joe signs it off on the memo.
