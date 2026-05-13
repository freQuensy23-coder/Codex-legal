---
name: commercial-legal-review-proposals
description: >
  Codex CLI version of commercial-legal:review-proposals. Review and approve (or reject) pending playbook update proposals from the playbook-monitor agent and apply approved changes to the practice profile. Use when the playbook-monitor agent has surfaced proposals, when the user says "review playbook proposals", "what playbook updates are pending", or wants to step through deviation-driven playbook changes.
argument-hint: "[no arguments needed — works from the pending proposals file]"
---

# Codex Adaptation Notes

This skill was converted from `commercial-legal:review-proposals` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `commercial-legal-review-proposals`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/commercial-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: commercial-legal-review-proposals

Steps through pending playbook update proposals from the monitor agent and applies approved changes to `~/.codex/claude-for-legal/commercial-legal/CLAUDE.md`.

## Instructions

1. **Load the playbook-monitor agent** and run Step 5 (review and approval flow).

2. **If no proposals file exists** or it is empty: respond *"No pending proposals. Playbook is up to date."* Do not proceed further.

3. **Present proposals one at a time.** For each, show the full proposal block and offer four options: Accept, Reject, Edit, Defer.

4. **For Accept or Edit:** show the exact diff to `~/.codex/claude-for-legal/commercial-legal/CLAUDE.md` before writing. Only apply after the attorney explicitly confirms.

5. **For Reject or Defer:** log the decision. Do not modify `~/.codex/claude-for-legal/commercial-legal/CLAUDE.md`.

6. **After all proposals are resolved:** show a summary of what changed, then archive the proposals file.

## Examples

```
commercial-legal-review-proposals
```

```
commercial-legal-review-proposals
(runs automatically after playbook-monitor notifies you)
```
