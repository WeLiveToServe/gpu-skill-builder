---
title: GPU Provision via gpu-skill-builder
description: Provision a GPU instance and get an OpenAI-compatible endpoint for use as a model backend.
---

# GPU Provision

Use this skill when you need a GPU-backed open-source model endpoint for inference.
The `gpu_provision` MCP tool provisions a cloud GPU, deploys a model onto it, and
returns an endpoint URL you can use immediately as an OpenAI-compatible backend.

## When to use

- A task requires a locally-hosted or open-source model
- You want to switch providers to a GPU endpoint mid-session
- You need a specific model not available via the current provider

## Tool: gpu_provision

**Required parameters:**
- `provider` — `"huggingface"`, `"modal"`, or `"digitalocean"`
- `hardware_slug` — provider-specific hardware ID (see below)
- `model_repo_id` — HuggingFace model ID (e.g. `"google/gemma-2-2b-it"`)

**Optional parameters:**
- `instance_name` — logical name for idempotency (default: `"gpu-skill-instance"`)
- `max_deployment_hours` — TTL in hours before auto-destroy (default: `2`)
- `region` — cloud region (default: `"us-east-1"`)

## Hardware slugs by provider

| Provider | Slug | GPU | VRAM |
|----------|------|-----|------|
| `huggingface` | `nvidia-t4-x1` | T4 | 16 GB |
| `huggingface` | `nvidia-a10g-x1` | A10G | 24 GB |
| `huggingface` | `nvidia-a100-x1` | A100 | 80 GB |
| `modal` | `t4` | T4 | 16 GB |
| `modal` | `a10g` | A10G | 24 GB |
| `modal` | `h100` | H100 | 80 GB |
| `modal` | `h200` | H200 | 141 GB |

## Example

```json
{
  "tool": "gpu_provision",
  "params": {
    "provider": "modal",
    "hardware_slug": "h100",
    "model_repo_id": "google/gemma-4-31B-it",
    "instance_name": "goose-coding-session",
    "max_deployment_hours": 2
  }
}
```

**Successful response:**
```json
{
  "success": true,
  "endpoint_url": "https://my-org--gpu-skill-vllm.modal.run/v1",
  "instance_id": "goose-coding-session",
  "provider": "modal",
  "hardware": "h100",
  "model": "google/gemma-4-31B-it",
  "status": "running"
}
```

After receiving `endpoint_url`, configure your OpenAI-compatible provider to use it:
- Set `OPENAI_HOST` to the `endpoint_url` value
- Set `OPENAI_API_KEY` to any non-empty string (the endpoint does not require auth)
- Set `GOOSE_PROVIDER=openai` and `GOOSE_MODEL` to the model name

## Notes

- Idempotent: calling with the same `instance_name` returns the existing active instance
- Auto-destroys after `max_deployment_hours` via a programmatic TTL scheduler
- OpenRouter fallback activates automatically if GPU provisioning fails (requires `OPENROUTER_API_KEY`)
- AMD / MI300X is blocked pending DO account entitlement — use `modal` or `huggingface` instead
