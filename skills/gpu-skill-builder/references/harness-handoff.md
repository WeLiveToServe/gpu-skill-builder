# Harness Handoff Reference

Use this reference when changing endpoint handoff manifests, harness profiles, CLI wrappers, or calling-agent integration.

## Runtime Truth

- Handoff manifest builder: `handoff.py`
- Manifest models: `models.py`
- Harness profile manifests: `profiles/harnesses/`
- Canonical CLI wrapper checkout: `~/dev/cli-harness` or `CLI_HARNESS_DIR`
- Canonical CLI wrapper common code: `~/dev/cli-harness/open_harness_common.py`
- Canonical CLI commands: `codex-os.cmd`, `claude-os.cmd`, `qwen.cmd`, `opencode.cmd`
- Local repo wrapper files: compatibility shims only
- Harness runbook evidence: `cli-playbooks/`

## Handoff Contract

`build_harness_handoff_manifest()` returns non-secret metadata:

- provider, hardware, instance ID/name
- endpoint URL and normalized base URL
- runtime and endpoint class
- model repo ID, served model name, harness model name
- profile IDs
- readiness state
- expected env var key names

Never include API keys or provider secrets in the handoff manifest.

## Base URL And Model Names

Harness profiles control whether `/v1` is appended and which model name source is used. Keep this centralized in `handoff.py` and `profiles/harnesses/` rather than hardcoding per caller.

The CLI wrappers are primarily OpenRouter/local-compatible launch helpers.
Benchmark and local-GPU routing should call the canonical `cli-harness` wrappers
and use process-scoped `HARNESS_OPENROUTER_BASE_URL`,
`HARNESS_OPENROUTER_MODEL`, and `HARNESS_OPENROUTER_API_KEY` overrides instead
of editing local `.env` files or sibling harness repos.

## Change Rules

- When adding a harness, add a harness profile and tests for expected base URL/model/env behavior.
- Keep sibling harness `.env` files local to those repos; this repo emits metadata, not secrets.
- Validate direct endpoint readiness before blaming harness transport.
- Treat `cli-playbooks/` as dated validation evidence, not automatic proof that current profile-driven behavior has been live-validated.
