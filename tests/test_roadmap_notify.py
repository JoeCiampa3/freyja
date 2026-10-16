"""
Roadmap T6: the notification. The frontier diff is a library function (tools/roadmap/notify.py) tested offline; `gh` is replaced by a
recording fake, and the workflow file is checked as text. Nothing here touches the network.

Run from the repo root:
    python -m pytest tests/test_roadmap_notify.py
"""
import json
import subprocess

import pytest
import yaml
from rmhelp import REPO, leaf, make

import roadmap
from roadmap import cli, notify, render

LINK = "https://github.com/o/r/blob/abc123"


def state_of(root):
    render.build(root)
    return json.loads((root / "roadmap" / "state.json").read_text(encoding="utf-8"))


NODES = {
    "rm.root": {"title": "Freyja walks"},
    "rm.a": leaf("rm.root", title="Cable routed", done=False),
    "rm.b": {**leaf("rm.root", title="Elbow selected", blocked_by=["rm.a"]), "estimate_days": 2,
             "done_when": {"type": "decision", "record": "decisions/0012-elbow.md"}},
    "rm.s": {"parent": "rm.root", "stub": True, "title": "Wrist decomposed", "blocked_by": ["rm.a"]},
    "rm.c": leaf("rm.root", title="Battery chosen", done=False),
}


def two_states(tmp_path, mutate=None):
    root = make(tmp_path / "r", NODES)
    before = state_of(root)
    make(root, {"rm.a": {**NODES["rm.a"], "signed_off": True}} if mutate is None else mutate)
    return before, state_of(root)


def test_newly_ready_leaf_and_newly_expandable_stub_each_get_one_issue_in_id_order(tmp_path):
    before, after = two_states(tmp_path)
    assert before["frontier"] == ["rm.a", "rm.c"] and after["frontier"] == ["rm.b", "rm.c", "rm.s"]
    got = notify.plan(before, after, [], LINK)
    assert [(g.id, g.title) for g in got] == [("rm.b", "Ready: Elbow selected (rm.b)"), ("rm.s", "Expandable: Wrist decomposed (rm.s)")]
    assert all(g.labels == ["roadmap"] for g in got)


def test_the_body_carries_criterion_estimate_cleared_blockers_and_a_link(tmp_path):
    before, after = two_states(tmp_path)
    leaf_issue, stub_issue = notify.plan(before, after, [], LINK)
    assert "decision: decisions/0012-elbow.md" in leaf_issue.body and "2 days" in leaf_issue.body
    assert "rm.a" in leaf_issue.body.split("just cleared")[1].splitlines()[0]
    assert f"{LINK}/roadmap/nodes/rm.b.md" in leaf_issue.body
    assert "stub" in stub_issue.body.lower() and "rm.a" in stub_issue.body.split("just cleared")[1].splitlines()[0]
    assert f"{LINK}/roadmap/nodes/rm.s.md" in stub_issue.body


def test_a_node_already_on_the_frontier_or_leaving_it_opens_nothing(tmp_path):
    before, after = two_states(tmp_path)
    assert notify.plan(after, after, [], LINK) == []  # no change
    assert [g.id for g in notify.plan(after, before, [], LINK)] == ["rm.a"]  # reversing: rm.a is newly ready again; rm.c, already ready, is not repeated


def test_a_new_node_has_no_cleared_blockers(tmp_path):
    root = make(tmp_path / "r", NODES)
    before = state_of(root)
    make(root, {"rm.new": leaf("rm.root", title="Fresh goal")})
    got = notify.plan(before, state_of(root), [], LINK)
    assert [g.id for g in got] == ["rm.new"] and "none (new node)" in got[0].body


def test_no_before_state_opens_nothing(tmp_path):
    root = make(tmp_path / "r", NODES)
    assert notify.plan(None, state_of(root), [], LINK) == []


def test_an_open_issue_whose_title_contains_the_id_as_a_token_suppresses_it(tmp_path):
    before, after = two_states(tmp_path)
    got = notify.plan(before, after, ["Ready: something else entirely (rm.b)"], LINK)
    assert [g.id for g in got] == ["rm.s"]
    # rm.b-extra and rm.b.x are different ids: they do not suppress rm.b
    got = notify.plan(before, after, ["Ready: x (rm.b-extra)", "Ready: y (rm.b.x)", "rm.bb"], LINK)
    assert [g.id for g in got] == ["rm.b", "rm.s"]
    assert [g.id for g in notify.plan(before, after, ["Ready: x (rm.b)", "Expandable: y (rm.s)"], LINK)] == []


def test_titles_are_one_line(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "T"}, "rm.x": leaf("rm.root", title="Two   words\tand\nmore")})
    before = {**state_of(root), "frontier": []}
    got = notify.plan(before, state_of(root), [], LINK)
    assert got[0].title == "Ready: Two words and more (rm.x)"


# ---- end to end on a throwaway git repository, with a recording fake for gh

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    root = make(tmp_path / "r", NODES)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "core.autocrlf", "false")
    render.build(root)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one")
    first = git(root, "rev-parse", "HEAD")
    make(root, {"rm.a": {**NODES["rm.a"], "signed_off": True}})
    render.build(root)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "two")
    return root, first, git(root, "rev-parse", "HEAD")


class FakeGh:
    def __init__(self, open_titles=(), labels=()):
        self.calls, self.open_titles, self.labels = [], list(open_titles), list(labels)

    def __call__(self, args, input=None):
        self.calls.append((list(args), input))
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"title": t} for t in self.open_titles])
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": n} for n in self.labels])
        return ""


def creates(gh):
    return [(a, i) for a, i in gh.calls if a[:2] == ["issue", "create"]]


def test_run_creates_one_issue_per_new_node_and_the_label_first(repo):
    root, first, second = repo
    gh, out = FakeGh(), []
    assert notify.run(root, first, second, "o/r", gh=gh, say=out.append) == 0
    made = creates(gh)
    assert [a[a.index("--title") + 1] for a, _ in made] == ["Ready: Elbow selected (rm.b)", "Expandable: Wrist decomposed (rm.s)"]
    assert all(a[a.index("--label") + 1] == "roadmap" and "--body-file" in a and "-" in a for a, _ in made)
    assert f"https://github.com/o/r/blob/{second}/roadmap/nodes/rm.b.md" in made[0][1]
    kinds = [a[:2] for a, _ in gh.calls]
    assert kinds.index(["label", "create"]) < kinds.index(["issue", "create"])  # the label exists before an issue asks for it
    assert out[0] == "notify: 2 issue(s) to open" and len(out) == 3


def test_run_does_not_create_the_label_when_it_exists_and_skips_open_issues(repo):
    root, first, second = repo
    gh = FakeGh(open_titles=["Ready: Elbow selected (rm.b)"], labels=["roadmap", "bug"])
    notify.run(root, first, second, "o/r", gh=gh, say=lambda s: None)
    assert [a[:2] for a, _ in gh.calls].count(["label", "create"]) == 0
    assert [a[a.index("--title") + 1] for a, _ in creates(gh)] == ["Expandable: Wrist decomposed (rm.s)"]


def test_dry_run_prints_the_issues_and_calls_gh_never(repo):
    root, first, second = repo
    gh, out = FakeGh(), []
    assert notify.run(root, first, second, "o/r", dry_run=True, gh=gh, say=out.append) == 0
    assert gh.calls == []
    text = "\n".join(out)
    assert "Ready: Elbow selected (rm.b)" in text and "Expandable: Wrist decomposed (rm.s)" in text and "dry run" in text.lower()


@pytest.mark.parametrize("before", ["0" * 40, "f" * 40, ""])
def test_a_zero_or_unknown_before_commit_opens_nothing(repo, before):
    root, first, second = repo
    gh, out = FakeGh(), []
    assert notify.run(root, before, second, "o/r", gh=gh, say=out.append) == 0
    assert gh.calls == [] and any("no before state" in s for s in out)


def test_a_before_commit_without_a_state_file_opens_nothing(repo):
    root, first, second = repo
    git(root, "rm", "-q", "--cached", "roadmap/state.json")
    git(root, "commit", "-q", "-m", "drop the state file")
    dropped = git(root, "rev-parse", "HEAD")
    git(root, "add", "roadmap/state.json")
    git(root, "commit", "-q", "-m", "restore it")
    gh = FakeGh()
    assert notify.run(root, dropped, git(root, "rev-parse", "HEAD"), "o/r", gh=gh, say=lambda s: None) == 0
    assert gh.calls == []


def test_a_missing_or_invalid_after_state_is_an_error(repo):
    root, first, second = repo
    gh, out = FakeGh(), []
    assert notify.run(root, first, "e" * 40, "o/r", gh=gh, say=out.append) == 1  # not a commit
    assert gh.calls == [] and any("after" in s for s in out)


def test_a_gh_failure_is_reported_and_exits_nonzero(repo):
    root, first, second = repo

    def failing(args, input=None):
        if args[:2] == ["issue", "create"]:
            raise notify.GhError("boom")
        return "[]"
    out = []
    assert notify.run(root, first, second, "o/r", gh=failing, say=out.append) == 1
    assert any("boom" in s for s in out)


def test_the_cli_runs_notify_as_a_dry_run(repo):
    root, first, second = repo
    out = []
    assert cli.main(["notify", "--root", str(root), "--before", first, "--after", second, "--repo", "o/r", "--dry-run"], say=out.append) == 0
    assert "Ready: Elbow selected (rm.b)" in "\n".join(out)


# ---- the workflow file, as text

WORKFLOW = REPO / ".github" / "workflows" / "roadmap.yml"


def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_triggers_on_push_to_the_default_branch_and_asks_for_issue_write_only():
    w = workflow()
    assert w["name"] == "roadmap"
    trigger = w.get("on", w.get(True))  # YAML 1.1 reads a bare `on` as True
    assert list(trigger) == ["push"] and trigger["push"]["branches"] == ["main"]
    assert w["permissions"] == {"contents": "read", "issues": "write"}


def test_workflow_validates_then_notifies_and_never_interpolates_event_data_into_a_script():
    w = workflow()
    steps = next(iter(w["jobs"].values()))["steps"]
    runs = [s["run"] for s in steps if "run" in s]
    assert any("fy roadmap validate" in r for r in runs)
    notify_step = next(s for s in steps if "fy roadmap notify" in s.get("run", ""))
    assert steps.index(notify_step) > max(i for i, s in enumerate(steps) if "fy roadmap validate" in s.get("run", ""))
    assert all("${{" not in r for r in runs)  # event values reach the script through env, not through text substitution
    assert notify_step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "$BEFORE" in notify_step["run"] and "$AFTER" in notify_step["run"]
    assert notify_step["env"]["BEFORE"] == "${{ github.event.before }}" and notify_step["env"]["AFTER"] == "${{ github.sha }}"
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0  # the before commit must be in the clone


def test_workflow_installs_only_the_two_pinned_packages_the_roadmap_uses():
    steps = next(iter(workflow()["jobs"].values()))["steps"]
    pip = next(s["run"] for s in steps if "pip install" in s.get("run", ""))
    pins = {l.split("==")[0].lower(): l.split("==")[1].strip() for l in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines() if "==" in l}
    wanted = pip.split("pip install", 1)[1].split()
    assert sorted(w.split("==")[0].lower() for w in wanted) == ["jsonschema", "pyyaml"]
    assert all(w.split("==")[1] == pins[w.split("==")[0].lower()] for w in wanted)


def test_the_library_is_importable_without_the_network_stack():
    assert roadmap.compute is not None
    import ast
    tree = ast.parse((REPO / "tools" / "roadmap" / "notify.py").read_text(encoding="utf-8"))
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | {
        n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not mods & {"requests", "urllib", "http", "socket", "httpx"}
