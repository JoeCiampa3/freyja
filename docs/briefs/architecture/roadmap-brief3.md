# Roadmap brief 3 (for Claude Code): short labels, tag vocabulary, colour by tag

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then `docs/memos/memo15-roadmap-brief2.md`. Briefs 1 and 2 stay in force wherever this brief does not change them.

## Purpose

The real roadmap is about to be written. Its first layer will be eight sectors: Skeletal, Muscular, Nervous, Metabolic, Mind, Ariadne, Workshop and Trials. Each sector is titled as an end state, so on the map its full title is long and gets truncated.

The tree carries one axis, systems. Joe also wants to see the roadmap by body region and by phase. Those two axes are carried as tags, and this brief adds a way to view the map by them.

This brief adds three things:

- a short label for nodes;
- a controlled tag vocabulary that the validator enforces;
- a "colour by" control in map mode.

There is one checkpoint, at the end.

## Out of scope

- Real roadmap content. `roadmap/nodes/` stays empty, apart from what a test creates.
- Any change to the sector structure, which is content, not tooling.
- Any viewer write path beyond the pins file.

## Ground rules

`CONVENTIONS.md` section 9 applies in full, including rule 10 on coupled tasks.

- No new dependencies.
- One commit per task, with the full suite run before every commit.
- Report any defect you observe in a path Joe uses.

## T1. Short label

Add an optional `short` field to the node front matter: a string of at most 16 characters, with no line breaks. Bump the node schema according to the versioning rule in `CONVENTIONS.md`, which most likely means `roadmap-node/2`. The loader must keep accepting existing files, and the fixtures must exercise both forms.

Where `short` is present, the viewer uses it in three places:

- map sector labels;
- map node labels at the zoom threshold;
- breadcrumb segments other than the last.

Everywhere else the viewer keeps showing the full title. The full title also stays in every tooltip and in the drawer.

Tests:

- The schema accepts `short` at 16 characters and rejects it at 17.
- The viewer test covers the sector label.

## T2. Tag vocabulary

Tags take one of two forms:

- **Namespaced:** `namespace:value`.
- **Free:** no colon.

An authored file, `roadmap/tags.yaml`, lists the allowed namespaces. For each namespace it gives the allowed values, plus an optional display colour per value. Validation:

- A namespaced tag whose namespace or value is not in the vocabulary is an **error** that names the node and the tag. The point is typo protection.
- A node carrying two values of the same namespace is a **warning**, because a node belongs to one region and one phase.
- Free tags pass unchecked.
- A missing `tags.yaml` means no namespaces are defined, and any namespaced tag is an error.

Create the initial `tags.yaml` with exactly these two namespaces:

- **`region`:** `head`, `neck`, `torso`, `spine`, `pelvis`, `arm-l`, `arm-r`, `hand-l`, `hand-r`, `leg-l`, `leg-r`, `foot-l`, `foot-r`, `whole-body`.
- **`phase`:** `spec`, `sim`, `design`, `fab`, `bench`, `integrate`.

Choose colour-blind-safe display colours that work in both light and dark themes. `tags.yaml` is authored and Joe owns its values, so add it to `CONVENTIONS.md` section 2 as authored.

Update the fixture generator to tag nodes from this vocabulary. Commit one hand-authored invalid fixture per new error.

Tests:

- every vocabulary error and warning;
- a missing `tags.yaml`;
- free tags passing.

## T3. Colour by tag in map mode

Add a "Colour by" control to the map toolbar, with options **Status** (the default), **Region** and **Phase**. Show only namespaces that exist in the vocabulary.

When a namespace is chosen:

- Each leaf and stub marker is filled with its tag value's colour.
- Status is still conveyed by marker shape, never by colour alone.
- A node without that namespace's tag is drawn in a neutral grey.
- Interior rings keep their progress fill.
- Sector backgrounds stay keyed to first-layer branches.
- A legend lists every value with its count, and clicking a value dims every node that doesn't carry it.

The choice persists across map open and close for the session, and is reflected in the URL hash, so a link reproduces the view.

Search also accepts `tag:<namespace>:<value>` and `tag:<free-tag>`, filtering the outline to matching nodes plus their ancestors.

Tests:

- the colour mapping for each option;
- the grey fallback;
- legend counts;
- hash round-trip;
- the search syntax.

Measure map-open time and recolour time on the 600-file fixture. Map open must stay under 0.5 s, and recolouring must show no visible lag.

## Checkpoint

Write the memo per `CLAUDE.md` rule 6. Include:

- the schema version decision;
- the initial colours chosen;
- the measured times;
- every finding;
- the exact commands for Joe to try region and phase colouring on a 300-node fixture.

Run `fy state` and stop.

## Prerequisites for Joe

- Point the "Current architecture brief" line in `CLAUDE.md` at this file.
- Push the existing commits first.
