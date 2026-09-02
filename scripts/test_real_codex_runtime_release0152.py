#!/usr/bin/env python3
"""Codex 0.152.1 compatibility entrypoint for the exhaustive runtime test."""

from pathlib import Path
import test_real_codex_runtime as runtime


def codex_base(codex: str, repo: Path) -> list[str]:
    # 0.152.1 explicitly rejects --strict-config for `codex debug`.
    return [
        codex,
        "-c", 'orchestrator.mcp.enabled=false',
        "-C", str(repo),
    ]


runtime.codex_base = codex_base
raise SystemExit(runtime.main())
