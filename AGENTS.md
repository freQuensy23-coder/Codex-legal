# AGENTS.md

Guidance for Codex when working on this repository.

This repository is the Codex port of Anthropic's `claude-for-legal`. The upstream Claude plugin tree is intentionally preserved as the source of truth. Codex runtime surfaces are generated or adapted from that source rather than replacing it in place.

## Codex runtime surfaces

- `.codex/skills/<plugin>-<skill>/SKILL.md` — generated Codex skills.
- `.codex/agents/<plugin>-<agent>.toml` — generated Codex custom subagents.
- `scripts/install_codex_mcp.py` — translates all repository `.mcp.json` declarations into Codex `config.toml` MCP entries.
- `scripts/codex_managed_agents.py` — Codex/Responses-compatible runtime for all managed-agent cookbooks.
- `scripts/test_codex_port.py` — mocked end-to-end validation for managed agents, Responses API boundary, and every MCP integration.
- `~/.codex/claude-for-legal/` — user practice profiles and shared organization configuration installed by the setup script.

## Source layout

- `<plugin>/skills/*/SKILL.md` is the canonical upstream skill content.
- `<plugin>/agents/*.md` is the canonical upstream custom-agent content.
- `<plugin>/.mcp.json` is the canonical upstream MCP declaration.
- `<plugin>/CLAUDE.md` is a practice-profile template. Keep this filename: workflows explicitly read and write these profile files under `~/.codex/claude-for-legal/<plugin>/CLAUDE.md`. It is data/configuration, not Codex repository instructions.
- `managed-agent-cookbooks/*/agent.yaml` and `subagents/*.yaml` are the canonical upstream managed-agent manifests.

Do not create per-plugin `AGENTS.md` files by blindly renaming those practice-profile templates.

## Porting rule

When upstream changes a skill, agent, MCP declaration, or managed-agent cookbook, update the corresponding Codex surface in the same change. A merge is incomplete if Claude-specific runtime semantics remain reachable from the Codex path.

The Codex managed-agent port must preserve:

1. system/developer instructions;
2. local tool scoping and write isolation;
3. MCP server/tool scoping;
4. referenced legal skills;
5. callable subagent topology;
6. structured output schemas;
7. handoff/security constraints.

Anthropic-specific runtime objects such as `agent_toolset_20260401`, `mcp_toolset`, Claude model IDs, and `anthropic.Anthropic().beta.agents` must not appear in generated Codex requests.

## Validation

Run before considering the port complete:

```bash
python3 scripts/convert_to_codex_skills.py
python3 scripts/convert_to_codex_agents.py
python3 scripts/install_codex_mcp.py --check
python3 scripts/codex_managed_agents.py --validate-all
python3 scripts/test_codex_port.py
python3 scripts/lint-tool-scope.py
```

Also test a clean installation:

```bash
tmp_home="$(mktemp -d)"
HOME="$tmp_home" scripts/install_codex_skills.sh --all --init-config --init-agents --init-mcp
```

The mocked E2E test is intentionally independent of live OpenAI credentials and live third-party MCP credentials. A green test means the Codex port, protocol shapes, orchestration, and integration boundaries are wired correctly; it does not assert that external vendors are currently online or that a user's OAuth/API credentials are valid.

## Safety and review

Legal outputs remain drafts for qualified attorney review. Preserve the upstream privilege, citation, deadline-verification, prompt-injection, and irreversible-action guardrails when adapting content. Do not weaken tool scopes to make a test pass.
