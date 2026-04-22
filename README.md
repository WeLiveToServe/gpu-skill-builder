# gpu-skill-builder

A reusable, agent-callable skill whose core purpose is to:
1. Provision a GPU from multiple providers.
2. Load an open-source model that fits the selected GPU.
3. Wire the resulting model endpoint into open-source coding harnesses with correct API configuration.

Works standalone as an interactive CLI or as a Python library called by another agent.

> Maintainer directive: The core purpose above is stable and must not be changed by agents unless the repo owner explicitly directs that change. Development stage details, supported providers, and harness availability can change over time.

## Current State

- Supported runtime providers in code: `huggingface`, `digitalocean`, `modal`, and `openrouter` as a fallback lane.
- Profile-driven runtime selection is now implemented through committed JSON manifests under `profiles/`, with typed resolution for model, deployment, and harness contracts.
- `run_skill()` is a fast-create path. It returns after infrastructure creation and provider handoff; it does **not** promise the endpoint is fully ready for traffic.
- `ensure_active_endpoint(result)` is the strict pre-use guard. It probes `/health`, `/v1/models`, and a fixed smoke prompt before trusting the endpoint.
- `gpu-skill-builder` now emits a non-secret harness handoff manifest in results so sibling harness repos can keep `.env` files local while consuming resolved endpoint metadata.
- Optional always-on monitoring is implemented with deterministic Telegram alerts, readiness watches, stale-endpoint detection, and configurable auto-stop guardrails.
- The research package under [docs/research/production-grade-gpu-deployment](docs/research/production-grade-gpu-deployment) is **draft planning material** and is not the runtime source of truth today.
- Current validation status: the profile-driven runtime and harness-handoff iteration is **untested on live providers and harness runs** in this repo cycle. The automated test suite is green, but treat the current manifests and renderers as unvalidated until we run live checks.

## What It Does

You run it, or another agent calls it, and the repo provisions an OpenAI-compatible inference endpoint with:

- TTL-based auto-destroy
- periodic uptime reporting
- stuck-pending watchdog protection
- per-instance spend guardrails
- concurrency and idempotency guardrails
- optional Telegram-backed fleet monitoring and readiness tracking

The resulting endpoint is intended for open-source coding harnesses that speak OpenAI chat-completions style APIs.

## Profiles And Handoffs

Runtime configuration is now split into committed JSON profile families under `profiles/`:

- `ModelProfile`
- `DeploymentProfile`
- `HarnessProfile`
- `GatewayProfile` schema only

Current runtime truth:

- `profiles/` is the canonical runtime contract source for profile-driven launches.
- the research docs remain draft guidance and do not generate runtime config.
- harness `.env` files stay local to each repo; this repo only emits non-secret handoff data.

## Readiness And Monitoring

There are two different readiness layers in the current repo:

1. Provision-time checks:
   `remote_vllm.py` waits for `/health` and validates `/v1/models` on remote `vLLM` launches used by the DigitalOcean path.
2. Runtime readiness checks:
   the shared probe layer validates:
   - `GET /health`
   - `GET /v1/models`
   - a minimal smoke prompt (`Reply with OK`)

The runtime probe classifies endpoints as:

- `ready`
- `warming`
- `wrong_model`
- `unhealthy`
- `unreachable`
- `provider_error`
- `scaled_to_zero` for Modal

If monitoring is enabled, the repo:

- probes immediately after instance creation or discovery
- keeps a `30` second readiness watch until the endpoint becomes ready or times out
- falls back to the normal fleet-monitor cadence afterward
- emits deterministic Telegram events on state transitions only
- can auto-stop long-running instances and, optionally, persistently stale or unhealthy ones

Current Telegram event names:

- `monitor_started`
- `instance_detected`
- `readiness_passed`
- `readiness_timeout`
- `health_regressed`
- `stale_endpoint`
- `provider_list_failed`
- `instance_disappeared`
- `runtime_threshold_exceeded`
- `auto_stop_attempted`

## Two Modes Of Operation

### Interactive

```bash
PYTHONIOENCODING=utf-8 python main.py
```

This walks through a deterministic three-step selection flow:

1. provider
2. hardware tier
3. model

It shows a summary and asks for confirmation before spending anything.

### Agent Mode

```python
from skill import ensure_active_endpoint, run_skill

result = await run_skill(
    instance_name="my-inference-node",
    region="us-east-1",
    max_deployment_hours=2,
    provider="huggingface",
    hardware_slug="nvidia-t4-x1",
    model_repo_id="google/gemma-2-2b-it",
)

if result.success:
    checked = await ensure_active_endpoint(result)
    print(checked.instance.endpoint_url)
```

Pass all three of `provider`, `hardware_slug`, and `model_repo_id` to bypass prompts.

Important current contract:

- `run_skill()` means the infrastructure path succeeded.
- `ensure_active_endpoint()` means the endpoint passed the stricter readiness probe and is the right function to call before real model usage in long-lived sessions.
- `result.harness_handoff` is non-secret and safe to pass to sibling harness repos; it contains resolved base URL, model name, profile IDs, and expected env key names, but no credentials.

## Supported Providers

| Provider | Current code status | Notes |
|---|---|---|
| HuggingFace | Supported | Uses HF Inference Endpoints API v2. Monitoring probes use `HF_TOKEN`. Current profile-driven iteration is untested live. |
| DigitalOcean | Supported | Creates droplets and deploys remote `vLLM` over SSH using resolved deployment profiles. Current profile-driven iteration is untested live. |
| Modal | Supported | Deploys OpenAI-compatible `vLLM` apps and monitors readiness and staleness. Current profile-driven iteration is untested live. |
| OpenRouter | Fallback only | OpenAI-compatible fallback lane when a GPU endpoint fails or later becomes unhealthy. Not part of the GPU fleet monitor. |
| AMD / MI300X | Blocked | No active provider integration; current code returns a clear blocked message. |

Other provider folders under `launch-playbooks/` are runbooks and research artifacts. They are not current `skill.py` provider integrations unless this README explicitly says so.

## Setup

```bash
pip install -r requirements.txt
```

Create a local `.env` in the repo root with the provider credentials and monitor settings you actually use:

```dotenv
HF_TOKEN=
DIGITALOCEAN_ACCESS_TOKEN=
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=qwen/qwen3.6-plus
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GPU_MONITOR_ENABLED=false
GPU_MONITOR_INTERVAL_MINUTES=5
GPU_MONITOR_RUNTIME_ALERT_MINUTES=120
GPU_MONITOR_AUTO_STOP_MINUTES=0
GPU_MONITOR_READINESS_POLL_SECONDS=30
GPU_MONITOR_READINESS_TIMEOUT_MINUTES=20
GPU_MONITOR_STALE_AFTER_MINUTES=10
GPU_MONITOR_UNHEALTHY_AUTO_STOP_MINUTES=0
```

Settings precedence is:

1. process environment
2. repo-local `.env`
3. `~/dev/.env`

Use provider-scoped variable names in this repo. Do not overload `OPENAI_API_KEY` for OpenRouter.

## Recommended Always-On Monitor

For durable alerting, run the monitor on an always-on host:

```bash
python gpu_monitor_daemon.py
```

This is the recommended way to avoid silent spend and stale endpoints during long sessions or after local agent processes exit.

Current monitor behavior:

- polls `huggingface`, `modal`, and `digitalocean`
- stores state in `.do_state.json` under `gpu_monitor`
- sends deterministic Telegram alerts
- tracks first seen, first ready, last successful probe, current classification, and consecutive failures
- supports runtime auto-stop and optional unhealthy/stale auto-stop

## File Structure

```text
gpu-skill-builder/
├── providers/                     # provider implementations used by run_skill()
├── skill.py                       # main entrypoint
├── profile_registry.py            # typed profile loading + runtime selection
├── profiles/                      # canonical JSON model/deployment/harness profiles
├── remote_vllm.py                 # remote vLLM deployment for raw GPU VMs
├── monitor.py                     # fleet monitor + readiness/staleness tracking
├── gpu_monitor_daemon.py          # always-on monitor process
├── scheduler.py                   # TTL, uptime, watchdog, readiness-watch scheduling
├── endpoint_probe.py              # shared readiness probe layer
├── monitor_alerts.py              # deterministic Telegram event formatting/sending
├── handoff.py                     # non-secret harness handoff manifest builder
├── catalog.py                     # static VRAM -> model compatibility map
├── docs/                          # research and planning material
└── launch-playbooks/              # provider and harness runbooks
```

## Draft Planning Material

The following folders are intentionally **not** runtime truth today:

- [docs/research/production-grade-gpu-deployment](docs/research/production-grade-gpu-deployment)
- [launch-playbooks/production-grade](launch-playbooks/production-grade)

They are draft planning artifacts for later architecture changes.

## Known Limitations

- `run_skill()` success does not mean the endpoint is fully ready; use `ensure_active_endpoint()` before relying on the endpoint.
- The current profile-driven runtime manifests and harness handoff flow are still untested against live provider and harness runs in this repo cycle.
- Telegram monitoring requires both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- OpenRouter is a fallback lane, not part of the GPU fleet monitor.
- AMD / MI300X is still blocked in current code.
- Some provider and harness runbooks under `launch-playbooks/` and `cli-playbooks/` are historical validation notes rather than first-class runtime integrations.
