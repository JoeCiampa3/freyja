---
id: adr-0036
status: accepted
date: 2026-10-19
links: []
---
## Context

v1 is meant to be a platform that later versions iterate on, not rebuild. Interfaces, load paths, and the mass and volume budgets are final in v1. Freyja is meant to end up autonomous, so it will fall, and fall protection (sacrificial parts, compliant material, protective behaviour) will need connectors, load paths, and mass and volume that v1 must already have left room for.

Two questions are tangled together here and this record keeps them apart:

1. **Protocol:** what v1's whole-body trials allow to touch the floor.
2. **Design basis:** what the v1 hardware is built to survive, and what it reserves for later.

This record decides the protocol and the principle that governs the design basis. It does not set magnitudes: those need the literature bracket (rm.v1-fall-sources) and are decided in 0037 (fall design basis).

## Decision

**Protocol.** Every v1 whole-body trial, from the first supported standing trial to the acceptance walk, runs with the catch rig fitted. Nothing but the feet may touch the floor. The rig's catch geometry (line length, slack and attachment point) is set so that no other part can reach the floor; that is a requirement on rm.v1-trial-rig-concept. The robot still balances and walks on its own onboard systems. If the catch fails or is not fitted, the fall is uncontrolled and v1 makes no survival claim for it: the mitigation is the rig's rated anchorage and its load test (rm.v1-trial-rig-built), not the robot.

**Principle.** For every segment, the v1 design either (a) carries the governing fall case, or (b) reserves the mass and envelope space to carry it later without moving an interface. A reservation is a quantity in the segment's budget (a reserved claim, as the hands and face already are), not an intention. The governing cases, the safety factors and the reservations are set in 0037. No segment is finalized before 0037.

**No credit for fall behaviour.** The hardware is not credited with bracing the arms, unlocking joints or any other protective behaviour: v1 neither implements nor tests it. Such behaviour can only lower loads later.

**Verification.** v1 makes no tested fall-survival claim. Where v1 claims a segment carries a fall case, the claim is verified by analysis against an independent source (literature now, a drop test later), never against simulation magnitudes alone: soft-contact peaks depend on solver parameters and the timestep.

## Consequences

- Fall testing is deferred to a later version, not removed from the goal. What v1 proves is the interfaces, the load paths and the reserved space; it does not prove survival.
- The rig concept inherits two requirements: a catch geometry that keeps every non-foot part off the floor, and an arrest load path into the harness points, which rm.v1-torso-structure carries.
- Every segment's design waits on 0037 (rm.v1-fall-design-basis). The upper arm's load basis (rm.v1-elbow-load-basis) waits on it too, because a braced fall may govern the elbow.
- Mass reservations enter the thread as reserved claims in the segment budgets. Volume reservations have no thread budget yet; rm.v1-thread-budgets adds one, and until it exists a volume reservation is prose and must not be treated as final.
- Open questions for 0037: how each reservation is quantified; which segments a fall governs and which it does not; whether the slim-leg aesthetic envelope leaves room to thicken a wall where it does; and where a fall's load path goes (hard stops into structure, not through the transmissions).

## Rejected options, and why each one died

**Chosen: A.** The catch rig is set so that nothing but the feet may touch the floor during v1 trials.

**B. Contact is tolerated on named regions during v1 trials, with sacrificial parts.** Rejected: it turns the trials into fall tests of hardware that has no tested protection and no independent bracket yet, with the only prototype at risk. One of the driving forces behind v1 is a functional platform that can be iterated on; fall testing for the wider range of operation is deferred to a later version.

**C. No fall design basis in v1: contact is not designed for.** Rejected: interfaces and load paths are final in v1, so if later fall protection needs a connector, a hard stop or a volume that v1 did not leave, the affected segments are redesigned. How many segments that is cannot be said until the bracket gives the ratio of fall loads to the walking envelope, so the claim here is the risk, not a count. By designing for the case or reserving the space now, v1 plans for the future instead.
