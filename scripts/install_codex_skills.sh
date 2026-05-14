#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install Claude for Legal skills into a Codex CLI skills root.

Default behavior follows the local Codex skill governance rules:
- install only the starter set, not all 151 skills
- install into ~/.codex/skills as third-party/runtime-installed skills
- do not write to ~/.agents/skills
- do not overwrite existing skills unless --force is passed

Usage:
  scripts/install_codex_skills.sh [--starter|--all] [--target DIR] [--dry-run] [--force] [--init-config] [--config-target DIR]

Options:
  --starter      Install .codex/starter-skills.txt (default).
  --all          Install every skill under .codex/skills.
  --target DIR   Install target. Default: ~/.codex/skills.
  --config-target DIR
                 Config template target. Default: ~/.codex/claude-for-legal.
  --dry-run      Print actions without copying files.
  --force        Overwrite existing target skill directories.
  --init-config  Also initialize ~/.codex/claude-for-legal templates if missing.
  -h, --help     Show this help.
EOF
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skills_root="$repo_root/.codex/skills"
starter_file="$repo_root/.codex/starter-skills.txt"
target="${HOME}/.codex/skills"
config_target="${HOME}/.codex/claude-for-legal"
mode="starter"
dry_run=0
force=0
init_config=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --starter)
      mode="starter"
      shift
      ;;
    --all)
      mode="all"
      shift
      ;;
    --target)
      target="${2:?--target requires a directory}"
      shift 2
      ;;
    --config-target)
      config_target="${2:?--config-target requires a directory}"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --force)
      force=1
      shift
      ;;
    --init-config)
      init_config=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$skills_root" ]]; then
  echo "Missing generated skills directory: $skills_root" >&2
  echo "Run: python3 scripts/convert_to_codex_skills.py" >&2
  exit 1
fi

skill_names=()
if [[ "$mode" == "all" ]]; then
  while IFS= read -r skill; do
    skill_names+=("$skill")
  done < <(find "$skills_root" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
else
  while IFS= read -r skill; do
    skill_names+=("$skill")
  done < <(sed -e 's/#.*$//' -e '/^[[:space:]]*$/d' "$starter_file")
fi

if [[ ${#skill_names[@]} -eq 0 ]]; then
  echo "No skills selected." >&2
  exit 1
fi

missing=()
for skill in "${skill_names[@]}"; do
  [[ -d "$skills_root/$skill" ]] || missing+=("$skill")
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Starter list references missing skills:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

target_physical="$(python3 -c 'import os, sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "$target")"
agents_skills_physical="$(python3 -c 'import os, sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "${HOME}/.agents/skills")"
if [[ "$target_physical" == "$agents_skills_physical" ]]; then
  echo "Refusing to install Codex skills into ~/.agents/skills." >&2
  echo "Use ~/.codex/skills for third-party/runtime-installed Codex skills." >&2
  exit 1
fi

echo "Mode: $mode"
echo "Selected skills: ${#skill_names[@]}"
echo "Target: $target"
if [[ "$dry_run" -eq 1 ]]; then
  echo "Dry run: yes"
fi

if [[ "$dry_run" -eq 0 ]]; then
  mkdir -p "$target"
fi

installed=0
skipped=0
overwritten=0

for skill in "${skill_names[@]}"; do
  src="$skills_root/$skill"
  dst="$target/$skill"

  if [[ -e "$dst" && "$force" -ne 1 ]]; then
    echo "skip existing: $skill"
    skipped=$((skipped + 1))
    continue
  fi

  if [[ "$dry_run" -eq 1 ]]; then
    if [[ -e "$dst" && "$force" -eq 1 ]]; then
      echo "would overwrite: $skill"
    else
      echo "would install: $skill"
    fi
    continue
  fi

  if [[ -e "$dst" ]]; then
    rm -rf "$dst"
    overwritten=$((overwritten + 1))
  fi

  cp -R "$src" "$dst"
  installed=$((installed + 1))
  echo "installed: $skill"
done

if [[ "$init_config" -eq 1 ]]; then
  echo "Initializing Codex-side config templates under $config_target"
  if [[ "$dry_run" -eq 0 ]]; then
    mkdir -p "$config_target"
  fi

  if [[ "$dry_run" -eq 1 ]]; then
    echo "would init config: company-profile.md"
  elif [[ ! -e "$config_target/company-profile.md" || "$force" -eq 1 ]]; then
    cp "$repo_root/references/company-profile-template.md" "$config_target/company-profile.md"
  fi

  for profile in "$repo_root"/*/CLAUDE.md; do
    [[ -f "$profile" ]] || continue
    plugin="$(basename "$(dirname "$profile")")"
    dst_dir="$config_target/$plugin"
    dst="$dst_dir/CLAUDE.md"
    if [[ "$dry_run" -eq 1 ]]; then
      echo "would init config: $plugin/CLAUDE.md"
      continue
    fi
    mkdir -p "$dst_dir"
    if [[ ! -e "$dst" || "$force" -eq 1 ]]; then
      python3 - "$profile" "$dst" <<'PY'
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

text = src.read_text()
text = text.replace(
    "~/.claude/plugins/config/claude-for-legal",
    "~/.codex/claude-for-legal",
)
text = text.replace(
    "~/.claude/plugins/cache/claude-for-legal",
    "~/.codex/claude-for-legal/cache",
)
text = re.sub(
    r"/([a-z][a-z0-9-]+):([a-z][a-z0-9-]+)",
    r"\1-\2",
    text,
)
dst.write_text(text)
PY
    fi
  done
fi

echo "Summary: installed=$installed skipped=$skipped overwritten=$overwritten"
echo "Restart Codex CLI to load newly installed skill descriptions."
