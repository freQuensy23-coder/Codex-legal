#!/usr/bin/env python3
"""Build a native Codex plugin marketplace from the upstream legal plugin tree.

The upstream plugin directories remain the source of truth. This builder creates a
throw-away Codex runtime tree whose skills keep their original names and are
therefore exposed by Codex as `$plugin:skill`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".sh", ".csv", ".tsv", ".html", ".xml"}
FORBIDDEN = (
    "~/.claude/plugins/config/claude-for-legal",
    "~/.claude/plugins/cache/claude-for-legal",
    "${CLAUDE_PLUGIN_ROOT}",
    "${CLAUDE_PLUGIN_DATA}",
    "$ARGUMENTS",
)
SLASH_COMMAND = re.compile(r"(?<![A-Za-z0-9_$])/(?P<plugin>[a-z][a-z0-9-]+):(?P<skill>[a-z][a-z0-9-]+)")


def source_path(entry: dict) -> Path:
    source = entry["source"]
    if isinstance(source, str):
        rel = source
    elif isinstance(source, dict) and source.get("source") == "local":
        rel = source["path"]
    else:
        raise ValueError(f"unsupported local plugin source: {source!r}")
    return (ROOT / rel).resolve()


def adapt_text(text: str, plugin: str, config_root: Path) -> str:
    config_root_s = config_root.as_posix()
    source_root_s = (config_root / "source" / plugin).as_posix()
    replacements = {
        "~/.claude/plugins/config/claude-for-legal": config_root_s,
        "~/.claude/plugins/cache/claude-for-legal": (config_root / "cache").as_posix(),
        "~/.claude/plugins/config/...": (config_root / "...").as_posix(),
        "~/.claude/plugins/config/": (config_root / "legacy-config").as_posix() + "/",
        "${CLAUDE_PLUGIN_ROOT}": source_root_s,
        "${CLAUDE_PLUGIN_DATA}": (config_root / plugin).as_posix(),
        "$ARGUMENTS": "the arguments in the user's current request",
        "Claude Code": "Codex CLI",
        "Claude Cowork": "Codex CLI",
        "Claude Desktop": "Codex CLI",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = SLASH_COMMAND.sub(lambda m: f"${m.group('plugin')}:{m.group('skill')}", text)
    return text


def add_skill_marker(text: str, plugin: str, skill: str) -> str:
    marker = f"<!-- codex-legal-skill-id: {plugin}:{skill} -->"
    if marker in text:
        return text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[: end + 5] + "\n" + marker + "\n" + text[end + 5 :]
    return marker + "\n" + text


def adapt_file(path: Path, plugin: str, config_root: Path) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "SKILL.md":
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    path.write_text(adapt_text(text, plugin, config_root), encoding="utf-8")


def copy_plugin(src: Path, dst: Path, plugin: str, config_root: Path) -> int:
    def ignore(path: str, names: list[str]) -> set[str]:
        ignored = {".git", "__pycache__"}
        # Claude agent markdown is converted separately into native Codex agent roles.
        if Path(path).resolve() == src.resolve():
            ignored.add("agents")
        return ignored.intersection(names)

    shutil.copytree(src, dst, ignore=ignore)
    for p in dst.rglob("*"):
        if p.is_file():
            adapt_file(p, plugin, config_root)

    skills = sorted((dst / "skills").glob("*/SKILL.md")) if (dst / "skills").exists() else []
    for skill_md in skills:
        skill = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        text = add_skill_marker(text, plugin, skill)
        skill_md.write_text(text, encoding="utf-8")
    return len(skills)


def canonical_manifest(src: Path, dst: Path, entry: dict) -> dict:
    claude_manifest = src / ".claude-plugin" / "plugin.json"
    if claude_manifest.exists():
        data = json.loads(claude_manifest.read_text(encoding="utf-8"))
    else:
        data = {
            "name": entry["name"],
            "version": "0.0.0",
            "description": entry.get("description", entry["name"]),
            "author": entry.get("author", {"name": "Unknown"}),
        }
    author = data.get("author") or entry.get("author") or {"name": "Unknown"}
    display = entry.get("displayName") or data["name"].replace("-", " ").title()
    desc = data.get("description") or entry.get("description") or data["name"]
    manifest = {
        "name": data["name"],
        "version": data.get("version", "0.0.0"),
        "description": desc,
        "author": author,
        "skills": "./skills/",
        "interface": {
            "displayName": display,
            "shortDescription": re.sub(r"\s+", " ", desc).strip()[:160],
            "developerName": author.get("name", "Unknown") if isinstance(author, dict) else str(author),
            "category": "Productivity",
        },
    }
    if (dst / ".mcp.json").exists():
        manifest["mcpServers"] = "./.mcp.json"
    out = dst / ".codex-plugin" / "plugin.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def validate_runtime(runtime: Path, expected_plugins: list[str], expected_skills: int) -> None:
    marketplace = json.loads((runtime / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    actual_plugins = [p["name"] for p in marketplace["plugins"]]
    if actual_plugins != expected_plugins:
        raise SystemExit(f"runtime marketplace plugin mismatch: {actual_plugins!r}")

    skill_files = list((runtime / "plugins").glob("*/skills/*/SKILL.md"))
    if len(skill_files) != expected_skills:
        raise SystemExit(f"runtime skill count mismatch: expected={expected_skills} actual={len(skill_files)}")

    seen: set[str] = set()
    for path in skill_files:
        plugin = path.parts[-4]
        skill = path.parent.name
        sid = f"{plugin}:{skill}"
        if sid in seen:
            raise SystemExit(f"duplicate runtime skill id: {sid}")
        seen.add(sid)
        text = path.read_text(encoding="utf-8")
        marker = f"<!-- codex-legal-skill-id: {sid} -->"
        if marker not in text:
            raise SystemExit(f"{path}: missing runtime marker")
        for token in FORBIDDEN:
            if token in text:
                raise SystemExit(f"{path}: unported Claude runtime token {token}")
        stale = SLASH_COMMAND.search(text)
        if stale:
            raise SystemExit(f"{path}: stale Claude slash command {stale.group(0)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--config-root", required=True, type=Path,
                    help="Absolute Codex-side legal config root used in generated instructions")
    args = ap.parse_args()

    output = args.output.expanduser().resolve()
    config_root = args.config_root.expanduser().resolve()
    if output.exists():
        shutil.rmtree(output)
    (output / "plugins").mkdir(parents=True)

    source_marketplace = json.loads(SOURCE_MARKETPLACE.read_text(encoding="utf-8"))
    entries = source_marketplace["plugins"]
    plugin_names = [entry["name"] for entry in entries]
    runtime_entries = []
    skill_count = 0

    for entry in entries:
        name = entry["name"]
        src = source_path(entry)
        if not src.is_dir():
            raise SystemExit(f"missing source plugin directory: {src}")
        dst = output / "plugins" / name
        skill_count += copy_plugin(src, dst, name, config_root)
        canonical_manifest(src, dst, entry)
        runtime_entries.append({
            "name": name,
            "source": {"source": "local", "path": f"./plugins/{name}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
            "category": "Productivity",
        })

    marketplace = {
        "name": "codex-legal",
        "interface": {"displayName": "Codex Legal"},
        "plugins": runtime_entries,
    }
    mp = output / ".agents/plugins/marketplace.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Keep a compact manifest for CI and installers.
    report = {
        "plugins": plugin_names,
        "plugin_count": len(plugin_names),
        "skill_count": skill_count,
        "config_root": config_root.as_posix(),
    }
    (output / "codex-legal-build.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    validate_runtime(output, plugin_names, skill_count)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
