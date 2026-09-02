#!/usr/bin/env python3
"""Install Claude for Legal MCP declarations into Codex config.toml.

The upstream repository stores MCP servers in per-plugin .mcp.json files.
Codex reads MCP servers from ~/.codex/config.toml. This script performs the
mechanical translation without copying credentials into the repository or the
Codex config.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "# BEGIN CODEX-LEGAL MCP (managed by scripts/install_codex_mcp.py)"
END = "# END CODEX-LEGAL MCP"
ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


@dataclass(frozen=True)
class Server:
    name: str
    source_name: str
    source_files: tuple[str, ...]
    config: dict[str, Any]
    oauth: bool = False


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-_").lower()
    if not slug:
        raise ValueError(f"MCP server name {name!r} cannot be converted to a Codex name")
    return slug


def canonical_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep runtime-relevant MCP fields; ignore Claude presentation metadata."""
    result: dict[str, Any] = {}
    server_type = raw.get("type")

    if raw.get("url"):
        result["url"] = str(raw["url"])
    elif raw.get("command"):
        result["command"] = str(raw["command"])
        if raw.get("args") is not None:
            result["args"] = [str(v) for v in raw.get("args", [])]
    else:
        raise ValueError("MCP server must define either url or command")

    if server_type not in (None, "http", "stdio"):
        raise ValueError(f"unsupported MCP transport type: {server_type!r}")

    if raw.get("cwd"):
        result["cwd"] = str(raw["cwd"])

    env = raw.get("env") or {}
    if env:
        if not isinstance(env, dict):
            raise ValueError("env must be an object")
        result["env"] = {str(k): str(v) for k, v in env.items()}

    env_vars = raw.get("env_vars") or raw.get("envVars") or []
    if env_vars:
        result["env_vars"] = [str(v) for v in env_vars]

    headers = raw.get("headers") or raw.get("http_headers") or raw.get("httpHeaders") or {}
    static_headers: dict[str, str] = {}
    env_headers: dict[str, str] = {}
    if headers:
        if not isinstance(headers, dict):
            raise ValueError("headers must be an object")
        for key, value in headers.items():
            text = str(value)
            match = ENV_REF.fullmatch(text)
            if match:
                env_headers[str(key)] = match.group(1)
            else:
                bearer = re.fullmatch(r"Bearer \$\{([A-Za-z_][A-Za-z0-9_]*)\}", text, re.I)
                if bearer and str(key).lower() == "authorization":
                    result["bearer_token_env_var"] = bearer.group(1)
                else:
                    static_headers[str(key)] = text
    if static_headers:
        result["http_headers"] = static_headers
    if env_headers:
        result["env_http_headers"] = env_headers

    explicit_bearer = raw.get("bearer_token_env_var") or raw.get("bearerTokenEnvVar")
    if explicit_bearer:
        result["bearer_token_env_var"] = str(explicit_bearer)

    for key in ("enabled", "required", "startup_timeout_sec", "tool_timeout_sec"):
        if key in raw:
            result[key] = raw[key]
    for key in ("enabled_tools", "disabled_tools", "scopes"):
        if key in raw and raw[key] is not None:
            result[key] = list(raw[key])
    if raw.get("oauth_resource"):
        result["oauth_resource"] = str(raw["oauth_resource"])

    return result


def discover(root: Path = ROOT) -> list[Server]:
    by_slug: dict[str, tuple[str, dict[str, Any], bool, list[str]]] = {}

    paths = sorted(
        p for p in root.rglob(".mcp.json")
        if ".git" not in p.parts and ".codex" not in p.parts
    )
    if not paths:
        raise RuntimeError("no .mcp.json files found")

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if not isinstance(servers, dict):
            raise ValueError(f"{path}: mcpServers must be an object")

        for source_name, raw in servers.items():
            if not isinstance(raw, dict):
                raise ValueError(f"{path}: {source_name}: server config must be an object")
            slug = slugify(str(source_name))
            config = canonical_config(raw)
            oauth = bool(raw.get("oauth"))
            rel = str(path.relative_to(root))

            previous = by_slug.get(slug)
            if previous is None:
                by_slug[slug] = (str(source_name), config, oauth, [rel])
                continue

            prev_name, prev_config, prev_oauth, prev_files = previous
            if prev_config != config:
                raise ValueError(
                    f"conflicting definitions for MCP server {slug!r}: "
                    f"{prev_files[-1]} and {rel}"
                )
            prev_files.append(rel)
            by_slug[slug] = (prev_name, prev_config, prev_oauth or oauth, prev_files)

    return [
        Server(
            name=slug,
            source_name=source_name,
            source_files=tuple(files),
            config=config,
            oauth=oauth,
        )
        for slug, (source_name, config, oauth, files) in sorted(by_slug.items())
    ]


def toml_string(value: str) -> str:
    # JSON string syntax is valid TOML basic-string syntax for the escapes we emit.
    return json.dumps(value, ensure_ascii=False)


def toml_array(values: list[Any]) -> str:
    if not all(isinstance(v, str) for v in values):
        raise ValueError("only string arrays are supported in generated MCP config")
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


def emit_table(lines: list[str], prefix: str, values: dict[str, str]) -> None:
    if not values:
        return
    lines.append("")
    lines.append(f"[{prefix}]")
    for key, value in sorted(values.items()):
        lines.append(f"{toml_string(key)} = {toml_string(value)}")


def render(servers: list[Server]) -> str:
    lines = [BEGIN]
    lines.append("# Generated from repository .mcp.json files. Do not put secrets here.")
    lines.append("# Re-run this installer after syncing the repository.")

    for server in servers:
        cfg = dict(server.config)
        lines.append("")
        lines.append(f"# {server.source_name}; source: {', '.join(server.source_files)}")
        if server.oauth:
            lines.append(f"# OAuth: run `codex mcp login {server.name}` after installation.")
        table = f"mcp_servers.{server.name}"
        lines.append(f"[{table}]")

        nested: dict[str, dict[str, str]] = {}
        for key in ("env", "http_headers", "env_http_headers"):
            if key in cfg:
                nested[key] = cfg.pop(key)

        preferred = [
            "url", "command", "args", "cwd", "env_vars",
            "bearer_token_env_var", "enabled", "required",
            "startup_timeout_sec", "tool_timeout_sec",
            "enabled_tools", "disabled_tools", "scopes", "oauth_resource",
        ]
        for key in preferred:
            if key not in cfg:
                continue
            value = cfg.pop(key)
            if isinstance(value, str):
                rendered = toml_string(value)
            elif isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, (int, float)):
                rendered = str(value)
            elif isinstance(value, list):
                rendered = toml_array(value)
            else:
                raise ValueError(f"unsupported TOML value for {server.name}.{key}: {value!r}")
            lines.append(f"{key} = {rendered}")

        if cfg:
            raise ValueError(f"unhandled MCP fields for {server.name}: {sorted(cfg)}")

        for nested_name in ("env", "http_headers", "env_http_headers"):
            emit_table(lines, f"{table}.{nested_name}", nested.get(nested_name, {}))

    lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n"


def replace_managed_block(existing: str, managed: str) -> str:
    begin = existing.find(BEGIN)
    end = existing.find(END)
    if (begin == -1) != (end == -1):
        raise ValueError("config contains only one CODEX-LEGAL MCP marker; refusing to edit")
    if begin != -1:
        end += len(END)
        suffix = existing[end:]
        if suffix.startswith("\n"):
            suffix = suffix[1:]
        prefix = existing[:begin].rstrip("\n")
        parts = [p for p in (prefix, managed.rstrip("\n"), suffix.rstrip("\n")) if p]
        return "\n\n".join(parts) + "\n"

    if not existing.strip():
        return managed
    return existing.rstrip("\n") + "\n\n" + managed


def validate_toml(text: str) -> None:
    try:
        import tomllib
    except ImportError as exc:  # pragma: no cover - Codex-supported Pythons are modern
        raise RuntimeError("Python 3.11+ is required to validate Codex config.toml") from exc
    tomllib.loads(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
        help="Codex config.toml path (default: ~/.codex/config.toml)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print generated managed block only")
    parser.add_argument("--check", action="store_true", help="validate discovery/rendering without writing")
    args = parser.parse_args()

    servers = discover()
    managed = render(servers)

    if args.dry_run:
        sys.stdout.write(managed)
        return 0

    target = args.target.expanduser()
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    result = replace_managed_block(existing, managed)
    validate_toml(result)

    if args.check:
        print(f"validated {len(servers)} unique MCP servers from repository declarations")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    print(f"installed {len(servers)} MCP servers into {target}")
    oauth = [server.name for server in servers if server.oauth]
    if oauth:
        print("OAuth login required for: " + ", ".join(oauth))
        for name in oauth:
            print(f"  codex mcp login {name}")
    print("Run `codex mcp list` to verify the resulting Codex MCP configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
