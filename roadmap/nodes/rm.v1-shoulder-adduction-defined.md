---
schema: roadmap-node/2
id: rm.v1-shoulder-adduction-defined
title: "Shoulder adduction defined and its limit rule recorded: what the adduction end of the abduction-adduction joint means, where its value comes from, and when a pose-dependent limit is added"
short: Adduction rule
parent: rm.v1-ariadne-walk-loads
estimate_days: 0.5
tags: ["region:arm", "phase:spec", "stage2"]
done_when:
  type: decision
  record: decisions/0043-shoulder-adduction.md
---
Open item from memo 25 item 4 (the sheet's shoulder adduction row is a deliberate 0; the note on 'Joint ROM' E21 says an angle-based model is needed) and from docs/briefs/ariadne/stage2g-sheet-spec.md section 3 ("define adduction before sourcing it"). rm.v1-rom-gaps-filled waits on this record.

The question: shoulder_fe is first in the chain and shoulder_aa second, so aa's axis follows the arm. At 0 flexion aa is frontal-plane adduction; at 90 flexion it is horizontal adduction. One sourced number has to mean one of them.

Options for the record:
- (A) Keep 0. Against it: the zero-width side puts the standing pose on the stop (memo 25 item 4: stand_static smallest limit margin 0, hold_pose limit_hit_fraction 1.0), and a 0 reads downstream as "no adduction range needed".
- (B) Frontal-plane adduction from neutral. Not a joint property: at 0 flexion the limit is the torso, so a goniometer value measures the body, not the joint.
- (C) Horizontal adduction at 90 degrees flexion, past the sagittal plane, as the aa limit. This is the capsule-bound regime, it is a reported quantity, and the chain order makes it the joint coordinate directly. Magnitude about 40 to 45 degrees past forward (AAOS 130 degrees from the abducted position), from memory: source it from Moromizato 2016 Table 1 (females) or Boone and Azen 1979 before it is entered. The low-flexion limit comes from arm-torso collision, not from the sheet. Sheet row plane becomes "Transverse (at 90 deg flexion)". Recommended.
- (D) A pose-dependent limit surface now. Not v1, see below.

Consequences for the record to state:
- The sheet's shoulder rows are single-plane intercepts used as a box. aa to -182.7 degrees at 90 flexion is an arm pointing backward; the same overstatement applies to the other rows. Logged here, not fixed.
- At 0 flexion the adduction half of the aa range is unreachable (torso). If arm-torso contact is not modelled, rom_sweep reaches it anyway; its gravity torque is bounded by the abduction side.
- hold_pose and stand_static limit margins change once the neutral pose is off the stop; the numbers move at rm.v1-toe-in-model, which already repeats the gait run once.
- shoulder_fe, shoulder_aa, shoulder_ier is singular where the arm points laterally (aa = +/-90 at any fe: fe and ier share an axis). Check before any IK or sweep through that direction.

Deferred, not dropped: the coupled pose-dependent limit (arm-torso collision from the adr-0007 bodies first, then fixed tendons or a fitted limit surface, plus clavicle and scapula DOF if girdle motion is wanted). It is not v1 work: the acceptance test does not need it, and no final interface does (actuator spans follow the per-axis extremes). It becomes work at the first task that commands combined shoulder poses (reach, IK, cross-body, household manipulation; v1 arm swing is flexion with aa near 0), or at v2 articulation. Re-parent it to the v2 roadmap when that exists; until then this record is where it is tracked.

Record number 0043 is the next free one when written (0042 is the highest seen); edit the path if records are written in a different order.
