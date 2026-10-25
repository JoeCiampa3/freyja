# data/makehuman: sources

| File | What it is |
|---|---|
| `base.obj` | MakeHuman's base mesh, unmodified. Upstream path `makehuman/data/3dobjs/base.obj` in github.com/makehumancommunity/makehuman, commit `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` (master, 2024-06-26). Retrieved 2026-10-25 from raw.githubusercontent.com. sha256 `8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c`, 1,749,303 bytes. The file's own header: "This asset was explicitly released as CC0 in september 2020." Marked `-text` in `.gitattributes` so no line-ending conversion changes the hash. It is the topology reference for Gate 1 (13,380 body vertices, 13,378 body faces) and the base of the attribution rebuild. |
| `freyja-body-v1.mhm`, `freyja-body-v1.obj` | The v1 sculpt as exported from MakeHuman 1.2.1 alpha (pose standing02). Never edited. |
| `freyja-body-v2.mhm` | v1 with three slider changes and the pose removed, written by `python analysis/makehuman_v2.py write-mhm`. `freyja-body-v2.obj` is exported by hand from it. |
| `ruler_measures.json` | Vertex lists of MakeHuman's Ruler measures. |
| `mhm_sources.json` | Pins: the upstream commit, `base.obj`, the license statement for the targets folder, and sha256 and size of every target file the analysis scripts read. |

The target files themselves (33 MB for the 161 files read) are not committed. `python analysis/makehuman_fetch.py` downloads them from the pinned commit into `data/makehuman/cache/targets` (gitignored), refuses any file whose hash differs from the manifest, and verifies the lot; `--verify` checks without the network. Then
`python analysis/makehuman_attribution.py --base data/makehuman/base.obj --targets data/makehuman/cache/targets`.

License. The targets folder has no license file of its own. Each target file read carries the header "explicitly released as CC0 in september 2020", and the upstream repository's `LICENSE.ASSETS.md` at the pinned commit is the CC0 1.0 Universal text. The manifest records this under `targets_license`.
