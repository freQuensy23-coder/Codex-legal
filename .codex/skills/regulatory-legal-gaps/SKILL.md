---
name: regulatory-legal-gaps
description: >
  Codex CLI version of regulatory-legal:gaps. Open gaps tracker — what's flagged and not yet closed. Use when the user asks "what gaps are open", "gap tracker", "remediation status", or wants to close (--close GAP-ID) or risk-accept (--accept GAP-ID) a tracked gap.
argument-hint: "[optional: --close GAP-ID | --accept GAP-ID]"
---

# Codex Adaptation Notes

This skill was converted from `regulatory-legal:gaps` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `regulatory-legal-gaps`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/regulatory-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: regulatory-legal-gaps

1. Read the gap tracker at `~/.codex/claude-for-legal/regulatory-legal/gap-tracker.yaml`.
2. If `--close`: mark gap closed with resolution note.
3. If `--accept`: record the risk-acceptance rationale and acceptor, status → risk-accepted.
4. Otherwise: report open gaps by age and materiality.

> Detailed tracker schema, status-report format, owner-notification logic (per-send confirmation, no exceptions), reminder cadence, the close/risk-accept modes, and the consequential-action gate live in the **gap-surfacer** reference skill — load it before doing substantive work.
