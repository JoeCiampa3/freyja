# Roadmap brief 4 (for Claude Code): bilateral region tags

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then `docs/memos/memo16-roadmap-brief3.md`. Briefs 1 to 3 stay in force wherever this brief does not change them.

## Purpose

The real roadmap is written, about 160 nodes. Limb parts are designed once and mirrored, so a knee, a shank or an ankle actuator has no single side. The region vocabulary has only side-specific limb values (`arm-l`, `leg-r` and so on), so bilateral work cannot carry a region tag and colour by region is mostly grey.

This brief replaces the eight side-specific limb values with four bilateral ones, and makes the palette, the tests and the docs follow. It changes the vocabulary and what depends on it, nothing else. There is one checkpoint, at the end.

## Out of scope

- **Node files.** `roadmap/nodes/` is content. Tagging the existing nodes with the new values happens afterwards, in the roadmap authoring session, once this brief has landed. Do not edit any node file.
- **The `phase` namespace**, its values and its colours.
- **The viewer.** It reads the vocabulary from the state file and needs no change; if it does, report why before changing it.
- **Briefs and memos.** They are history. Do not edit them.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full.

- No new dependencies.
- One commit per task, with the full suite run before every commit.
- Edit test files with the editor tool, not shell heredocs. Memo 16, finding 3: backslash escapes in a heredoc broke two test files.
- The values and their order below are Joe's and are fixed. If you think they are wrong, say so in the memo; do not change them.

## T1. The vocabulary

First scan `roadmap/nodes/` for any tag `region:<value>` whose value is one of the eight being removed. If any node carries one, stop, list the nodes and their tags, and ask. Do not edit the nodes.

Then, in `roadmap/tags.yaml`, replace `arm-l`, `arm-r`, `hand-l`, `hand-r`, `leg-l`, `leg-r`, `foot-l` and `foot-r` with `arm`, `hand`, `leg` and `foot`. The region values, in file order, are then:

`head`, `neck`, `torso`, `spine`, `pelvis`, `arm`, `hand`, `leg`, `foot`, `whole-body`

Update the header comment, whose example is `region:arm-l`, to use a value that still exists.

Update the tests to match:

- the `REGION` constant in `tests/test_roadmap_tags.py`, and every test that reads the real `tags.yaml`;
- the fixture test that expects at least 10 distinct region values. With exactly ten values that assertion holds only if every value appears. Make it robust, and say in the memo what you changed it to.

The invalid-fixture directories carry their own small `tags.yaml` files that use `arm-l` as sample data. Leave them unchanged.

## T2. Colours

The six values that stay (`head`, `neck`, `torso`, `spine`, `pelvis`, `whole-body`) keep their current hex where the goals below still hold. Choose the four new colours to meet the goals against those six, against each other and against the viewer's grey for "no tag". If six fixed colours make that impossible, re-search all ten and report why.

The goals are unchanged from brief 3 and are not to be lowered:

- contrast at least 3 : 1 against all four viewer backgrounds;
- CIE76 Delta E at least 12 between every pair of region colours, and between each and the grey, under normal vision, protanopia, deuteranopia and tritanopia.

Ten values should leave more margin than fourteen did. Report the new minima for contrast and for separation per vision mode.

`analysis/tag_palette.py` is the provenance of the colours. If it keeps its own list of region values, update it, or make it read `tags.yaml` if that is the smaller change, so that running it reproduces the committed file. Keep any test that ties the committed colours to the script.

The `phase` colours do not move.

## T3. Docs

Update every place outside briefs and memos that lists the region values or describes how bilateral parts are tagged. At least the Tags paragraph in `roadmap/README.md` section 7, which lists the initial region values. Grep for `arm-l`, `leg-l` and `foot-l` to find the rest, and report what you find.

Add one sentence to that paragraph: a part designed once and mirrored carries the bilateral value; a free tag such as `left` or `right`, which is never checked, marks the rare asymmetric item.

## Checkpoint

Write the memo per `CLAUDE.md` rule 6. Include:

- the result of the node scan in T1;
- the old and new region colours in a table, marking which are unchanged;
- the minimum contrast and the per-vision-mode separation for region, and confirmation that `phase` is unchanged;
- the suite count before and after;
- `fy roadmap validate` output on the real roadmap, which should be clean;
- the exact commands for Joe to open the map coloured by region;
- every finding, including anything else that listed the old values.

Run `fy state` and stop.

## Prerequisites for Joe

- Commit the roadmap nodes first, so the working tree is clean and `fy roadmap validate` passes.
- Point the "Current architecture brief" line in `CLAUDE.md` at this file.
- Give Claude Code the sha256 prefix of this file in the prompt.
