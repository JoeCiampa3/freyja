"""
The edge-type registry: the one place each relationship in the thread is documented. Each type has a name (also the key under which a
record's derived JSON carries the relation), the kinds it runs from and to, whether it is authored or derived, and a docstring saying what
the relation means and what is derived from it. thread/graph.json carries this registry so a viewer can explain any edge without anyone
writing documentation per edge. Adding an edge type is a decision for Joe (the Stage 3a brief).
"""
from __future__ import annotations

from dataclasses import dataclass

KINDS = ("segment", "joint", "part", "interface", "load_case", "harness_run", "work_item")
PREFIX_KIND = {"seg": "segment", "jnt": "joint", "part": "part", "if": "interface", "lc": "load_case", "hn": "harness_run", "work": "work_item"}


def kind_of(id: str):
    return PREFIX_KIND.get(id.split(".", 1)[0]) if "." in id else None


@dataclass(frozen=True)
class EdgeType:
    name: str
    from_kinds: tuple
    to_kinds: tuple
    origin: str  # authored | derived
    doc: str

    def to_dict(self) -> dict:
        return {"name": self.name, "from_kinds": list(self.from_kinds), "to_kinds": list(self.to_kinds), "origin": self.origin, "doc": self.doc}


_ALL = KINDS
EDGE_TYPES = tuple(sorted((
    EdgeType("housed_in", ("part",), ("segment",), "authored",
             "The segment a part sits in. Stored on the part. Derives `houses` on the segment, the mass claim in the segment's budget, and where the part appears in the segment's dossier."),
    EdgeType("acts_across", ("part",), ("joint",), "authored",
             "The joint a part drives or loads. Stored on the part, optional. Derives `acted_on_by` on the joint. Requires `reacts_into`."),
    EdgeType("reacts_into", ("part",), ("segment",), "authored",
             "The segment that takes the reaction torque of a part acting across a joint, which sets the load path. Stored on the part; required with `acts_across`. Derives `reacted_by` on the segment."),
    EdgeType("harness", ("part",), ("harness_run",), "authored",
             "A cable run the part is wired into. Stored on the part. Derives `used_by` on the run."),
    EdgeType("between", ("interface",), ("part", "segment"), "authored",
             "The two ends of an interface, a contract between two parts or a part and a segment. Stored on the interface. Derives `interfaces` on both ends."),
    EdgeType("carries_cut_of", ("interface",), ("joint",), "authored",
             "The joint whose cut wrench passes through an interface. Stored on the interface, optional. Derives `interfaces` on the joint."),
    EdgeType("path", ("harness_run",), ("segment",), "authored",
             "The ordered segments a harness run passes through. Stored on the run. Derives `crossed_by` on every segment on the path."),
    EdgeType("of", ("work_item",), _ALL, "authored",
             "The record a work item belongs to (a CAD model of a part, an FEA study of a segment). Stored on the work item. The owner's dossier lists the item with its status."),
    EdgeType("consumes", ("work_item",), _ALL, "authored",
             "A record that holds an address the work item consumes (the address itself is in the item's `consumes` list; an address into a record or its derived file counts). Derives `consumed_by`, and the work status from the hash of every consumed address against the baseline stamp."),
    EdgeType("superseded_by", _ALL, _ALL, "authored",
             "A retired record points at its live replacement of the same kind. IDs are permanent, so a superseded record stays."),
    EdgeType("houses", ("segment",), ("part",), "derived",
             "Inverse of `housed_in`: the parts housed in a segment, proposed and superseded ones included. Only active and proposed parts claim mass."),
    EdgeType("reacted_by", ("segment",), ("part",), "derived",
             "Inverse of `reacts_into`: the parts whose reaction torque a segment takes."),
    EdgeType("acted_on_by", ("joint",), ("part",), "derived",
             "Inverse of `acts_across`: the parts acting across a joint."),
    EdgeType("used_by", ("harness_run",), ("part",), "derived",
             "Inverse of `harness`: the parts wired into a run."),
    EdgeType("crossed_by", ("segment",), ("harness_run",), "derived",
             "Inverse of `path`: the harness runs that pass through a segment."),
    EdgeType("interfaces", _ALL, ("interface",), "derived",
             "Inverse of `between` and `carries_cut_of`: the interfaces that touch a record."),
    EdgeType("consumed_by", _ALL, ("work_item",), "derived",
             "Inverse of `consumes`: the work items that consume an address in a record."),
    EdgeType("joints_as_parent", ("segment",), ("joint",), "derived",
             "From the model's body tree: the joints whose hinges sit in a child body of this segment's body. Not stored in any record."),
    EdgeType("joints_as_child", ("segment",), ("joint",), "derived",
             "From the model's body tree: the joints whose hinges sit in this segment's body. Not stored in any record."),
    EdgeType("parent_segments", ("joint",), ("segment",), "derived",
             "From the model's body tree: the segment(s) the joint's hinges hang from. Not stored in any record."),
    EdgeType("child_segments", ("joint",), ("segment",), "derived",
             "From the model's body tree: the segment(s) that contain the joint's hinges. Not stored in any record."),
), key=lambda t: t.name))
BY_NAME = {t.name: t for t in EDGE_TYPES}
