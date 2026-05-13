---
name: employment-legal-investigation-open
description: >
  Codex CLI version of employment-legal:investigation-open. Open a new internal investigation matter — runs intake, generates the sources checklist, and creates the persistent investigation log. Use when a complaint or allegation comes in and the attorney needs to stand up a privileged investigation workspace.
argument-hint: "[brief description of the allegation]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:investigation-open` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-investigation-open`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-investigation-open

Opens a new investigation matter — runs intake, generates the sources
checklist, and creates the persistent investigation log.

## Instructions

1. Load `~/.codex/claude-for-legal/employment-legal/CLAUDE.md`.
2. Load the `internal-investigation` reference skill and run Mode 1 (Open).
3. If a matter with the same slug already exists, warn before overwriting.

## Examples

```
employment-legal-investigation-open
Harassment complaint filed against a manager in the Austin office.
```

```
employment-legal-investigation-open
(skill will ask for details)
```

> Detailed intake, privilege-formation requirements, sources checklist, and log
> templates live in the `internal-investigation` reference skill — load it
> before doing substantive work.
