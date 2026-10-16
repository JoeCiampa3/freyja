"""
The roadmap library: a graph of small, verifiable goals read from roadmap/nodes/*.md under a root directory, validated, with every
node's status derived. Domain logic lives here; tools/fy only wraps it (CONVENTIONS section 2). Rules: docs/briefs/architecture/roadmap-brief1.md.
"""
from .derive import STATUSES, Roadmap, compute  # noqa: F401
from .model import ESTIMATE_CAP_DAYS, Issue, Node  # noqa: F401
