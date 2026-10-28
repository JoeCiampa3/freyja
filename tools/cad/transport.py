"""The transport to Fusion (Stage 3b, gate G1): the official Autodesk Fusion MCP server on localhost, over plain HTTP (JSON-RPC at /mcp, session id in a header).

Every bridge operation is a function of the repo's Fusion-side module (`cad/fusion_addin/bridge.py`), invoked through the server's `fusion_mcp_execute`
`script` tool. `call(verb, args)` sends a short script that imports the module from the repo path and prints the verb's JSON result; nothing else is
ever sent. The port is a per-machine setting (`FUSION_MCP_PORT`, default 27182).
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADDIN = REPO / "cad" / "fusion_addin"
DEFAULT_PORT = 27182
TIMEOUT_S = 120
READ_ONLY_VERBS = frozenset({"doc_info", "read_params", "capture", "physical_properties", "export_stl", "export_step", "max_curvature_radius", "timeline_health"})
_MARK = "FREYJA-BRIDGE-RESULT "

_SCRIPT = '''import sys, json
sys.path.insert(0, {addin!r})
import importlib
import {module}
importlib.reload({module})

def run(_context: str):
    result = {module}.{verb}(**json.loads({args!r}))
    text = json.dumps(result, sort_keys=True)
    with open({out!r}, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        print({mark!r} + text)
    except RecursionError:
        pass            # Fusion's stdout capture can fail after the file is written (memo 42); the file is the result
'''


class FusionError(RuntimeError):
    """The server was unreachable, refused the call, or the script raised."""


def url() -> str:
    return f"http://127.0.0.1:{int(os.environ.get('FUSION_MCP_PORT', DEFAULT_PORT))}/mcp"


class Session:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or url()
        self.sid = None
        self._id = 0

    def _post(self, body: dict) -> tuple:
        headers = {"Content-Type": "application/json"}
        if self.sid:
            headers["MCP-Session-Id"] = self.sid
        req = urllib.request.Request(self.endpoint, json.dumps(body).encode("utf-8"), headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return r.headers.get("MCP-Session-Id"), r.read().decode("utf-8")
        except OSError as e:
            raise FusionError(f"cannot reach the Fusion MCP server at {self.endpoint}: {e}") from e

    def open(self):
        self.sid, _ = self._post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "freyja-fy-cad", "version": "1"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def tools(self) -> list:
        return self._rpc("tools/list", {})["tools"]

    def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        _, text = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        doc = json.loads(text)
        if "error" in doc:
            raise FusionError(f"{method}: {doc['error']}")
        return doc["result"]

    def tool(self, name: str, arguments: dict) -> dict:
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        text = "".join(c.get("text", "") for c in res.get("content", []))
        try:
            body = json.loads(text)
        except ValueError:
            body = {"message": text}
        if res.get("isError") or body.get("success") is False:
            raise FusionError(body.get("message") or body.get("error") or text)
        return body

    def script(self, source: str, read_only: bool) -> str:
        body = self.tool("fusion_mcp_execute", {"featureType": "script", "object": {"script": source, "readOnly": read_only}})
        return body.get("message", "")


def open_document(session: Session, file_id: str) -> str:
    """Open a document by its id through the server's `document open`. The bridge opens only the two documents it is allowed to: callers pass the id from a
    binding or the fixture's."""
    body = session.tool("fusion_mcp_execute", {"featureType": "document", "object": {"operation": "open", "fileId": file_id}})
    return body.get("message", "")


def build_script(verb: str, args: dict, module: str = "bridge", out: str = "result.json") -> str:
    return _SCRIPT.format(addin=ADDIN.as_posix(), module=module, verb=verb, args=json.dumps(args, sort_keys=True), mark=_MARK, out=out)


def parse_output(text: str):
    """The verb's JSON result from the script's printed output; FusionError when the script printed none."""
    for line in reversed(text.splitlines()):
        if line.startswith(_MARK):
            return json.loads(line[len(_MARK):])
    raise FusionError("the script printed no result: " + text[-500:])


def call(verb: str, args: dict | None = None, session: Session | None = None, module: str = "bridge"):
    """Run a verb of a Fusion-side module (the bridge, or the fixture builder in tests) in Fusion and return its JSON result. A bridge verb in READ_ONLY_VERBS
    runs as a read-only script, which Fusion enforces."""
    s = session or Session().open()
    with tempfile.TemporaryDirectory(prefix="freyja-cad-") as d:
        out_path = (Path(d) / "result.json").as_posix()
        printed = s.script(build_script(verb, args or {}, module, out_path), read_only=module == "bridge" and verb in READ_ONLY_VERBS)
        # The result travels in a file as well as on stdout: the server's output capture stopped returning anything in one T3 session while scripts kept running.
        f = Path(out_path)
        if f.is_file():
            return json.loads(f.read_text(encoding="utf-8"))
    return parse_output(printed)
