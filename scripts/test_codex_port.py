#!/usr/bin/env python3
"""End-to-end mocked validation for the Codex Legal port.

Covers:
- every managed-agent cookbook/subagent compiles to Responses-compatible tools;
- the Responses boundary works through an HTTP mock, including a tool round-trip;
- every repository MCP integration is exercised against a mock MCP JSON-RPC server.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import codex_managed_agents as cma  # noqa: E402
import install_codex_mcp as mcp_install  # noqa: E402


def _json_response(handler: BaseHTTPRequestHandler, body: dict[str, Any], status: int = 200) -> None:
    raw = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class ResponsesMockHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []
    lock = threading.Lock()
    tool_round_tripped = False

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/responses":
            _json_response(self, {"error": "not found"}, 404)
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        with self.lock:
            self.requests.append(payload)

        model = str(payload.get("model") or "")
        if not model or "claude" in model.lower():
            _json_response(self, {"error": "Claude model leaked into Codex request"}, 400)
            return

        for tool in payload.get("tools") or []:
            t = tool.get("type")
            if t in {"mcp_toolset", "agent_toolset_20260401"}:
                _json_response(self, {"error": f"Anthropic tool leaked: {t}"}, 400)
                return
            if t == "mcp" and not (tool.get("server_label") and tool.get("server_url")):
                _json_response(self, {"error": "invalid MCP tool"}, 400)
                return

        if not payload.get("previous_response_id") and not self.tool_round_tripped:
            load_skill = next(
                (t for t in payload.get("tools") or [] if t.get("name") == "load_legal_skill"),
                None,
            )
            if load_skill:
                enum = load_skill["parameters"]["properties"]["name"]["enum"]
                self.__class__.tool_round_tripped = True
                _json_response(
                    self,
                    {
                        "id": "resp_tool_1",
                        "output": [
                            {
                                "type": "function_call",
                                "call_id": "call_load_skill",
                                "name": "load_legal_skill",
                                "arguments": json.dumps({"name": enum[0]}),
                            }
                        ],
                    },
                )
                return

        _json_response(
            self,
            {
                "id": f"resp_{len(self.requests)}",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "mock-ok"}],
                    }
                ],
            },
        )


class McpMockHandler(BaseHTTPRequestHandler):
    calls: dict[str, set[str]] = defaultdict(set)
    lock = threading.Lock()

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        req = json.loads(self.rfile.read(length))
        slug = self.path.strip("/")
        method = str(req.get("method") or "")
        with self.lock:
            self.calls[slug].add(method)

        request_id = req.get("id")
        if method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": f"mock-{slug}", "version": "1.0"},
            }
        elif method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "ping",
                        "description": f"Mock ping for {slug}",
                        "inputSchema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"value": {"type": "string"}},
                        },
                    }
                ]
            }
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": f"mock-ok:{slug}"}],
                "isError": False,
            }
        else:
            _json_response(
                self,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"unknown method {method}"},
                },
            )
            return

        _json_response(self, {"jsonrpc": "2.0", "id": request_id, "result": result})


def start_server(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def rpc(url: str, method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def validate_cookbooks() -> tuple[list[cma.AgentSpec], set[str]]:
    slugs = cma.all_cookbook_slugs()
    if len(slugs) != 5:
        raise AssertionError(f"expected 5 managed-agent cookbooks, got {slugs}")

    roots = [cma.load_cookbook(slug) for slug in slugs]
    compiled = [agent for root in roots for agent in root.all_agents()]
    source_files = sorted(cma.COOKBOOKS.glob("*/agent.yaml")) + sorted(cma.COOKBOOKS.glob("*/subagents/*.yaml"))
    compiled_paths = {agent.source_path.resolve() for agent in compiled}
    source_paths = {p.resolve() for p in source_files}
    if compiled_paths != source_paths:
        missing = sorted(str(p.relative_to(ROOT)) for p in source_paths - compiled_paths)
        extra = sorted(str(p.relative_to(ROOT)) for p in compiled_paths - source_paths)
        raise AssertionError(f"managed-agent coverage mismatch missing={missing} extra={extra}")

    mcp_labels: set[str] = set()
    for agent in compiled:
        if "claude" in agent.model.lower():
            raise AssertionError(f"{agent.name}: Claude model leaked")
        if agent.output_schema:
            jsonschema.Draft202012Validator.check_schema(agent.output_schema)
        payload = cma.response_payload(agent, {"mock": True})
        raw = json.dumps(payload)
        if "agent_toolset_20260401" in raw or "mcp_toolset" in raw:
            raise AssertionError(f"{agent.name}: Anthropic tool shape leaked")
        for tool in payload["tools"]:
            if tool["type"] == "mcp":
                mcp_labels.add(tool["server_label"])

    return roots, mcp_labels


def validate_responses_mock(roots: list[cma.AgentSpec]) -> None:
    ResponsesMockHandler.requests = []
    ResponsesMockHandler.tool_round_tripped = False
    server, base_url = start_server(ResponsesMockHandler)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            client = cma.ResponsesHTTPClient(base_url=base_url, api_key="mock")
            runner = cma.AgentRunner(client, Path(tmp))
            for root in roots:
                result = runner.run(root, {"task": "mock smoke test"})
                if result != "mock-ok":
                    raise AssertionError(f"{root.name}: unexpected mock result {result!r}")
    finally:
        server.shutdown()
        server.server_close()

    if not ResponsesMockHandler.tool_round_tripped:
        raise AssertionError("Responses mock never exercised a function-call round-trip")
    if not any(req.get("previous_response_id") for req in ResponsesMockHandler.requests):
        raise AssertionError("Responses mock never received a continuation request")


def validate_all_mcp_mocks() -> int:
    servers = mcp_install.discover(ROOT)
    if len(servers) != 20:
        raise AssertionError(f"expected 20 unique repository MCP servers, got {len(servers)}")

    McpMockHandler.calls = defaultdict(set)
    httpd, base_url = start_server(McpMockHandler)
    try:
        for i, server in enumerate(servers, 1):
            url = f"{base_url}/{server.name}"
            init = rpc(
                url,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "codex-legal-test", "version": "1.0"},
                },
                i * 10,
            )
            if init.get("result", {}).get("serverInfo", {}).get("name") != f"mock-{server.name}":
                raise AssertionError(f"{server.name}: bad initialize response")
            tools = rpc(url, "tools/list", {}, i * 10 + 1)
            if tools.get("result", {}).get("tools", [{}])[0].get("name") != "ping":
                raise AssertionError(f"{server.name}: tools/list failed")
            called = rpc(
                url,
                "tools/call",
                {"name": "ping", "arguments": {"value": server.name}},
                i * 10 + 2,
            )
            text = called.get("result", {}).get("content", [{}])[0].get("text")
            if text != f"mock-ok:{server.name}":
                raise AssertionError(f"{server.name}: tools/call failed")
    finally:
        httpd.shutdown()
        httpd.server_close()

    expected = {s.name for s in servers}
    if set(McpMockHandler.calls) != expected:
        raise AssertionError("not every MCP server was exercised")
    for name, methods in McpMockHandler.calls.items():
        if methods != {"initialize", "tools/list", "tools/call"}:
            raise AssertionError(f"{name}: incomplete MCP mock coverage: {methods}")
    return len(servers)


def main() -> int:
    roots, managed_mcp = validate_cookbooks()
    validate_responses_mock(roots)
    mcp_count = validate_all_mcp_mocks()
    summary = cma.validate_all()
    print(
        "Codex Legal mocked E2E OK: "
        f"{summary['cookbooks']} cookbooks, "
        f"{summary['agents']} managed agents, "
        f"{summary['skills_referenced']} referenced skills, "
        f"{mcp_count}/{mcp_count} MCP integrations mocked, "
        f"{len(managed_mcp)} MCP labels used by managed-agent leaves, "
        "Responses API boundary mocked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
