---
name: employment-legal-investigation-summary
description: >
  Codex CLI version of employment-legal:investigation-summary. Draft an audience-specific summary from the privileged investigation memo — HR, leadership, or outside counsel versions. Use when an investigation memo needs to be communicated to an audience that should not see the full privileged work product.
argument-hint: "[matter name] [audience: hr / leadership / outside-counsel]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:investigation-summary` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-investigation-summary`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-investigation-summary

Drafts a stripped-down, audience-appropriate summary from the privileged
investigation memo. HR summaries contain no privilege analysis. Leadership
summaries are high-level. Outside counsel briefings include full context.

## Instructions

1. Load the `internal-investigation` reference skill and run Mode 5 (Audience summary).
2. If no memo exists yet, offer to draft the memo first.
3. HR summaries must not include attorney mental impressions, credibility
   methodology, or legal exposure analysis.

## Examples

```
employment-legal-investigation-summary [matter name] hr
```

```
employment-legal-investigation-summary [matter name] leadership
```

```
employment-legal-investigation-summary [matter name] outside-counsel
```

> Detailed audience-stripping rules and summary templates live in the
> `internal-investigation` reference skill — load it before doing substantive
> work.
