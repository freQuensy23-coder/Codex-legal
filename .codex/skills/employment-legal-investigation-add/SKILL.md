---
name: employment-legal-investigation-add
description: >
  Codex CLI version of employment-legal:investigation-add. Add data to an open investigation — documents, interview notes, or observations. Processes batches against the documented pull criteria, surfaces significant items, and logs everything reviewed for coverage verification. Use when new evidence, interview notes, or document productions come in for an open investigation.
argument-hint: "[matter name or slug, then paste or attach data]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:investigation-add` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-investigation-add`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-investigation-add

Adds data to an open investigation log. Processes document batches using
documented pull criteria, surfaces significant items, logs everything
reviewed for coverage verification.

## Instructions

1. Load `~/.codex/claude-for-legal/employment-legal/CLAUDE.md`.
2. Load the `internal-investigation` reference skill and run Mode 2 (Add data).
3. After processing, show the surface ratio and list of surfaced items.
4. Prompt to update the sources checklist if the data covers a checklist item.

## Examples

```
employment-legal-investigation-add [matter name]
[paste interview notes]
```

```
employment-legal-investigation-add [matter name]
[attach email export]
```

> Detailed needle-finding process, log entry format, surface-ratio rules, and
> sources-checklist tracking live in the `internal-investigation` reference
> skill — load it before doing substantive work.
