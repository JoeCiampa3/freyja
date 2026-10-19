---
schema: roadmap-node/2
id: rm.v1-thread-sources
title: "Load cases can cite a literature or test source, and the thread refuses to stamp work that consumes a flagged load case with none attached"
short: Thread sources
parent: rm.v1-ariadne-system-model
blocked_by: [rm.v1-fall-design-basis]
estimate_days: 1.5
tags: ["stage3"]
done_when:
  type: manual
---
A schema bump (thread-record/2) and one rule. Without the rule the independent_source_required flag is decorative: stamping is refused for an active work item that consumes a flagged case with no source attached, and warned for anything else. Needed once the fall cases exist as thread load cases, so it waits on rm.v1-fall-design-basis. Joe signs it off on the memo.
