"""
Roadmap T7: the viewer's server. The application (tools/roadmap/server.py, class App) is driven in-process: App.handle(method, target,
headers) returns a Response, so no socket is opened here (CONVENTIONS section 9: no network access in tests). The thin http.server shell
and the bind address are covered by a text check here and by a manual smoke run reported in the memo.

Run from the repo root:
    python -m pytest tests/test_roadmap_server.py
"""
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
from rmhelp import REPO, leaf, make, write_node

import roadmap
from roadmap import fixture, render, server

INVALID = REPO / "tests" / "fixtures" / "roadmap" / "invalid"
STATE_SCHEMA = json.loads((REPO / "docs" / "schemas" / "roadmap-state-1.schema.json").read_text(encoding="utf-8"))
PORT = 8765
HOST = {"Host": f"127.0.0.1:{PORT}"}
METRIC = {"type": "metric", "record": "records/m.json", "pointer": "/v", "op": ">", "value": 1}

NODES = {
    "rm.root": {"title": "Freyja walks"},
    "rm.a": leaf("rm.root", title="Cable routed", done=True),
    "rm.b": leaf("rm.root", title="Elbow selected", blocked_by=["rm.a"]),
    "rm.m": {**leaf("rm.root", title="Torque measured"), "done_when": METRIC},
}


class Opened(list):
    def __call__(self, path):
        self.append(Path(path))


def app_for(root, tmp_path, **kw):
    viewer = tmp_path / "viewer"
    viewer.mkdir(exist_ok=True)
    (viewer / "index.html").write_text('<!doctype html><meta name="roadmap-token" content="__ROADMAP_TOKEN__"><script src="app.js"></script>', encoding="utf-8")
    (viewer / "app.js").write_text("// app", encoding="utf-8")
    (viewer / "notes.bin").write_bytes(b"\x00")
    kw.setdefault("opener", Opened())
    return server.App(root, token="tok123", port=PORT, viewer_dir=viewer, **kw)


@pytest.fixture()
def root(tmp_path):
    r = make(tmp_path / "r", NODES)
    (r / "records").mkdir()
    (r / "records" / "m.json").write_text('{"v": 0.5}', encoding="utf-8")
    (r / "log").mkdir()
    (r / "log" / "events.log").write_text("touched rm.b today\n", encoding="utf-8")
    return r


@pytest.fixture()
def app(root, tmp_path):
    return app_for(root, tmp_path)


def get(app, target, headers=None):
    return app.handle("GET", target, {**HOST, **(headers or {})})


def post(app, target, headers=None):
    return app.handle("POST", target, {**HOST, "Origin": f"http://127.0.0.1:{PORT}", "X-Roadmap-Token": "tok123", **(headers or {})})


# ---- /api/state

def test_state_is_the_roadmap_state_computed_live_and_validates(app, root):
    r = get(app, "/api/state")
    assert r.status == 200 and r.headers["Content-Type"].startswith("application/json") and r.headers["Cache-Control"] == "no-store"
    st = r.json()
    assert list(jsonschema.Draft202012Validator(STATE_SCHEMA).iter_errors(st)) == []
    rm = roadmap.compute(root)
    want = render.state_dict(rm)
    assert {k: v for k, v in st.items() if k != "_generated"} == {k: v for k, v in want.items() if k != "_generated"}
    assert st["frontier"] == ["rm.b", "rm.m"] and st["nodes"]["rm.m"]["evaluation"]["result"] == "fail"
    assert "not a build output" in st["_generated"] and str(root) not in r.body.decode("utf-8")


def test_a_broken_graph_still_returns_what_parsed_with_the_errors_and_unknown_statuses(tmp_path):
    root = tmp_path / "bad"
    shutil.copytree(INVALID / "parent-cycle", root)
    st = get(app_for(root, tmp_path), "/api/state").json()
    assert st["errors"] and st["errors"][0]["code"] == "parent-cycle" and st["nodes"]
    assert {n["status"] for n in st["nodes"].values()} & {"unknown"}
    assert list(jsonschema.Draft202012Validator(STATE_SCHEMA).iter_errors(st)) == []


def test_an_unparseable_node_file_is_a_problem_and_the_other_nodes_are_still_served(root, tmp_path):
    (root / "roadmap" / "nodes" / "rm.broken.md").write_text("no front matter at all\n", encoding="utf-8")
    st = get(app_for(root, tmp_path), "/api/state").json()
    assert any("rm.broken" in e["message"] for e in st["errors"]) and "rm.a" in st["nodes"]


def test_a_crash_inside_the_library_becomes_an_internal_problem_not_an_error_page(root, tmp_path, monkeypatch):
    monkeypatch.setattr(server.derive, "compute", lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    r = get(app_for(root, tmp_path), "/api/state")
    st = r.json()
    assert r.status == 200 and st["errors"][0]["code"] == "internal" and "boom" in st["errors"][0]["message"] and st["nodes"] == {}
    assert list(jsonschema.Draft202012Validator(STATE_SCHEMA).iter_errors(st)) == []


def test_an_empty_roadmap_is_valid(tmp_path):
    st = get(app_for(tmp_path / "empty", tmp_path), "/api/state").json()
    assert st["nodes"] == {} and st["errors"] == []


# ---- the cache, keyed on file mtimes and sizes

def counting(monkeypatch):
    calls = []
    real = server.derive.compute
    monkeypatch.setattr(server.derive, "compute", lambda r: calls.append(1) or real(r))
    return calls


def test_nothing_is_recomputed_while_no_file_changes(app, monkeypatch):
    calls = counting(monkeypatch)
    first = get(app, "/api/state").body
    for _ in range(5):
        assert get(app, "/api/state").body == first
    assert len(calls) == 1


def test_a_node_edit_a_new_node_a_removed_node_and_a_changed_record_each_recompute(app, root, monkeypatch):
    calls = counting(monkeypatch)
    get(app, "/api/state")
    write_node(root, "rm.a", title="Cable routed and tested", parent="rm.root", estimate_days=1, done_when={"type": "manual"}, signed_off=True)
    assert get(app, "/api/state").json()["nodes"]["rm.a"]["title"] == "Cable routed and tested" and len(calls) == 2
    write_node(root, "rm.c", title="Third", parent="rm.root", estimate_days=1, done_when={"type": "manual"})
    assert "rm.c" in get(app, "/api/state").json()["nodes"] and len(calls) == 3
    (root / "roadmap" / "nodes" / "rm.c.md").unlink()
    assert "rm.c" not in get(app, "/api/state").json()["nodes"] and len(calls) == 4
    (root / "records" / "m.json").write_text('{"v": 5.5}', encoding="utf-8")  # a file a done_when reads, not a node file
    st = get(app, "/api/state").json()
    assert st["nodes"]["rm.m"]["status"] == "done" and len(calls) == 5


def test_a_record_that_appears_later_is_noticed(root, tmp_path, monkeypatch):
    (root / "records" / "m.json").unlink()
    app = app_for(root, tmp_path)
    assert get(app, "/api/state").json()["nodes"]["rm.m"]["evaluation"]["result"] == "unknown"
    (root / "records" / "m.json").write_text('{"v": 9}', encoding="utf-8")
    assert get(app, "/api/state").json()["nodes"]["rm.m"]["status"] == "done"


def test_the_state_version_header_moves_only_with_a_change(app, root):
    v1 = get(app, "/api/state").headers["X-Roadmap-Version"]
    assert get(app, "/api/state").headers["X-Roadmap-Version"] == v1
    (root / "records" / "m.json").write_text('{"v": 7777}', encoding="utf-8")
    assert get(app, "/api/state").headers["X-Roadmap-Version"] != v1


# ---- /api/node/<id>

def test_node_returns_the_body_references_title_and_repo_relative_path(app, root):
    write_node(root, "rm.b", title="Elbow selected", parent="rm.root", estimate_days=1, done_when={"type": "manual"}, blocked_by=["rm.a"], _body="# Notes\nSee **rm.a**.\n")
    r = get(app, "/api/node/rm.b")
    d = r.json()
    assert r.status == 200 and d["id"] == "rm.b" and d["title"] == "Elbow selected" and d["path"] == "roadmap/nodes/rm.b.md"
    assert d["body"].startswith("# Notes") and d["references"]["files"][0]["path"] == "log/events.log" and d["references"]["commits"] == []
    assert str(root) not in r.body.decode("utf-8")


@pytest.mark.parametrize("target", ["/api/node/rm.nope", "/api/node/", "/api/node/../../CONVENTIONS.md", "/api/node/rm.a/extra", "/api/node/RM.A",
                                    "/api/node/rm.a%2f..%2f..", "/api/node/%2e%2e"])
def test_node_404s_for_anything_but_an_id_in_the_loaded_graph(app, target):
    r = get(app, target)
    assert r.status == 404 and "error" in r.json()


# ---- /api/events

def test_events_announce_a_change_and_heartbeat_when_quiet(app, root):
    stream = app.event_stream(interval=0.01, heartbeat_s=0.05, max_seconds=10)
    assert next(stream).startswith(b"retry:")
    (root / "records" / "m.json").write_text('{"v": 123456}', encoding="utf-8")
    chunk = next(stream)
    while chunk.startswith(b":"):  # a heartbeat may precede it
        chunk = next(stream)
    assert chunk.startswith(b"event: changed\ndata: ") and chunk.endswith(b"\n\n")
    assert json.loads(chunk.split(b"data: ")[1])["version"] >= 2
    assert next(stream).startswith(b": ping")


def test_events_end_when_asked_to_stop(app):
    flag = []
    stream = app.event_stream(interval=0.01, heartbeat_s=1, max_seconds=10, should_stop=lambda: bool(flag))
    next(stream)
    flag.append(1)
    assert list(stream) == []


def test_the_events_route_returns_a_stream(app):
    r = get(app, "/api/events")
    assert r.status == 200 and r.headers["Content-Type"] == "text/event-stream" and r.stream is not None and r.body is None


# ---- POST /api/open/<id>

def test_open_requires_the_token_the_origin_and_a_known_id(root, tmp_path):
    opened = Opened()
    app = app_for(root, tmp_path, opener=opened)
    assert post(app, "/api/open/rm.a", {"X-Roadmap-Token": "wrong"}).status == 403
    assert app.handle("POST", "/api/open/rm.a", {**HOST, "Origin": f"http://127.0.0.1:{PORT}"}).status == 403  # no token
    assert post(app, "/api/open/rm.a", {"Origin": "http://evil.example"}).status == 403
    assert post(app, "/api/open/rm.a", {"Origin": f"http://127.0.0.1:{PORT + 1}"}).status == 403
    assert post(app, "/api/open/rm.nope").status == 404
    assert post(app, "/api/open/..%2f..%2fCONVENTIONS.md").status == 404
    assert opened == []
    r = post(app, "/api/open/rm.a")
    assert r.status == 200 and r.json() == {"opened": "roadmap/nodes/rm.a.md"}
    assert opened == [root / "roadmap" / "nodes" / "rm.a.md"]


def test_open_without_an_origin_header_still_needs_the_token(root, tmp_path):
    app = app_for(root, tmp_path)
    ok = app.handle("POST", "/api/open/rm.a", {**HOST, "X-Roadmap-Token": "tok123"})  # a non-browser client such as curl
    assert ok.status == 200


def test_open_never_takes_a_path_from_the_request(root, tmp_path):
    opened = Opened()
    app = app_for(root, tmp_path, opener=opened)
    post(app, "/api/open/rm.a?path=/etc/passwd")
    assert opened == [root / "roadmap" / "nodes" / "rm.a.md"]


def test_get_on_open_and_post_on_state_are_not_allowed(app):
    assert get(app, "/api/open/rm.a").status == 405
    assert post(app, "/api/state").status == 405


def test_an_opener_failure_is_a_500_with_a_message_not_a_crash(root, tmp_path):
    def bad(path):
        raise OSError("no editor")
    r = post(app_for(root, tmp_path, opener=bad), "/api/open/rm.a")
    assert r.status == 500 and "no editor" in r.json()["error"]


# ---- Origin, Host, headers

def test_a_foreign_origin_or_host_is_rejected_on_every_route(app):
    for target in ("/", "/api/state", "/api/node/rm.a", "/api/events", "/app.js"):
        assert get(app, target, {"Origin": "http://evil.example"}).status == 403, target
        assert app.handle("GET", target, {"Host": "evil.example"}).status == 403, target  # DNS rebinding
        assert app.handle("GET", target, {}).status == 403, target
    assert get(app, "/api/state", {"Origin": f"http://127.0.0.1:{PORT}"}).status == 200
    assert get(app, "/api/state", {"Origin": f"http://localhost:{PORT}"}).status == 200


def test_every_response_carries_the_hardening_headers(app):
    for target in ("/", "/api/state", "/api/node/rm.a", "/api/node/rm.nope", "/app.js"):
        h = get(app, target).headers
        assert h["X-Content-Type-Options"] == "nosniff" and h["Referrer-Policy"] == "no-referrer"
        csp = h["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp


# ---- static files

def test_the_page_embeds_the_token_and_other_assets_do_not(app):
    page = get(app, "/")
    assert page.status == 200 and page.headers["Content-Type"].startswith("text/html")
    assert b'content="tok123"' in page.body and b"__ROADMAP_TOKEN__" not in page.body
    assert get(app, "/index.html").body == page.body
    js = get(app, "/app.js")
    assert js.status == 200 and js.headers["Content-Type"].startswith("text/javascript") and b"tok123" not in js.body


@pytest.mark.parametrize("target", ["/../CONVENTIONS.md", "/%2e%2e/CONVENTIONS.md", "/..%2fCONVENTIONS.md", "/.", "/..", "/sub/app.js", "/notes.bin",
                                    "/missing.js", "/app.js/", "//etc/passwd", "/\\app.js", "/app.js%00.html", "/viewer"])
def test_static_serves_only_whitelisted_files_directly_inside_the_viewer_directory(app, target):
    assert get(app, target).status == 404


def test_the_default_viewer_directory_is_inside_the_library():
    d = server.VIEWER_DIR
    assert d == REPO / "tools" / "roadmap" / "viewer" and (d / "index.html").is_file()


# ---- start-up

def test_the_server_binds_loopback_only():
    src = (REPO / "tools" / "roadmap" / "server.py").read_text(encoding="utf-8")
    assert server.HOST == "127.0.0.1" and "0.0.0.0" not in src and '""' not in src.split("ThreadingHTTPServer((")[1].split(",")[0]
    assert "ThreadingHTTPServer((HOST, port)" in src


def test_prepare_builds_the_url_and_resolves_focus_with_the_cli_query_rules(tmp_path):
    root = tmp_path / "f"
    fixture.generate(60, root, seed=1)
    url, focus = server.prepare(root, 8765, None)
    assert url == "http://127.0.0.1:8765/" and focus is None
    url, focus = server.prepare(root, 8765, "n005")
    ids = sorted(roadmap.compute(root).nodes)
    assert focus == next(i for i in ids if "n005" in i) and url == f"http://127.0.0.1:8765/#/node/{focus}"
    with pytest.raises(server.FocusError) as e:
        server.prepare(root, 8765, "zzzz-no-such")
    assert "no node matches" in str(e.value)
    with pytest.raises(server.FocusError) as e:
        server.prepare(root, 8765, "n0")
    assert "matches" in str(e.value)


def test_token_is_random_per_app_and_long_enough(root, tmp_path):
    a = server.App(root, port=PORT, viewer_dir=tmp_path)
    b = server.App(root, port=PORT, viewer_dir=tmp_path)
    assert a.token != b.token and len(a.token) >= 20


def test_the_cli_serve_command_reports_a_bad_focus_without_starting_a_server(tmp_path):
    from roadmap import cli
    root = tmp_path / "f"
    fixture.generate(30, root, seed=2)
    out = []
    assert cli.main(["serve", "--root", str(root), "--focus", "zzz-no-such", "--no-browser"], say=out.append) == 1
    assert "no node matches" in out[0]
    ns = cli._parser().parse_args(["serve", "--port", "9000", "--root", "x", "--focus", "q", "--no-browser"])
    assert (ns.port, ns.focus, ns.no_browser) == (9000, "q", True)
    assert cli._parser().parse_args(["serve"]).port == server.DEFAULT_PORT
