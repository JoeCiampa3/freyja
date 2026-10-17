"""
Helpers for the roadmap tests: write a repo-shaped root with node files, and load the library from tools/.
"""
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TOOLS = str(REPO / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


def node_text(**fields):
    """A node file: YAML front matter (sorted keys) and a body."""
    body = fields.pop("_body", "Body.\n")
    front = {"schema": "roadmap-node/2" if "short" in fields else "roadmap-node/1", **fields}  # `short` exists from version 2; both versions load
    return "---\n" + yaml.safe_dump(front, sort_keys=True) + "---\n" + body


def write_node(root, id, **fields):
    d = Path(root) / "roadmap" / "nodes"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{id}.md").write_text(node_text(id=id, **fields), encoding="utf-8", newline="\n")


def make(root, nodes):
    """nodes: {id: fields}; title defaults to the id, parent to None. Returns root."""
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "roadmap" / "nodes").mkdir(parents=True, exist_ok=True)
    for id, f in nodes.items():
        f = dict(f)
        f.setdefault("title", f"{id} reached")
        f.setdefault("parent", None)
        write_node(root, id, **f)
    return Path(root)


MANUAL = {"type": "manual"}


def leaf(parent, done=False, **extra):
    """A manual leaf, signed off when done."""
    return {"parent": parent, "estimate_days": 1, "done_when": MANUAL, "signed_off": done, **extra}
