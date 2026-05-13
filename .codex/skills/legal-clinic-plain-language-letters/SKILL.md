---
name: legal-clinic-plain-language-letters
description: >
  Codex CLI version of legal-clinic:plain-language-letters. Reference: DEPRECATED — use `/client-letter` for routine correspondence or `/status client` for substantive updates. Split into two more focused skills during the v2 rebuild. Kept as a redirect for migration.
---

# Codex Adaptation Notes

This skill was converted from `legal-clinic:plain-language-letters` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `legal-clinic-plain-language-letters`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/legal-clinic/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# [DEPRECATED] Plain-Language Letters → see `/client-letter` and `/status client`

This skill was split during the v2 rebuild:

- **Routine correspondence** (appointment confirms, document requests, brief
  "we filed it" updates) → `skills/client-letter/` — use `/client-letter [type]`

- **Substantive client status updates** → `skills/status/` in client-facing
  mode — use `/status client`

Both apply the plain-language standards (reading level, no jargon) from CLAUDE.md.

See the respective SKILL.md files for full workflows.
