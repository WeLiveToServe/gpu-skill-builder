# gpu-builder

Provision a GPU instance on a supported cloud provider, load a compatible open-source model, and manage the lifecycle programmatically.

## When to use

Invoke this skill when the user wants to:
- Spin up a GPU-backed inference endpoint
- Deploy an open-source model on cloud GPU hardware
- Manage (list, status-check, destroy) existing GPU instances

## How to invoke

Run the skill interactively:
```bash
python main.py
```

Or call it programmatically from another agent:
```python
import asyncio
from skill import run_skill

result = await run_skill(
    instance_name="my-instance",
    region="us-east-1",
    max_deployment_hours=4,
)
```

## Interaction flow

The skill always drives a deterministic 3-step selection:

1. **Provider** — choose from available GPU providers (e.g., `huggingface`, `digitalocean`)
2. **Hardware tier** — choose a GPU size; VRAM, price/hr, and provider are shown
3. **Model** — choose from a curated list of models verified to fit the selected VRAM

The user confirms before any resources are created.

## What is programmatic (never ask the LLM)

| Concern | Mechanism |
|---|---|
| TTL / max deployment time | `scheduler.schedule_ttl()` — APScheduler DateTrigger |
| Uptime reporting | `scheduler.schedule_uptime_report()` — APScheduler IntervalTrigger |
| Retry on API failure | `tenacity` decorators on provider methods |
| Model ↔ VRAM matching | `catalog.get_compatible_models()` — static lookup table |
| Credentials | `pydantic-settings` — local `gpu-skill-builder/.env` first, then `C:/Users/keith/dev/.env` |

## Supported providers

| Provider | Status | Notes |
|---|---|---|
| `huggingface` | POC ready | Uses HF Inference Endpoints API v2 |
| `digitalocean` | Stub ready | Requires `DIGITALOCEAN_TOKEN` and SSH key `codex-do-oci-ampere` |

## Adding a provider

1. Create `providers/<name>_provider.py` inheriting `GpuProvider`
2. Implement: `list_hardware`, `create_instance`, `get_instance`, `destroy_instance`, `list_instances`
3. Add hardware catalog entries (see `providers/hf_provider.py` for reference)
4. Register in `providers/__init__.py` `PROVIDER_MAP`
5. Add VRAM-appropriate models to `catalog.py` if needed

## Environment variables required

| Variable | Provider |
|---|---|
| `HF_TOKEN` | HuggingFace |
| `DIGITALOCEAN_ACCESS_TOKEN` | DigitalOcean |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | Modal |
| `OPENROUTER_API_KEY` | OpenRouter fallback |
