---
schema: roadmap-node/2
id: rm.v1-ariadne-actuator-map
title: "Every v1 actuated joint's envelope mapped from the model's hinge axes into its actuator's own coordinates"
short: Actuator map
parent: rm.v1-ariadne
---
One leaf per joint, behind a recorded method. Each actuator selection waits on its own joint's map, not on this node as a whole, so the hip does not wait on the lumbosacral joint.
