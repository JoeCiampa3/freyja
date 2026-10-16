"""
Roadmap viewer server (docs/briefs/architecture/roadmap-brief1.md, T7). Standard library only. `App` is the application: handle() takes a
method, a request target and the headers and returns a Response, so it is tested without a socket; `Shell` is the thin http.server
adapter around it. The server binds 127.0.0.1 only and has no write path to the repo: its single POST asks the user's editor to open
a node file whose path the library supplies, never the request.

    GET  /                 the viewer page, with this launch's token in a <meta> tag
    GET  /<file>           a whitelisted file directly inside tools/roadmap/viewer/
    GET  /api/state        the roadmap-state/1 content, computed live (cached on file mtimes and sizes)
    GET  /api/node/<id>    the body Markdown, references and file path of a node in the loaded graph
    GET  /api/events       server-sent events; `changed` when a node file or a record a done_when reads changes
    POST /api/open/<id>    open the node file with the T4 editor resolution (token and Origin required)

Every request must carry a Host of this server and, when it has an Origin, an Origin of this server. State requests cost a stat of each
watched file when nothing changed, which is what keeps the first render of a 600-node roadmap under a second.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import derive, editor, query, refs, render
from .evaluate import referenced_files, safe_path
from .model import ID_RE, NODES_DIR

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
VIEWER_DIR = Path(__file__).resolve().parent / "viewer"
POLL_SECONDS = 1.0  # how often an events stream looks at the watched files
HEARTBEAT_SECONDS = 15.0  # an SSE comment line, so that a closed browser tab is noticed by the failing write
TOKEN_HEADER = "x-roadmap-token"
TOKEN_PLACEHOLDER = b"__ROADMAP_TOKEN__"
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
        ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Content-Security-Policy": CSP}
STATIC_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LIVE_BANNER = ("GENERATED live by tools/roadmap serve from roadmap/nodes and the records its done_when criteria read; "
               "not a build output (roadmap/state.json is). Do not edit.")


class FocusError(ValueError):
    """--focus did not resolve to exactly one node."""


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes | None = None
    stream: object = None  # an iterator of bytes, for server-sent events

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def _json(status, obj, **headers) -> Response:
    body = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Response(status, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", **headers}, body)


def _error(status, message) -> Response:
    return _json(status, {"error": message})


@dataclass
class Snapshot:
    rm: object
    body: bytes
    signature: tuple
    watch: list  # (repo-relative name, absolute path) of every file whose change can alter the state


def _stat(path):
    try:
        s = os.stat(path)
        return (s.st_mtime_ns, s.st_size)
    except OSError:
        return None


class Backend:
    """The roadmap under one root, recomputed only when a watched file's mtime or size changes (or a node file appears or goes)."""

    def __init__(self, root):
        self.root = Path(root)
        self.version = 0
        self._snap = None
        self._lock = threading.Lock()

    def _signature(self, watch) -> tuple:
        nodes = self.root / NODES_DIR
        listing = []
        try:
            with os.scandir(nodes) as it:
                for e in it:
                    if e.name.endswith(".md"):
                        st = e.stat()
                        listing.append((e.name, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
        return (tuple(sorted(listing)), tuple((name, _stat(path)) for name, path in watch))

    def _watch_list(self, rm) -> list:
        names = set()
        for n in rm.nodes.values():
            names.update(referenced_files(n))
        out = []
        for name in sorted(names):
            p = safe_path(self.root, name)  # resolved once per snapshot; polling then only stats
            if p is not None:
                out.append((name, str(p)))
        return out

    def _state_body(self, rm) -> bytes:
        return json.dumps(render.state_dict(rm, banner_text=LIVE_BANNER), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def _build(self) -> Snapshot:
        try:
            rm = derive.compute(self.root)
            return Snapshot(rm, self._state_body(rm), (), self._watch_list(rm))
        except Exception as e:  # noqa: BLE001 - a broken edit must show up as a problem, never as a blank page
            body = json.dumps(_internal_state(e), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return Snapshot(None, body, (), [])

    def refresh(self) -> bool:
        """Recompute if the watched files changed. True when it did."""
        prior = self._snap
        watch = prior.watch if prior else []
        sig = self._signature(watch)  # taken before the files are read, so an edit during the compute shows up as a change on the next poll
        with self._lock:
            if self._snap is not None and self._snap.signature == sig:
                return False
            snap = self._build()
            if [n for n, _ in snap.watch] != [n for n, _ in watch]:
                sig = self._signature(snap.watch)  # the first build, or the references changed: the new files can only be stat'ed afterwards
            snap.signature = sig
            self._snap, self.version = snap, self.version + 1
            return True

    def snapshot(self) -> Snapshot:
        self.refresh()
        return self._snap


def _internal_state(e) -> dict:
    return {"_generated": LIVE_BANNER, "generated_by": render.TOOL, "inputs": ["roadmap/nodes/*.md"], "schema": "roadmap-state/1", "node_count": 0,
            "superseded_count": 0, "counts": {}, "frontier": [], "nodes": {}, "warnings": [],
            "errors": [{"code": "internal", "message": f"the roadmap library failed: {e.__class__.__name__}: {e}", "ids": [], "paths": []}]}


class App:
    def __init__(self, root, port=DEFAULT_PORT, token=None, opener=None, viewer_dir=None):
        self.root = Path(root)
        self.port = port
        self.token = token or secrets.token_urlsafe(24)
        self.opener = opener if opener is not None else editor.open_file
        self.viewer_dir = Path(viewer_dir or VIEWER_DIR)
        self.backend = Backend(self.root)

    # ---- request gate
    def _origin_ok(self, headers) -> bool:
        allowed_hosts = {f"{HOST}:{self.port}", f"localhost:{self.port}"}
        if headers.get("host") not in allowed_hosts:
            return False  # a request addressed to anything else (DNS rebinding) is refused
        origin = headers.get("origin")
        return origin is None or origin in {f"http://{h}" for h in allowed_hosts}

    def handle(self, method, target, headers) -> Response:
        h = {str(k).lower(): v for k, v in dict(headers).items()}
        try:
            if not self._origin_ok(h):
                r = _error(403, "forbidden: this server answers only requests addressed to it")
            else:
                r = self._route(method, urlsplit(target).path, h)
        except Exception as e:  # noqa: BLE001
            r = _error(500, f"{e.__class__.__name__}: {e}")
        r.headers = {**SECURITY_HEADERS, **r.headers}
        return r

    def _route(self, method, path, h) -> Response:
        if path.startswith("/api/"):
            return self._api(method, path, h)
        if method != "GET":
            return _error(405, "method not allowed")
        return self._static(path)

    def _api(self, method, path, h) -> Response:
        if path == "/api/state":
            return self._only("GET", method) or self._state()
        if path == "/api/events":
            return self._only("GET", method) or Response(200, {"Content-Type": "text/event-stream", "Cache-Control": "no-store"}, stream=self.event_stream())
        if path.startswith("/api/node/"):
            return self._only("GET", method) or self._node(path[len("/api/node/"):])
        if path.startswith("/api/open/"):
            return self._only("POST", method) or self._open(path[len("/api/open/"):], h)
        return _error(404, "no such endpoint")

    @staticmethod
    def _only(allowed, method):
        return None if method == allowed else _error(405, "method not allowed")

    # ---- endpoints
    def _state(self) -> Response:
        snap = self.backend.snapshot()
        return Response(200, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Roadmap-Version": str(self.backend.version)}, snap.body)

    def _known(self, raw):
        """The id when `raw` (a path segment) names a node in the loaded graph, else None."""
        id = unquote(raw)
        snap = self.backend.snapshot()
        return id if snap.rm is not None and ID_RE.match(id) and id in snap.rm.nodes else None

    def _node(self, raw) -> Response:
        id = self._known(raw)
        if id is None:
            return _error(404, "no such node")
        rm = self.backend.snapshot().rm
        n = rm.nodes[id]
        return _json(200, {"id": id, "title": n.title, "path": n.path, "body": n.body, "references": refs.references(self.root, id)})

    def _open(self, raw, h) -> Response:
        if not hmac.compare_digest(h.get(TOKEN_HEADER, "").encode("utf-8"), self.token.encode("utf-8")):
            return _error(403, "forbidden: missing or wrong token")
        id = self._known(raw)
        if id is None:
            return _error(404, "no such node")
        n = self.backend.snapshot().rm.nodes[id]
        try:
            self.opener(self.root / n.path)
        except Exception as e:  # noqa: BLE001
            return _error(500, f"could not open the editor: {e}")
        return _json(200, {"opened": n.path})

    def _static(self, path) -> Response:
        name = "index.html" if path == "/" else unquote(path)[1:]
        suffix = os.path.splitext(name)[1].lower()
        if not STATIC_NAME.match(name) or name in (".", "..") or suffix not in MIME:
            return _error(404, "not found")
        p = self.viewer_dir / name
        if not p.is_file() or p.parent.resolve() != self.viewer_dir.resolve():
            return _error(404, "not found")
        body = p.read_bytes()
        if name == "index.html":
            body = body.replace(TOKEN_PLACEHOLDER, self.token.encode("ascii"))
        return Response(200, {"Content-Type": MIME[suffix], "Cache-Control": "no-store"}, body)

    # ---- server-sent events
    def event_stream(self, interval=POLL_SECONDS, heartbeat_s=HEARTBEAT_SECONDS, max_seconds=None, should_stop=None):
        """Yield SSE chunks: a retry hint, then `changed` whenever the version moves, and a comment line when quiet. Polls the shared backend."""
        self.backend.snapshot()  # the baseline is taken before the first chunk goes out, so a change after the client connects is never missed
        seen = self.backend.version
        yield b"retry: 3000\n\n"
        start = last = time.monotonic()
        while not (should_stop and should_stop()) and (max_seconds is None or time.monotonic() - start < max_seconds):
            time.sleep(interval)
            if should_stop and should_stop():
                return
            self.backend.refresh()
            if self.backend.version != seen:
                seen = self.backend.version
                last = time.monotonic()
                yield b"event: changed\ndata: " + json.dumps({"version": seen}).encode("ascii") + b"\n\n"
            elif time.monotonic() - last >= heartbeat_s:
                last = time.monotonic()
                yield b": ping\n\n"


# ---- start-up and the http.server shell

def prepare(root, port, focus):
    """(url, focus id). Raises FocusError with the CLI's wording when --focus does not name exactly one node."""
    url = f"http://{HOST}:{port}/"
    if focus is None:
        return url, None
    rm = derive.compute(root)
    status, got = query.resolve(rm, focus)
    if status == "ok":
        return f"{url}#/node/{got}", got
    if status == "ambiguous":
        raise FocusError(f"{focus!r} matches {len(got)} nodes (showing up to {query.MAX_CANDIDATES}); be more specific: " + ", ".join(got))
    raise FocusError(f"no node matches {focus!r}." + (" Close ids: " + ", ".join(got) if got else ""))


class Shell(BaseHTTPRequestHandler):
    app: App = None  # set on the subclass made by make_server
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet: the viewer polls
        pass

    def _serve(self, method):
        r = self.app.handle(method, self.path, dict(self.headers.items()))
        self.send_response(r.status)
        for k, v in r.headers.items():
            self.send_header(k, v)
        if r.stream is not None:
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for chunk in r.stream:
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionError, OSError):
                pass
            self.close_connection = True
            return
        body = r.body or b""
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")


def make_server(app: App, port) -> ThreadingHTTPServer:
    shell = type("BoundShell", (Shell,), {"app": app})
    srv = ThreadingHTTPServer((HOST, port), shell)
    srv.daemon_threads = True
    app.port = srv.server_address[1]
    return srv


def serve(root, port=DEFAULT_PORT, focus=None, browser=True, say=print, opener=None) -> int:
    root = Path(root)
    try:
        url, focus_id = prepare(root, port, focus)
    except FocusError as e:
        say(f"serve: {e}")
        return 1
    app = App(root, port=port, opener=opener)
    try:
        srv = make_server(app, port)
    except OSError as e:
        say(f"serve: cannot listen on {HOST}:{port}: {e.strerror or e}. Try --port.")
        return 1
    if app.port != port:  # --port 0 picked a free port
        url = url.replace(f":{port}/", f":{app.port}/")
    app.backend.refresh()  # compute once now, so the first request is served from the cache
    say(f"roadmap viewer: {url}   (Ctrl+C to stop)")
    sys.stdout.flush()  # a piped stdout is block-buffered, and a script waiting for this line would hang
    if browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
