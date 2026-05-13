---
name: employment-legal-investigation-query
description: >
  Codex CLI version of employment-legal:investigation-query. Ask questions against an open investigation log — what witnesses said, where accounts conflict, what gaps exist, what the strongest evidence is on each issue. Use when the attorney needs to query the investigation record without re-reading every entry.
argument-hint: "[matter name] [question]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:investigation-query` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-investigation-query`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-investigation-query

Answers questions against the investigation log — what witnesses said,
where accounts conflict, what gaps exist, what the strongest evidence is
on each issue.

## Instructions

1. Load the `internal-investigation` reference skill and run Mode 3 (Query).
2. Always cite log entry IDs in the answer.
3. If the log contains nothing relevant to the question, say so explicitly —
   "I have not seen any information on [topic] in this investigation log
   ([N] entries reviewed)" — and offer to flag it as a gap.

## Examples

```
employment-legal-investigation-query [matter name]
What did the respondent say about the December team dinner?
```

```
employment-legal-investigation-query [matter name]
Where do the complainant's and respondent's accounts conflict?
```

```
employment-legal-investigation-query [matter name]
What do we still need?
```

> Detailed log-query process, citation rules, and gap-flagging templates live
> in the `internal-investigation` reference skill — load it before doing
> substantive work.
