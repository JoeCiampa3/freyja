---
schema: roadmap-node/2
id: rm.v1-trial-rig-concept
title: "Trial rig concept recorded: stand and travel arrangement, load rating, harness attachment points on the body and their rating, how it releases the robot, and how it catches a fall"
short: Rig concept
parent: rm.v1-trial-rig
blocked_by: [rm.v1-acceptance-protocol, rm.v1-fall-intent]
estimate_days: 2.0
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0034-trial-rig-concept.md
---
Working assumption, decided in the record: a rail on the ceiling of the test room rather than a floor stand, a trolley that follows the robot along it, a swivel so the turn does not wind the line, and a release stand at one end. The anchorage must be rated for a dynamic arrest of the full robot mass, not its static weight, through the building's framing, and the record says how the arrest load is limited (for example an energy absorber). The harness hardpoint on the body is a final interface: rm.v1-torso-structure waits on this record.

It waits on rm.v1-fall-intent, which sets the protocol: nothing but the feet may touch the floor, so the catch geometry (line length, slack and attachment point) must keep every other part off it. The anchorage and its rating carry the arrest load, because a catch failure is a fall v1 makes no survival claim for. The arrest load path into the harness points follows from the same record and belongs in rm.v1-torso-structure.
