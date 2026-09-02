#!/usr/bin/env python3
"""Codex-native runtime/compiler for Claude for Legal managed-agent cookbooks.

The upstream cookbooks target Anthropic Managed Agents. This module preserves
their orchestration, tool scoping, skills, MCP declarations, subagents, and
structured-output contracts while targeting the OpenAI Responses API boundary.

Live OpenAI calls are optional. Tests use a mock /v1/responses endpoint.
"""

from __future__ import annotations

import argparse
import fnmatch
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
COOKBOOKS = ROOT / "managed-agent-cookbooks"
DEFAULT_MODEL = os.environ.get("CODEX_LEGAL_MODEL", "gpt-5.6-sol")
ENV_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
SAFE_ENV_VALUE = re.compile(r"^[A-Za-z0-9._/:@?&=%+-]+$")
LOCAL_TOOL_NAMES = {"read", "grep", "glob", "write", "edit", "web_fetch"}
MCP_ALIASES = {
    "gdrive": "google-drive",
    "google_drive": "google-drive",
    "court-listener": "courtlistener",
}


def slugify(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-_").lower()
    if not value:
        raise ValueError(f"cannot slugify {name!r}")
    return value


def substitute_env(text: str, *, strict: bool = False) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = os.environ.get(key)
        if value is None:
            if strict:
                raise ValueError(f"missing environment variable {key}")
            return match.group(0)
        if not SAFE_ENV_VALUE.fullmatch(value):
            raise ValueError(f"unsafe value for {key}")
        return value
    return ENV_RE.sub(repl, text)


def source_mcp_registry() -> dict[str, str]:
    registry: dict[str, str] = {}
    for path in sorted(ROOT.glob("**/.mcp.json")):
        if ".git" in path.parts or ".codex" in path.parts:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, raw in (data.get("mcpServers") or {}).items():
            if not isinstance(raw, dict) or not raw.get("url"):
                continue
            key = slugify(str(name))
            url = str(raw["url"])
            if key in registry and registry[key] != url:
                raise ValueError(f"conflicting MCP URL for {key}: {registry[key]} vs {url}")
            registry[key] = url
    return registry


def canonical_mcp_name(name: str) -> str:
    slug = slugify(name)
    return MCP_ALIASES.get(slug, slug)


@dataclass
class McpServer:
    name: str
    url: str
    source_url: str

    def resolved_url(self, registry: dict[str, str]) -> str:
        resolved = substitute_env(self.url)
        if ENV_RE.search(resolved):
            fallback = registry.get(canonical_mcp_name(self.name))
            if fallback:
                return fallback
            missing = ", ".join(sorted(set(ENV_RE.findall(resolved))))
            raise ValueError(f"{self.name}: unresolved MCP URL env vars: {missing}")
        return resolved


@dataclass
class AgentSpec:
    name: str
    source_path: Path
    model: str
    instructions: str
    local_tools: list[str] = field(default_factory=list)
    mcp_tools: list[str] = field(default_factory=list)
    mcp_servers: dict[str, McpServer] = field(default_factory=dict)
    skills: dict[str, Path] = field(default_factory=dict)
    children: dict[str, "AgentSpec"] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None

    def all_agents(self) -> list["AgentSpec"]:
        result = [self]
        for child in self.children.values():
            result.extend(child.all_agents())
        return result


def _system_text(doc: dict[str, Any], manifest: Path) -> str:
    system = doc.get("system", "")
    if isinstance(system, str):
        return system
    if not isinstance(system, dict):
        raise ValueError(f"{manifest}: system must be string or mapping")
    base = manifest.parent
    body = str(system.get("text") or "")
    file_name = system.get("file")
    if file_name:
        path = (base / str(file_name)).resolve()
        if not path.is_file():
            raise ValueError(f"{manifest}: system.file not found: {path}")
        body = path.read_text(encoding="utf-8")
    append = str(system.get("append") or "")
    if append:
        body = body.rstrip() + "\n\n" + append.strip() + "\n"
    return body


def _local_tools(doc: dict[str, Any], manifest: Path) -> list[str]:
    enabled: set[str] = set()
    for entry in doc.get("tools") or []:
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest}: tools entries must be mappings")
        t = str(entry.get("type") or "")
        if not t.startswith("agent_toolset"):
            continue
        default_enabled = bool((entry.get("default_config") or {}).get("enabled", False))
        if default_enabled:
            raise ValueError(
                f"{manifest}: default-enabled Anthropic agent_toolset cannot be safely ported; "
                "enumerate enabled tools explicitly"
            )
        for cfg in entry.get("configs") or []:
            if not isinstance(cfg, dict):
                continue
            name = str(cfg.get("name") or "")
            if bool(cfg.get("enabled", default_enabled)):
                if name not in LOCAL_TOOL_NAMES:
                    raise ValueError(f"{manifest}: unsupported local tool {name!r}")
                enabled.add(name)
    return sorted(enabled)


def _mcp_tool_names(doc: dict[str, Any], manifest: Path) -> list[str]:
    result: set[str] = set()
    for entry in doc.get("tools") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "mcp_toolset":
            name = str(entry.get("mcp_server_name") or "")
            if not name:
                raise ValueError(f"{manifest}: mcp_toolset missing mcp_server_name")
            result.add(slugify(name))
    return sorted(result)


def _mcp_servers(doc: dict[str, Any], manifest: Path) -> dict[str, McpServer]:
    result: dict[str, McpServer] = {}
    for entry in doc.get("mcp_servers") or []:
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest}: mcp_servers entries must be mappings")
        if entry.get("type") not in (None, "url"):
            raise ValueError(f"{manifest}: unsupported MCP declaration {entry.get('type')!r}")
        name = slugify(str(entry.get("name") or ""))
        url = str(entry.get("url") or "")
        if not name or not url:
            raise ValueError(f"{manifest}: MCP server requires name and url")
        result[name] = McpServer(name=name, url=url, source_url=url)
    return result


def _skill_dest_from_source(source: Path) -> tuple[str, Path]:
    source = source.resolve()
    parts = source.parts
    try:
        idx = parts.index("skills")
    except ValueError as exc:
        raise ValueError(f"skill source is not under a skills directory: {source}") from exc
    plugin = parts[idx - 1]
    skill = parts[idx + 1]
    name = f"{plugin}-{skill}"
    dest = ROOT / ".codex" / "skills" / name / "SKILL.md"
    if not dest.is_file():
        raise ValueError(f"converted Codex skill missing for {source}: {dest}")
    return name, dest


def _skills(doc: dict[str, Any], manifest: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    base = manifest.parent
    for entry in doc.get("skills") or []:
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest}: skills entries must be mappings")
        if entry.get("from_plugin"):
            plugin_dir = (base / str(entry["from_plugin"])).resolve()
            for source in sorted(plugin_dir.glob("skills/*/SKILL.md")):
                name, dest = _skill_dest_from_source(source)
                result[name] = dest
        elif entry.get("path"):
            source_dir = (base / str(entry["path"])).resolve()
            source = source_dir / "SKILL.md" if source_dir.is_dir() else source_dir
            name, dest = _skill_dest_from_source(source)
            result[name] = dest
        else:
            raise ValueError(f"{manifest}: unsupported skill declaration: {entry}")
    return result


def load_agent(manifest: Path, *, model: str | None = None) -> AgentSpec:
    manifest = manifest.resolve()
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{manifest}: expected mapping")
    name = slugify(str(doc.get("name") or manifest.stem))
    servers = _mcp_servers(doc, manifest)
    mcp_tools = _mcp_tool_names(doc, manifest)
    missing_servers = sorted(set(mcp_tools) - set(servers))
    if missing_servers:
        raise ValueError(f"{manifest}: mcp toolsets missing declarations: {missing_servers}")

    children: dict[str, AgentSpec] = {}
    for entry in doc.get("callable_agents") or []:
        if not isinstance(entry, dict) or not entry.get("manifest"):
            raise ValueError(f"{manifest}: callable_agents entries require manifest")
        child_path = (manifest.parent / str(entry["manifest"])).resolve()
        child = load_agent(child_path, model=model)
        if child.name in children:
            raise ValueError(f"{manifest}: duplicate child agent {child.name}")
        children[child.name] = child

    return AgentSpec(
        name=name,
        source_path=manifest,
        model=model or DEFAULT_MODEL,
        instructions=_system_text(doc, manifest),
        local_tools=_local_tools(doc, manifest),
        mcp_tools=mcp_tools,
        mcp_servers=servers,
        skills=_skills(doc, manifest),
        children=children,
        output_schema=doc.get("output_schema"),
    )


def load_cookbook(slug: str, *, model: str | None = None) -> AgentSpec:
    path = COOKBOOKS / slug / "agent.yaml"
    if not path.is_file():
        raise ValueError(f"unknown cookbook {slug!r}")
    return load_agent(path, model=model)


def all_cookbook_slugs() -> list[str]:
    return sorted(p.parent.name for p in COOKBOOKS.glob("*/agent.yaml"))


def _function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
        "strict": False,
    }


LOCAL_TOOL_DEFS: dict[str, dict[str, Any]] = {
    "read": _function_tool(
        "read",
        "Read a UTF-8 file inside the cookbook workspace.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": ["integer", "null"]},
                "end_line": {"type": ["integer", "null"]},
            },
        },
    ),
    "grep": _function_tool(
        "grep",
        "Search UTF-8 files in the workspace for a literal or regex pattern.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["pattern"],
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "regex": {"type": "boolean"},
            },
        },
    ),
    "glob": _function_tool(
        "glob",
        "List workspace files matching a glob pattern.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["pattern"],
            "properties": {"pattern": {"type": "string"}},
        },
    ),
    "write": _function_tool(
        "write",
        "Write a UTF-8 file inside the workspace, creating parents.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "content"],
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        },
    ),
    "edit": _function_tool(
        "edit",
        "Replace exact text inside a UTF-8 workspace file.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "old", "new"],
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
        },
    ),
    "web_fetch": _function_tool(
        "web_fetch",
        "Fetch a public HTTPS URL as UTF-8 text. Private/link-local targets are rejected.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["url"],
            "properties": {"url": {"type": "string"}},
        },
    ),
}


def response_tools(spec: AgentSpec, registry: dict[str, str] | None = None) -> list[dict[str, Any]]:
    registry = registry or source_mcp_registry()
    tools: list[dict[str, Any]] = [LOCAL_TOOL_DEFS[name] for name in spec.local_tools]

    if spec.skills:
        tools.append(
            _function_tool(
                "load_legal_skill",
                "Load the full instructions for one installed Codex legal skill before applying it.",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "enum": sorted(spec.skills)}
                    },
                },
            )
        )

    for child_name in sorted(spec.children):
        tools.append(
            _function_tool(
                f"delegate_{child_name}",
                f"Delegate a bounded task to the {child_name} legal subagent.",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["input"],
                    "properties": {
                        "input": {"type": "object", "additionalProperties": True},
                    },
                },
            )
        )

    for name in spec.mcp_tools:
        server = spec.mcp_servers[name]
        tools.append(
            {
                "type": "mcp",
                "server_label": name,
                "server_url": server.resolved_url(registry),
                "require_approval": "never",
            }
        )
    return tools


def response_payload(spec: AgentSpec, user_input: Any, *, previous_response_id: str | None = None) -> dict[str, Any]:
    if not isinstance(user_input, (str, list)):
        user_input = json.dumps(user_input, ensure_ascii=False)
    payload: dict[str, Any] = {
        "model": spec.model,
        "instructions": spec.instructions,
        "input": user_input,
        "tools": response_tools(spec),
        "tool_choice": "auto",
        "store": False,
        "metadata": {
            "codex_legal_agent": spec.name,
            "source_manifest": str(spec.source_path.relative_to(ROOT)),
        },
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if spec.output_schema:
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": f"{spec.name}-output"[:64],
                "schema": spec.output_schema,
                "strict": True,
            }
        }
    return payload


class ResponsesHTTPClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.base_url + "/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"Responses API HTTP {exc.code}: {body}") from exc


def _workspace_path(workspace: Path, raw: str) -> Path:
    target = (workspace / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    root = workspace.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {raw}") from exc
    return target


def _public_https_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("web_fetch requires https")
    infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("web_fetch refuses non-public address")
    return url


class LocalExecutor:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def call(self, name: str, args: dict[str, Any], spec: AgentSpec, runner: "AgentRunner") -> str:
        if name == "load_legal_skill":
            skill_name = str(args["name"])
            path = spec.skills.get(skill_name)
            if not path:
                raise ValueError(f"skill not available to agent: {skill_name}")
            return path.read_text(encoding="utf-8")

        if name.startswith("delegate_"):
            child_name = name[len("delegate_"):]
            child = spec.children.get(child_name)
            if not child:
                raise ValueError(f"unknown child agent {child_name}")
            result = runner.run(child, args.get("input") or {})
            return json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result

        if name == "read":
            path = _workspace_path(self.workspace, str(args["path"]))
            lines = path.read_text(encoding="utf-8").splitlines()
            start = max(1, int(args.get("start_line") or 1))
            end = int(args.get("end_line") or len(lines))
            return "\n".join(lines[start - 1:end])

        if name == "glob":
            pattern = str(args["pattern"])
            matches = [
                str(p.relative_to(self.workspace))
                for p in self.workspace.rglob("*")
                if p.is_file() and fnmatch.fnmatch(str(p.relative_to(self.workspace)), pattern)
            ]
            return json.dumps(sorted(matches))

        if name == "grep":
            pattern = str(args["pattern"])
            base = _workspace_path(self.workspace, str(args.get("path") or "."))
            rx = re.compile(pattern) if args.get("regex") else None
            out: list[str] = []
            paths = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
            for path in paths:
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except UnicodeDecodeError:
                    continue
                for no, line in enumerate(lines, 1):
                    hit = bool(rx.search(line)) if rx else pattern in line
                    if hit:
                        out.append(f"{path.relative_to(self.workspace)}:{no}:{line}")
            return "\n".join(out[:1000])

        if name == "write":
            path = _workspace_path(self.workspace, str(args["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(args["content"]), encoding="utf-8")
            return "ok"

        if name == "edit":
            path = _workspace_path(self.workspace, str(args["path"]))
            text = path.read_text(encoding="utf-8")
            old = str(args["old"])
            new = str(args["new"])
            if old not in text:
                raise ValueError("edit old text not found")
            if args.get("replace_all"):
                updated = text.replace(old, new)
            else:
                updated = text.replace(old, new, 1)
            path.write_text(updated, encoding="utf-8")
            return "ok"

        if name == "web_fetch":
            url = _public_https_url(str(args["url"]))
            req = urllib.request.Request(url, headers={"user-agent": "codex-legal/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("web_fetch response too large")
            return raw.decode("utf-8", "replace")

        raise ValueError(f"unsupported function tool {name}")


def _output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    pieces: list[str] = []
    for item in response.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                pieces.append(part["text"])
    return "\n".join(pieces)


def _function_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in (response.get("output") or [])
        if item.get("type") == "function_call"
    ]


class AgentRunner:
    def __init__(self, client: ResponsesHTTPClient, workspace: Path):
        self.client = client
        self.executor = LocalExecutor(workspace)

    def run(self, spec: AgentSpec, user_input: Any) -> Any:
        response = self.client.create(response_payload(spec, user_input))
        for _ in range(32):
            calls = _function_calls(response)
            if not calls:
                text = _output_text(response)
                if spec.output_schema and text:
                    value = json.loads(text)
                    jsonschema.validate(instance=value, schema=spec.output_schema)
                    return value
                return text
            outputs = []
            for call in calls:
                args = json.loads(call.get("arguments") or "{}")
                result = self.executor.call(str(call["name"]), args, spec, self)
                outputs.append({
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": result,
                })
            response = self.client.create(
                response_payload(
                    spec,
                    outputs,
                    previous_response_id=str(response.get("id") or ""),
                )
            )
        raise RuntimeError(f"{spec.name}: exceeded 32 Responses tool rounds")


def compile_summary(spec: AgentSpec) -> dict[str, Any]:
    registry = source_mcp_registry()
    return {
        "name": spec.name,
        "model": spec.model,
        "source": str(spec.source_path.relative_to(ROOT)),
        "local_tools": spec.local_tools,
        "mcp_tools": [
            {"name": name, "url": spec.mcp_servers[name].resolved_url(registry)}
            for name in spec.mcp_tools
        ],
        "skills": sorted(spec.skills),
        "children": [compile_summary(child) for child in spec.children.values()],
        "output_schema": bool(spec.output_schema),
    }


def validate_all() -> dict[str, Any]:
    registry = source_mcp_registry()
    specs = [load_cookbook(slug) for slug in all_cookbook_slugs()]
    agents = [agent for spec in specs for agent in spec.all_agents()]
    for agent in agents:
        response_tools(agent, registry)
        if "claude-" in agent.model.lower():
            raise ValueError(f"{agent.name}: Claude model leaked into Codex runtime")
    return {
        "cookbooks": len(specs),
        "agents": len(agents),
        "source_mcp_servers": len(registry),
        "skills_referenced": len({name for a in agents for name in a.skills}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cookbook", nargs="?")
    parser.add_argument("--validate-all", action="store_true")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--run", metavar="INPUT")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    args = parser.parse_args()

    if args.validate_all:
        print(json.dumps(validate_all(), indent=2))
        return 0
    if not args.cookbook:
        parser.error("cookbook is required unless --validate-all is used")
    spec = load_cookbook(args.cookbook, model=args.model)
    if args.compile:
        print(json.dumps(compile_summary(spec), indent=2))
        return 0
    if args.run is not None:
        client = ResponsesHTTPClient(base_url=args.base_url)
        result = AgentRunner(client, args.workspace).run(spec, args.run)
        print(json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result)
        return 0
    parser.error("choose --compile or --run")


if __name__ == "__main__":
    raise SystemExit(main())
