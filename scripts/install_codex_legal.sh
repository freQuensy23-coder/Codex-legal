#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_bin="${CODEX_BIN:-$(command -v codex || true)}"
if [[ -z "$codex_bin" ]]; then
  echo "codex CLI not found (set CODEX_BIN or install Codex)" >&2
  exit 1
fi

codex_home="${CODEX_HOME:-${HOME}/.codex}"
config_root="${codex_home}/claude-for-legal"
runtime="${config_root}/runtime-marketplace"
agents_tmp="$(mktemp -d)"
trap 'rm -rf "$agents_tmp"' EXIT

mkdir -p "$codex_home" "$config_root" "$codex_home/agents"

# Local marketplaces are referenced by path by Codex, so this runtime tree must
# be persistent. Rebuild it atomically under CODEX_HOME rather than /tmp.
python3 "$repo_root/scripts/build_codex_marketplace.py" \
  --output "$runtime" \
  --config-root "$config_root"
python3 "$repo_root/scripts/convert_to_codex_agents.py" \
  --output "$agents_tmp" \
  --config-root "$config_root"

# Keep a stable local source snapshot for upstream instructions that refer to the
# plugin root. It is runtime data, not an Anthropic Managed Agent deployment.
rm -rf "$config_root/source"
mkdir -p "$config_root/source"
cp -R "$runtime/plugins/." "$config_root/source/"

# Initialize editable practice profiles without overwriting existing user data.
if [[ -f "$repo_root/references/company-profile-template.md" && ! -e "$config_root/company-profile.md" ]]; then
  cp "$repo_root/references/company-profile-template.md" "$config_root/company-profile.md"
fi
for plugin_dir in "$runtime"/plugins/*; do
  [[ -d "$plugin_dir" ]] || continue
  plugin="$(basename "$plugin_dir")"
  if [[ -f "$plugin_dir/CLAUDE.md" ]]; then
    mkdir -p "$config_root/$plugin"
    if [[ ! -e "$config_root/$plugin/CLAUDE.md" ]]; then
      cp "$plugin_dir/CLAUDE.md" "$config_root/$plugin/CLAUDE.md"
    fi
  fi
done

# Install native Codex agent roles. Generated role names are namespaced by legal plugin.
agent_count=0
for src in "$agents_tmp"/*.toml; do
  [[ -f "$src" ]] || continue
  cp "$src" "$codex_home/agents/$(basename "$src")"
  agent_count=$((agent_count + 1))
done

# Re-register the persistent marketplace. Removal failures are harmless on first install.
"$codex_bin" plugin marketplace remove codex-legal >/dev/null 2>&1 || true
"$codex_bin" plugin marketplace add "$runtime" >/dev/null

mapfile -t plugins < <(python3 - "$runtime/codex-legal-build.json" <<'PY'
import json, sys
for p in json.load(open(sys.argv[1], encoding='utf-8'))['plugins']:
    print(p)
PY
)

for plugin in "${plugins[@]}"; do
  "$codex_bin" plugin remove "$plugin@codex-legal" >/dev/null 2>&1 || true
  "$codex_bin" plugin add "$plugin@codex-legal" --json >/dev/null
done

# Ask the actual Codex plugin manager for the final state and fail if anything is missing.
"$codex_bin" plugin list --marketplace codex-legal --json >"$runtime/plugin-list.json"
python3 - "$runtime/codex-legal-build.json" "$runtime/plugin-list.json" <<'PY'
import json, sys
expected = set(json.load(open(sys.argv[1], encoding='utf-8'))['plugins'])
state = json.load(open(sys.argv[2], encoding='utf-8'))
installed = {p['name'] for p in state.get('installed', []) if p.get('enabled', True)}
missing = sorted(expected - installed)
if missing:
    raise SystemExit('Codex did not install/enable plugins: ' + ', '.join(missing))
print(f'Codex Legal installed: {len(expected)} plugins')
PY

cat <<EOF
Codex Legal local install complete.
Plugins: ${#plugins[@]}
Agents: $agent_count
Practice data: $config_root
Marketplace: $runtime
Run with GPT-5.6/xhigh: bash $repo_root/scripts/codex-legal
EOF
