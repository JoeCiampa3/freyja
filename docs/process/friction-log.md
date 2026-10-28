# Friction log

One line per entry, added the moment something feels like busywork. Aim for under ten seconds per entry; rough numbers are fine.

Format: `date | what happened | est. minutes lost | how often | where (chat / Claude Code / repo / other)`

Examples (replace with real entries):

- 2026-10-19 | re-explained the same project context at the start of a chat | 5 | every session | chat
- 2026-10-20 | copied output from one place into another by hand | 8 | daily | repo
- 2026-10-21 | brief came back wrong, redid it because success criteria were vague | 25 | weekly | Claude Code

## Entries
- 2026-10-19 | full suite run is not necessary at each commit but is being run | 18 | every commit and more | Claude Code

proposed fix:
fy state runs the suite again even when the tree hasn’t changed since the last full run. Caching the result by tree hash would remove the second 18 minutes at every checkpoint.
Running the suite in parallel with pytest-xdist would likely cut 18 minutes to a few on a multi-core machine. It’s a new dependency, so it’s your call.