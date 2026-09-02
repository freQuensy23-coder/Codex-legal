# Claude for Legal - Codex

This directory contains the Codex CLI adaptation of Claude for Legal: converted skills, custom subagents, practice-profile setup, and MCP configuration.

## Install

Default install uses the starter skill set and can initialize every Codex runtime surface in one command:

```bash
scripts/install_codex_skills.sh --starter --init-config --init-agents --init-mcp
```

Restart Codex CLI after installation. If an MCP server uses OAuth, complete the login command printed by the installer (for example `codex mcp login cocounsel-legal`).

Use `--dry-run` to preview changes. Use `--all` only when you want every generated skill installed:

```bash
scripts/install_codex_skills.sh --starter --init-config --init-agents --init-mcp --dry-run
scripts/install_codex_skills.sh --all --init-config --init-agents --init-mcp
```

## Invoke

Codex skill names use `<plugin>-<skill>`:

| Claude plugin command | Codex skill |
|---|---|
| `/commercial-legal:review` | `commercial-legal-review` |
| `/privacy-legal:dsar-response` | `privacy-legal-dsar-response` |
| `/ai-governance-legal:use-case-triage` | `ai-governance-legal-use-case-triage` |
| `/litigation-legal:claim-chart` | `litigation-legal-claim-chart` |
| `/law-student:socratic-drill` | `law-student-socratic-drill` |

You can invoke a skill by name or describe the task in natural language. Converted custom subagents are installed under `~/.codex/agents` and are available to Codex's subagent system.

## Configuration

Converted skills read Codex-side practice profiles:

```text
~/.codex/claude-for-legal/company-profile.md
~/.codex/claude-for-legal/<plugin>/CLAUDE.md
```

Run the relevant `<plugin>-cold-start-interview` before relying on other skills in that practice area.

MCP declarations are sourced from all upstream `.mcp.json` files and translated into a managed block in:

```text
~/.codex/config.toml
```

The installer preserves unrelated user configuration and never writes credentials into the repository. OAuth-enabled connectors still require the normal Codex OAuth login flow.

## Scope

- `skills/` contains 151 converted `SKILL.md` workflows.
- `agents/` contains Codex TOML ports of every upstream `agents/*.md` custom agent.
- `starter-skills.txt` lists the default skill install set.
- `templates/README.md` explains practice-profile initialization.
- `scripts/install_codex_mcp.py` translates and deduplicates upstream MCP declarations for Codex.
- Original Claude plugin files remain in the repository as the canonical upstream source.
- Managed-agent cookbook source remains preserved; agent prompts referenced by those cookbooks are also converted into Codex custom subagents.

Regenerate the Codex runtime surfaces after upstream edits:

```bash
python3 scripts/convert_to_codex_skills.py
python3 scripts/convert_to_codex_agents.py
python3 scripts/install_codex_mcp.py --check
```

Every output remains a draft for qualified attorney review. These workflows do not authorize filing, sending, executing, or relying on legal conclusions without human review.
