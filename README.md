# gpu-skill-builder

A reusable, agent-callable skill for provisioning GPU cloud instances and loading
open-source models onto them. Works standalone (interactive CLI) or as a Python
library called by an orchestrating LLM agent.

---

## What it does

You run it (or another agent calls it), choose a cloud provider, a GPU tier, and a
model, and it creates a live inference endpoint with:

- automatic TTL (it self-destructs after a configurable number of hours)
- uptime reporting on a fixed interval
- a stuck-pending watchdog (kills instances that never reach `running`)
- cost, concurrency, and idempotency guardrails to prevent runaway spend

The endpoint it creates is OpenAI-compatible, so any harness that can talk to the
OpenAI chat completions API can use it immediately after provision.

---

## Two modes of operation

### Interactive (for humans)

```bash
PYTHONIOENCODING=utf-8 python main.py
```

## Project Handoff Plan

For detailed information about completed work, cloud provider configurations, and next steps, please see the [handoff-plan.md](handoff-plan.md) document. This file contains comprehensive documentation of all research, setup, and configuration work completed to date, and should be consumed by the next agent working on this project.

Walks through a three-step selection menu: provider → hardware tier → model.
Shows a summary and asks for confirmation before spending anything.

### Agent mode (for LLM orchestrators)

```python
import asyncio
from skill import run_skill

result = await run_skill(
    instance_name="my-inference-node",
    region="us-east-1",
    max_deployment_hours=2,
    provider="huggingface",
    hardware_slug="nvidia-t4-x1",
    model_repo_id="google/gemma-2-2b-it",
)

if result.success:
    print(result.instance.endpoint_url)  # ready to use
```

Pass all three of `provider`, `hardware_slug`, and `model_repo_id` and every prompt
is bypassed. The skill provisions and returns a structured result.

---

## Architecture decisions and why

### Why not a workflow framework (Prefect, Airflow, ControlFlow)?

We evaluated these and rejected them. The provisioning flow is three fixed sequential
steps with no branching logic — there is nothing to orchestrate. Workflow frameworks
earn their weight when you have DAGs, retries across steps, visibility dashboards, and
teams sharing pipelines. Here, they would require running a server just to schedule a
single TTL job. APScheduler embedded in-process gives us DateTrigger (TTL) and
IntervalTrigger (uptime, watchdog) with zero infrastructure.

### Why not Pydantic AI or another agent framework?

This skill is itself called by an LLM agent. Wrapping it in another agent framework
would add a layer with no benefit — you'd have an agent framework calling an agent
framework. The skill is a plain async Python function. The caller decides how to
orchestrate it.

### Why are retries in tenacity and not in the providers?

Provider API calls fail transiently (rate limits, cold starts, network blips). Tenacity
decorators sit directly on the HTTP call sites and retry with exponential backoff
without any retry logic leaking into the calling code. The skill stays clean.

### Why is model selection a static catalog and not an LLM call?

Two reasons. First, correctness: a model must physically fit in the VRAM of the chosen
hardware. An LLM making that judgment is a liability — it can hallucinate model sizes
or get VRAM numbers wrong. Second, determinism: the same inputs should always produce
the same valid options. The catalog (`catalog.py`) is a hand-curated VRAM-to-model
map. The LLM's creative role is scoped to *which* model to pick from the verified list,
not to inventing the list itself.

### Why are credentials loaded via pydantic-settings?

All tokens come from a shared `.env` file via `pydantic-settings`. This means the
skill works the same whether called interactively, from a test harness, or from a
remote agent — no credential argument threading, no hardcoded paths in provider code.

### Why is the TTL programmatic and not delegated to the LLM?

Because the LLM will forget. An LLM orchestrator that provisions a GPU instance and
then enters a long conversation loop may never issue a destroy call. The TTL job is
scheduled immediately on creation and fires on a wall-clock trigger regardless of what
the calling agent does next. This is the primary defence against forgotten instances
burning credits.

---

## Operational guardrails

These fire automatically — no configuration needed at call time:

| Guardrail | Default | What it does |
|---|---|---|
| Cost cap | $5.00 per instance | Rejects provision if `hours × rate` exceeds limit |
| Idempotency | — | Returns the existing instance if the same name is already active |
| Concurrency cap | 2 instances | Rejects new provision if 2+ instances are already live |
| Stuck watchdog | 15 min pending timeout | Destroys instances that never leave pending/initializing |
| Startup reconciliation | 1h fallback TTL | Re-registers TTL jobs for live instances on process restart |

All defaults are in `config.py` and can be overridden via environment variables.

The biggest risk when an LLM orchestrates this skill is **calling it in a loop** —
each iteration provisions a new instance if the name changes. Always use a stable,
predictable instance name. The idempotency guard returns the existing instance
immediately on a name collision, making repeat calls safe.

---

## Supported providers

| Provider | Status | Notes |
|---|---|---|
| HuggingFace | Ready | Uses HF Inference Endpoints API v2. Endpoint is OpenAI-compatible. Requires payment method on account. |
| DigitalOcean | Ready (secondary) | H200 GPU (`gpu-h200x1-141gb`) in `atl1` confirmed working. SSH key: `codex-do-oci-ampere`. |
| Modal | Ready | Deploys an OpenAI-compatible vLLM app endpoint via `modal deploy`. |
| AMD / MI300X | Blocked | DO account has $200 AMD credits but AMD GPU entitlement not enabled on the backend. Needs DO support ticket. See `human-amd-credits-use.md`. |

---

## File structure

```
gpu-skill-builder/
├── .claude/skills/gpu-builder.md   ← Skill definition for LLM agent callers
├── providers/
│   ├── __init__.py                 ← PROVIDER_MAP registry
│   ├── base.py                     ← Abstract GpuProvider interface
│   ├── hf_provider.py              ← HuggingFace Inference Endpoints (v2 API)
│   └── do_provider.py              ← DigitalOcean droplets
├── config.py                       ← Settings via pydantic-settings (.env loader)
├── models.py                       ← Pydantic models: request, result, instance
├── catalog.py                      ← Static VRAM→model map (~20 curated models)
├── skill.py                        ← run_skill(): agent mode + interactive mode
├── scheduler.py                    ← TTL, uptime, watchdog, startup reconciliation
├── main.py                         ← Test harness: provisions T4 + Gemma 2 2B
├── requirements.txt
├── agent-amd-credits-use.md        ← Agent-readable AMD/DO credit investigation
├── human-amd-credits-use.md        ← Human-readable version of same
├── create-h200-droplet.ps1         ← Manual H200 droplet creation script (DO)
└── h200-ip.txt                     ← IP of a prior H200 probe droplet (stale, destroyed)
```

---

## Setup

```bash
pip install -r requirements.txt
```

Required environment variables (in your `.env`):

```
HF_TOKEN=hf_...               # HuggingFace — required for HF provider
DIGITALOCEAN_ACCESS_TOKEN=dop_v1_... # DigitalOcean — required for DO provider
MODAL_TOKEN_ID=ak-...         # Modal token id
MODAL_TOKEN_SECRET=as-...     # Modal token secret
```

The `.env` path is configured in `config.py`. Default is `C:/Users/keith/dev/.env`.

---

## Hardware catalog (HuggingFace)

| Slug | Display | VRAM | $/hr |
|---|---|---|---|
| `nvidia-t4-x1` | NVIDIA T4 | 16 GB | $0.60 |
| `nvidia-a10g-x1` | NVIDIA A10G | 24 GB | $1.00 |
| `nvidia-a10g-x4` | 4× A10G | 96 GB | $4.00 |
| `nvidia-a100-x1` | NVIDIA A100 | 80 GB | $4.00 |
| `nvidia-a100-x4` | 4× A100 | 320 GB | $16.00 |

---

## Model catalog

Models are matched to hardware by VRAM. Only models verified to fit are shown.

| Tier | Hardware | Models |
|---|---|---|
| 16 GB | T4 | Llama 3.2 1B/3B Instruct, Gemma 2 2B Instruct, Phi-3 Mini 4K, Mistral 7B |
| 24 GB | A10G | Llama 3.1 8B, Llama 3.2 11B Vision, Gemma 2 9B, Mistral 7B, Qwen 2.5 7B |
| 80 GB | A100 | Llama 3.1/3.3 70B, Qwen 2.5 72B, Mixtral 8×7B, Gemma 2 27B |
| 96 GB | 4× A10G | Llama 3.1 70B, Qwen 2.5 72B, Mixtral 8×7B, Gemma 2 27B |
| 320 GB | 4× A100 | Llama 3.1 405B FP8, Llama 3.3 70B, Qwen 2.5 72B |

---

## H200 Optimization Notes

See [h200-Qwen3.6-35B-A3B-text-only-droplet-optimization.txt](h200-Qwen3.6-35B-A3B-text-only-droplet-optimization.txt).
This includes advanced vLLM flags for ACP (Automatic Compression Pooling), KV cache management, and monitoring guidance.

## Adding a provider

1. Create `providers/<name>_provider.py` inheriting `GpuProvider` from `providers/base.py`
2. Implement: `list_hardware`, `create_instance`, `get_instance`, `destroy_instance`, `list_instances`
3. Add a hardware catalog (list of `HardwareTier` objects with VRAM and price)
4. Register in `providers/__init__.py` `PROVIDER_MAP`
5. Add models to `catalog.py` for any new VRAM tiers you introduce

See `providers/hf_provider.py` as the reference implementation.

---

## What is not done yet

- Post-provision health probe (confirm inference responds after `running`)
- Cross-session spend tracking (current cost cap is per-instance, not cumulative)
- Model deployment step for DO droplets (SSH in, install vLLM, load model)
- AMD provider (blocked on DO support — see `human-amd-credits-use.md`)
- Multi-provider parallel availability check
