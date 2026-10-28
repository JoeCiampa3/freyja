"""
Stage 3b T3, without Fusion: static properties of the Fusion-side module (gate G2: it never assigns a parameter's `.value`), the generated scripts, the
transport against a fake server, and the tessellation rule.

    python -m pytest tests/test_cad_static.py
"""
import ast
import json
import math
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import mesh as cm  # noqa: E402
from cad import transport  # noqa: E402

ADDIN = REPO / "cad" / "fusion_addin"
BRIDGE = ADDIN / "bridge.py"
# attributes the bridge may assign: a parameter's expression and the STL export options. Never `value`.
ASSIGNABLE = {"expression", "meshRefinement", "surfaceDeviation", "normalDeviation", "isBinaryFormat", "sendToPrintUtility"}
ALLOWED_IMPORTS = {"adsk"}


def attribute_assignments(source: str) -> set:
    """Names of every attribute assigned in the source, including augmented and annotated assignments and setattr with a literal name."""
    out = set()
    for node in ast.walk(ast.parse(source)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Store):
                    out.add(sub.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("setattr", "exec", "eval"):
            out.add(f"<{node.func.id}>")
    return out


def test_no_fusion_side_module_assigns_a_value():
    for p in sorted(ADDIN.glob("*.py")):
        assert "value" not in attribute_assignments(p.read_text(encoding="utf-8")), p.name


def test_the_bridge_never_assigns_a_value():
    assigned = attribute_assignments(BRIDGE.read_text(encoding="utf-8"))
    assert "value" not in assigned
    assert assigned <= ASSIGNABLE, sorted(assigned - ASSIGNABLE)


@pytest.mark.parametrize("bad", [
    "p.value = 3.0",
    "p.value += 1",
    "obj.param.value: float = 2",
    "a.b.value = c",
    "setattr(p, 'value', 3)",
    "for p in ps:\n    p.value = 1",
])
def test_the_static_check_catches_a_value_assignment(bad):
    got = attribute_assignments(bad)
    assert "value" in got or "<setattr>" in got


def test_the_static_check_lets_an_expression_through():
    assert attribute_assignments("p.expression = '3 mm'") == {"expression"}


def test_the_fusion_side_modules_import_only_adsk_and_the_standard_library():
    stdlib = set(sys.stdlib_module_names)
    for p in sorted(ADDIN.glob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                assert m.split(".")[0] in stdlib | ALLOWED_IMPORTS, (p.name, m)


def test_only_the_write_verbs_set_expressions():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    writers = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
               and any(isinstance(n, ast.Attribute) and n.attr == "expression" and isinstance(n.ctx, ast.Store) for n in ast.walk(f))}
    assert writers == {"_set"}
    callers = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
               and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_set" for n in ast.walk(f))}
    assert callers == {"set_expressions", "restore"}


def test_the_bridge_carries_no_unit_factor():
    text = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert not (nums & {10, 10.0, 100, 100.0, 1000, 1000.0, 0.1, 0.01, 0.001, 180, 180.0}), nums & {10, 100, 1000, 0.1, 0.01, 0.001, 180}
    assert "math" not in text


def test_every_read_only_verb_is_a_verb_of_the_module_and_the_write_verbs_are_not_read_only():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    verbs = {f.name for f in tree.body if isinstance(f, ast.FunctionDef) and not f.name.startswith("_")}
    assert transport.READ_ONLY_VERBS <= verbs
    assert {"set_expressions", "restore", "save_document"} <= verbs and not ({"set_expressions", "restore", "save_document"} & transport.READ_ONLY_VERBS)


# ---- the generated script and the transport --------------------------------------------------------------------------------------------

def test_the_generated_script_is_valid_python_with_a_run_entry_and_no_other_payload():
    src = transport.build_script("set_expressions", {"expressions": {"in_x": "5 mm"}, "expect_name": "n'a\"me"})
    tree = ast.parse(src)
    assert [f.name for f in tree.body if isinstance(f, ast.FunctionDef)] == ["run"]
    assert "bridge.set_expressions(**json.loads(" in src and "'result.json'" in src and "cad/fusion_addin" in src


def test_the_printed_result_is_parsed_from_the_last_marked_line():
    out = "noise\n" + transport._MARK + '{"a": 1}\nmore noise\n'
    assert transport.parse_output(out) == {"a": 1}
    with pytest.raises(transport.FusionError):
        transport.parse_output("no marker here")


class _FakeFusion(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeFusion.calls.append((body.get("method"), self.headers.get("MCP-Session-Id"), body.get("params")))
        if "id" not in body:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if body["method"] == "initialize":
            result = {"capabilities": {}, "protocolVersion": "2025-03-26"}
        elif body["method"] == "tools/list":
            result = {"tools": [{"name": "fusion_mcp_execute"}]}
        else:
            args = body["params"]["arguments"]
            printed = transport._MARK + json.dumps({"echo": args["object"]["readOnly"]}) + "\n"
            result = {"content": [{"type": "text", "text": json.dumps({"message": printed, "success": True})}]}
        out = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("MCP-Session-Id", "sid-1")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def test_the_transport_speaks_the_protocol_and_marks_read_only_verbs():
    srv = HTTPServer(("127.0.0.1", 0), _FakeFusion)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        _FakeFusion.calls.clear()
        s = transport.Session(f"http://127.0.0.1:{srv.server_port}/mcp").open()
        assert transport.call("read_params", {}, session=s) == {"echo": True}
        assert transport.call("set_expressions", {"expressions": {}}, session=s) == {"echo": False}
        methods = [c[0] for c in _FakeFusion.calls]
        assert methods[:2] == ["initialize", "notifications/initialized"]
        assert all(c[1] == "sid-1" for c in _FakeFusion.calls[1:])
    finally:
        srv.shutdown()


def test_an_unreachable_server_is_a_fusion_error():
    with pytest.raises(transport.FusionError, match="cannot reach"):
        transport.Session("http://127.0.0.1:1/mcp").open()


# ---- tessellation ----------------------------------------------------------------------------------------------------------------------

def test_the_normal_deviation_keeps_the_chord_error_of_the_largest_arc_within_the_tolerance():
    for r in (5.0, 15.0, 46.0, 120.0):
        theta = cm.normal_deviation_deg(0.05, r)
        sagitta = r * (1 - math.cos(math.radians(theta) / 2))
        assert sagitta <= 0.05 + 1e-12 or theta == cm.MIN_NORMAL_DEG
    assert cm.normal_deviation_deg(0.05, 15.0) == pytest.approx(9.3590, abs=1e-3)   # 4 asin(sqrt(0.05 / 30)), by hand: 2 * 2 * 2.3398 deg
    assert cm.normal_deviation_deg(0.05, None) == cm.MAX_NORMAL_DEG                    # no analytic arc: Fusion's default
    assert cm.normal_deviation_deg(0.05, 0.02) == cm.MAX_NORMAL_DEG                    # an arc smaller than the tolerance
    assert cm.normal_deviation_deg(0.05, 1e6) == cm.MIN_NORMAL_DEG                     # clamped, the mesh stays small


def test_a_broken_tessellation_rule_fails_the_known_answer(monkeypatch):
    monkeypatch.setattr(cm.math, "degrees", lambda x: x)  # mutation: radians left unconverted
    assert cm.normal_deviation_deg(0.05, 15.0) != pytest.approx(9.3590, abs=1e-3)
