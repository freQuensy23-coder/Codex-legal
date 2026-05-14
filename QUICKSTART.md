# Quick Start

**60 seconds.** This gets the legal skill pack loaded into Codex CLI.

## Install in Codex CLI

Default install uses the starter set, not the full 151-skill pack. This keeps Codex startup light and follows the local rule for third-party/runtime-installed skills.

```bash
scripts/install_codex_skills.sh --starter --init-config
```

Restart Codex CLI after syncing.

For a dry run:

```bash
scripts/install_codex_skills.sh --starter --dry-run
```

For the full pack, opt in explicitly:

```bash
scripts/install_codex_skills.sh --all --init-config
```

## Run setup

Each practice area has a cold-start interview that writes a Codex-side practice profile under `~/.codex/claude-for-legal/<plugin>/CLAUDE.md`.

```text
privacy-legal-cold-start-interview
commercial-legal-cold-start-interview
corporate-legal-cold-start-interview
```

Run setup before relying on substantive workflows. Otherwise the skills will either stop or produce generic output because they do not know your playbook, jurisdiction footprint, escalation rules, or house style.

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

## What you're installing

The converted Codex skills live in `.codex/skills/<plugin>-<skill>/SKILL.md`. They are adapted from the upstream Claude plugin skills but use Codex-side configuration paths:

```text
~/.codex/claude-for-legal/company-profile.md
~/.codex/claude-for-legal/<plugin>/CLAUDE.md
```

The original Claude plugin structure remains in this repository for compatibility.

The starter list is maintained in `.codex/starter-skills.txt`. The full generated set remains available under `.codex/skills/`.

Smoke tests are in [docs/codex-smoke-tests.md](docs/codex-smoke-tests.md).

## Claude plugin compatibility

If you are using upstream Claude plugin tooling instead of Codex CLI, use the original marketplace flow:

```text
/plugin marketplace add <path-to-this-repo>
/plugin install privacy-legal@claude-for-legal
/privacy-legal:cold-start-interview
```

That flow writes profiles to `~/.claude/plugins/config/claude-for-legal/<plugin>/CLAUDE.md`. Codex skills do not read that path unless you copy the profile into `~/.codex/claude-for-legal/<plugin>/CLAUDE.md`.

## Stuck?

- **Codex does not see the skills** -> restart Codex CLI after syncing `.codex/skills`.
- **Run setup first** -> run `<plugin>-cold-start-interview` before any other skill in that practice area.
- **Citations are flagged `[verify]`** -> configure a legal research connector or verify citations manually before relying on them.
- **The skill cannot read a file** -> give Codex an accessible local path or move the file into the current workspace.
- **You need the old Claude command name** -> replace `/plugin:skill` with `plugin-skill`, for example `/privacy-legal:dsar-response` becomes `privacy-legal-dsar-response`.

Every output is a draft for attorney review. The skills flag uncertainty, mark citations by source, and gate irreversible actions. A lawyer reviews, verifies, and takes responsibility.
