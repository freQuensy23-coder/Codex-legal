#!/usr/bin/env python3
"""End-to-end validation against a real Codex CLI and a localhost Responses mock.

No OpenAI model endpoint is contacted. The CLI is forced to a custom provider whose
base_url points to the HTTP server in this process.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import time
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], env: dict[str, str], timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def marketplace_entries() -> list[dict[str, Any]]:
    return json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))["plugins"]


def source_path(entry: dict[str, Any]) -> Path:
    source = entry["source"]
    rel = source if isinstance(source, str) else source["path"]
    return (ROOT / rel).resolve()


def expected_skill_ids() -> list[str]:
    result: list[str] = []
    for entry in marketplace_entries():
        plugin = entry["name"]
        src = source_path(entry)
        for skill_md in sorted((src / "skills").glob("*/SKILL.md")) if (src / "skills").exists() else []:
            result.append(f"{plugin}:{skill_md.parent.name}")
    return result


def agent_files(codex_home: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for p in sorted((codex_home / "agents").glob("*.toml")):
        text = p.read_text(encoding="utf-8")
        if not text.startswith("# generated-from-claude-for-legal:"):
            continue
        data = tomllib.loads(text)
        result[data["name"]] = p
    return result


def stringify(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sse(events: list[dict[str, Any]]) -> bytes:
    out: list[str] = []
    for ev in events:
        kind = ev["type"]
        out.append(f"event: {kind}\n")
        out.append("data: " + json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n\n")
    return "".join(out).encode()


def created(resp_id: str) -> dict[str, Any]:
    return {"type": "response.created", "response": {"id": resp_id}}


def completed(resp_id: str) -> dict[str, Any]:
    return {
        "type": "response.completed",
        "response": {
            "id": resp_id,
            "usage": {
                "input_tokens": 0,
                "input_tokens_details": None,
                "output_tokens": 0,
                "output_tokens_details": None,
                "total_tokens": 0,
            },
        },
    }


def message(item_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "response.output_item.done",
        "item": {
            "type": "message",
            "role": "assistant",
            "id": item_id,
            "content": [{"type": "output_text", "text": text}],
        },
    }


def function_call(call_id: str, name: str, arguments: dict[str, Any], namespace: str | None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, separators=(",", ":")),
    }
    if namespace:
        item["namespace"] = namespace
    return {"type": "response.output_item.done", "item": item}


def contains_text(value: Any, needle: str) -> bool:
    return needle in stringify(value)


def find_spawn_tool(body: dict[str, Any]) -> tuple[str | None, dict[str, Any]] | None:
    for tool in body.get("tools", []):
        if not isinstance(tool, dict):
            continue
        if tool.get("name") == "spawn_agent":
            return None, tool
        nested = tool.get("tools")
        if isinstance(nested, list):
            for child in nested:
                if isinstance(child, dict) and child.get("name") == "spawn_agent":
                    return tool.get("name"), child
    return None


class MockState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []
        self.mode = "simple"
        self.role: str | None = None
        self.role_instruction_probe: str | None = None
        self.child_answered = threading.Event()
        self.spawn_namespace: str | None = None
        self.error: str | None = None

    def reset_simple(self) -> None:
        with self.lock:
            self.requests.clear()
            self.mode = "simple"
            self.role = None
            self.role_instruction_probe = None
            self.spawn_namespace = None
            self.error = None
            self.child_answered.clear()

    def reset_spawn(self, role: str, probe: str) -> None:
        with self.lock:
            self.requests.clear()
            self.mode = "spawn"
            self.role = role
            self.role_instruction_probe = probe
            self.spawn_namespace = None
            self.error = None
            self.child_answered.clear()

    def add(self, body: dict[str, Any]) -> None:
        with self.lock:
            self.requests.append(body)


STATE = MockState()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_json(self, status: int, data: Any) -> None:
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_sse(self, events: list[dict[str, Any]]) -> None:
        raw = sse(events)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def do_GET(self) -> None:
        # The custom provider normally uses fallback model metadata, but make an
        # accidental models lookup local as well.
        if self.path.endswith("/models"):
            self._send_json(200, {"data": []})
        else:
            self._send_json(404, {"error": "mock endpoint"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return
        STATE.add(body)

        if not self.path.endswith("/responses"):
            self._send_json(404, {"error": "mock only supports /responses"})
            return

        if STATE.mode == "simple":
            self._send_sse([created("resp-simple"), message("msg-simple", "MOCK_OK"), completed("resp-simple")])
            return

        role = STATE.role
        probe = STATE.role_instruction_probe
        assert role and probe
        body_text = stringify(body)

        # Child requests carry the role's developer instructions. Verify the role
        # config actually became the child config, then answer the child locally.
        if probe in body_text:
            if body.get("model") != "gpt-5.6":
                STATE.error = f"child {role} model was {body.get('model')!r}"
            effort = (body.get("reasoning") or {}).get("effort")
            if effort != "xhigh":
                STATE.error = f"child {role} reasoning effort was {effort!r}"
            self._send_sse([created("resp-child"), message("msg-child", "CHILD_OK"), completed("resp-child")])
            STATE.child_answered.set()
            return

        # First parent request for this role: force Codex itself to call spawn_agent.
        if contains_text(body, f"SPAWN_ROLE:{role}") and not contains_text(body, "function_call_output"):
            found = find_spawn_tool(body)
            if not found:
                STATE.error = f"spawn_agent tool missing while testing {role}"
                self._send_sse([created("resp-no-spawn"), message("msg-no-spawn", "NO_SPAWN"), completed("resp-no-spawn")])
                return
            namespace, _tool = found
            STATE.spawn_namespace = namespace
            args: dict[str, Any] = {"message": "Reply exactly CHILD_OK", "agent_type": role}
            if namespace is None:
                # Multi-agent v2 uses a required task_name.
                args["task_name"] = "child"
            self._send_sse([
                created("resp-parent-spawn"),
                function_call("spawn-1", "spawn_agent", args, namespace),
                completed("resp-parent-spawn"),
            ])
            return

        # Parent follow-up after the tool output. Do not finish the parent until a
        # child Responses request has completed, so a false-positive spawn cannot pass.
        if not STATE.child_answered.wait(timeout=20):
            STATE.error = f"no child Responses request observed for {role}"
        self._send_sse([created("resp-parent-final"), message("msg-parent-final", "PARENT_OK"), completed("resp-parent-final")])


def start_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def codex_base(codex: str, repo: Path) -> list[str]:
    return [
        codex,
        "--strict-config",
        "-c", 'orchestrator.mcp.enabled=false',
        "-C", str(repo),
    ]


def model_overrides(port: int) -> list[str]:
    provider = (
        'model_providers.mock={ name="mock", base_url="http://127.0.0.1:%d/v1", '
        'env_key="MOCK_API_KEY", wire_api="responses" }' % port
    )
    return [
        "-c", 'model_provider="mock"',
        "-c", provider,
        "-m", "gpt-5.6",
        "-c", 'model_reasoning_effort="xhigh"',
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codex", required=True)
    ap.add_argument("--codex-home", required=True, type=Path)
    args = ap.parse_args()
    codex = str(Path(args.codex).resolve())
    codex_home = args.codex_home.resolve()
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    env["MOCK_API_KEY"] = "local-mock-only"
    env.pop("OPENAI_API_KEY", None)

    version = run([codex, "--version"], env).stdout.strip()
    print("codex_version=", version)

    expected_plugins = [entry["name"] for entry in marketplace_entries()]
    plugin_state = json.loads(run([codex, "plugin", "list", "--marketplace", "codex-legal", "--json"], env).stdout)
    installed = {p["name"] for p in plugin_state.get("installed", []) if p.get("enabled", True)}
    missing_plugins = sorted(set(expected_plugins) - installed)
    if missing_plugins:
        raise SystemExit("plugins missing from real Codex: " + ", ".join(missing_plugins))
    print(f"plugins_ok={len(expected_plugins)}")

    # Exhaustive skill resolution: invoke every namespaced skill through Codex's
    # own parser and demand its unique marker in model-visible prompt JSON.
    skills = expected_skill_ids()
    failures: list[str] = []
    base = codex_base(codex, ROOT)
    for index, sid in enumerate(skills, 1):
        marker = f"codex-legal-skill-id: {sid}"
        proc = run(base + ["debug", "prompt-input", f"Use ${sid}. Return only TEST_OK."], env, timeout=45, check=False)
        combined = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0 or marker not in combined:
            failures.append(f"{sid}: rc={proc.returncode}; marker={marker in combined}; tail={combined[-800:]}" )
        if index % 25 == 0 or index == len(skills):
            print(f"skills_checked={index}/{len(skills)}")
    if failures:
        raise SystemExit("skill resolution failures:\n" + "\n".join(failures))
    print(f"skills_ok={len(skills)}")

    agents = agent_files(codex_home)
    if not agents:
        raise SystemExit("no generated Codex legal agents installed")
    for role, path in agents.items():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if data.get("model") != "gpt-5.6" or data.get("model_reasoning_effort") != "xhigh":
            raise SystemExit(f"{role}: model config not GPT-5.6/xhigh")
    print(f"agent_files_ok={len(agents)}")

    server, thread = start_server()
    port = server.server_address[1]
    overrides = model_overrides(port)
    try:
        # One complete skill request through the actual Responses client.
        STATE.reset_simple()
        prompt = "Use $litigation-legal:claim-chart. Do not call tools. Reply exactly MOCK_OK."
        proc = run(base + overrides + ["exec", prompt], env, timeout=90)
        if "MOCK_OK" not in (proc.stdout + proc.stderr):
            raise SystemExit("real codex exec did not return localhost mock response")
        if not STATE.requests:
            raise SystemExit("localhost Responses mock captured no request")
        first = STATE.requests[0]
        if first.get("model") != "gpt-5.6":
            raise SystemExit(f"parent request model mismatch: {first.get('model')!r}")
        if (first.get("reasoning") or {}).get("effort") != "xhigh":
            raise SystemExit(f"parent reasoning effort mismatch: {(first.get('reasoning') or {}).get('effort')!r}")
        if "codex-legal-skill-id: litigation-legal:claim-chart" not in stringify(first):
            raise SystemExit("claim-chart skill marker missing from actual Responses request")
        print("mocked_responses_skill_ok=1")

        # The first parent request must advertise every loaded custom role. This
        # catches role TOMLs that parsed statically but were ignored by Codex.
        tool_blob = stringify(first.get("tools", []))
        missing_roles = sorted(role for role in agents if role not in tool_blob)
        if missing_roles:
            raise SystemExit("Codex spawn_agent schema missing roles: " + ", ".join(missing_roles))
        print(f"agent_discovery_ok={len(agents)}")

        # Spawn every custom role through the real multi-agent tool. The localhost
        # mock verifies each child request actually receives GPT-5.6/xhigh and the
        # role-specific developer instructions.
        for role, path in agents.items():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            instructions = data["developer_instructions"]
            probe = instructions[: min(180, len(instructions))]
            STATE.reset_spawn(role, probe)
            proc = run(
                base + overrides + ["exec", f"SPAWN_ROLE:{role}. Use spawn_agent with exactly that agent_type."],
                env,
                timeout=120,
                check=False,
            )
            if proc.returncode != 0:
                raise SystemExit(
                    f"spawn test failed for {role}: rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
                )
            if STATE.error:
                raise SystemExit(STATE.error)
            if not STATE.child_answered.is_set():
                raise SystemExit(f"spawn test did not complete child request for {role}")
            print(f"agent_spawn_ok={role}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    report = {
        "codex_version": version,
        "plugins": len(expected_plugins),
        "skills": len(skills),
        "agents": len(agents),
        "mock_provider": "127.0.0.1",
        "real_model_requests": 0,
    }
    print("RUNTIME_VALIDATION_OK " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
