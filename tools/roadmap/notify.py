"""
Roadmap notification: compare the frontier at two commits and open one GitHub issue per leaf that became ready and one per stub that
became expandable (docs/briefs/architecture/roadmap-brief1.md T6; roadmap-brief2.md T5). The frontiers are not read from the committed
roadmap/state.json, which a commit that bypassed the pre-commit hook leaves stale: both commits are checked out into temporary git
worktrees and built fresh with the code that is running (the after commit's tool code). A before commit with no roadmap/nodes is an empty
frontier. When the committed state.json at the after commit differs from the fresh build, a `::warning::` annotation names the differing
nodes; it is a warning, never a failure, so a byte difference between platforms cannot turn every push red. The diff is a pure function
of two parsed state dicts; `gh` is reached only through the `gh` callable passed to run(), so the tests never touch the network and this
module imports no network library. Nothing is opened without a before commit (first push, all-zero or unknown before commit) or when the
before roadmap has errors.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .derive import compute
from .refs import token_re
from .render import STATE_JSON, criterion_text, state_dict

LABEL = "roadmap"
LABEL_COLOR = "0e8a16"
LABEL_DESCRIPTION = "A roadmap node became workable"
MAX_NAMED = 30  # node ids named in the stale-state warning


class GhError(RuntimeError):
    """The gh command line failed."""


class StateError(ValueError):
    """A commit cannot be resolved, checked out or read."""


@dataclass(frozen=True)
class IssueSpec:
    id: str
    kind: str  # ready | expandable
    title: str
    body: str
    labels: list

    def lines(self) -> list:
        return [f"title: {self.title}", f"label: {', '.join(self.labels)}", *["  " + l for l in self.body.splitlines()]]


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _cleared(before: dict, after: dict, id: str) -> list:
    b = before["nodes"].get(id)
    if b is None:
        return None  # the node did not exist before
    return sorted(set(b["uncleared_blockers"]) - set(after["nodes"][id]["uncleared_blockers"]))


def build_issue(id: str, before: dict, after: dict, link_base: str) -> IssueSpec:
    n = after["nodes"][id]
    stub = n["kind"] == "stub"
    cleared = _cleared(before, after, id)
    if cleared is None:
        cleared_text = "none (new node)"
    else:
        cleared_text = ", ".join(f"`{c}`" for c in cleared) or "none"
    if stub:
        criterion, estimate = "none; a stub. Decompose it into children, or give it a criterion and an estimate and drop `stub: true`.", "none (stub)"
    else:
        criterion, estimate = f"`{criterion_text(n['done_when'])}`", f"{n['estimate_days']:g} days"
    body = "\n".join([
        f"**Criterion:** {criterion}", f"**Estimate:** {estimate}", f"**Blockers that just cleared:** {cleared_text}",
        f"**Node file:** {link_base}/{n['path']}", "", "Opened by the roadmap workflow because this node entered the frontier."])
    return IssueSpec(id, "expandable" if stub else "ready", f"{'Expandable' if stub else 'Ready'}: {_one_line(n['title'])} ({id})", body, [LABEL])


def plan(before: dict | None, after: dict, open_titles, link_base: str) -> list:
    """The issues to open: nodes on the after frontier and not on the before frontier, in id order, minus any whose id is a whole token in an open issue's title."""
    if before is None:
        return []
    fresh = sorted(set(after["frontier"]) - set(before["frontier"]))
    out = []
    for id in fresh:
        rx = token_re(id)
        if not any(rx.search(t) for t in open_titles):
            out.append(build_issue(id, before, after, link_base))
    return out


def _git(root, *args) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise StateError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def resolve_commit(root, ref: str) -> str:
    """The full hash of a commit that exists in the clone. Raises StateError."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()


@contextmanager
def worktree(root, commit: str):
    """A detached, temporary checkout of `commit`; removed on exit. Nothing is written into the clone's own working tree."""
    tmp = tempfile.mkdtemp(prefix="roadmap-notify-")
    path = Path(tmp) / "wt"
    try:
        _git(root, "-c", "core.autocrlf=false", "worktree", "add", "--detach", "--force", str(path), commit)
        yield path
    finally:
        try:
            _git(root, "worktree", "remove", "--force", str(path))
        except StateError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            _git(root, "worktree", "prune")
        except StateError:
            pass


def fresh_state(wt_root):
    """(state dict, []) for the roadmap under a checkout, built by the running code; (None, errors) when the roadmap has errors."""
    rm = compute(wt_root)
    if rm.errors:
        return None, rm.errors
    return json.loads(json.dumps(state_dict(rm), sort_keys=True, ensure_ascii=False)), []


def committed_state(root, commit: str):
    """roadmap/state.json as committed at `commit` (parsed), or None when it is absent or not JSON."""
    try:
        return json.loads(_git(root, "show", f"{commit}:{STATE_JSON}"))
    except (StateError, ValueError):
        return None


def differing(committed: dict, fresh: dict) -> tuple:
    """(node ids whose entry differs or exists on one side only, other top-level fields that differ). The banner is ignored."""
    a, b = committed.get("nodes", {}), fresh.get("nodes", {})
    ids = sorted(i for i in set(a) | set(b) if a.get(i) != b.get(i))
    fields = sorted(k for k in (set(committed) | set(fresh)) - {"nodes", "_generated"} if committed.get(k) != fresh.get(k))
    return ids, fields


def _annotation(text: str) -> str:
    """One GitHub Actions workflow-command line (message escaping per the runner's rules)."""
    return "::warning title=roadmap/state.json is stale::" + text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def stale_warning(root, commit: str, fresh: dict):
    """The ::warning:: line when the committed state.json at `commit` differs from the fresh build, else None."""
    old = committed_state(root, commit)
    if old is None:
        return _annotation(f"{STATE_JSON} is missing or unreadable at {commit[:12]}; run `python tools/fy roadmap build` and commit it.")
    ids, fields = differing(old, fresh)
    if not ids and not fields:
        return None
    named = ", ".join(ids[:MAX_NAMED]) + (f" (and {len(ids) - MAX_NAMED} more)" if len(ids) > MAX_NAMED else "")
    parts = [f"{len(ids)} node(s): {named}"] if ids else []
    if fields:
        parts.append("fields: " + ", ".join(fields))
    return _annotation(f"{STATE_JSON} at {commit[:12]} differs from a fresh build in " + "; ".join(parts) +
                       ". The issues were computed from the fresh build. A commit that bypassed the pre-commit hook leaves it stale: run `python tools/fy roadmap build`.")


def default_gh(args, input=None) -> str:
    r = subprocess.run(["gh", *args], input=input, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise GhError(f"gh {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def run(root, before: str, after: str, repo: str, dry_run=False, gh=None, say=print) -> int:
    """Open the issues for the nodes that entered the frontier between two commits. Exit code 0 (including 'nothing to open'), or 1 on an unusable after commit or roadmap, or a gh failure."""
    gh = gh or default_gh
    try:
        after_sha = resolve_commit(root, after)
    except StateError as e:
        say(f"notify: no usable after state: {after} is not a commit here ({e})")
        return 1
    if not before or re.fullmatch("0+", before):
        say("notify: no before state (no previous commit); opening nothing.")
        return 0
    try:
        before_sha = resolve_commit(root, before)
    except StateError:
        say(f"notify: no before state ({before[:12]} is not a commit in this clone); opening nothing.")
        return 0
    try:
        with worktree(root, after_sha) as wt:
            after_state, errs = fresh_state(wt)
        if after_state is None:
            say(f"notify: no usable after state: the roadmap at {after_sha[:12]} has {len(errs)} error(s), first: {errs[0].code}: {errs[0].message}")
            return 1
        with worktree(root, before_sha) as wt:
            before_state, errs = fresh_state(wt)
    except StateError as e:
        say(f"notify: could not check out the commits: {e}")
        return 1
    if before_state is None:
        say(f"notify: no before state (the roadmap at {before_sha[:12]} has {len(errs)} error(s)); opening nothing.")
        return 0
    warning = stale_warning(root, after_sha, after_state)
    if warning:
        say(warning)
    after = after_sha
    link_base = f"https://github.com/{repo}/blob/{after}"
    try:
        if dry_run:
            titles = []
        else:
            titles = [i["title"] for i in json.loads(gh(["issue", "list", "--state", "open", "--limit", "1000", "--json", "title"]) or "[]")]
        issues = plan(before_state, after_state, titles, link_base)
        say(f"notify: {len(issues)} issue(s) to open" + (" (dry run: gh was not called, so open issues were not checked for duplicates)" if dry_run else ""))
        if issues and not dry_run:
            have = {l["name"] for l in json.loads(gh(["label", "list", "--json", "name", "--limit", "200"]) or "[]")}
            if LABEL not in have:
                gh(["label", "create", LABEL, "--color", LABEL_COLOR, "--description", LABEL_DESCRIPTION])
        for spec in issues:
            if dry_run:
                for line in spec.lines():
                    say(line)
                continue
            gh(["issue", "create", "--title", spec.title, "--label", ",".join(spec.labels), "--body-file", "-"], input=spec.body)
            say(f"opened: {spec.title}")
    except GhError as e:
        say(f"notify: {e}")
        return 1
    return 0
