---
name: employment-legal-investigation-memo
description: >
  Codex CLI version of employment-legal:investigation-memo. Draft or update the privileged investigation memo from the investigation log. Use when an investigation is far enough along to write the first memo cut, or when new data has been added and the existing draft needs updating.
argument-hint: "[matter name]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:investigation-memo` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-investigation-memo`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-investigation-memo

Drafts the first cut of the privileged investigation memo from the log,
or updates an existing draft when new data has been added.

## Instructions

1. Load the `internal-investigation` reference skill and run Mode 4 (Draft or update memo).
2. If drafting for the first time, warn if high-priority sources are still
   open on the checklist.
3. If updating, show what changed before rewriting.
4. All output is marked PRIVILEGED AND CONFIDENTIAL — ATTORNEY WORK PRODUCT.

## Examples

```
employment-legal-investigation-memo [matter name]
```

```
employment-legal-investigation-memo [matter name]
(updates existing memo if one exists)
```

> Detailed memo structure, credibility-assessment framework, and update rules
> live in the `internal-investigation` reference skill — load it before doing
> substantive work.
