# Implementation Work Items

This document turns the roadmap into issue-sized work items for `gpu-skill-builder`. Each item is written to be small enough to assign, review, and merge without mixing unrelated concerns.

Use this together with:

- [Adoption Roadmap](./ADOPTION_ROADMAP.md)
- [Deployment Checklists and Launch Recipes](./DEPLOYMENT_CHECKLISTS.md)
- [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json)

## Working Rule

Do not mix "new package adoption", "deployment contract changes", and "provider behavior changes" in the same pull request. The repo is already carrying live provider logic and bench work, so the safest implementation path is narrow PRs with explicit acceptance gates.

## Work Item List

### `PG-01` Canonical Deployment Matrix Loader

Goal:
- Make the new machine-readable matrix the canonical mapping for resolved model names, provider classifications, and runtime defaults.

Primary touch points:
- `docs/research/production-grade-gpu-deployment/MODEL_PROVIDER_RUNTIME_MATRIX.json`
- `catalog.py`
- `models.py`
- `README.md`

Deliverables:
- a small loader/helper that validates the matrix schema
- canonical names for:
  - `gpt-oss-120b`
  - `Qwen3-Coder-480B`
  - `DeepSeek-V3.1`
  - `MiniMax-M2.7`
  - `Kimi-K2`
- README docs aligned to those names

Acceptance criteria:
- one code path can answer "what is the canonical target for this model family?"
- docs and code no longer drift on model naming

### `PG-02` Deployment Profile Schema

Goal:
- Define a typed deployment-profile object that mirrors the new manifest drafts.

Primary touch points:
- `models.py`
- new profile/schema helper module
- `remote_vllm.py`
- `tests/test_models.py`

Deliverables:
- a Pydantic model for self-host `vLLM` deployment profiles
- explicit fields for:
  - runtime kind
  - model id
  - provider
  - hardware slug
  - `max_model_len`
  - `max_num_seqs`
  - `gpu_memory_utilization`
  - TP / PP / expert-parallel switches
  - prefix-caching policy
  - chunked-prefill policy

Acceptance criteria:
- deployment profiles are validated before any remote launch starts
- unsafe or incomplete profiles fail fast with clear messages

### `PG-03` Manifest-Driven `remote_vllm`

Goal:
- Stop hardcoding one generic `vLLM` service in `remote_vllm.py` and instead render from a profile/manifest.

Primary touch points:
- `remote_vllm.py`
- `launch-playbooks/production-grade/manifests/`
- `launch-playbooks/production-grade/systemd/vllm-model.service.template`
- `tests/test_do_provider_hardening.py`

Deliverables:
- remote deployment path that accepts a profile or manifest-derived configuration
- rendered service file instead of today's fixed inline template
- conservative per-model argument sets applied on launch

Acceptance criteria:
- `remote_vllm.py` can launch at least:
  - `gpt-oss-120b` `1x H200`
  - one `8x H200` MoE profile
- the resulting unit file matches the selected manifest values

### `PG-04` Health, Readiness, And Acceptance Gates

Goal:
- Make endpoint readiness stricter than "service started" and align it with the new checklist doc.

Primary touch points:
- `remote_vllm.py`
- `providers/do_provider.py`
- `skill.py`
- `monitor.py`
- `tests/test_do_provider_hardening.py`

Deliverables:
- readiness checks for:
  - `/health`
  - `/v1/models`
  - one smoke prompt
- optional long-prompt gate for profiles marked `128k`
- structured failure reason when a node is live but not truly usable

Acceptance criteria:
- the provider result can distinguish:
  - instance created but model unhealthy
  - instance healthy but wrong model
  - instance healthy but failed smoke prompt

### `PG-05` Surface The Right `vLLM` Knobs

Goal:
- Widen the repo's `vLLM` control surface to the parameters that actually matter for `128k`.

Primary touch points:
- `config.py`
- `remote_vllm.py`
- `README.md`
- `docs/research/production-grade-gpu-deployment/DEPLOYMENT_CHECKLISTS.md`

Deliverables:
- supported settings for:
  - `max_model_len`
  - `max_num_seqs`
  - `gpu_memory_utilization`
  - `max_num_batched_tokens`
  - TP / PP
  - expert parallel
  - prefix caching
  - chunked prefill

Acceptance criteria:
- the repo can express all conservative profiles in the new manifest set without patching shell strings by hand

### `PG-06` Systemd And Rollback Standardization

Goal:
- Standardize service installation, restart policy, and rollback inputs across providers.

Primary touch points:
- `launch-playbooks/production-grade/systemd/`
- `scripts/monitor/install_monitor_service.sh`
- `remote_vllm.py`
- `README.md`

Deliverables:
- one canonical model-service unit template
- one env-file template
- one rollback checklist that references:
  - image version
  - model revision
  - runtime profile id

Acceptance criteria:
- a deployment can be recreated from the same profile without hand-editing the remote host
- rollback inputs are explicit and reviewable

### `PG-07` Metrics, Tracing, And GPU State

Goal:
- Add enough telemetry that failures are explainable instead of guessed at.

Primary touch points:
- `monitor.py`
- `gpu_monitor_daemon.py`
- `requirements.txt`
- future metrics/tracing helper module
- `tests/test_monitor.py`

Deliverables:
- request/deploy counters
- deploy latency
- restart count
- endpoint readiness timing
- GPU memory and utilization collection

Package direction:
- `prometheus-client`
- `opentelemetry-*`
- `nvidia-ml-py`

Acceptance criteria:
- operator can answer:
  - which profile was launched
  - how long readiness took
  - whether GPU memory pressure was already high

### `PG-08` Model Evals And Harness Evals

Goal:
- Add repeatable eval entry points for both endpoint quality and harness behavior.

Primary touch points:
- `.bench/`
- `requirements.txt`
- new eval runner docs/scripts

Deliverables:
- baseline model regression path
- baseline harness tool-call correctness path
- profile-aware smoke evals

Package direction:
- `inspect-ai`
- `lm-evaluation-harness`

Acceptance criteria:
- every supported deployment profile has:
  - a smoke eval
  - a harness/tool-call probe

### `PG-09` Provider Contract Cleanup

Goal:
- Make providers explicitly return deployment-contract details instead of burying assumptions in provider-specific code.

Primary touch points:
- `providers/base.py`
- `providers/do_provider.py`
- `providers/hf_provider.py`
- `providers/modal_provider.py`
- `providers/openrouter_provider.py`
- `models.py`

Deliverables:
- provider result shape that can carry:
  - runtime kind
  - profile id
  - endpoint class
  - managed vs self-hosted
- clearer boundaries between:
  - infrastructure provision
  - model launch
  - endpoint validation

Acceptance criteria:
- control-plane logic does not need to reverse-engineer provider behavior from strings

### `PG-10` Control Plane / Inference Plane Separation

Goal:
- Prepare the repo to orchestrate GPU nodes without assuming orchestration runs on the GPU node itself.

Primary touch points:
- `skill.py`
- `main.py`
- `monitor.py`
- `gpu_monitor_daemon.py`
- provider modules

Deliverables:
- explicit notion of control-plane host responsibilities
- remote deployment and monitoring documented as first-class workflows
- clear support path for Oracle as control-plane infrastructure even when not serving inference

Acceptance criteria:
- orchestration can survive GPU node replacement
- monitoring and eval coordination do not require colocating on the inference host

## Suggested Merge Order

1. `PG-01` Canonical deployment matrix loader
2. `PG-02` Deployment profile schema
3. `PG-03` Manifest-driven `remote_vllm`
4. `PG-04` Health, readiness, and acceptance gates
5. `PG-05` Surface the right `vLLM` knobs
6. `PG-06` Systemd and rollback standardization
7. `PG-07` Metrics, tracing, and GPU state
8. `PG-08` Model evals and harness evals
9. `PG-09` Provider contract cleanup
10. `PG-10` Control plane / inference plane separation

## PR Grouping Advice

Recommended PR boundaries:

- PR 1:
  - `PG-01`
  - `PG-02`
- PR 2:
  - `PG-03`
  - `PG-04`
- PR 3:
  - `PG-05`
  - `PG-06`
- PR 4:
  - `PG-07`
- PR 5:
  - `PG-08`
- PR 6:
  - `PG-09`
  - `PG-10`

This keeps deployment-contract changes, runtime behavior changes, and observability changes from colliding in one review.
