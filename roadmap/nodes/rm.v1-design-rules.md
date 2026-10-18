---
schema: roadmap-node/2
id: rm.v1-design-rules
title: "In-house design rules confirmed against the qualified capability: tolerances the DMC2 holds, how round features are made on the mill, setup and workholding limits, and what is bought instead"
short: Rules confirmed
parent: rm.v1-workshop
blocked_by: [rm.v1-dmc2-qualified, rm.v1-process-plan, rm.v1-provisional-design-rules]
estimate_days: 1.0
tags: ["phase:spec"]
done_when:
  type: decision
  record: decisions/0023-design-rules.md
---
Written from measured capability, not the machine's specification. It confirms or amends each rule in the provisional record (0024) without superseding it. It gates fabrication and press-fit qualification, not design: design waits on rm.v1-provisional-design-rules. Any design that used a rule this record changes is rechecked before it is cut.
