---
name: employment-legal-leave-tracker
description: >
  Codex CLI version of employment-legal:leave-tracker. Check open leaves for deadline alerts and required decisions. Surfaces only the leaves that require an action and explains why — not a status board. Use weekly, or whenever the attorney needs to know which leaves have upcoming designation, certification, or exhaustion deadlines.
argument-hint: "[no arguments — works from HRIS or leave-register.yaml]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:leave-tracker` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-leave-tracker`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-leave-tracker

Checks all open leaves with hard legal deadlines and surfaces only the ones
requiring a decision or action. Not a status board — tells you what you need
to do and why.

## Instructions

1. Load the `leave-tracker` agent and run the full workflow.

2. If no HRIS is connected and no `~/.codex/claude-for-legal/employment-legal/leave-register.yaml` exists, prompt
   the attorney to upload a leave spreadsheet or use
   `employment-legal-log-leave` to add entries.

3. Alerts only for leaves requiring action. Clean leaves summarized one line each.

## Examples

```
employment-legal-leave-tracker
```

Run this weekly — set a Monday-morning reminder to invoke
`employment-legal-leave-tracker`. Automated scheduling requires a separate
integration (calendar reminder, cron job, etc.); Codex CLI agents do not
self-schedule.
