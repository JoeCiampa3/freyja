---
schema: roadmap-node/2
id: rm.v1-workbench
title: "Unified desktop workbench over the repo: the roadmap, the thread graph, CAD sidecars and meshes, recorded sim runs, FEA results and the repo's pickers in one app that holds no data of its own"
short: Workbench
parent: rm.v1-ariadne
blocked_by: [rm.v1-thread-viewer]
stub: true
---
An enabler, like the Workshop: the acceptance test and the final interfaces do not need it, but it makes the work around Ariadne cheaper, and it marks the step Ariadne is. The rule for enablers: nothing on the v1 path may block on one. Joe's budget: about one evening; if Code cannot finish it in a few sessions, it is dropped.

Constraints when it is expanded:
- It reads only generated files and acts only through `fy` commands, so the repo stays the only home of every quantity.
- It absorbs the roadmap viewer and rm.v1-thread-viewer as panes rather than reimplementing them.
- Fusion cannot be embedded: the CAD pane shows each part's sidecar and canonical STL and runs `fy cad push`, `pull` and `status`.
- MuJoCo's viewer is a native window: the sim pane replays recorded runs, or uses MuJoCo's WebAssembly build.
- The FEA pane waits on rm.v1-fea-route.
- The landmark picker and the envelope's inspect bundles become panes.

First leaf when expanded: the shell (Tauri or Electron) decided and recorded. Expand when rm.v1-thread-viewer is done.
