---
schema: roadmap-node/2
id: rm.v1-hip-registration-decided
title: "Hip registration settled and recorded: the lateral target the pelvis and thigh bodies are registered to, and the hip-plane step between them"
short: Hip registration
parent: rm.v1-volume-extracted
estimate_days: 0.5
tags: ["region:pelvis", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0039-hip-registration.md
---
ADR 0007 D11, memo 39 item 6b. The mesh's hip joint centres are 75.6 mm from its midline and the sheet's are 92.43 mm, so in the model frames the pelvis and thigh bodies are 17 mm apart at the hip plane (the check's flag is 5 mm). data/envelope/hip_registration.json holds the report, including the pelvis and thigh volumes under the alternative shear target (the sheet's HJC lateral offset against the section centroid). The aesthetic invariants (pelvic dimensions, 0.68 waist-to-hip ratio) bound the choice.

The record states the target. If it changes the target, the pelvis and thigh ledgers are rebuilt and the closure rechecked against 0.5% in the same commit; if it keeps the target, the record says what the 17 mm costs the hip actuator housings. Blocks the thigh and pelvis structures.

The number 0039 is the next free record number when written; edit the path if records are written in a different order.
