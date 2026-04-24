# Readiness, Monitoring, And Cost Reference

Use this reference when changing endpoint checks, fallback behavior, monitor alerts, TTL, watchdogs, auto-stop, or spend guardrails.

## Runtime Truth

- Fast-create and fallback contract: `skill.py`
- Shared endpoint probe: `endpoint_probe.py`
- Fleet monitor and readiness watch: `monitor.py`
- Scheduled TTL, uptime, watchdog, monitor jobs: `scheduler.py`
- Telegram event formatting/sending: `monitor_alerts.py`
- Always-on daemon entrypoint: `gpu_monitor_daemon.py`
- Settings and env precedence: `config.py`

## Readiness Contract

`run_skill()` returning success means provider creation and handoff succeeded. It does not promise the endpoint is ready for real traffic.

`ensure_active_endpoint(result)` is the strict pre-use guard. It checks provider instance state and probes the endpoint before returning a verified-ready result or OpenRouter fallback.

The shared probe validates:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions` with a minimal smoke prompt

Probe classifications are `ready`, `warming`, `wrong_model`, `unhealthy`, `unreachable`, `provider_error`, and `scaled_to_zero`.

## Monitoring And Cost

The monitor tracks first seen, first active, first ready, probe state, consecutive failures, stale endpoint age, runtime thresholds, and auto-stop attempts. Alerts are deterministic Telegram events emitted on state transitions.

Core guardrails include:

- pre-flight spend cap
- max concurrent instances
- TTL auto-destroy
- uptime reporting
- stuck-pending watchdog
- readiness timeout
- stale/unhealthy endpoint detection
- optional runtime and unhealthy auto-stop

## Change Rules

- Keep alert event names stable unless updating tests and README together.
- Do not add provider-specific readiness checks outside `endpoint_probe.py` unless the provider truly cannot expose the shared OpenAI-compatible surface.
- When changing monitor state semantics, update tests around monitor transitions and stale/disappeared instances.
- Billing helpers are currently DigitalOcean-specific side utilities, not a normalized runtime billing layer.
