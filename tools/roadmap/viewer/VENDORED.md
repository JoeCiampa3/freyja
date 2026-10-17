# Vendored JavaScript

Authored. Pre-approved for roadmap brief 1, T8 (`docs/briefs/architecture/roadmap-brief1.md`): d3 v7 and marked, each a single pinned minified file. Nothing is loaded from a CDN at runtime; `index.html` references only the files in this directory. `tests/test_roadmap_viewer.py` checks the hashes below.

| File | Package | Version | Licence | Licence text | sha256 of the file |
|---|---|---|---|---|---|
| `d3.min.js` | d3 (`dist/d3.min.js`) | 7.9.0 | ISC | `d3.LICENSE.txt` | `f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539` |
| `marked.min.js` | marked (`marked.min.js`) | 12.0.2 | MIT | `marked.LICENSE.txt` | `15fabce5b65898b32b03f5ed25e9f891a729ad4c0d6d877110a7744aa847a894` |

Fetched once, by hand, from `https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js` and `https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js`. Each was fetched a second time from `https://unpkg.com/<package>@<version>/...` and the two copies were byte-identical (same size and hash). To upgrade, replace the file, update the version and hash here, and run the viewer test.

`marked` does not sanitise its output. `app.js` renders a node's Markdown body through an instance whose renderer escapes raw HTML and allows only http, https, mailto and relative link targets; the page's Content-Security-Policy (set by `server.py`) also forbids inline scripts.
