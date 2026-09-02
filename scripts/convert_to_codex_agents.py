#!/usr/bin/env python3
"""Generate native local Codex agent roles from upstream Claude agents/*.md."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "# generated-from-claude-for-legal:"
SLASH_COMMAND = re.compile(r"(?<![A-Za-z0-9_$])/(?P<plugin>[a-z][a-z0-9-]+):(?P<skill>[a-z][a-z0-9-]+)")


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    data: dict[str, str] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value in (">", "|", ">-", "|-"):
            i += 1
            block: list[str] = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                if lines[i].strip():
                    block.append(lines[i].strip())
                i += 1
            data[key] = " ".join(block).strip()
            continue
        data[key] = value.strip("\"'")
        i += 1
    return data, body


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


def plugin_slug(src: Path) -> str:
    parts = src.relative_to(ROOT).parts
    idx = parts.index("agents")
    if parts[0] == "external_plugins":
        return parts[1]
    return parts[idx - 1]


def adapt_text(text: str, plugin: str, config_root: Path) -> str:
    root = config_root.as_posix()
    replacements = {
        "~/.claude/plugins/config/claude-for-legal": root,
        "~/.claude/plugins/cache/claude-for-legal": (config_root / "cache").as_posix(),
        "~/.claude/plugins/config/...": (config_root / "...").as_posix(),
        "~/.claude/plugins/config/": (config_root / "legacy-config").as_posix() + "/",
        "${CLAUDE_PLUGIN_ROOT}": (config_root / "source" / plugin).as_posix(),
        "${CLAUDE_PLUGIN_DATA}": (config_root / plugin).as_posix(),
        "$ARGUMENTS": "the arguments in the user's current request",
        "Claude Code": "Codex CLI",
        "Claude Cowork": "Codex CLI",
        "Claude Desktop": "Codex CLI",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return SLASH_COMMAND.sub(lambda m: f"${m.group('plugin')}:{m.group('skill')}", text)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def source_agents() -> list[Path]:
    return sorted(
        p for p in ROOT.glob("**/agents/*.md")
        if ".codex" not in p.parts and ".git" not in p.parts
    )


def convert(src: Path, config_root: Path) -> tuple[str, str]:
    plugin = plugin_slug(src)
    meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
    source_name = meta.get("name") or src.stem
    role_name = f"{plugin}-{source_name}"
    desc = re.sub(
        r"\s+", " ", adapt_text(meta.get("description") or f"{plugin} {source_name} legal workflow agent", plugin, config_root)
    ).strip()
    tools = parse_tools(meta.get("tools", ""))
    writable = any(
        tool.lower() in {"write", "edit", "bash", "notebookedit"}
        or (tool.lower().startswith("mcp__") and any(x in tool.lower() for x in ("write", "send", "create", "update", "post")))
        for tool in tools
    )
    sandbox = "workspace-write" if writable else "read-only"
    body = adapt_text(body, plugin, config_root).strip()

    scope = ""
    if tools:
        scope = (
            "\n\nOriginal Claude tool scope: "
            + ", ".join(f"`{tool}`" for tool in tools)
            + ". Codex does not expose an identical per-role allowlist field; stay within this original scope and the configured sandbox."
        )
    instructions = (
        f"Local Codex port of `{src.relative_to(ROOT)}`. Preserve the upstream workflow, verification rules, and human-review gates."
        + scope
        + "\n\n"
        + body
    )

    rendered = "\n".join([
        f"{MARKER} {src.relative_to(ROOT)}",
        f"name = {toml_string(role_name)}",
        f"description = {toml_string(desc)}",
        'model = "gpt-5.6"',
        'model_reasoning_effort = "xhigh"',
        f"sandbox_mode = {toml_string(sandbox)}",
        f"developer_instructions = {toml_string(instructions)}",
        "",
    ])
    return role_name, rendered


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / ".codex/agents")
    ap.add_argument("--config-root", type=Path, default=Path.home() / ".codex/claude-for-legal")
    args = ap.parse_args()
    out = args.output.expanduser().resolve()
    config_root = args.config_root.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    for p in out.glob("*.toml"):
        try:
            if p.read_text(encoding="utf-8").startswith(MARKER):
                p.unlink()
        except UnicodeDecodeError:
            pass

    names: set[str] = set()
    for src in source_agents():
        name, rendered = convert(src, config_root)
        if name in names:
            raise SystemExit(f"duplicate Codex agent role name: {name}")
        names.add(name)
        (out / f"{name}.toml").write_text(rendered, encoding="utf-8")

    import tomllib
    for p in sorted(out.glob("*.toml")):
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        for key in ("name", "description", "developer_instructions"):
            if not data.get(key):
                raise SystemExit(f"{p}: missing {key}")
        if data.get("model") != "gpt-5.6" or data.get("model_reasoning_effort") != "xhigh":
            raise SystemExit(f"{p}: GPT-5.6/xhigh not pinned")
        text = p.read_text(encoding="utf-8")
        for bad in ("~/.claude/plugins/config/claude-for-legal", "${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS"):
            if bad in text:
                raise SystemExit(f"{p}: stale Claude runtime token {bad}")

    print(json.dumps({"agent_count": len(names), "agents": sorted(names)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
