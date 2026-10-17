"""
Roadmap brief 2 T6: pins, the personal bookmarks to any node. The library (tools/roadmap/pins.py), the `fy roadmap pin|unpin|pins`
commands and the three server endpoints. Pins are not roadmap state: nothing derives from them, and the file is gitignored. Every test
works in a temporary root; no test touches a real clone's roadmap/.pins.json.

Run from the repo root:
    python -m pytest tests/test_roadmap_pins.py
"""
import json
import subprocess
from pathlib import Path

import pytest
from rmhelp import REPO, leaf, make

import roadmap
from roadmap import cli, pins, render, server

PORT = 8765
HOST = {"Host": f"127.0.0.1:{PORT}"}
NODES = {
    "rm.root": {"title": "Freyja walks"},
    "rm.a": leaf("rm.root", title="Cable routed", done=True),
    "rm.b": leaf("rm.root", title="Elbow selected", blocked_by=["rm.a"]),
    "rm.c": leaf("rm.root", title="Battery chosen"),
}


@pytest.fixture()
def root(tmp_path):
    return make(tmp_path / "r", NODES)


def pins_file(root):
    return root / "roadmap" / ".pins.json"


def run(args, root):
    out = []
    code = cli.main(list(args) + ["--root", str(root)], say=out.append)
    return code, "\n".join(out)


# ---- the library

def test_no_file_means_no_pins(root):
    assert pins.load(root) == [] and not pins_file(root).exists()


def test_add_writes_a_sorted_deduplicated_list_deterministically(root):
    assert pins.add(root, "rm.c") is True
    assert pins.add(root, "rm.a") is True
    assert pins.add(root, "rm.c") is False  # already pinned
    text = pins_file(root).read_text(encoding="utf-8")
    assert json.loads(text) == ["rm.a", "rm.c"] and text.endswith("\n") and "\r" not in text
    before = pins_file(root).read_bytes()
    pins.add(root, "rm.a")
    assert pins_file(root).read_bytes() == before


def test_remove_is_idempotent(root):
    pins.add(root, "rm.a")
    assert pins.remove(root, "rm.a") is True and pins.remove(root, "rm.a") is False
    assert pins.load(root) == []


def test_a_corrupt_file_is_an_error_and_is_never_overwritten(root):
    pins_file(root).write_text("{not json", encoding="utf-8")
    with pytest.raises(pins.PinsError):
        pins.load(root)
    with pytest.raises(pins.PinsError):
        pins.add(root, "rm.a")
    assert pins_file(root).read_text(encoding="utf-8") == "{not json"
    pins_file(root).write_text('{"a": 1}', encoding="utf-8")  # valid JSON, wrong shape
    with pytest.raises(pins.PinsError):
        pins.load(root)
    pins_file(root).write_text('["rm.a", 3]', encoding="utf-8")
    with pytest.raises(pins.PinsError):
        pins.load(root)


def test_the_pins_file_is_gitignored():
    p = subprocess.run(["git", "check-ignore", "-q", "roadmap/.pins.json"], cwd=REPO)
    assert p.returncode == 0


def test_pins_do_not_change_anything_the_roadmap_derives(root):
    before = render.state_json_text(roadmap.compute(root))
    pins.add(root, "rm.b")
    assert render.state_json_text(roadmap.compute(root)) == before


# ---- the CLI

def test_pin_and_unpin_resolve_queries_like_show(root):
    code, out = run(["pin", "elbow"], root)
    assert code == 0 and "pinned rm.b" in out and pins.load(root) == ["rm.b"]
    code, out = run(["pin", "rm.b"], root)
    assert code == 0 and "already pinned" in out
    code, out = run(["unpin", "e"], root)  # "e" matches several nodes by substring: ambiguous, and nothing changes
    assert code == 1 and pins.load(root) == ["rm.b"]
    code, out = run(["unpin", "elbow"], root)
    assert code == 0 and "unpinned rm.b" in out and pins.load(root) == []
    code, out = run(["unpin", "elbow"], root)
    assert code == 0 and "was not pinned" in out
    code, out = run(["pin", "zzzzzz"], root)
    assert code == 1 and "no node matches" in out and pins.load(root) == []


def test_pins_lists_status_and_marks_dangling_ids_instead_of_dropping_them(root):
    pins.add(root, "rm.c")
    pins.add(root, "rm.a")
    pins.add(root, "rm.gone")  # a node that no longer exists
    code, out = run(["pins"], root)
    lines = out.splitlines()
    assert code == 0 and [l.split()[0] for l in lines] == ["rm.a", "rm.c", "rm.gone"]
    assert "done" in lines[0] and "Cable routed" in lines[0] and "ready" in lines[1] and "dangling" in lines[2].lower()
    code, out = run(["pins", "--json"], root)
    rows = json.loads(out)
    assert [r["id"] for r in rows] == ["rm.a", "rm.c", "rm.gone"]
    assert rows[0]["status"] == "done" and rows[0]["title"] == "Cable routed" and rows[2] == {"id": "rm.gone", "status": "dangling", "title": None}


def test_a_dangling_pin_can_be_unpinned_by_its_exact_id(root):
    pins.add(root, "rm.gone")
    code, out = run(["unpin", "rm.gone"], root)
    assert code == 0 and pins.load(root) == []


def test_pins_with_none_says_so(root):
    code, out = run(["pins"], root)
    assert code == 0 and "no pins" in out
    assert json.loads(run(["pins", "--json"], root)[1]) == []


def test_a_corrupt_pins_file_is_reported_by_the_cli_with_exit_1(root):
    pins_file(root).write_text("nope", encoding="utf-8")
    code, out = run(["pins"], root)
    assert code == 1 and ".pins.json" in out
    code, out = run(["pin", "cable"], root)
    assert code == 1 and pins_file(root).read_text(encoding="utf-8") == "nope"


# ---- the server

def app_for(root, tmp_path):
    viewer = tmp_path / "viewer"
    viewer.mkdir(exist_ok=True)
    (viewer / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return server.App(root, token="tok123", port=PORT, viewer_dir=viewer, opener=lambda p: None)


@pytest.fixture()
def app(root, tmp_path):
    return app_for(root, tmp_path)


def get(app, target, headers=None):
    return app.handle("GET", target, {**HOST, **(headers or {})})


def post(app, target, headers=None):
    return app.handle("POST", target, {**HOST, "Origin": f"http://127.0.0.1:{PORT}", "X-Roadmap-Token": "tok123", **(headers or {})})


def test_get_pins_returns_the_sorted_ids(app, root):
    assert get(app, "/api/pins").json() == {"pins": []}
    pins.add(root, "rm.c")
    pins.add(root, "rm.a")
    r = get(app, "/api/pins")
    assert r.status == 200 and r.json() == {"pins": ["rm.a", "rm.c"]} and r.headers["Cache-Control"] == "no-store"


def test_a_pin_round_trip_through_the_api_writes_only_the_pins_file(app, root):
    def tree():
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
    before = tree()
    r = post(app, "/api/pin/rm.b")
    assert r.status == 200 and r.json() == {"pins": ["rm.b"]}
    assert pins.load(root) == ["rm.b"]
    assert post(app, "/api/pin/rm.a").json() == {"pins": ["rm.a", "rm.b"]}
    assert get(app, "/api/pins").json() == {"pins": ["rm.a", "rm.b"]}
    r = post(app, "/api/unpin/rm.b")
    assert r.status == 200 and r.json() == {"pins": ["rm.a"]}
    post(app, "/api/unpin/rm.a")
    after = tree()
    assert set(after) - set(before) == {"roadmap/.pins.json"} and {k: v for k, v in after.items() if k != "roadmap/.pins.json"} == before


def test_pin_and_unpin_are_idempotent(app):
    assert post(app, "/api/pin/rm.a").json() == post(app, "/api/pin/rm.a").json() == {"pins": ["rm.a"]}
    assert post(app, "/api/unpin/rm.a").json() == post(app, "/api/unpin/rm.a").json() == {"pins": []}


@pytest.mark.parametrize("verb", ["pin", "unpin"])
def test_foreign_requests_are_rejected_and_change_nothing(app, root, verb):
    pins.add(root, "rm.a")
    before = pins_file(root).read_bytes()
    assert post(app, f"/api/{verb}/rm.b", {"X-Roadmap-Token": "wrong"}).status == 403
    assert app.handle("POST", f"/api/{verb}/rm.b", {**HOST, "Origin": f"http://127.0.0.1:{PORT}"}).status == 403  # no token
    assert post(app, f"/api/{verb}/rm.b", {"Origin": "http://evil.example"}).status == 403
    assert post(app, f"/api/{verb}/rm.b", {"Origin": f"http://127.0.0.1:{PORT + 1}"}).status == 403
    assert app.handle("POST", f"/api/{verb}/rm.b", {"Host": "evil.example", "X-Roadmap-Token": "tok123"}).status == 403  # DNS rebinding
    assert get(app, f"/api/{verb}/rm.b").status == 405
    assert pins_file(root).read_bytes() == before


def test_pin_accepts_only_ids_in_the_loaded_graph(app, root):
    for bad in ("rm.nope", "..%2f..%2fCONVENTIONS.md", "rm.a%0a", "RM.A", "rm.a/../b", ""):
        assert post(app, f"/api/pin/{bad}").status == 404, bad
    assert not pins_file(root).exists()


def test_unpin_accepts_a_graph_id_or_an_id_already_pinned_but_nothing_else(app, root):
    pins.add(root, "rm.gone")  # dangling: not in the graph, but pinned, so it can be cleared
    assert post(app, "/api/unpin/rm.other").status == 404
    assert post(app, "/api/unpin/..%2fx").status == 404
    r = post(app, "/api/unpin/rm.gone")
    assert r.status == 200 and r.json() == {"pins": []}


def test_pins_survive_a_roadmap_change_and_a_pin_to_a_removed_node_dangles(app, root):
    post(app, "/api/pin/rm.c")
    (root / "roadmap" / "nodes" / "rm.c.md").unlink()
    assert get(app, "/api/pins").json() == {"pins": ["rm.c"]}  # listed, never silently dropped
    assert post(app, "/api/pin/rm.c").status == 404  # but it cannot be pinned again


def test_a_corrupt_pins_file_is_a_500_with_a_message_and_is_not_overwritten(app, root):
    pins_file(root).write_text("nope", encoding="utf-8")
    assert get(app, "/api/pins").status == 500 and "pins" in get(app, "/api/pins").json()["error"].lower()
    assert post(app, "/api/pin/rm.a").status == 500
    assert pins_file(root).read_text(encoding="utf-8") == "nope"


def test_the_server_module_documents_the_pins_file_as_its_one_write():
    text = (REPO / "tools" / "roadmap" / "server.py").read_text(encoding="utf-8")
    assert "roadmap/.pins.json" in text.split('"""', 2)[1]
