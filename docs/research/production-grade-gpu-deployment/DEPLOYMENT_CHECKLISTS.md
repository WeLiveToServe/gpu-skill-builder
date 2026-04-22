# Deployment Checklists And Launch Recipes

This companion document turns the research package into operator-ready steps. It is written for "tomorrow morning" deployment decisions and assumes a conservative posture: stable `128k`, skills-heavy operation matters more than squeezing out maximum tokens per second.

The parameter choices below are intentionally conservative and should be treated as the first stable profile, not the final throughput-optimized profile. For self-hosted `vLLM`, pin the runtime version in the image and keep the CLI surface stable across your fleet. These recipes were written against the `vLLM` CLI documented as of `2026-04-22`.

## Reading Order

1. Read the [Executive Summary](./EXECUTIVE_SUMMARY.md) for the provider/model decision.
2. Read the [Main Report](./MAIN_REPORT.md) if you need the reasoning behind the recommendation.
3. Use this file to stand up the node or endpoint.
4. Use the [Implementation Work Items](./IMPLEMENTATION_WORK_ITEMS.md) for the exact repo touch points.
5. Use the [Adoption Roadmap](./ADOPTION_ROADMAP.md) for the rollout order.
6. Use the [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json) if you want one machine-readable source of truth.

## Global Guardrails

- Pin one `vLLM` version per image. Do not float `latest`.
- Pin one exact model revision per deployment. Do not auto-upgrade weights during active evaluation periods.
- Keep model weights and cache on local NVMe whenever possible.
- Set `max_model_len` to `131072` for `128k` plans instead of leaving the model at a larger advertised ceiling.
- Enable `chunked prefill` on every `128k` self-host path.
- Treat `max_num_seqs` as the primary KV-safety lever.
- Treat `gpu_memory_utilization` as a guardrail, not a challenge target.
- Keep `kv_cache_dtype=auto` until the exact model/runtime pair has passed long-context validation.
- Turn prefix caching on only when sessions share real prefixes. Leave it off for benchmark sweeps and one-shot evals.
- Do not rely on CPU offload or swap as the normal way to survive `128k`.
- Run one major model family per node. Do not co-host multiple giant models on the same GPU box.
- Put the inference process under `systemd` and make rollback a service-file and model-revision change, not an ad hoc shell sequence.

## Profile Defaults

Use these profiles as the default policy overlays for the recipes below.

| Profile | Best use | `max_num_seqs` | `max_num_batched_tokens` | Prefix caching |
|---|---|---:|---:|---|
| `interactive-stable` | Sticky multi-turn agent sessions | `4` on `1x H200`, `4-8` on `8x H200` | `16384-24576` | `On` |
| `medium-stable` | Mixed traffic with some parallel work | `6-8` on `8x H200` | `24576` | `Off` unless prefix reuse is proven |
| `harness-eval` | Deterministic benchmark runs | `1-2` | `8192-12288` | `Off` |

## Common Self-Hosted Preflight

Run this checklist before launching any self-hosted `vLLM` node on DigitalOcean or Oracle.

- Confirm the exact GPU shape is the one recommended in the report.
- Confirm the host has working NVIDIA driver, CUDA userspace, and NCCL.
- Confirm local NVMe exists and has enough space for weights, tokenizer files, and cache.
- Confirm the Hugging Face or provider token required for the model is present.
- Confirm the node clock is correct and NTP-synchronized.
- Confirm outbound network access is available for the initial model pull, or that weights are already staged.
- Confirm `ulimit` and file descriptor ceilings are not tiny.
- Confirm `systemd` unit files and log paths are created before the first production launch.
- Confirm a health endpoint poller exists before routing real traffic.
- Confirm a rollback target exists: prior image, prior model revision, or prior service file.

Recommended shared environment on Linux hosts:

```bash
export HF_HOME=/mnt/nvme/hf
export VLLM_ASSETS_CACHE=/mnt/nvme/vllm-assets
export VLLM_API_KEY="$(openssl rand -hex 24)"
mkdir -p "$HF_HOME" "$VLLM_ASSETS_CACHE"
```

If the weight path is on network storage rather than local NVMe, prefer `--safetensors-load-strategy eager` to avoid lazy-mmap pain on slow or remote filesystems.

## Acceptance Gate After Any Launch

Do not call a node "ready" until it passes all of the following:

1. `GET /v1/models` succeeds.
2. A one-line smoke prompt returns successfully.
3. A long-prompt prefill test at `32k` succeeds.
4. A synthetic or real-session test near `128k` succeeds with the target response size.
5. A tool-call or structured-output smoke test succeeds if the workload depends on it.
6. The service survives one controlled restart and comes back healthy without manual repair.
7. Metrics and logs are visible from outside the process.

## DigitalOcean Checklists And Recipes

### DO-1: `gpt-oss-120b` On `1x H200`

Classification: `Recommended`

#### Preflight

- Use the provider's native `1x H200 141 GB` class.
- Keep weights and cache on local NVMe.
- Reserve the node for one model only.
- Start with the `interactive-stable` profile for agent work or `harness-eval` for deterministic evals.

#### Base `vLLM` recipe

```bash
CUDA_VISIBLE_DEVICES=0 \
vllm serve openai/gpt-oss-120b \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --served-model-name gpt-oss-120b \
  --download-dir "$HF_HOME" \
  --generation-config vllm \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.80 \
  --tensor-parallel-size 1 \
  --pipeline-parallel-size 1 \
  --kv-cache-dtype auto \
  --enable-chunked-prefill \
  --max-num-seqs 4 \
  --max-num-batched-tokens 16384 \
  --enable-prefix-caching
```

#### Harness-eval variant

- Change `--max-num-seqs` to `2`
- Change `--max-num-batched-tokens` to `8192`
- Remove `--enable-prefix-caching`

#### First fallback if KV pressure appears

1. Lower `--max-num-seqs` from `4` to `2`
2. Lower `--max-num-batched-tokens` to `8192`
3. Turn prefix caching off
4. Reduce output token ceiling at the application layer before touching swap/offload

### DO-2: `Qwen3-Coder-480B-A35B-Instruct-FP8` On `8x H200`

Classification: `Recommended`

#### Preflight

- Use a single `8x H200` node. Do not split this across smaller boxes for a tomorrow deployment.
- Confirm local scratch/NVMe is mounted and large enough for the checkpoint plus caches.
- Keep NUMA locality in mind if the host exposes multiple CPU sockets.
- Start with one replica only. Do not add data parallelism until the first replica is boringly stable.

#### Base `vLLM` recipe

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
numactl --interleave=all \
vllm serve Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --served-model-name qwen3-coder-480b-a35b-instruct \
  --download-dir "$HF_HOME" \
  --generation-config vllm \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.76 \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 1 \
  --enable-expert-parallel \
  --enable-eplb \
  --kv-cache-dtype auto \
  --enable-chunked-prefill \
  --max-num-seqs 4 \
  --max-num-batched-tokens 16384 \
  --enable-prefix-caching \
  --max-parallel-loading-workers 2
```

#### Medium-stable variant

- Raise `--max-num-seqs` to `6`
- Raise `--max-num-batched-tokens` to `24576`
- Keep prefix caching off unless repeated prefixes are common and measured

#### Harness-eval variant

- Set `--max-num-seqs 1`
- Set `--max-num-batched-tokens 8192`
- Remove `--enable-prefix-caching`

#### First fallback if KV pressure appears

1. Lower `--max-num-seqs` to `2`
2. Remove prefix caching
3. Lower `--max-num-batched-tokens` to `12288`
4. Keep `tensor_parallel_size=8`; do not start adding complex parallel modes on the first recovery attempt

### DO-3: `DeepSeek-V3.1` On `8x H200`

Classification: `Recommended`

Use the same node shape and deployment pattern as Qwen, but keep the traffic profile even more conservative because the MoE runtime behavior is less forgiving under mixed long-context load.

#### Base `vLLM` recipe

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
numactl --interleave=all \
vllm serve deepseek-ai/DeepSeek-V3.1 \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --served-model-name deepseek-v3.1 \
  --download-dir "$HF_HOME" \
  --generation-config vllm \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.74 \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 1 \
  --enable-expert-parallel \
  --enable-eplb \
  --kv-cache-dtype auto \
  --enable-chunked-prefill \
  --max-num-seqs 4 \
  --max-num-batched-tokens 16384 \
  --max-parallel-loading-workers 2
```

Default policy: leave prefix caching off until you have proved that repeated session prefixes are common enough to justify the extra memory pressure.

#### First fallback if KV pressure appears

1. Lower `--max-num-seqs` to `2`
2. Lower `--max-num-batched-tokens` to `12288`
3. Keep expert parallel on
4. If instability persists, prototype `SGLang` rather than layering on more `vLLM` complexity

### DO-4: `MiniMax-M2.7` On `8x H200`

Classification: `Recommended`

#### Base `vLLM` recipe

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
numactl --interleave=all \
vllm serve MiniMaxAI/MiniMax-M2.7 \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --served-model-name minimax-m2.7 \
  --download-dir "$HF_HOME" \
  --generation-config vllm \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.74 \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 1 \
  --enable-expert-parallel \
  --enable-eplb \
  --kv-cache-dtype auto \
  --enable-chunked-prefill \
  --max-num-seqs 4 \
  --max-num-batched-tokens 16384 \
  --max-parallel-loading-workers 2
```

#### First fallback if KV pressure appears

1. Lower `--max-num-seqs`
2. Lower batched tokens
3. Keep one replica only
4. Move back to a deterministic harness profile before trying to increase concurrency again

### DO-5: `Kimi-K2` On DigitalOcean

Classification: `Do not attempt` for tomorrow production, `Possible but risky` only as a deliberate prototype.

There is no production-safe tomorrow `vLLM` recipe for Kimi on DigitalOcean in this package. The right answer is still managed-first or a much more deliberate multi-node cluster with validated fabric behavior. If you must prototype, do it as an isolated R&D exercise and prefer `SGLang` as the alternate runtime lane.

## Oracle Checklists And Recipes

### OCI-1: Managed `gpt-oss-120b` Through OCI Generative AI

Classification: `Recommended`

This is a managed endpoint path, so there is no `vLLM` launch recipe here.

#### Preflight

- Confirm the model is available in the exact region you intend to use.
- Confirm the tenancy already has access to the required Generative AI mode.
- Set the application-side request ceiling to the actual context length you need, not the model's theoretical maximum.
- Put a lightweight control-plane service in front of the endpoint for retries, logging, and metrics.

#### Acceptance gate

- Smoke prompt succeeds
- Long prompt succeeds
- Tool-call or structured-output smoke succeeds if your workload requires it
- Error budget and latency are measured before routing production traffic

### OCI-2: Self-Hosted `Qwen3-Coder`, `DeepSeek`, Or `MiniMax` On `BM.GPU.H200.8`

Classification: `Recommended` only if quota already exists

Use the same conservative `vLLM` recipes as the DigitalOcean `8x H200` paths, but treat Oracle bare metal as more NUMA-sensitive and more operationally explicit.

#### Additional Oracle preflight

- Confirm quota, region, and capacity are already available before promising a deployment date.
- Confirm the host has a local storage plan; do not assume network-attached storage will behave like local NVMe.
- Confirm `numactl` is installed and used.
- Confirm host bootstrap installs metrics, tracing, and health checks before the model service starts.

#### Oracle launch rules

- Use `numactl --interleave=all`
- Keep one model service per host
- Keep `tensor_parallel_size=8`
- Keep `pipeline_parallel_size=1` for the first stable deployment
- Add prefix caching only after proving repeated-prefix traffic exists

### OCI-3: `Kimi-K2` On Oracle

Classification: `Possible but risky`

There is still no "tomorrow-safe" `vLLM` recipe for Kimi in this package. If you already have `2x BM.GPU.H200.8` available and want to prototype, do that under a separate R&D lane and treat `SGLang` as the first alternate runtime to test. Do not promise `128k` production stability on Oracle for Kimi until the cluster survives repeated cold starts, warm restarts, and mixed long-context traffic.

### OCI-4: Oracle As Control Plane

Classification: `Recommended`

Even when Oracle is not the inference host, it is a strong place to run:

- orchestration
- health and readiness polling
- eval coordination
- metrics collection
- traffic routing

This is the default Oracle role whenever GPU quota or capacity is uncertain.

## NVIDIA Managed Portal / Free Testing Checklist

### NV-1: Hosted Endpoint Validation

Classification: `Testing only`

Use NVIDIA managed endpoints for:

- smoke validation
- tool-call validation
- comparative output checks
- quick evaluation of which model family deserves a real self-host attempt

#### Checklist

- Create the endpoint for the exact mapped model family
- Record the endpoint limits and exposed parameters
- Run a smoke prompt
- Run a tool-call or structured-output probe if needed
- Run one long-prompt validation pass
- Record observed latency and failure behavior

#### Do not treat NVIDIA managed as the final answer for

- stable `128k` skills-heavy serving
- low-level KV policy tuning
- topology tuning
- rollback testing
- deterministic long-session cache behavior

## Recommended Launch Sequence By Model

Use this order when you want the safest progression from "not deployed" to "production candidate."

1. `gpt-oss-120b`
   Start with Oracle managed or `1x H200` on DigitalOcean.
2. `Qwen3-Coder-480B`
   Move to a single `8x H200` node and validate tool use.
3. `DeepSeek-V3.1`
   Reuse the same `8x H200` operational pattern, but keep traffic more conservative.
4. `MiniMax-M2.7`
   Treat like the other large MoE `8x H200` paths.
5. `Kimi-K2`
   Keep on managed endpoints until you have a real `16 GPU` R&D lane.

## Recovery And Rollback Checklist

If a node becomes unstable under real traffic:

1. Stop increasing concurrency.
2. Lower `max_num_seqs`.
3. Lower `max_num_batched_tokens`.
4. Turn prefix caching off.
5. Reduce application-side output ceilings.
6. Restart the service cleanly.
7. If instability remains, roll back to the last known-good image or model revision.
8. Only after the node is stable again should you test alternate runtime strategies such as `SGLang`.
