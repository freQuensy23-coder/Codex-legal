---
name: legal-clinic-form-generation
description: >
  Codex CLI version of legal-clinic:form-generation. Reference: DEPRECATED — use `/draft` instead. This skill has been folded into the draft skill, which handles practice-area document generation including form population. Kept as a redirect for migration.
---

# Codex Adaptation Notes

This skill was converted from `legal-clinic:form-generation` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `legal-clinic-form-generation`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/legal-clinic/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# [DEPRECATED] Form Generation → see `/draft`

This skill was folded into `skills/draft/` during the v2 rebuild. The `/draft`
command handles first-draft generation for all clinic documents including form
population (asylum applications, eviction answers, protective order petitions,
etc.) with practice-area templates and jurisdiction-aware formatting.

**Use `/draft [document type]` instead.**

See `skills/draft/SKILL.md` for the full workflow.
