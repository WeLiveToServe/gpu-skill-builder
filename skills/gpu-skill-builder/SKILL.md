---
name: gpu-skill-builder
description: Use when Codex needs to work in the gpu-skill-builder repo on GPU-backed OpenAI-compatible inference endpoints, provider integrations, model/deployment/harness profiles, vLLM serving, readiness and monitoring guardrails, cost controls, harness handoff manifests, CLI wrappers, or benchmark workflows. Also use for safe maintenance touching skill.py, providers, profiles, profile_registry.py, remote_vllm.py, endpoint_probe.py, monitor.py, scheduler.py, handoff.py, or .bench.
---

# GPU Skill Builder

## Operating Principle

Treat this repo as an operational system that can spend money and launch live GPU infrastructure. Read the relevant runtime files before changing behavior. Do not run live provider provisioning, destroy, billing, or benchmark orchestration commands unless the user explicitly asks for that operation.

The runtime source of truth is the root `README.md`, committed manifests under `profiles/`, and the Python code. Treat `docs/research/` and most `launch-playbooks/` content as planning, runbook, or validation history unless current code or the root README says otherwise.

## Core Workflow

1. Classify the work before editing:
   - Provider/GPU creation: read `references/providers.md`.
   - Model profiles, vLLM launch, memory, KV cache, or serving setup: read `references/runtime-profiles-and-serving.md`.
   - Readiness, health, staleness, TTL, spend, or Telegram alerts: read `references/readiness-monitoring-cost.md`.
   - Harness/calling-agent integration or CLI wrappers: read `references/harness-handoff.md`.
   - Benchmark suites, matrix runs, or local-GPU overrides: read `references/benchmarks.md`.
2. Preserve the main contract:
   - `run_skill()` means the infrastructure/provider handoff path succeeded.
   - `ensure_active_endpoint()` is the strict pre-use guard and must pass before relying on an endpoint for real work.
   - `result.harness_handoff` is non-secret endpoint metadata for sibling harnesses; it must not contain API keys.
3. Keep profile-driven behavior explicit:
   - Add or edit committed profiles for distinct runtime behavior.
   - Do not silently mutate default interactive profiles for benchmark or one-off needs.
   - Keep profile, README, and tests aligned when a runtime contract changes.
4. Distinguish implementation from evidence:
   - Supported runtime providers are those wired through `Provider` and `PROVIDER_MAP`.
   - Playbook validation notes do not by themselves mean `skill.py` supports a provider.
   - OpenRouter is a fallback lane, not a monitored GPU provider.

## Safety Rules

- Before live spend or destructive operations, surface provider, hardware, model, estimated duration, and whether auto-stop/monitoring is configured.
- Prefer process-scoped environment overrides for benchmark and harness routing. Do not write secrets into sibling repos.
- If a provider endpoint is not ready, wrong-model, unhealthy, unreachable, provider-error, or scaled-to-zero, route decisions through the existing probe/fallback paths instead of inventing ad hoc checks.
- If changing shared contracts, add focused tests around profile resolution, endpoint probing, monitor state, handoff manifests, or benchmark command generation.

## Validation

Use the narrowest relevant tests first. For changes to this skill package, run:

```bash
python C:/Users/keith/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gpu-skill-builder
```

For repo contract changes related to this skill, usually run:

```bash
pytest tests/test_readme_consistency.py tests/test_profile_registry.py tests/test_remote_vllm_profiles.py
```
