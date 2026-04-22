# Production-Grade GPU Deployment Research Package

This report is the deployment guide for running frontier open-weight or open-access agentic models at up to `128k` context with conservative, production-safe settings. It is written for `gpu-skill-builder` and assumes a strong bias toward stability, repeatability, and skills-heavy agent workloads rather than benchmark-max throughput.

## Companion Documents

- [Executive Summary](./EXECUTIVE_SUMMARY.md)
- [Deployment Checklists and Launch Recipes](./DEPLOYMENT_CHECKLISTS.md)
- [Implementation Work Items](./IMPLEMENTATION_WORK_ITEMS.md)
- [Package Recommendations](./PACKAGE_RECOMMENDATIONS.md)
- [Adoption Roadmap](./ADOPTION_ROADMAP.md)
- [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json)

## Confidence Legend

- `[Doc]` Explicitly documented by an official model, provider, or runtime source.
- `[Inf]` Inferred from primary sources and standard serving behavior.
- `[Ops]` Operator-derived or community-validated guidance with medium confidence.

## Resolved Model Targets

| Requested family | Resolved self-host target | Resolved NVIDIA portal target | Why this mapping |
|---|---|---|---|
| `openai oss 120b` | `openai/gpt-oss-120b` | `openai / gpt-oss-120b` | Exact match. |
| `Qwen3-Coder-480b` | `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8` | `qwen / qwen3-coder-480b-a35b-instruct` | FP8 is the official serving-oriented checkpoint and the right target for self-hosting large-context inference. `[Doc]` |
| `DeepSeek-v3.2` | `deepseek-ai/DeepSeek-V3.1` | `deepseek-ai / deepseek-v3.1` | `v3.2` is not the practical public deployment target today; `V3.1` is the latest clearly documented deployable V3-family release. `[Inf]` |
| `Kimi 2.6` | `moonshotai/Kimi-K2-Instruct-0905` | `moonshotai / kimi-k2-5` | Public deployable Kimi is currently the K2 family; NVIDIA’s managed catalog uses the `k2-5` naming while Moonshot’s public weights point to `K2-Instruct-0905`. `[Doc]` / `[Inf]` |
| `MiniMax 2.7` | `MiniMaxAI/MiniMax-M2.7` | `minimaxai / minimax-m2.7` | Exact current deployable family. |

## Foundation

### What actually consumes VRAM

1. Weights.
   For giant MoE models, total parameter count still matters because all experts must live somewhere even if only a subset is active per token. `[Doc]`
2. KV cache.
   This is the main long-context pain point. KV grows roughly with sequence length, active requests, layer count, and KV head layout. `[Inf]`
3. Runtime overhead.
   CUDA graphs, attention kernels, comm buffers, router state, fragmentation, and allocator slack all cost memory beyond weights plus KV. `[Inf]`
4. Activations and prefilling work buffers.
   These spike during prefill and during large batched requests. `[Inf]`

### Why `128k` is operationally different from “supports 128k”

- A model “supporting” `128k` only means its position encoding and training recipe allow it. It does not mean a single production replica can hold `128k` prompts, long replies, and many concurrent skill sessions safely. `[Inf]`
- Long-context serving is dominated by:
  - prefill cost on the way in
  - decode KV residency after the prompt is loaded
  - tail latency under mixed prompt sizes
  - whether repeated prefixes are reused or recomputed

### Prompt caching, prefix caching, and KV reuse

- Prompt caching:
  A general application-level idea: if multiple requests share the same prompt prefix, reuse work instead of recomputing it. `[Inf]`
- Automatic prefix caching in `vLLM`:
  `vLLM` can reuse KV blocks for requests that share the same prefix, which is especially valuable for long documents and multi-turn sessions. `[Doc]`
- KV reuse:
  The actual runtime effect of prefix caching. It reduces prefill cost, not decode cost. `[Doc]`
- Practical policy:
  - enable prefix caching for repeated codebase sessions, tool-heavy chats, and multi-turn agents
  - disable it for one-shot evals, unique giant prompts, or when VRAM is already tight

### Paged attention, chunked prefill, and long-context scheduling

- Paged attention reduces KV fragmentation and makes dynamic allocation more practical. `[Doc]`
- Chunked prefill is important for very long prompts because it reduces peak prefill pressure and controls tail latency more predictably. `[Doc]` / `[Inf]`
- Disaggregated prefill becomes useful when prefill and decode need different parallel strategies or service-level objectives. `[Doc]`

### When CPU, RAM, storage, and network matter

- CPU:
  Important for tokenization, orchestration, API routing, tracing, and hosting sidecars. It does not fix a pure GPU KV-cache limit. `[Inf]`
- System RAM:
  Important for weight download, CPU spill, build tools, and large runtime staging buffers. It is a backup, not a substitute for VRAM, in latency-sensitive serving. `[Inf]`
- Storage:
  Large models need fast local NVMe for checkpoints, caches, and restarts. Slow storage lengthens cold start and makes recovery painful. `[Inf]`
- Network:
  Multi-node MoE serving becomes network-sensitive very quickly. Commodity cloud private networking is acceptable for some throughput use cases, but weak for “rock-solid tomorrow” 16-GPU MoE clusters. `[Inf]`

## Parameter Policy Table

| Knob | What it controls | Rock-solid policy |
|---|---|---|
| `max_model_len` | Maximum prompt + response span admitted by the server | Set it to the actual required ceiling. Do not leave it at model max if you only need `128k`. This is the first hard cap that protects KV. `[Inf]` |
| `max_num_seqs` | Concurrent live sequences per replica/rank | Treat this as the biggest KV-pressure lever. Lower it before chasing more exotic fixes. `[Inf]` |
| `gpu_memory_utilization` | Fraction of free GPU memory that `vLLM` pre-allocates for its KV/system budget | Start lower for long-context MoE: roughly `0.72-0.80`. Only push higher after observing stable headroom. `[Doc]` / `[Inf]` |
| `tensor_parallel_size` | Weight sharding across GPUs | Use the smallest TP that makes weights fit and preserves KV headroom. `[Doc]` / `[Inf]` |
| `pipeline_parallel_size` | Layer sharding across GPUs/nodes | Use when TP alone is not enough or node boundaries force it. Keep at `1` unless there is a clear reason. `[Doc]` |
| `data_parallel_size` | Replica count for throughput | Add only after a single replica is stable. DP is a throughput tool, not a fit tool. `[Doc]` |
| `enable_expert_parallel` | MoE expert sharding behavior | Prefer it for large MoE models when supported, especially DeepSeek/Qwen/MiniMax/Kimi classes. `[Doc]` |
| `context parallel` | Sharding for long-context prefill/decode | Use only for the largest long-context clusters; it is a power tool, not a default tomorrow setting. `[Doc]` / `[Inf]` |
| `kv_cache_dtype` | KV cache precision | Default to `auto` for conservative production. Use FP8 KV only after model-specific validation. `[Doc]` / `[Inf]` |
| `enable_prefix_caching` | APC / shared-prefix reuse | Enable for repeated sessions with bounded concurrency. Disable for one-shot harness sweeps and giant unique prompts. `[Doc]` |
| `enable_chunked_prefill` | Long prompt admission behavior | Enable for all `128k` plans. `[Doc]` / `[Inf]` |
| `swap-space` / CPU offload | Spill behavior under pressure | Not a default. Use only as a fallback for boot or rare oversubscription, not for low-latency production. `[Inf]` |
| `max_num_batched_tokens` | Scheduler pressure during batch formation | Keep conservative for long-context nodes. It is a tail-latency and OOM control, not just a throughput knob. `[Doc]` / `[Inf]` |
| `numa-bind` | CPU/memory locality on multi-socket GPU hosts | Turn on for 8-GPU bare-metal or dual-socket nodes. `[Doc]` |

## Provider Chapters

### DigitalOcean

#### What matters

- GPU Droplets currently expose current-generation NVIDIA GPUs including `H200` and also 8-GPU configurations, with `10 Gbps` public and `25 Gbps` private networking. `[Doc]`
- Current published H200 shape:
  - `1x H200 141 GB`
  - `24 vCPU`
  - `240 GiB RAM`
  - `720 GiB` boot NVMe
  - `5 TiB` scratch NVMe `[Doc]`
- 8-GPU H200 is available as a Droplet/Bare-Metal class with `1,128 GB` aggregate GPU RAM. `[Doc]`

#### What DigitalOcean is good at

- Single-node self-hosted inference with straightforward operations.
- Fast iteration on `1x H200` and `8x H200`.
- Clean systemd-driven deployments and deterministic model swap scripts.

#### What DigitalOcean is weak at

- Multi-node giant-MoE serving that needs 16 GPUs and excellent east-west fabric.
- Production-safe long-context clusters that depend on low-latency, high-bandwidth inter-node expert traffic. `[Inf]`

#### DigitalOcean continuity policy

- Use one fixed OS image per model family and pin CUDA/runtime versions. `[Inf]`
- Keep checkpoints and Hugging Face cache on local NVMe scratch where practical. `[Inf]`
- Run the inference server under `systemd` with health checks and a deterministic rewrite of the service file per model swap. Existing repo patterns already move in this direction. `[Doc]` / `[Inf]`
- Add separate monitoring for:
  - health endpoint
  - GPU memory used / total
  - token latency
  - restart count
  - prefix-cache hit behavior where instrumented

#### DigitalOcean recommendation

- Recommended for tomorrow:
  - `gpt-oss-120b` on `1x H200`
  - `Qwen3-Coder-480B`, `DeepSeek-V3.1`, `MiniMax-M2.7` on `8x H200`
- Good for testing only:
  - NVIDIA-model parity checks against managed endpoints
  - `gpt-oss-120b` on `1x H100` if H200 is not available
- Not trustworthy for `128k` skills-heavy production:
  - `Kimi-K2` class on 2 nodes unless you have proven the 16-GPU networking path and failover policy yourself

### Oracle

#### What matters

- OCI currently documents GPU shapes including:
  - `VM.GPU.A10.1` / `.2`
  - `BM.GPU.H100.8`
  - `BM.GPU.H200.8`
  - `BM.GPU.A100-v2.8`
  - `BM.GPU.L40S-NC.4` `[Doc]`
- The relevant large-model shapes are the 8-GPU bare-metal `H100` and `H200` families. `[Doc]`
- OCI also offers managed `Generative AI` access for `openai.gpt-oss-120b`, including on-demand and dedicated cluster modes. `[Doc]`

#### What Oracle is good at

- Managed `gpt-oss-120b` without self-hosting.
- Potentially the best self-hosting path for very large MoE models if GPU quota/service limits already exist.
- Always-on control-plane nodes even when GPU capacity is unavailable.

#### What Oracle is weak at

- Real-world access is quota- and region-gated.
- If GPU quota is not already enabled, Oracle is not a dependable “tomorrow morning” inference host.
- A10 shapes are useful for smaller models and utilities, but not for the target families in this report. `[Inf]`

#### Oracle control-plane pattern

If OCI GPU quota is unavailable, Oracle is still highly useful as:
- orchestration node
- SSH bastion / config runner
- eval coordinator
- skill router / API gateway
- metrics concentrator

This is the recommended Oracle role unless GPU reservations or limits are already in place. `[Inf]`

#### Oracle recommendation

- Recommended for tomorrow:
  - `openai.gpt-oss-120b` through OCI Generative AI managed service
  - `BM.GPU.H200.8` for `Qwen3-Coder-480B`, `DeepSeek-V3.1`, or `MiniMax-M2.7`, but only if quota already exists
- Good for testing only:
  - `BM.GPU.H100.8` for the largest MoE families when H200 is unavailable
- Not trustworthy for `128k` skills-heavy production:
  - any plan that assumes new Oracle GPU quota will appear immediately

### NVIDIA Managed Portal / Free Testing

#### What matters

- NVIDIA Build / NIM portal exposes managed hosted inference endpoints for the mapped target families, including:
  - `openai / gpt-oss-120b`
  - `qwen / qwen3-coder-480b-a35b-instruct`
  - `deepseek-ai / deepseek-v3.1`
  - `moonshotai / kimi-k2-5`
  - `minimaxai / minimax-m2.7` `[Doc]`
- NVIDIA’s quickstart is centered on live hosted API endpoints on DGX Cloud-backed infrastructure. `[Doc]`

#### What NVIDIA managed is good at

- Fast smoke testing
- model availability checks
- API behavior checks
- tool-calling behavior checks
- comparative model evaluation without provisioning raw GPU infrastructure

#### What NVIDIA managed does not give you

- no low-level control over:
  - TP / PP / DP / EP / CP
  - KV dtype
  - prefix-cache policy
  - scheduler batching policy
  - chunked-prefill tuning
  - service restart / placement policy `[Inf]`

#### NVIDIA recommendation

- Recommended for tomorrow:
  - smoke validation
  - output quality comparison
  - provider fallback for quick evaluation
- Good for testing only:
  - short-run harness experiments
  - syntax/tool-calling validation
- Not trustworthy for `128k` skills-heavy production:
  - any workload where you must reserve KV headroom explicitly, tune scheduling, or guarantee model/runtime policy

## Model Playbooks

### 1. `openai/gpt-oss-120b`

#### Facts

- `117B` total params, `5.1B` active params per token, native `128k` context. `[Doc]`
- OpenAI states it runs efficiently on a single `80 GB` GPU. `[Doc]`
- NVIDIA’s managed page says it fits into a single `H100` and is optimized for `H200` / `Blackwell` on NIM. `[Doc]`

#### Tomorrow recommendation

- Best self-host path: `DigitalOcean 1x H200 141 GB` running `vLLM`. `[Inf]`
- Best Oracle path: `OCI Generative AI` managed `openai.gpt-oss-120b`. `[Doc]`
- Best NVIDIA path: managed endpoint for validation and smoke testing only. `[Inf]`

#### Deployment classification

| Provider | Minimum viable | Recommended | Classification |
|---|---|---|---|
| DigitalOcean | `1x H100 80 GB` `[Doc]` | `1x H200 141 GB` `[Inf]` | `Recommended` on H200, `Testing only` on H100 |
| Oracle | OCI Generative AI managed `[Doc]` | OCI Generative AI managed or dedicated AI cluster `[Doc]` | `Recommended` |
| NVIDIA portal | managed endpoint `[Doc]` | managed endpoint for smoke validation `[Inf]` | `Testing only` |

#### Conservative self-host profile

```bash
vllm serve openai/gpt-oss-120b \
  --max-model-len 131072 \
  --max-num-seqs 8 \
  --gpu-memory-utilization 0.82 \
  --enable-prefix-caching \
  --enable-chunked-prefill
```

Why:
- `max_model_len=131072`: exact requested ceiling. `[Doc]`
- `max_num_seqs=8`: conservative on `1x H200`; drop to `4` on `1x H100`. `[Inf]`
- `gpu_memory_utilization=0.82`: leaves headroom for graphs and large prompt behavior. `[Inf]`
- `enable-prefix-caching`: good default for repeated codebase sessions. `[Doc]`
- `enable-chunked-prefill`: safer for long prompts. `[Doc]` / `[Inf]`

#### Fallback order

1. Lower `max_num_seqs` from `8` to `4`.
2. Lower `gpu_memory_utilization` if graph/allocator pressure appears.
3. Disable prefix caching for unique-prompt eval sweeps.
4. Move from `1x H100` to `1x H200`.
5. If concurrency matters more than simplicity, move to `TP=2` on a 2-GPU managed/cluster path. `[Inf]`

### 2. `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`

#### Facts

- `480B` total, `35B` active, native `262,144` context, extendable with YaRN. `[Doc]`
- Qwen officially recommends `vLLM` for deployment and calls out FP8 support for Hopper/Ada and later. `[Doc]`
- Qwen docs warn that some TP settings can interact badly with FP8 block quant and suggest reducing TP or enabling expert parallel. `[Doc]`

#### Tomorrow recommendation

- Best self-host path: `8x H200` single node on DigitalOcean or Oracle. `[Inf]`
- `8x H100` can be made to work, but it is not the “rock-solid” recommendation for `128k` agentic coding. `[Inf]`
- NVIDIA portal is useful for validation, not primary production. `[Inf]`

#### Deployment classification

| Provider | Minimum viable | Recommended | Classification |
|---|---|---|---|
| DigitalOcean | `8x H100` `[Inf]` | `8x H200` `[Inf]` | `Recommended` on H200, `Possible but risky` on H100 |
| Oracle | `BM.GPU.H100.8` `[Inf]` | `BM.GPU.H200.8` `[Inf]` | `Recommended` on H200, `Possible but risky` on H100 |
| NVIDIA portal | managed endpoint `[Doc]` | managed endpoint for validation `[Inf]` | `Testing only` |

#### Conservative self-host profile

```bash
vllm serve Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 \
  --tensor-parallel-size 8 \
  --enable-expert-parallel \
  --max-model-len 131072 \
  --max-num-seqs 4 \
  --gpu-memory-utilization 0.76 \
  --enable-chunked-prefill \
  --trust-remote-code
```

Policy notes:
- Keep prefix caching `off` by default for large eval sweeps and `on` only for bounded interactive coding sessions. `[Inf]`
- Use the FP8 checkpoint for self-hosting. `[Doc]`
- Stay off YaRN because `128k` is below the model’s native `262k`. `[Doc]`

#### Fallback order

1. Lower `max_num_seqs` from `4` to `2`.
2. Disable prefix caching if enabled.
3. Lower to `64k` if you are forced onto H100 and see KV pressure.
4. Switch to `SGLang` if `vLLM` EP/TP behavior is unstable on your target cluster. `[Inf]`

### 3. `deepseek-ai/DeepSeek-V3.1`

#### Facts

- `671B` total, `37B` active, `128k` context. `[Doc]`
- DeepSeek documents hybrid thinking/non-thinking, non-thinking tool call mode, code-agent and search-agent templates. `[Doc]`
- `vLLM` expert-parallel docs use DeepSeek-V3 as the canonical MoE EP example and explicitly recommend single-node H200 or two-node H200/H20 class clusters. `[Doc]`

#### Tomorrow recommendation

- Best self-host path: `8x H200` with `vLLM` EP on a single node. `[Doc]` / `[Inf]`
- Best Oracle path: `BM.GPU.H200.8` if quota exists.
- Best NVIDIA path: managed endpoint for validation only.

#### Deployment classification

| Provider | Minimum viable | Recommended | Classification |
|---|---|---|---|
| DigitalOcean | `8x H200` `[Inf]` | `8x H200` `[Doc]` / `[Inf]` | `Recommended` |
| Oracle | `BM.GPU.H100.8` with caveats `[Inf]` | `BM.GPU.H200.8` `[Doc]` / `[Inf]` | `Recommended` on H200, `Possible but risky` on H100 |
| NVIDIA portal | managed endpoint `[Doc]` | managed endpoint for validation `[Inf]` | `Testing only` |

#### Conservative self-host profile

```bash
VLLM_ALL2ALL_BACKEND=pplx VLLM_USE_DEEP_GEMM=1 \
vllm serve deepseek-ai/DeepSeek-V3.1 \
  --tensor-parallel-size 1 \
  --data-parallel-size 8 \
  --enable-expert-parallel \
  --enable-eplb \
  --max-model-len 131072 \
  --max-num-seqs 2 \
  --gpu-memory-utilization 0.75 \
  --enable-chunked-prefill \
  --trust-remote-code
```

Why:
- DeepSeek MLA-style MoE is exactly the case where `DP + EP` is attractive in `vLLM`. `[Doc]`
- `max_num_seqs=2` is intentionally conservative at `128k`. `[Inf]`
- `enable-eplb` helps smooth expert skew. `[Doc]`

#### Fallback order

1. Lower `max_num_seqs` to `1`.
2. Turn prefix caching off if it was enabled.
3. Reduce `max_model_len` to `96k`.
4. Move from H100 to H200 or from 8 GPUs to 16 GPUs with multi-node EP for throughput. `[Inf]`

### 4. `moonshotai/Kimi-K2-Instruct-0905` (mapped from “Kimi 2.6”)

#### Facts

- `1T` total params, `32B` active, `256k` context in the current public K2 release. `[Doc]`
- Moonshot’s deployment guide says the smallest deployment unit for FP8 weights with `128k` sequence length on mainstream `H200` / `H20` is a `16-GPU` cluster. `[Doc]`
- Supported runtimes include `vLLM`, `SGLang`, `KTransformers`, and `TensorRT-LLM`. `[Doc]`

#### Tomorrow recommendation

- Best practical immediate path: use the managed Kimi API or NVIDIA portal for validation, not self-hosting. `[Doc]` / `[Inf]`
- Best self-host path, if you already have serious GPU capacity and networking: `2x 8-GPU H200` class nodes, preferably on Oracle rather than DigitalOcean. `[Doc]` / `[Inf]`

#### Deployment classification

| Provider | Minimum viable | Recommended | Classification |
|---|---|---|---|
| DigitalOcean | `2x (8x H200)` `[Doc]` / `[Inf]` | same, but networking makes it risky `[Inf]` | `Possible but risky` |
| Oracle | `2x BM.GPU.H200.8` `[Doc]` / `[Inf]` | `2x BM.GPU.H200.8` with strong networking `[Inf]` | `Recommended` only if quota and cluster ops already exist |
| NVIDIA portal | managed endpoint `[Doc]` | managed endpoint for validation `[Inf]` | `Testing only` |

#### Conservative self-host profile

```bash
vllm serve moonshotai/Kimi-K2-Instruct-0905 \
  --tensor-parallel-size 16 \
  --max-model-len 131072 \
  --max-num-seqs 1 \
  --gpu-memory-utilization 0.72 \
  --enable-chunked-prefill \
  --trust-remote-code
```

Policy notes:
- This is the simplest conservative starting point for a 16-GPU cluster.
- Do not turn prefix caching on initially; KV is too precious at this scale. `[Inf]`
- For throughput rather than simplicity, move to `DP + EP` or `SGLang` disaggregated prefill after the basic cluster is stable. `[Doc]` / `[Inf]`

#### Fallback order

1. Keep the model on managed APIs for validation while infra is prepared.
2. Use `SGLang` if `vLLM` control-plane complexity or throughput shape becomes the bottleneck.
3. Do not try to rescue an underprovisioned `8-GPU` deployment with CPU offload and call it production-safe. `[Inf]`

### 5. `MiniMaxAI/MiniMax-M2.7`

#### Facts

- `229B` params, officially recommended on `vLLM`, `SGLang`, and NVIDIA NIM. `[Doc]`
- MiniMax’s vLLM guide states:
  - about `220 GB` for weights
  - about `240 GB` per `1M` context tokens
  - `96G x4` recommended for total KV capacity around `400K`
  - `144G x8` recommended for total KV capacity up to `3M`
  - maximum individual sequence length remains `196K` `[Doc]`

#### Tomorrow recommendation

- Best self-host path: `8x H200` if using the providers in this report. `[Inf]`
- A theoretical `4x 96 GB` node would be sufficient, but it is not the cleanest target in the providers available here. `[Doc]` / `[Inf]`
- NVIDIA portal is useful for validation and feature checks.

#### Deployment classification

| Provider | Minimum viable | Recommended | Classification |
|---|---|---|---|
| DigitalOcean | `8x H100` with risk `[Inf]` | `8x H200` `[Inf]` | `Recommended` on H200, `Possible but risky` on H100 |
| Oracle | `BM.GPU.H100.8` with risk `[Inf]` | `BM.GPU.H200.8` `[Inf]` | `Recommended` on H200, `Possible but risky` on H100 |
| NVIDIA portal | managed endpoint `[Doc]` | managed endpoint for validation `[Inf]` | `Testing only` |

#### Conservative self-host profile

```bash
SAFETENSORS_FAST_GPU=1 \
vllm serve MiniMaxAI/MiniMax-M2.7 \
  --trust-remote-code \
  --enable_expert_parallel \
  --tensor-parallel-size 8 \
  --enable-auto-tool-choice \
  --tool-call-parser minimax_m2 \
  --reasoning-parser minimax_m2_append_think \
  --max-model-len 131072 \
  --max-num-seqs 2 \
  --gpu-memory-utilization 0.78 \
  --enable-chunked-prefill
```

Runtime notes:
- Use MiniMax’s recommended sampling defaults for application traffic:
  - `temperature=1.0`
  - `top_p=0.95`
  - `top_k=40` `[Doc]`
- Keep prefix caching off initially; enable only for highly repetitive sessions after measuring headroom. `[Inf]`

#### Fallback order

1. Lower `max_num_seqs`.
2. Disable prefix caching if it was enabled.
3. Prefer H200 over H100.
4. If self-hosting remains awkward, keep MiniMax behind managed endpoints for validation while deploying smaller or simpler self-hosted models elsewhere.

## Multi-GPU Guidance

### When to use each strategy

- `TP`:
  Use first when weights do not fit on one GPU or when you need more KV headroom per GPU. `[Doc]`
- `PP`:
  Use when TP is already large and you still cannot fit, or when crossing node boundaries with very large models. `[Doc]`
- `DP`:
  Add only after one replica is stable. It scales throughput and isolates queues. `[Doc]`
- `EP`:
  Prefer for giant MoE models once supported and documented for that model/runtime pair. `[Doc]`
- `CP`:
  Reserve for the largest long-context clusters where `128k`+ throughput and KV sharding dominate the design. `[Doc]`

### Provider-specific multi-GPU posture

| Provider | Best use of multiple GPUs | Main risk |
|---|---|---|
| DigitalOcean | single-node `8x H200` | multi-node networking is not the first-choice path for Kimi-scale MoE serving |
| Oracle | `BM.GPU.H200.8` and multi-node if quotas exist | quota/service-limit friction |
| NVIDIA portal | not applicable as a tuning surface | no control over low-level parallelism |

### Rock-solid rule

For giant MoE models, do not spend your first operational day trying to be clever with DP, EP, CP, and disaggregated prefill all at once. First prove:

1. one conservative replica boots
2. one `128k` request succeeds
3. a small repeated-prefix skills session is stable
4. only then increase concurrency or introduce more complex parallelism

## Skills-Heavy Serving Policy

### What changes when skills/tool use matter

- Tool transcripts, edited files, retrieved documents, and multi-turn agent state can make the “effective prompt” much larger than the visible user message. `[Inf]`
- Prefix caching is more valuable for skill loops than for one-shot prompts, because many turns share a large common prefix. `[Doc]` / `[Inf]`
- The same feature can also pin too much KV if too many distinct sessions are alive at once. `[Inf]`

### Recommended skills policy

#### Interactive agent sessions

- Keep sessions sticky to a replica when possible.
- Enable prefix caching.
- Keep `max_num_seqs` modest.
- Prefer longer-lived sessions with fewer replicas over high-churn routing. `[Inf]`

#### Harness runs and one-shot evals

- Disable prefix caching unless the benchmark reuses identical repository context.
- Favor lower `max_model_len` when the benchmark does not truly need `128k`.
- Separate throughput benchmarking from correctness benchmarking. `[Inf]`

#### Control-plane separation

- Keep orchestration, tracing, and eval control on CPU or cheap always-on nodes.
- Do not spend scarce GPU memory on gateway logic, metrics aggregation, or retry routers.
- Oracle is a strong control-plane candidate even when it is not the best inference host. `[Inf]`

## Bottom Line

If you had to deploy tomorrow with conservative odds of success:

- `gpt-oss-120b`: use `OCI Generative AI` or `1x H200` on DigitalOcean.
- `Qwen3-Coder-480B-A35B`: use `8x H200`, self-hosted.
- `DeepSeek-V3.1`: use `8x H200` with `vLLM` expert-parallel, or Oracle `BM.GPU.H200.8` if quota exists.
- `Kimi-K2`: do not treat self-hosting as a day-one commodity deployment; validate on managed APIs first and self-host only on a real `16-GPU` class cluster.
- `MiniMax-M2.7`: use `8x H200` if self-hosting, otherwise managed validation.

## Primary Sources

- OpenAI gpt-oss announcement: `https://openai.com/index/introducing-gpt-oss/`
- Hugging Face model cards:
  - `https://huggingface.co/openai/gpt-oss-120b`
  - `https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`
  - `https://huggingface.co/deepseek-ai/DeepSeek-V3.1`
  - `https://huggingface.co/moonshotai/Kimi-K2-Instruct-0905`
  - `https://huggingface.co/MiniMaxAI/MiniMax-M2.7`
- Moonshot Kimi deployment guide: `https://github.com/MoonshotAI/Kimi-K2/blob/main/docs/deploy_guidance.md`
- Qwen deployment docs:
  - `https://github.com/QwenLM/Qwen3/blob/main/docs/source/deployment/vllm.md`
  - `https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.html`
- vLLM docs:
  - `https://docs.vllm.ai/en/latest/configuration/optimization/`
  - `https://docs.vllm.ai/en/stable/serving/data_parallel_deployment/`
  - `https://docs.vllm.ai/en/v0.10.1.1/serving/expert_parallel_deployment.html`
  - `https://docs.vllm.ai/usage/automatic_prefix_caching.html`
  - `https://docs.vllm.ai/en/latest/serving/context_parallel_deployment.html`
  - `https://docs.vllm.ai/usage/disagg_prefill/`
- DigitalOcean GPU docs:
  - `https://www.digitalocean.com/products/gpu-droplets`
  - `https://www.digitalocean.com/pricing/gpu-droplets`
  - `https://www.digitalocean.com/products/gradient/bare-metal-gpus`
- Oracle docs:
  - `https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm`
  - `https://docs.oracle.com/en-us/iaas/data-science/using/supported-shapes.htm`
  - `https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-gpt-oss-120b.htm`
  - `https://docs.oracle.com/iaas/releasenotes/generative-ai/openai-gpt-oss.htm`
- NVIDIA managed endpoint docs:
  - `https://docs.api.nvidia.com/nim/docs/api-quickstart`
  - `https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-120b`
  - `https://docs.api.nvidia.com/nim/reference/qwen-qwen3-coder-480b-a35b-instruct`
  - `https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v3_1`
  - `https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k2-5`
  - `https://docs.api.nvidia.com/nim/reference/minimaxai-minimax-m2.7`
