---
name: employment-legal-expansion-kickoff
description: >
  Codex CLI version of employment-legal:expansion-kickoff. Kick off international expansion planning for a new country — gathers intake, runs EOR vs. entity framing, drafts cross-functional questions, surfaces country-specific flags, and creates a persistent tracker. Use when someone says "we're hiring in [country]", "expansion to [country]", or "first hire in [country]".
argument-hint: "[country name]"
---

# Codex Adaptation Notes

This skill was converted from `employment-legal:expansion-kickoff` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `employment-legal-expansion-kickoff`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: employment-legal-expansion-kickoff

Starts an international expansion project for a new country — gathers intake,
runs EOR vs. entity framing, drafts cross-functional questions, surfaces
country-specific flags, and creates a persistent tracker.

## Instructions

1. Load `~/.codex/claude-for-legal/employment-legal/CLAUDE.md` → jurisdictional footprint, escalation table.
2. Load the `international-expansion` reference skill and run the full workflow.
3. If a tracker file already exists for this country (`~/.codex/claude-for-legal/employment-legal/expansion-[slug].yaml`),
   flag it: "An expansion tracker for [country] already exists. Use
   `employment-legal-expansion-update [country]` to update it, or confirm
   you want to start over."
4. Create `~/.codex/claude-for-legal/employment-legal/expansion-[slug].yaml` on completion.

## Examples

```
employment-legal-expansion-kickoff Germany
```

```
employment-legal-expansion-kickoff
(skill will ask which country)
```

> Detailed EOR vs. entity framework, cross-functional questions, briefing
> templates, and tracker schema live in the `international-expansion`
> reference skill — load it before doing substantive work.
