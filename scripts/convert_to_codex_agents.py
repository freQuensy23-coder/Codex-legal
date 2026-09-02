#!/usr/bin/env python3
"""Generate Codex custom subagents from Claude for Legal agents/*.md files."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / ".codex" / "agents"
MARKER = "# generated-from-claude-for-legal:"


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    frontmatter = text[4:end]
    body = text[end + 5 :]
    data: dict[str, str] = {}
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in (">", "|"):
            i += 1
            block: list[str] = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            data[key] = "\n".join(block).strip()
            continue
        data[key] = value.strip("\"'")
        i += 1
    return data, body


def codex_replacements(text: str, plugin_slug: str) -> str:
    replacements = {
        "~/.claude/plugins/config/claude-for-legal": "~/.codex/claude-for-legal",
        "~/.claude/plugins/cache/claude-for-legal": "~/.codex/claude-for-legal/cache",
        "~/.claude/plugins/config/...": "~/.codex/claude-for-legal/...",
        "~/.claude/plugins/config/": "~/.codex/claude-for-legal/",
        "${CLAUDE_PLUGIN_ROOT}": plugin_slug,
        "Claude Code": "Codex CLI",
        "Claude Cowork": "Codex CLI",
        "Claude Desktop": "Codex CLI",
    }
    converted = text
    for old, new in replacements.items():
        converted = converted.replace(old, new)
    return re.sub(
        r"/([a-z][a-z0-9-]+):([a-z][a-z0-9-]+)",
        r"\1-\2",
        converted,
    )


def parse_tools(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(v) for v in value]
    except json.JSONDecodeError:
        pass
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [part.strip().strip("\"'") for part in raw.split(",") if part.strip()]


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    # TOML multiline literal strings cannot contain '''. Fall back to a basic string if needed.
    if "'''" in value:
        return toml_string(value)
    return "'''\n" + value.rstrip() + "\n'''"


def plugin_slug(src: Path) -> str:
    parts = src.relative_to(ROOT).parts
    idx = parts.index("agents")
    if parts[0] == "external_plugins":
        return parts[1]
    return parts[idx - 1]


def source_agent_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.glob("**/agents/*.md")
        if ".codex" not in path.parts and ".git" not in path.parts
    )


def convert(src: Path) -> tuple[str, str]:
    plugin = plugin_slug(src)
    frontmatter, body = split_frontmatter(src.read_text(encoding="utf-8"))
    source_name = frontmatter.get("name") or src.stem
    name = f"{plugin}-{source_name}"
    description = frontmatter.get("description") or f"{plugin} {source_name} legal workflow agent"
    description = re.sub(r"\s+", " ", codex_replacements(description, plugin)).strip()
    tools = parse_tools(frontmatter.get("tools", ""))
    writable = any(
        tool.lower() in {"write", "edit", "bash", "notebookedit"}
        or tool.lower().startswith("mcp__") and any(token in tool.lower() for token in ("write", "send", "create", "update", "post"))
        for tool in tools
    )
    sandbox = "workspace-write" if writable else "read-only"

    converted_body = codex_replacements(body, plugin).strip()
    scope_note = ""
    if tools:
        scope_note = (
            "\n\n## Ported tool scope\n"
            "The Claude source limited this agent to: " + ", ".join(f"`{t}`" for t in tools) + ". "
            "Use the Codex equivalents and configured MCP servers needed for this job; do not broaden the tool surface beyond the task."
        )
    instructions = (
        f"This is the Codex custom-agent port of `{src.relative_to(ROOT)}`. "
        "Preserve the workflow, guardrails, human-review gates, and source-verification rules from the source agent."
        + scope_note
        + "\n\n"
        + converted_body
    )

    lines = [
        f"{MARKER} {src.relative_to(ROOT)}",
        f"name = {toml_string(name)}",
        f"description = {toml_string(description)}",
        f"sandbox_mode = {toml_string(sandbox)}",
        "developer_instructions = " + toml_multiline(instructions),
        "",
    ]
    return name, "\n".join(lines)


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in OUT_ROOT.glob("*.toml"):
        try:
            first = path.read_text(encoding="utf-8").splitlines()[0]
        except (UnicodeDecodeError, IndexError):
            continue
        if first.startswith(MARKER):
            path.unlink()

    names: set[str] = set()
    count = 0
    for src in source_agent_files():
        name, text = convert(src)
        if name in names:
            raise SystemExit(f"duplicate generated Codex agent name: {name}")
        names.add(name)
        (OUT_ROOT / f"{name}.toml").write_text(text, encoding="utf-8")
        count += 1

    # Validate every generated TOML file with the standard library.
    import tomllib
    for path in sorted(OUT_ROOT.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for required in ("name", "description", "developer_instructions"):
            if not data.get(required):
                raise SystemExit(f"{path}: missing required field {required}")

    print(f"converted {count} Claude agents into {OUT_ROOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
