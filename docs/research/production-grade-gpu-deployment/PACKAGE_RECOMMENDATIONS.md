# Package Recommendations For gpu-skill-builder

This matrix evaluates open-source packages that could materially improve `gpu-skill-builder` in four areas:

- `vLLM` configuration quality
- GPU/runtime observability
- devops continuity
- evals for both models and harnesses

The classifications are:

- `Adopt now`
- `Prototype`
- `Track only`
- `Avoid`

## Companion Documents

- [Main Report](./MAIN_REPORT.md)
- [Executive Summary](./EXECUTIVE_SUMMARY.md)
- [Deployment Checklists and Launch Recipes](./DEPLOYMENT_CHECKLISTS.md)
- [Implementation Work Items](./IMPLEMENTATION_WORK_ITEMS.md)
- [Adoption Roadmap](./ADOPTION_ROADMAP.md)
- [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json)

## Current Repo Fit

`gpu-skill-builder` already has:

- provider abstractions
- raw remote deployment logic for `vLLM`
- monitoring and guardrail code
- local pytest coverage for provider hardening

What it does not yet have is a standardized package layer for:

- richer runtime tuning policy
- service telemetry
- deployment automation beyond hand-rolled scripts
- reusable model and harness evaluation stacks

## Recommendation Matrix

| Package | Category | Fit for `gpu-skill-builder` | Recommendation | Why |
|---|---|---|---|---|
| `vllm` | Serving/runtime | Core self-host runtime for DO and Oracle GPU nodes | `Adopt now` | Already aligns with repo architecture and existing deployment scripts; strongest default for raw self-host OpenAI-compatible serving. |
| `sglang` | Serving/runtime | Alternate runtime for giant MoE and disaggregated serving | `Prototype` | Worth keeping as the fallback lane for `Kimi`, `DeepSeek`, and other large MoE cases where `vLLM` topology or EP support is not the operational sweet spot. |
| `text-generation-inference` | Serving/runtime | Alternate OpenAI-ish serving stack | `Track only` | Official HF docs place TGI in maintenance mode and explicitly point users toward `vLLM` and `SGLang` going forward. |
| `litellm` | Gateway/router | Unified gateway across NVIDIA, OCI, OpenRouter, and self-hosted endpoints | `Prototype` | Strong fit if `gpu-skill-builder` needs a control-plane routing layer, retries, budgets, and provider abstraction at the API level; do not replace the provisioning layer with it. |
| `prometheus-client` | Observability | Python-native app metrics for builder, scheduler, and gateway paths | `Adopt now` | Low complexity and high payoff. It gives request, retry, error, and model lifecycle metrics immediately. |
| `opentelemetry-sdk` | Observability | End-to-end traces across `httpx`, FastAPI-style services, remote calls, and eval orchestration | `Adopt now` | Strong fit for tracing provisioning, health checks, and evaluation calls across multiple providers. |
| `opentelemetry-instrumentation-httpx` | Observability | Trace outbound provider requests and health probes | `Adopt now` | Direct fit because the repo already uses `httpx`. |
| `opentelemetry-instrumentation-fastapi` | Observability | Future service/API layer tracing | `Adopt now` | Useful if `gpu-skill-builder` is exposed as an internal service or MCP-facing gateway. |
| `nvidia-ml-py` | GPU telemetry | Low-level NVML access from Python | `Adopt now` | Better fit than a UI tool when the goal is to read VRAM, utilization, temperature, and device health inside automation. |
| `nvitop` | GPU telemetry | Operator/debug view on GPU hosts | `Prototype` | Excellent for humans on boxes, but not the primary telemetry substrate for the control plane. |
| `dcgm-exporter` | GPU telemetry | Prometheus-grade GPU metrics on self-hosted NVIDIA nodes | `Prototype` | Very strong for H100/H200 fleets, but it belongs on the GPU hosts and observability stack more than in the Python package runtime. |
| `inspect-ai` | Agent and harness evals | Tool-use, agent-loop, and traceable eval framework | `Adopt now` | Best single package for harness and agent evaluation because it handles tools, logs, tracing, and custom scoring cleanly. |
| `lm-evaluation-harness` | Model evals | Standard academic and regression evaluation across local and `vLLM` backends | `Adopt now` | Best-established lightweight model regression framework to add beside current custom benchmark flows. |
| `lighteval` | Model evals | Higher-level, multi-backend eval framework with strong HF ecosystem ties | `Prototype` | Good complement, especially where Hub-facing evaluation or inspect-backed workflows help, but do not make it the only eval stack yet. |
| `locust` | Load/perf evals | Request-rate and latency testing against local or managed endpoints | `Prototype` | Good fit for sustained endpoint validation and throughput regression, especially after a model is “working.” |
| `ansible-core` | Devops continuity | Repeatable host setup, runtime install, systemd rollout, and drift control | `Prototype` | Strong operational value, but it is an architectural step up from the repo’s current script-driven deployment style. |
| `ansible-runner` | Devops continuity | Python integration layer for Ansible workflows | `Track only` | Useful only if the repo commits to Ansible as a first-class deployment substrate. |
| `ray[serve]` | Orchestration/runtime | Multi-node serving and control plane | `Avoid` | Powerful but too invasive and too large a conceptual jump for the repo’s current shape; it would add complexity before the existing simpler deployment story is hardened. |
| `tensorRT-LLM` | Runtime | NVIDIA-optimized high-end serving for select models | `Track only` | Important for future NVIDIA-heavy specialization and some Kimi-class deployments, but too provider-specific and operationally heavy to make a first adoption target here. |

## Recommended First Package Set

If the goal is the highest payoff with the smallest architectural shock, the first package bundle should be:

1. `vllm`
2. `prometheus-client`
3. `opentelemetry-sdk`
4. `opentelemetry-instrumentation-httpx`
5. `opentelemetry-instrumentation-fastapi`
6. `nvidia-ml-py`
7. `inspect-ai`
8. `lm-evaluation-harness`

This set materially improves runtime policy, telemetry, and eval coverage without forcing a full platform rewrite.

## What Each “Adopt Now” Package Should Do

### `vllm`

Use it as the standard self-host runtime and make future deployment code widen its policy surface to cover:

- `max_model_len`
- `max_num_seqs`
- `gpu_memory_utilization`
- `enable_prefix_caching`
- `enable_chunked_prefill`
- `kv_cache_dtype`
- TP / DP / EP / CP policy

The current repo already deploys `vLLM`, but the surfaced knobs are too narrow for the model set in the research package.

### `prometheus-client`

Add service-level metrics for:

- provision request count
- deploy success/failure
- health check latency
- remote restart count
- model endpoint readiness time
- eval pass/fail counters

This is the easiest operational win in the whole package list.

### `OpenTelemetry`

Use it for:

- tracing provider API calls
- tracing remote deployment phases
- tracing benchmark/eval runs
- correlating tool-use failure back to endpoint and provider state

This is especially useful once the project spans DO, Oracle, NVIDIA, and OpenRouter paths simultaneously.

### `nvidia-ml-py`

Use it to collect:

- VRAM used / total
- SM utilization
- temperature / throttling indicators
- PCIe / device health where available

This is the right machine-readable substrate for the Python control plane. Human operators can still use `nvitop` on the host.

### `inspect-ai`

Use it for:

- harness correctness evaluations
- tool-call reliability evaluations
- agent-loop evaluations with logs and traces
- reusable scenario-driven tests for “skills-heavy” behavior

This is the best fit for the “models AND harnesses” requirement when tools are involved.

### `lm-evaluation-harness`

Use it for:

- standard model regression suites
- pre/post config comparisons
- local self-hosted `vLLM` comparisons
- comparisons between provider endpoints that share the same model family

This should complement, not replace, the repo’s custom harness benchmarks.

## Prototype Lane

These packages are worth testing next, but not adopting blindly.

### `sglang`

Prototype it specifically for:

- `Kimi`
- `DeepSeek`
- other MoE models where disaggregated serving or giant-cluster behavior dominates

Decision rule:
- keep `vLLM` as default
- adopt `SGLang` only where it wins clearly on stability or long-context throughput

### `litellm`

Prototype it if you want:

- one OpenAI-compatible gateway for NVIDIA, OCI, OpenRouter, and self-hosted `vLLM`
- retries/fallbacks
- cost and budget hooks
- central auth and routing

Do not use LiteLLM as a substitute for provisioning logic. Use it, if adopted, as the traffic and routing layer above provisioned endpoints.

### `lighteval`

Prototype it for:

- richer Hugging Face evaluation flows
- sample-by-sample debugging
- backend portability

Its main value is breadth and ecosystem fit. The main risk is overlap with both `inspect-ai` and `lm-eval-harness`.

### `dcgm-exporter`

Prototype it on self-hosted NVIDIA nodes if:

- Prometheus is available
- GPU fleet telemetry matters
- you want stable operational metrics outside the Python process

This is especially strong for multi-node H100/H200 deployments.

### `ansible-core`

Prototype it if the repo graduates from “scripts that provision boxes” to “repeatable fleet deployment.”

The highest-value Ansible targets would be:

- base GPU host bootstrap
- CUDA/runtime validation
- systemd service installation
- metrics sidecar installation
- model swap and rollback

## Packages To Avoid Or Defer

### `text-generation-inference`

Do not make TGI a new first-class runtime in this repo. Hugging Face’s own docs say it is now in maintenance mode and point users to `vLLM` and `SGLang`.

### `ray serve`

Avoid it for now. It is a major platform shift, not a tactical improvement. The repo needs a stronger single-node and small-cluster story before taking on Ray’s complexity.

### `ansible-runner`

Do not add it unless `ansible-core` itself becomes a real part of the deployment architecture. Otherwise it just creates an extra abstraction layer without operational payoff.

## Final Recommendation

If the goal is to strengthen `gpu-skill-builder` without overcomplicating it, the right package direction is:

- make `vLLM` the explicit self-host runtime policy target
- add metrics and tracing now
- add `inspect-ai` plus `lm-evaluation-harness` now
- prototype `SGLang`, `LiteLLM`, `Lighteval`, `dcgm-exporter`, and `Ansible`
- do not expand into TGI or Ray as primary platform bets

## Primary Sources

- LiteLLM docs: `https://docs.litellm.ai/`
- OpenTelemetry Python docs: `https://opentelemetry.io/docs/languages/python/instrumentation/`
- NVIDIA DCGM Exporter: `https://github.com/NVIDIA/dcgm-exporter`
- nvitop: `https://github.com/XuehaiPan/nvitop`
- lm-evaluation-harness: `https://github.com/EleutherAI/lm-evaluation-harness`
- Lighteval docs: `https://huggingface.co/docs/lighteval/main/index`
- Inspect docs:
  - `https://inspect.aisi.org.uk/tutorial.html`
  - `https://inspect.aisi.org.uk/agent-custom.html`
  - `https://inspect.aisi.org.uk/tracing.html`
- TGI docs: `https://huggingface.co/docs/text-generation-inference/main/index`
