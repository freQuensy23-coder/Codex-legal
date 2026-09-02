# Quick Start

## Install in Codex CLI

Install the starter skill set plus the Codex practice profiles, custom subagents, and MCP connectors:

```bash
scripts/install_codex_skills.sh --starter --init-config --init-agents --init-mcp
```

Restart Codex CLI after installation. If the installer prints an OAuth command, run it; for example:

```text
codex mcp login cocounsel-legal
```

For a dry run:

```bash
scripts/install_codex_skills.sh --starter --init-config --init-agents --init-mcp --dry-run
```

For all 151 skills:

```bash
scripts/install_codex_skills.sh --all --init-config --init-agents --init-mcp
```

## Run setup

Each practice area has a cold-start interview that writes a Codex-side practice profile under `~/.codex/claude-for-legal/<plugin>/CLAUDE.md`.

```text
privacy-legal-cold-start-interview
commercial-legal-cold-start-interview
litigation-legal-cold-start-interview
```

Run the matching setup before relying on substantive workflows so Codex has your playbook, jurisdiction footprint, escalation rules, and house style.

## What gets installed

- Skills: `~/.codex/skills/<plugin>-<skill>/SKILL.md`
- Custom subagents: `~/.codex/agents/<plugin>-<agent>.toml`
- Practice profiles: `~/.codex/claude-for-legal/`
- MCP servers: managed entries in `~/.codex/config.toml`

The MCP installer translates all repository `.mcp.json` declarations, deduplicates shared servers, preserves unrelated Codex config, and leaves secrets to environment variables or Codex OAuth.

## Which skill is for me?

| You are a... | Start with... | Then try... |
|---|---|---|
| Privacy lawyer / DPO | `privacy-legal-cold-start-interview` | `privacy-legal-use-case-triage` |
| Commercial / contracts lawyer | `commercial-legal-cold-start-interview` | `commercial-legal-review` |
| Corporate / M&A lawyer | `corporate-legal-cold-start-interview` | `corporate-legal-diligence-issue-extraction` |
| Employment lawyer / HR counsel | `employment-legal-cold-start-interview` | `employment-legal-wage-hour-qa` |
| Product counsel | `product-legal-cold-start-interview` | `product-legal-is-this-a-problem` |
| IP lawyer / patent agent | `ip-legal-cold-start-interview` | `ip-legal-clearance` |
| Litigator, in-house or firm | `litigation-legal-cold-start-interview` | `litigation-legal-matter-intake` |
| Regulatory / compliance counsel | `regulatory-legal-cold-start-interview` | `regulatory-legal-reg-feed-watcher` |
| AI governance lead | `ai-governance-legal-cold-start-interview` | `ai-governance-legal-use-case-triage` |
| Clinic supervisor | `legal-clinic-cold-start-interview` | `legal-clinic-client-intake` |
| Law student | `law-student-cold-start-interview` | `law-student-socratic-drill` |
| Legal ops / looking for skills | `legal-builder-hub-cold-start-interview` | `legal-builder-hub-registry-browser` |

## Upstream compatibility

The original Claude plugin tree remains in this repository as the upstream source. The Codex runtime copies are generated from it; after upstream changes, the sync workflow regenerates skills and agents and validates the MCP translation.

Every output is a draft for attorney review. The workflows flag uncertainty, mark citations by source, and gate irreversible actions.
