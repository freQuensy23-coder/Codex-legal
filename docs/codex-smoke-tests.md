# Codex Smoke Tests

Use these checks after installing the starter set with:

```bash
scripts/install_codex_skills.sh --starter --init-config
```

Restart Codex CLI before testing. These are smoke tests, not legal correctness tests. The goal is to confirm skill loading, routing language, Codex-side profile paths, and attorney-review gates.

## Expected install shape

```bash
test -f ~/.codex/skills/privacy-legal-dsar-response/SKILL.md
test -f ~/.codex/skills/commercial-legal-review/SKILL.md
test -f ~/.codex/skills/ai-governance-legal-use-case-triage/SKILL.md
test -f ~/.codex/claude-for-legal/company-profile.md
```

Expected result: all commands exit `0`.

## DSAR Response

Prompt:

```text
Use privacy-legal-dsar-response. A customer emailed: "Please send me all personal data you hold about me and delete my account." I only need a draft workflow and questions for attorney review; do not send anything.
```

Expected checks:

- Mentions `~/.codex/claude-for-legal/privacy-legal/CLAUDE.md`, not `~/.claude/plugins/...`.
- Produces acknowledgment and substantive-response workflow or drafts.
- Flags identity verification, systems search, jurisdiction, exemptions, and attorney review.
- Does not present itself as legal advice.

## Commercial Contract Review

Prompt:

```text
Use commercial-legal-review. I have a vendor MSA with an order form, DPA, auto-renewal, limitation of liability, and indemnity sections. No file yet; ask me for the minimum inputs you need before review.
```

Expected checks:

- Routes by document structure and asks for the agreement or relevant text.
- Mentions `~/.codex/claude-for-legal/commercial-legal/CLAUDE.md`.
- Does not silently assume sales-side vs purchasing-side if ambiguous.
- Keeps output as a draft for attorney review.

## AI Use Case Triage

Prompt:

```text
Use ai-governance-legal-use-case-triage. Sales wants to use AI to score leads automatically and prioritize outreach. Give a first-pass triage and list what must be verified before approval.
```

Expected checks:

- Distinguishes use-case triage from final approval.
- Flags registry lookup, applicable jurisdictions, role/risk classification, privacy/product handoffs, and human review.
- Uses Codex-side profile path.

## Litigation Claim Chart

Prompt:

```text
Use litigation-legal-claim-chart. Build the scaffold for a breach of contract claim chart. Do not invent facts; show the columns and the evidence I need to provide.
```

Expected checks:

- Produces a scaffold with elements, source/evidence columns, gaps, and verification notes.
- Does not fabricate facts, citations, or case posture.
- Keeps privilege/work-product and attorney review boundaries clear.

## Law Student Socratic Drill

Prompt:

```text
Use law-student-socratic-drill for consideration in contracts. Ask me one question at a time and do not give me the answer unless I ask after trying.
```

Expected checks:

- Starts with a question, not a mini lecture.
- Preserves learning mode and does not write a model answer.
- Uses study-scaffold language rather than legal advice.

## Failure Signals

Treat any of these as a conversion or install bug:

- Mentions `~/.claude/plugins/config/claude-for-legal` in a Codex skill response.
- Tells the user to run `/plugin install` as the primary Codex install path.
- Uses `/plugin:skill` as the only invocation form instead of `<plugin>-<skill>`.
- Proceeds with substantive legal output after stating the required practice profile is missing.
- Suggests filing, sending, executing, or relying on a legal position without attorney review.
