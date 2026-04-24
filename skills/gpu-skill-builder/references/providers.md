# Providers Reference

Use this reference when changing provider support, GPU creation paths, provider status claims, or live provisioning behavior.

## Runtime Truth

- Provider enum and shared models: `models.py`
- Provider registration: `providers/__init__.py`
- Main orchestration: `skill.py`
- Provider implementations: `providers/`
- Current support table and caveats: root `README.md`

Only providers registered in `PROVIDER_MAP` are runtime providers for `run_skill()`.

## Current Provider Roles

- `huggingface`: supported runtime provider using Hugging Face Inference Endpoints API v2. Probes require `HF_TOKEN`.
- `digitalocean`: supported runtime provider creating droplets and deploying remote `vLLM` over SSH with resolved deployment profiles.
- `modal`: supported runtime provider deploying OpenAI-compatible `vLLM` apps and classifying scaled-to-zero behavior.
- `openrouter`: fallback-only OpenAI-compatible lane when a GPU path fails or becomes unhealthy. It is not part of GPU fleet monitoring.
- `amd`: blocked in current code and should return a clear unsupported message until a real provider integration exists.

Provider folders under `launch-playbooks/` are runbooks or placeholders unless code and the root README explicitly say they are wired into `skill.py`.

## Change Rules

- When adding a provider, update the enum, provider class, provider registration, runtime profiles, root README support table, and tests together.
- When changing provider status language, verify both provider code and root README before editing docs.
- Keep live operations explicit. Do not create, destroy, or benchmark GPU resources just to validate a code or documentation change unless the user asks for live execution.
- Preserve idempotency, concurrency, spend-cap, TTL, and fallback behavior in `skill.py` when modifying create paths.
