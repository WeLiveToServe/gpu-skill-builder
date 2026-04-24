# Runtime Profiles And Serving Reference

Use this reference when changing model selection, deployment profiles, harness profiles, vLLM launch arguments, memory behavior, KV cache settings, or model-serving contracts.

## Runtime Truth

- Profile schemas and resolution: `profile_registry.py`
- Committed profile manifests: `profiles/`
- Static model catalog for interactive choices: `catalog.py`
- DigitalOcean remote serving: `remote_vllm.py`
- Provider create paths: `providers/`

The committed `profiles/` tree is the canonical runtime contract for profile-driven launches. Generated fallback profiles exist for flexibility, but durable behavior should be represented by committed JSON profiles.

## Profile Families

- `ModelProfile`: provider model ID, alias, context window, throughput hints, launch hints.
- `DeploymentProfile`: provider/hardware/runtime kind, served model name, vLLM/runtime knobs, readiness expectations.
- `HarnessProfile`: protocol, base URL normalization mode, model-name source, expected env key names.
- `GatewayProfile`: schema exists, but current runtime behavior is direct endpoint selection.

## Serving Paths

- DigitalOcean: create droplet, SSH into it, write a `systemd` `vllm.service`, wait for `/health`, then validate `/v1/models`.
- Modal: deploy a managed Modal `vLLM` app and probe the resulting OpenAI-compatible endpoint.
- Hugging Face: create a managed protected endpoint through the HF endpoint API.
- OpenRouter: return fallback endpoint metadata from configured OpenRouter settings.

## Performance And Memory Knobs

Treat these deployment runtime fields as contract-bearing:

- `max_model_len`
- `max_num_seqs`
- `gpu_memory_utilization`
- `max_num_batched_tokens`
- `tensor_parallel_size`
- `pipeline_parallel_size`
- `expert_parallel`
- `enable_eplb`
- `prefix_caching_policy`
- `chunked_prefill_policy`
- `kv_cache_dtype`
- `extra_args`

Use explicit benchmark or evaluation deployment profiles for benchmark-safe behavior such as disabled prefix caching or lower concurrency. Do not hide benchmark behavior inside generic defaults.

## Change Rules

- When changing `remote_vllm.py` argument rendering, add or update focused tests in `tests/test_remote_vllm_profiles.py`.
- When adding profile fields or selection behavior, update schema tests and README consistency checks.
- Keep served model naming consistent across deployment profile, `/v1/models`, endpoint probe, and harness handoff.
