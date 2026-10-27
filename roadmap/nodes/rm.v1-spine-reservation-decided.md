---
schema: roadmap-node/2
id: rm.v1-spine-reservation-decided
title: "V2 spine actuator volume reserved and recorded: which body holds the modules, where, and the density the rest of that body must carry"
short: Spine reserve
parent: rm.v1-volume-extracted
blocked_by: [rm.v1-trunk-offset-decided]
estimate_days: 0.5
tags: ["region:spine", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0041-spine-reservation.md
---
Memo 39 item 5, data/envelope/reservations.yaml and reservations_result.json. Three modules of 90 mm diameter and 81.5 mm length (1,555,442 mm3 against the 1.55e6 figure, +0.35%), 1.4 kg each, 5 mm clearance, vertical axes assumed, drivetrain not counted. Results: the abdomen holds none even at a skin margin of 0; the pelvis holds them at a 17.0 mm margin but the rest of it must then carry 1.717 kg/l inside its mass budget (1.862 kg/l without the modules); the thorax holds them at 13.5 mm and the rest carries 1.052 kg/l (1.188 without). A margin of at least the 5 mm design shell is feasible in the sense of ADR 0007 D4. The placement search depends on the trunk axis, hence the blocker.

Deferral trigger: if no body holds the modules with a density the rest can carry, fall back to a simpler v2 spine and add hardware in v2, and say so in the record. Blocks the pelvis and torso structures, the harness and the battery.

The number 0041 is the next free record number when written; edit the path if records are written in a different order.
