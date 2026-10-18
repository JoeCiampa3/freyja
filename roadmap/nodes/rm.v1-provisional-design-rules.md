---
schema: roadmap-node/2
id: rm.v1-provisional-design-rules
title: "Provisional design rules recorded from the process plan: nominal tolerances, bore and fit conventions, and which features wait for the qualified mill"
short: Prov. rules
parent: rm.v1-workshop
blocked_by: [rm.v1-process-plan]
estimate_days: 1.0
tags: ["phase:spec"]
done_when:
  type: decision
  record: decisions/0024-provisional-design-rules.md
---
Gates design only: rm.v1-upper-arm-connectors and rm.v1-upper-arm-designed directly, every other design through rm.v1-upper-arm-validated. The values are Joe's and live in the record. rm.v1-design-rules confirms them against the qualified DMC2 before anything is cut, and it confirms or amends this record rather than superseding it: a superseded record would reopen this leaf and block every design made under it.
