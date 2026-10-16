"""
Roadmap notification: compare the frontier in roadmap/state.json at two commits and open one GitHub issue per leaf that became ready and
one per stub that became expandable (docs/briefs/architecture/roadmap-brief1.md, T6). The diff is a pure function of two parsed state
files; `gh` is reached only through the `gh` callable passed to run(), so the tests never touch the network and this module imports no
network library. Nothing is opened without a before state (first push, all-zero before commit, a commit with no state file).
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from .refs import token_re
from .render import STATE_JSON, criterion_text

LABEL = "roadmap"
LABEL_COLOR = "0e8a16"
LABEL_DESCRIPTION = "A roadmap node became workable"
STATE_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "roadmap-state-1.schema.json"


class GhError(RuntimeError):
    """The gh command line failed."""


class StateError(ValueError):
    """roadmap/state.json at a commit is missing, unparseable or does not match its schema."""


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


def read_state_at(root, commit: str) -> dict:
    """roadmap/state.json as committed at `commit`, validated against roadmap-state/1. Raises StateError."""
    text = _git(root, "show", f"{commit}:{STATE_JSON}")
    try:
        state = json.loads(text)
        errs = list(jsonschema.Draft202012Validator(json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))).iter_errors(state))
    except ValueError as e:
        raise StateError(f"{STATE_JSON} at {commit[:12]} is not valid JSON ({e.__class__.__name__})") from e
    if errs:
        raise StateError(f"{STATE_JSON} at {commit[:12]} does not match roadmap-state/1: {errs[0].message[:120]}")
    return state


def default_gh(args, input=None) -> str:
    r = subprocess.run(["gh", *args], input=input, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise GhError(f"gh {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def run(root, before: str, after: str, repo: str, dry_run=False, gh=None, say=print) -> int:
    """Open the issues for the nodes that entered the frontier between two commits. Exit code 0 (including 'nothing to open'), or 1 on an unusable after state or a gh failure."""
    gh = gh or default_gh
    try:
        after_state = read_state_at(root, after)
    except StateError as e:
        say(f"notify: no usable after state: {e}")
        return 1
    if not before or re.fullmatch("0+", before):
        say("notify: no before state (no previous commit); opening nothing.")
        return 0
    try:
        before_state = read_state_at(root, before)
    except StateError as e:
        say(f"notify: no before state ({e}); opening nothing.")
        return 0
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
