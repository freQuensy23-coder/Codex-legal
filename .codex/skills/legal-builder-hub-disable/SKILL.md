---
name: legal-builder-hub-disable
description: >
  Codex CLI version of legal-builder-hub:disable. Disable a community skill installed through the hub without removing its files. Use when the user wants to temporarily quiet a community skill ("disable [skill]"), stop its hooks from firing while keeping its config, or re-enable a previously disabled skill.
argument-hint: "[skill name]"
---

# Codex Adaptation Notes

This skill was converted from `legal-builder-hub:disable` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `legal-builder-hub-disable`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/legal-builder-hub/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: legal-builder-hub-disable

Run the `disable` workflow from the skill-manager reference skill against the
named skill.

What disable does:

- Renames the skill's `SKILL.md` to `SKILL.md.disabled` so Claude no longer
  discovers it as an active skill. Files, references, templates, and config
  stay in place.
- If the skill ships hooks in `hooks/hooks.json`, also rename that file to
  `hooks.json.disabled` so no automatic triggers fire while the skill is
  disabled.
- Logs the action to
  `~/.codex/claude-for-legal/legal-builder-hub/install-log.yaml`.

Safety rules:

1. **Only disable community skills installed through this hub.** Same check
   as uninstall — consult the install log and CLAUDE.md installed table.
2. **Never disable a first-party plugin's skill.** Off-limits.
3. **Confirm before renaming.** Show the paths, get explicit `yes`.

Re-enable by running the command again with the same skill name — the
skill-manager workflow recognizes a disabled skill and flips the rename back.

> Detailed uninstall, disable, and re-enable workflows live in the
> `skill-manager` reference skill — load it before doing substantive work.
