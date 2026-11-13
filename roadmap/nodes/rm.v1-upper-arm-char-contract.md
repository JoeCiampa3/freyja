---
schema: roadmap-node/2
id: rm.v1-upper-arm-char-contract
title: "Upper-arm characterization file contract decided and recorded: what the file carries and how a fall case reaches the segment it strikes"
short: UA char contract
parent: rm.v1-upper-arm-characterized
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0045-upper-arm-characterization-contract.md
---
Settled in chat with Joe, 2026-11-13; the record writes these down and names the schema id (a segment-generic name is preferred, since every segment is wired as the upper arm is).

**Demand only.** The file carries what the world and the task impose: the static gravity sweep with payload, inertial loads from the minimum-jerk trajectories, and the fall cases. It carries nothing from the actuator (peak or stall torque, torque-speed curve, reflected inertia). The actuator-peak structural case enters at requirements and validation once the actuator is chosen. rm.v1-elbow-actuator-selected is not a blocker of the characterization, by Joe's ruling.

**Interfaces are frames, not geometry.** Each interface is carried as a frame (origin and axes on the adr-0042 D1 nodes with the D4 roll, quoted with D2's 7 mm elbow and 5 mm wrist error bars), the envelope section at that station, and the loads transmitted through it expressed in that frame. Bolt circle, clocking, fasteners, compliance stroke and overload stop belong to decision 0020 (rm.v1-upper-arm-connectors), which already sits downstream through the requirement records. The shoulder interface frame is defined from the joint centre alone, so the shoulder concept stays open.

**ROM is elbow only.** The ceiling is Soucie's 4.7 to 150 degrees, with Morrey's arc for loads, and the mechanism must reach the full ceiling (Magermans 2005, about 157 degrees in daily activities). Shoulder-side ROM waits on the shoulder concept.

**Fall contact.** Memo 59 finding 7: lc.fall-shoulder-lateral is housed in the thorax but strikes upper_arm_R. The case record gains an optional `contact_in` field defaulting to `zone_in`. It means only the segment whose skin is struck; housing, reserves and budgets stay keyed on `zone_in`, so nothing is counted twice. A segment's characterization reads every case whose contact is that segment, and the file flags each case as a structural load or a clearance constraint (the latter where the shell grounds the impact into another segment's structure, as in the lateral shoulder fall). Joe approves this schema change through the record. Gates for the amendment: every existing thread record validates unchanged; the housing segments' derived `fall_cases` are identical to before; `seg.upper_arm` gains lc.fall-shoulder-lateral through contact.

**Error bars.** Every position and clearance in the file quotes its anchor's bar; a value stated more finely is inside the anchor's uncertainty.

The number 0045 is the next free record number if no node references a higher one; edit the path if not.
