# Claude for Legal - Codex Skills

This directory contains the Codex CLI adaptation of Claude for Legal.

## Install

Default install uses the starter set, not the full 151-skill pack. This keeps Codex startup light and follows the local rule for third-party/runtime-installed skills.

```bash
scripts/install_codex_skills.sh --starter --init-config
```

Restart Codex CLI after syncing so the skill descriptions are loaded.

Use `--dry-run` to preview changes. Use `--all` only when you want every generated skill installed:

```bash
scripts/install_codex_skills.sh --starter --dry-run
scripts/install_codex_skills.sh --all --init-config
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

You can invoke a skill by name or by describing the task in natural language.

## Configuration

Converted skills read Codex-side practice profiles:

```text
~/.codex/claude-for-legal/company-profile.md
~/.codex/claude-for-legal/<plugin>/CLAUDE.md
```

Run the relevant `<plugin>-cold-start-interview` skill before relying on other skills in that practice area. The cold-start interview creates or updates the practice profile used by the rest of that plugin's converted skills.

## Scope

- `skills/` contains 151 converted `SKILL.md` files.
- `starter-skills.txt` lists the default install set.
- `templates/README.md` explains how Codex-side practice-profile templates are initialized.
- Original Claude plugin files remain in the repository root under `<plugin>/`.
- Managed-agent cookbooks and `.mcp.json` connector declarations are preserved from upstream, but Codex MCP setup may require separate local configuration.

Regenerate this tree after upstream skill edits:

```bash
python3 scripts/convert_to_codex_skills.py
```

Every output remains a draft for qualified attorney review. These skills are not legal advice and do not authorize filing, sending, executing, or relying on legal conclusions without human review.
