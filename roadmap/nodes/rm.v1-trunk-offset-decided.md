---
schema: roadmap-node/2
id: rm.v1-trunk-offset-decided
title: "Trunk stack offset settled and recorded: how the sim's stack and the mesh trunk are reconciled, in the zero pose and in the design stance"
short: Trunk offset
parent: rm.v1-volume-extracted
estimate_days: 0.5
tags: ["region:spine", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0040-trunk-stack-offset.md
---
ADR 0007 D11, memos 37 and 39. The model's zero-pose stack is 56.7 mm behind the hip line, 38.6 mm behind the mesh thorax's centre line at the CJC, and 52 mm behind the column that fits best (the corridor sweep's d = -5 mm); the design stance brings it to 30 mm. The skin margin at the stack axis at the TJC is -12.2 mm in the zero pose (outside the skin) and +10.3 mm in the design stance. Inputs: data/envelope/trunk_offsets.json and data/envelope/corridor_result.json.

The extraction does not change the sim, the sheet or the model. If the record moves the stack or the stance, that is model work in its own node, not part of this leaf. Waits on nothing; blocks the spine reservation and the lumbosacral concept.

The number 0040 is the next free record number when written; edit the path if records are written in a different order.
