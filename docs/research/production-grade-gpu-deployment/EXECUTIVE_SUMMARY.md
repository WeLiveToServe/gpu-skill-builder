# Executive Summary

This is the short answer for what to deploy tomorrow if the goal is `128k`, skill-heavy, conservative serving.

## Companion Documents

- [Main Report](./MAIN_REPORT.md)
- [Deployment Checklists and Launch Recipes](./DEPLOYMENT_CHECKLISTS.md)
- [Implementation Work Items](./IMPLEMENTATION_WORK_ITEMS.md)
- [Package Recommendations](./PACKAGE_RECOMMENDATIONS.md)
- [Adoption Roadmap](./ADOPTION_ROADMAP.md)
- [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json)

## Best Tomorrow Path By Model

| Model family | Best tomorrow path | Why |
|---|---|---|
| `openai/gpt-oss-120b` | `Oracle OCI Generative AI` or `DigitalOcean 1x H200` | This is the only target in this set that is genuinely comfortable as a single-GPU self-host candidate and also has a strong managed Oracle path. |
| `Qwen3-Coder-480B` | `DigitalOcean 8x H200` or `Oracle BM.GPU.H200.8` | Native long context, agentic coding, and official FP8 serving path make it a strong self-host target if you have one large 8-GPU node. |
| `DeepSeek-V3.1` | `Oracle BM.GPU.H200.8` if quota exists, otherwise `DigitalOcean 8x H200` | DeepSeek’s MLA + MoE deployment is best treated as an expert-parallel H200-class workload. |
| `Kimi-K2` (mapped from “2.6”) | `Managed API first`, then `Oracle 2x BM.GPU.H200.8` only if already available | Kimi is the hardest model in this set to self-host safely at `128k`; vendor guidance already starts at `16 GPUs`. |
| `MiniMax-M2.7` | `DigitalOcean 8x H200` or `Oracle BM.GPU.H200.8` | The official docs already assume multi-GPU serving; H200 is the cleanest provider fit in your environment. |

## Provider Bottom Line

### DigitalOcean

- Best self-host provider for tomorrow if you want straightforward raw-GPU control.
- Strongest for:
  - `1x H200` `gpt-oss-120b`
  - `8x H200` `Qwen3-Coder`, `DeepSeek-V3.1`, `MiniMax-M2.7`
- Weakest for:
  - `Kimi` 16-GPU clustered production, because multi-node networking is the least confidence-inspiring part of the stack.

### Oracle

- Best provider when you can use managed `OCI Generative AI` or when you already have H200 GPU quotas.
- Strongest for:
  - managed `gpt-oss-120b`
  - `BM.GPU.H200.8` for large MoE self-hosting
- If quotas are not already in place, treat Oracle as:
  - control plane
  - orchestrator
  - eval coordinator
  - gateway

### NVIDIA portal / free testing

- Best for:
  - smoke validation
  - comparing model behavior
  - tool-calling checks
  - quick trial access to the mapped model families
- Not enough control for:
  - guaranteed `128k` headroom
  - low-level KV tuning
  - TP/PP/EP/CP decisions
  - production-safe self-host style capacity planning

## Minimum Viable vs Production-Safe

| Model family | Minimum viable | Production-safe recommendation |
|---|---|---|
| `gpt-oss-120b` | `1x H100 80 GB` | `1x H200 141 GB` or Oracle managed |
| `Qwen3-Coder-480B` | `8x H100` with risk | `8x H200` |
| `DeepSeek-V3.1` | `8x H200` | `8x H200` with `vLLM` EP |
| `Kimi-K2` | `16x H200/H20` class cluster | `16x H200` class cluster plus validated ops path |
| `MiniMax-M2.7` | `4x 96 GB` class node or `8x H100` with risk | `8x H200` |

## Testing-Only Paths

- NVIDIA portal for every target model family.
- DigitalOcean `1x H100` for `gpt-oss-120b`.
- Oracle `BM.GPU.H100.8` for `Qwen3-Coder`, `DeepSeek-V3.1`, `MiniMax-M2.7` if H200 is unavailable.

## Do-Not-Attempt Calls

- Do not call `Kimi` on a single 8-GPU node “production ready” at `128k`.
- Do not rely on CPU offload as the primary answer to KV-cache pressure for these large MoE models.
- Do not leave `max_model_len` at a model’s absolute maximum if the workload only needs `128k`.
- Do not enable prefix caching blindly on giant-MoE eval nodes with lots of unique prompts.

## Default Runtime Posture

- `vLLM` is the default self-host runtime.
- `SGLang` is the main alternate runtime for the largest MoE models when `vLLM` stability or topology becomes the bottleneck.
- `NVIDIA managed` and `OCI Generative AI` are managed-service options, not substitutes for low-level runtime tuning.

## One-Sentence Recommendation

If the goal is to make smart, conservative choices tomorrow, deploy `gpt-oss-120b` on Oracle managed or a single H200, deploy `Qwen3-Coder`, `DeepSeek-V3.1`, and `MiniMax-M2.7` on `8x H200`, and keep `Kimi` on managed endpoints until you truly have a validated `16-GPU` cluster.
