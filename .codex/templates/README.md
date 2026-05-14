# Codex Configuration Templates

Converted skills read practice profiles from:

```text
~/.codex/claude-for-legal/company-profile.md
~/.codex/claude-for-legal/<plugin>/CLAUDE.md
```

Use the installer to initialize those templates from the canonical repository files:

```bash
scripts/install_codex_skills.sh --starter --init-config
```

The installer copies:

- `references/company-profile-template.md` to `~/.codex/claude-for-legal/company-profile.md`
- each root-level `<plugin>/CLAUDE.md` template to `~/.codex/claude-for-legal/<plugin>/CLAUDE.md`

It also rewrites Claude plugin paths to Codex paths and converts slash-command examples to Codex skill names.

The templates are intentionally not duplicated under `.codex/templates/`; keeping a single canonical source prevents drift when upstream practice profiles change.
