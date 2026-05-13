#!/usr/bin/env python3
"""Generate Codex CLI skills from the Claude plugin skill tree."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / ".codex" / "skills"
MARKER = ".generated-from-claude-for-legal"


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


def yaml_block(name: str, description: str, argument_hint: str | None) -> str:
    desc = re.sub(r"\s+", " ", description).strip()
    if len(desc) > 850:
        desc = desc[:847].rstrip() + "..."

    lines = ["---", f"name: {name}", "description: >", "  " + desc]
    if argument_hint:
        lines.append(f"argument-hint: {json.dumps(argument_hint, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def plugin_and_skill(src: Path) -> tuple[str, str]:
    parts = src.relative_to(ROOT).parts
    idx = parts.index("skills")
    plugin_slug = parts[idx - 1]
    if parts[0] == "external_plugins":
        plugin_slug = parts[1]
    return plugin_slug, parts[idx + 1]


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


def convert_body(body: str, plugin_slug: str, codex_name: str) -> str:
    converted = codex_replacements(body, plugin_slug)
    return re.sub(r"^#\s*/([^\n]+)", f"# Codex skill: {codex_name}", converted, count=1, flags=re.M)


def converted_skill_text(src: Path) -> tuple[str, str, str]:
    plugin_slug, skill_slug = plugin_and_skill(src)
    codex_name = f"{plugin_slug}-{skill_slug}"
    frontmatter, body = split_frontmatter(src.read_text(encoding="utf-8"))
    description = frontmatter.get("description") or f"Use the {plugin_slug} {skill_slug} legal workflow in Codex CLI."
    description = codex_replacements(description, plugin_slug)
    description = f"Codex CLI version of {plugin_slug}:{skill_slug}. {description}"
    argument_hint = frontmatter.get("argument-hint")

    preface = f"""# Codex Adaptation Notes

This skill was converted from `{plugin_slug}:{skill_slug}` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `{codex_name}`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/{plugin_slug}/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---

"""
    text = yaml_block(codex_name, description, argument_hint)
    text += preface
    text += convert_body(body, plugin_slug, codex_name)
    return codex_name, plugin_slug, text


def convert_copied_text(path: Path, plugin_slug: str) -> None:
    if path.is_dir():
        files = (item for item in path.rglob("*") if item.is_file())
    else:
        files = (path,)

    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        file_path.write_text(codex_replacements(text, plugin_slug), encoding="utf-8")


def source_skill_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.glob("**/skills/*/SKILL.md")
        if ".codex" not in path.parts and ".git" not in path.parts
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    for child in OUT_ROOT.iterdir():
        if child.is_dir() and (child / MARKER).exists():
            shutil.rmtree(child)

    count = 0
    for src in source_skill_files():
        codex_name, plugin_slug, text = converted_skill_text(src)
        dest_dir = OUT_ROOT / codex_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "SKILL.md").write_text(text, encoding="utf-8")
        (dest_dir / MARKER).write_text(str(src.relative_to(ROOT)) + "\n", encoding="utf-8")

        for child in src.parent.iterdir():
            if child.name == "SKILL.md":
                continue
            target = dest_dir / child.name
            if child.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(child, target)
                convert_copied_text(target, plugin_slug)
            else:
                shutil.copy2(child, target)
                convert_copied_text(target, plugin_slug)

        count += 1

    print(f"converted {count} skills into {OUT_ROOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
