#!/usr/bin/env python3
"""Exhaustive real-Codex validation for the local Codex Legal port.

The Codex binary is real. Model traffic is forced to a localhost Responses mock.
Plugin/skill discovery is queried from the real Codex app-server. Every discovered
legal skill is then explicitly invoked by the exact SKILL.md path returned by Codex,
and the mock asserts that the skill's unique marker reached the model-visible input.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

import test_real_codex_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


def base(codex: str) -> list[str]:
    return [
        codex,
        "-c", 'orchestrator.mcp.enabled=false',
        "-C", str(ROOT),
    ]


def read_json_line(proc: subprocess.Popen[str], wanted_id: int, timeout: float = 30.0) -> dict[str, Any]:
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    seen: list[str] = []
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([proc.stdout], [], [], remaining)
        if not ready:
            break
        line = proc.stdout.readline()
        if line == "":
            break
        line = line.strip()
        if not line:
            continue
        seen.append(line)
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == wanted_id:
            return msg
    stderr = ""
    if proc.poll() is not None and proc.stderr is not None:
        stderr = proc.stderr.read()
    raise RuntimeError(
        f"app-server response id={wanted_id} not received; rc={proc.poll()}; "
        f"stdout_tail={seen[-10:]!r}; stderr={stderr[-2000:]!r}"
    )


def send_json(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def list_skills_via_real_codex(codex: str, env: dict[str, str]) -> list[dict[str, Any]]:
    proc = subprocess.Popen(
        base(codex) + ["app-server"],
        cwd=ROOT,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    try:
        send_json(proc, {
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "codex-legal-ci",
                    "title": "Codex Legal CI",
                    "version": "1.0.0",
                }
            },
        })
        init = read_json_line(proc, 1)
        if "error" in init:
            raise RuntimeError(f"app-server initialize failed: {init}")
        send_json(proc, {"method": "initialized"})
        send_json(proc, {
            "id": 2,
            "method": "skills/list",
            "params": {"cwds": [str(ROOT)], "forceReload": True},
        })
        response = read_json_line(proc, 2, timeout=60)
        if "error" in response:
            raise RuntimeError(f"skills/list failed: {response}")
        entries = response.get("result", {}).get("data", [])
        if not entries:
            raise RuntimeError(f"skills/list returned no cwd entries: {response}")
        errors = [err for entry in entries for err in entry.get("errors", [])]
        if errors:
            raise RuntimeError("Codex skills/list parse errors: " + json.dumps(errors, ensure_ascii=False))
        return [skill for entry in entries for skill in entry.get("skills", [])]
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def legal_skills_by_marker(skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    marker_prefix = "codex-legal-skill-id: "
    for skill in skills:
        raw_path = skill.get("path")
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        pos = text.find(marker_prefix)
        if pos == -1:
            continue
        tail = text[pos + len(marker_prefix):]
        sid = tail.split("-->", 1)[0].strip()
        if not sid or ":" not in sid:
            raise RuntimeError(f"malformed Codex Legal marker in {path}: {sid!r}")
        if sid in found:
            raise RuntimeError(f"duplicate discovered Codex Legal skill id: {sid}")
        if not skill.get("enabled", False):
            raise RuntimeError(f"Codex discovered {sid} but marked it disabled")
        if not skill.get("pluginId"):
            raise RuntimeError(f"Codex discovered {sid} without plugin ownership")
        found[sid] = skill
    return found


def assert_request_has_skill(sid: str, requests: list[dict[str, Any]]) -> None:
    marker = f"codex-legal-skill-id: {sid}"
    matching = [req for req in requests if marker in runtime.stringify(req)]
    if not matching:
        raise RuntimeError(f"skill {sid} was not injected into any actual Responses request")
    req = matching[0]
    if req.get("model") != "gpt-5.6":
        raise RuntimeError(f"skill {sid}: model was {req.get('model')!r}, expected gpt-5.6")
    if (req.get("reasoning") or {}).get("effort") != "xhigh":
        raise RuntimeError(
            f"skill {sid}: reasoning effort was {(req.get('reasoning') or {}).get('effort')!r}, expected xhigh"
        )


def collect_items(value: Any, item_type: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("type") == item_type:
            result.append(value)
        for child in value.values():
            result.extend(collect_items(child, item_type))
    elif isinstance(value, list):
        for child in value:
            result.extend(collect_items(child, item_type))
    return result


def compact_spawn_diagnostics(requests: list[dict[str, Any]]) -> str:
    outputs: list[dict[str, Any]] = []
    for request in requests:
        outputs.extend(collect_items(request, "function_call_output"))
    if not outputs:
        return "no function_call_output captured"
    compact: list[dict[str, Any]] = []
    for item in outputs:
        compact.append({
            "call_id": item.get("call_id"),
            "output": item.get("output"),
        })
    return json.dumps(compact, ensure_ascii=False)[:8000]


def invoke_skill(
    codex: str,
    env: dict[str, str],
    overrides: list[str],
    sid: str,
    skill: dict[str, Any],
) -> dict[str, Any]:
    skill_path = skill["path"]
    skill_name = skill["name"]
    runtime.STATE.reset_simple()
    prompt = (
        f"Use [${skill_name}](skill://{skill_path}). "
        "Do not call tools. Reply exactly MOCK_OK."
    )
    proc = runtime.run(base(codex) + overrides + ["exec", prompt], env, timeout=120, check=False)
    if proc.returncode != 0:
        raise SystemExit(
            f"real Codex skill exec failed for {sid}: rc={proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    if "MOCK_OK" not in (proc.stdout + proc.stderr):
        raise SystemExit(f"real Codex skill exec did not return localhost mock response for {sid}")
    assert_request_has_skill(sid, runtime.STATE.requests)
    return runtime.STATE.requests[0]


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

    version = runtime.run([codex, "--version"], env).stdout.strip()
    print("codex_version=", version)

    expected_plugins = [entry["name"] for entry in runtime.marketplace_entries()]
    plugin_state = json.loads(
        runtime.run([codex, "plugin", "list", "--marketplace", "codex-legal", "--json"], env).stdout
    )
    installed = {p["name"] for p in plugin_state.get("installed", []) if p.get("enabled", True)}
    missing_plugins = sorted(set(expected_plugins) - installed)
    if missing_plugins:
        raise SystemExit("plugins missing from real Codex: " + ", ".join(missing_plugins))
    print(f"plugins_ok={len(expected_plugins)}")

    all_skills = list_skills_via_real_codex(codex, env)
    discovered = legal_skills_by_marker(all_skills)
    expected_skill_ids = runtime.expected_skill_ids()
    expected = set(expected_skill_ids)
    actual = set(discovered)
    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SystemExit(f"real Codex skill discovery mismatch; missing={missing}; extra={extra}")
    print(f"skills_list_ok={len(discovered)}")

    agents = runtime.agent_files(codex_home)
    if not agents:
        raise SystemExit("no generated Codex legal agents installed")
    for role, path in agents.items():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if data.get("model") != "gpt-5.6" or data.get("model_reasoning_effort") != "xhigh":
            raise SystemExit(f"{role}: model config not GPT-5.6/xhigh")
    print(f"agent_files_ok={len(agents)}")

    server, thread = runtime.start_server()
    port = server.server_address[1]
    overrides = runtime.model_overrides(port)
    try:
        # Run one real skill first so we can inspect the real parent tool schema
        # before spending minutes on the exhaustive 151-skill pass.
        representative_sid = "litigation-legal:claim-chart"
        first_request = invoke_skill(codex, env, overrides, representative_sid, discovered[representative_sid])
        print("representative_skill_exec_ok=1")

        tool_blob = runtime.stringify(first_request.get("tools", []))
        missing_roles = sorted(role for role in agents if role not in tool_blob)
        if missing_roles:
            raise SystemExit("Codex spawn_agent schema missing roles: " + ", ".join(missing_roles))
        print(f"agent_discovery_ok={len(agents)}")

        # Validate spawning before the expensive exhaustive skill loop. On a real
        # spawn failure report the exact function_call_output returned by Codex.
        for role, path in agents.items():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            instructions = data["developer_instructions"]
            probe = instructions[: min(180, len(instructions))]
            runtime.STATE.reset_spawn(role, probe)
            proc = runtime.run(
                base(codex) + overrides + [
                    "exec",
                    f"SPAWN_ROLE:{role}. Use spawn_agent with exactly that agent_type.",
                ],
                env,
                timeout=150,
                check=False,
            )
            diagnostics = compact_spawn_diagnostics(runtime.STATE.requests)
            if proc.returncode != 0:
                raise SystemExit(
                    f"spawn test failed for {role}: rc={proc.returncode}; tool_output={diagnostics}\n"
                    f"STDOUT:\n{proc.stdout[-4000:]}\nSTDERR:\n{proc.stderr[-4000:]}"
                )
            if runtime.STATE.error:
                raise SystemExit(
                    f"{runtime.STATE.error}; tool_output={diagnostics}; "
                    f"stdout_tail={proc.stdout[-2000:]!r}; stderr_tail={proc.stderr[-2000:]!r}"
                )
            if not runtime.STATE.child_answered.is_set():
                raise SystemExit(
                    f"spawn test did not complete child request for {role}; tool_output={diagnostics}"
                )
            print(f"agent_spawn_ok={role}")

        # Every legal skill is activated through Codex's real explicit skill-path
        # mechanism. This tests discovery, selection, SKILL.md reading and prompt
        # injection rather than merely checking files on disk.
        for index, sid in enumerate(expected_skill_ids, 1):
            invoke_skill(codex, env, overrides, sid, discovered[sid])
            if index % 25 == 0 or index == len(expected_skill_ids):
                print(f"skills_exec_ok={index}/{len(expected_skill_ids)}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    report = {
        "codex_version": version,
        "plugins": len(expected_plugins),
        "skills": len(expected_skill_ids),
        "agents": len(agents),
        "mock_provider": "127.0.0.1",
        "real_model_requests": 0,
    }
    print("RUNTIME_VALIDATION_OK " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
