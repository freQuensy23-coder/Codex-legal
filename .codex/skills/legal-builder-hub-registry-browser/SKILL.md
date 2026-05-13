---
name: legal-builder-hub-registry-browser
description: >
  Codex CLI version of legal-builder-hub:registry-browser. Search watched registries for community legal skills, showing matches with descriptions and offering to show the full SKILL.md before install. Use when the user says "browse", "search skills", "find a skill for", "what's out there for", or wants to add a new registry to the watchlist.
argument-hint: "[search query]"
---

# Codex Adaptation Notes

This skill was converted from `legal-builder-hub:registry-browser` in the Claude for Legal repository. In Codex CLI, invoke it by asking for the workflow by name, for example `legal-builder-hub-registry-browser`, or by describing the legal task in natural language.

Configuration for this fork uses `~/.codex/claude-for-legal/legal-builder-hub/CLAUDE.md` instead of the Claude plugin config directory. Shared organization facts live in `~/.codex/claude-for-legal/company-profile.md`.

All outputs remain drafts for qualified attorney review. Do not treat this skill as legal advice or as authority to file, send, execute, or rely on a legal conclusion without human review.

---


# Codex skill: legal-builder-hub-registry-browser

1. Load `~/.codex/claude-for-legal/legal-builder-hub/CLAUDE.md` → watched registries.
2. Use the workflow below.
3. Search each registry. Show matches with descriptions.
4. Offer to show full SKILL.md for any match.

---

## Purpose

Find skills across the watched registries. Search, preview, decide.

## Load context

`~/.codex/claude-for-legal/legal-builder-hub/CLAUDE.md` → watched registries list.

## Workflow

### Step 1: Fetch registry indexes

For each watched registry:

- GitHub repos: fetch `skills/` directory listing and each `SKILL.md` frontmatter (name + description).
- Marketplace-style registries: fetch the index.

Cache the index locally (`references/registry-cache.json`) so browsing is fast. Refresh cache if >7 days old or on request.

### Step 2: Search

Match query against skill names and descriptions. Simple keyword match is fine — these are small enough that fuzzy search is overkill.

Also: browse by category if the registry organizes skills that way.

### Step 3: Present matches

```markdown
## Search: "[query]"

**Found [N] skills across [M] registries:**

### [skill-name]
**From:** [registry name]
**Description:** [from frontmatter]
[View full SKILL.md] [Install]

### [skill-name]
[...]
```

### Step 4: Preview

On "view full SKILL.md": fetch and show the whole file. User reads it before deciding to install. No surprises.

### Step 5: Add a registry

If the user has a URL to a registry not in the watchlist:

1. Fetch it, validate it's a skills repo (has `skills/` or `.claude-plugin/`)
2. Show what's in it
3. Add to `~/.codex/claude-for-legal/legal-builder-hub/CLAUDE.md` → watched registries on confirmation

## Default registries

- **lpm-skills** — 14 legal project management skills. Practice-agnostic. Good starting point.
- Space for others to be added as the ecosystem grows.

## What this skill does not do

- Install anything. It browses. skill-installer installs.
- Rate or review skills. It shows you the SKILL.md; you judge.
- Search the whole internet. Only watched registries.
