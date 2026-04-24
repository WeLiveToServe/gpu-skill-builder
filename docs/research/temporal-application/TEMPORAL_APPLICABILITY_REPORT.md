# Temporal Applicability Report For gpu-skill-builder

Analysis date: 2026-04-23

Upstream analyzed:

- Repository: `temporalio/temporal`
- Public positioning: durable execution platform for reliable applications
- Local analysis checkout: `12e860ca7402ddc647a8735a8ed3524c181077df`
- Observed branch: `main`
- Observed commit date: `2026-04-22T19:37:10-05:00`
- Observed commit subject: `[Standalone Activity] Emit ContextMetadata keys from CHASM handlers (#10037)`
- Repo shape observed in the checkout: `3375` files, `2620` Go files, `776` Go test files, `1072` files under `service/`, `1142` files under `common/`, and `65` docs files

Local project analyzed:

- Repository: `gpu-skill-builder`
- Current purpose: provision GPU inference endpoints, load compatible open-source models, monitor readiness, and emit OpenAI-compatible handoff metadata for coding harnesses
- Current runtime truth: root `README.md`, Python source files, and committed manifests under `profiles/`
- Current planning truth: `docs/research/production-grade-gpu-deployment/`
- Current benchmark surface: `.bench/`, especially the DigitalOcean H200 `extreme100` matrix orchestrator
- Current warning from docs index: the DigitalOcean H200 benchmark matrix orchestration is implemented but not yet live-validated end to end

## Executive Summary

Temporal is more directly applicable to `gpu-skill-builder` than Phoenix at the orchestration layer. Phoenix helps with product shape, test scaffolding, telemetry, and optional UI. Temporal helps with the hardest operational problem in this repo: long-running GPU deployment work that must survive crashes, restarts, retries, timeouts, cancellations, operator actions, and partial failure.

The strongest lesson is not "rewrite this repo in Go" and not "vendor Temporal Server." The strongest lesson is that GPU launch and benchmark execution should be modeled as durable workflows:

- A workflow owns the deployment state machine.
- Activities perform side effects such as cloud API calls, SSH commands, endpoint probes, benchmark subprocesses, and destroy calls.
- Every side-effecting activity has explicit retry, timeout, heartbeat, and idempotency semantics.
- Operators can query workflow state without scraping logs.
- Operators can signal or update a live workflow to cancel, extend TTL, force destroy, retry a probe, promote fallback, or start a benchmark.
- Deployment runs have searchable metadata such as provider, hardware slug, model profile, deployment profile, instance ID, readiness state, cost guardrail result, and benchmark label.
- TTL, stale endpoint handling, recurring probes, cleanup, and benchmark windows are durable schedules rather than only in-memory jobs.

The immediate recommendation is a staged approach:

- Do not add Temporal Server as a mandatory runtime dependency yet.
- First add a Temporal-inspired deployment ledger and activity boundary inside the current Python project.
- Then prototype Temporal with the Python SDK around one narrow workflow: the DigitalOcean H200 benchmark matrix or a single GPU deployment run.
- Adopt Temporal as an optional orchestration backend only after the internal workflow events, idempotency keys, and compensation behavior are clear.

That sequencing avoids platform churn while still applying Temporal's best ideas where they matter most.

## What Temporal Actually Is

Temporal is a durable execution platform. Its core idea is that application progress is represented by a durable workflow history. If a worker crashes, redeploys, or loses the network, the workflow can be replayed from history and continue from the same logical point.

The upstream repository analyzed here is the Temporal Server. It is not the Python SDK, although the repo depends on SDK and API modules and includes functional tests that validate server behavior against SDK-facing concepts.

The architecture docs describe these server-side services:

- `Frontend` receives API requests from applications and workers.
- `History` owns workflow execution state, appends events, drives timers, and creates tasks.
- `Matching` owns task queues that workers poll.
- `Worker` runs internal system workflows and background tasks.

The docs describe a cluster that executes workflows durably and correctly despite transient failures in Temporal Server processes or user-hosted worker processes. User code still runs in user-owned environments, which matters for this repo because GPU provider calls, SSH commands, and benchmark subprocesses should remain in Python workers that we control.

Important upstream concepts:

- Event sourcing: workflow history is an append-only event log sufficient to recreate workflow state.
- Workflow definitions: deterministic orchestration code that schedules activities, timers, child workflows, queries, signals, and updates.
- Activity definitions: normal code that performs side effects and may be non-deterministic, with idempotency recommended.
- Task queues: lightweight queues polled by workers; task queue names form an operational routing boundary.
- Timers and schedules: durable time-based execution primitives.
- Visibility and search attributes: indexed metadata for finding and filtering workflow executions.
- Worker versioning and safe deployment: mechanisms and practices for changing workflow/worker code without breaking replay.

## Why This Matters For gpu-skill-builder

`gpu-skill-builder` is already a small orchestration system. It does not just call one API. It coordinates a sequence of operations that may take minutes or hours:

- Resolve provider, hardware, model, deployment profile, and harness profile.
- Enforce spend and concurrency guardrails.
- Check for existing active instances.
- Create provider-managed or raw GPU instances.
- For DigitalOcean, SSH into a VM and install or restart `vLLM` under `systemd`.
- Probe `/health`, `/v1/models`, and chat or responses endpoints.
- Emit a harness handoff manifest without secrets.
- Schedule TTL, uptime reporting, stuck-pending cleanup, readiness watch, and fleet monitoring.
- Detect stale or unhealthy endpoints and optionally auto-stop them.
- Run benchmark harnesses through local tunnels.
- Restore interactive service configuration after benchmark mode.

That is exactly the kind of work that benefits from durable execution. The risk is not that a single Python function is hard to read. The risk is that one process crash, local laptop sleep, network interruption, or partial provider failure can split reality:

- The cloud provider may have a running GPU instance.
- `.do_state.json` may or may not have enough state to recover.
- APScheduler jobs may have been lost on restart.
- A remote `systemd` unit may have been changed to benchmark mode.
- A benchmark tunnel may be down while the remote service is still burning money.
- A handoff manifest may say "provisioned" even though readiness later regressed.
- A failed destroy may be logged but not retried with enough context.

Temporal's design language gives this repo a cleaner way to express and test those failure modes.

## Recommendation: Treat Temporal As An Orchestration Reference First

Temporal should be treated as a production-grade reference architecture before it becomes a runtime dependency.

The repo should first introduce the primitives that Temporal would require anyway:

- A deployment run ID.
- An append-only deployment event ledger.
- Idempotency keys for provider and remote actions.
- Explicit activity boundaries.
- Per-activity retry and timeout policy.
- A queryable deployment state projection.
- Cancellation and operator commands as first-class state transitions.
- Compensation steps for expensive or destructive actions.

Once those exist, moving to Temporal becomes much lower risk. The workflow can map cleanly onto the existing state model instead of forcing a new abstraction onto scattered side effects.

## What Not To Do

Do not embed Temporal Server inside this repository.

Reasons:

- Temporal Server is a large Go service with its own persistence, membership, dynamic config, visibility, worker, and deployment concerns.
- This repo is Python-first and already integrated with `pydantic`, `httpx`, `apscheduler`, provider SDKs, Modal, MCP, pytest, and benchmark scripts.
- The useful adoption path would be the Temporal Python SDK plus a Temporal service, not copying server internals.
- Adding a mandatory Temporal cluster too early would make local development and simple provider tests harder.

Do not put cloud API calls, SSH calls, random timestamps, subprocess execution, or HTTP probes into workflow code if the project adopts Temporal later. Those are activities. Workflow code should stay deterministic orchestration.

Do not store provider tokens, API keys, SSH material, prompt contents containing secrets, or PII-like operator data in search attributes. Temporal's own search attribute docs warn against sensitive data because search attributes are intended for filtering and visibility.

## Adoption Options

| Option | Description | Recommended Use |
|---|---|---|
| Temporal-inspired internal ledger | Keep current Python runtime, add workflow events, state projection, and activity policies. | Recommended immediate path. |
| Temporal Python SDK prototype | Add optional worker/client package and run against local Temporal dev server. | Recommended for one narrow workflow after the ledger design is clear. |
| Temporal as production control plane | Run self-hosted Temporal or Temporal Cloud for deployment workflows. | Later, if GPU operations become multi-host, multi-user, or always-on. |
| Temporal Server code reuse | Copy or vendor Temporal Server internals. | Avoid. |

## Current Local Architecture Fit

The current repo already has several pieces that map cleanly to Temporal concepts:

| Current repo concept | Temporal concept | Why it maps |
|---|---|---|
| `skill.run_skill()` | Workflow entrypoint candidate | It coordinates provider choice, guardrails, provision, monitor setup, and result construction. |
| Provider `create_instance()` and `destroy_instance()` | Activities | They perform external side effects and require retry/idempotency discipline. |
| `remote_vllm.deploy_vllm_remote()` | Long-running activity | It SSHes, writes service files, restarts `systemd`, waits for health, and validates model serving. |
| `endpoint_probe.probe_openai_compatible_endpoint()` | Activity | It performs HTTP IO and classifies readiness. |
| `scheduler.py` TTL/watchdog/readiness jobs | Timers and schedules | The timing intent should survive process restarts. |
| `monitor.py` state and alerts | Workflow state projection plus reporter | It records lifecycle state and emits operator-facing events. |
| `.do_state.json` | Recovery cache or lightweight event store | It is a local persistence mechanism, but not yet a full durable history. |
| `handoff.py` | Workflow result/query payload | It gives clients the endpoint contract after readiness or fallback. |
| `.bench/run_do_h200_extreme100_matrix.py` | Benchmark matrix workflow candidate | It has stages, smoke gates, retries, restore logic, and long-running side effects. |

This is a good fit. The repo is already close to workflow-oriented. Temporal mainly supplies names, constraints, and durability semantics.

## Pattern 1: Durable Deployment Event History

Temporal's History Service stores a linear sequence of events for each workflow execution. That history is sufficient to recover workflow state through replay.

For `gpu-skill-builder`, add a deployment run event log before adding Temporal itself.

Suggested event names:

- `DeploymentRequested`
- `RuntimeSelectionResolved`
- `SpendGuardrailPassed`
- `SpendGuardrailRejected`
- `ExistingInstanceReused`
- `ProviderCreateScheduled`
- `ProviderCreateStarted`
- `ProviderCreateSucceeded`
- `ProviderCreateFailed`
- `RemoteVllmDeployStarted`
- `RemoteVllmDeployHeartbeat`
- `RemoteVllmDeploySucceeded`
- `RemoteVllmDeployFailed`
- `ReadinessProbeStarted`
- `ReadinessProbeClassified`
- `ReadinessVerified`
- `ReadinessTimedOut`
- `FallbackActivated`
- `HandoffManifestCreated`
- `TtlScheduled`
- `DestroyRequested`
- `DestroyStarted`
- `DestroySucceeded`
- `DestroyFailed`
- `BenchmarkModeActivated`
- `BenchmarkSmokeStarted`
- `BenchmarkSmokePassed`
- `BenchmarkSmokeFailed`
- `BenchmarkFullRunStarted`
- `BenchmarkFullRunSucceeded`
- `BenchmarkFullRunFailed`
- `InteractiveServiceRestoreStarted`
- `InteractiveServiceRestoreSucceeded`
- `InteractiveServiceRestoreFailed`

Suggested event envelope:

```json
{
  "run_id": "gpusb-20260423-001",
  "event_id": 17,
  "event_type": "RemoteVllmDeployHeartbeat",
  "occurred_at": "2026-04-23T02:41:00Z",
  "provider": "digitalocean",
  "instance_id": "123456",
  "instance_name": "gpu-skill-instance",
  "hardware_slug": "h200x1",
  "model_profile_id": "openai-gpt-oss-120b",
  "deployment_profile_id": "digitalocean-gpt-oss-120b-h200x1",
  "harness_profile_id": "openai-compatible-generic",
  "activity": "remote_vllm_deploy",
  "attempt": 1,
  "status": "running",
  "detail": "waiting_for_health",
  "secret_ref": ""
}
```

The event log should not store raw tokens, full SSH commands with secrets, API keys, or unredacted provider responses.

Immediate storage options:

- JSONL under `.runs/deployments/` for simple local durability.
- SQLite for queryable local state and safer writes.
- A small abstraction that can later be backed by Temporal history and visibility.

Recommendation: start with SQLite if this is expected to become operator-facing. Start with JSONL if the goal is only to unblock tests and a proof of concept.

## Pattern 2: Workflow Code Versus Activity Code

Temporal draws a strong line between deterministic workflow orchestration and non-deterministic activity execution.

In this repo, the workflow should decide the next step. Activities should do the work.

Candidate workflow responsibilities:

- Validate that required inputs are present.
- Resolve or record the selected profiles.
- Check the latest projected state before destructive work.
- Schedule activities with policy.
- Wait on timers.
- Accept cancel, extend, fallback, and benchmark commands.
- Create handoff state after readiness.
- Choose compensation on failure.
- Expose state queries.

Candidate activity responsibilities:

- List provider instances.
- Create provider instance.
- Destroy provider instance.
- Deploy `vLLM` over SSH.
- Render and write remote service files.
- Probe endpoint readiness.
- Build non-secret handoff manifest.
- Send monitor or Telegram alert.
- Start and stop local SSH tunnel.
- Run benchmark harness subprocess.
- Restore remote service from backup.

This split is useful even without Temporal. It creates testable functions with stable inputs and outputs.

## Pattern 3: Idempotency Keys For Expensive Side Effects

Temporal activities may retry. Retried activities must be idempotent or explicitly non-retryable.

This repo needs idempotency at these boundaries:

| Activity | Idempotency strategy |
|---|---|
| Provider create | Use deterministic instance name and `run_id`; check existing instances before create; record provider instance ID after success. |
| Remote service deploy | Render deterministic service unit; verify active unit before rewrite; record checksum of applied unit. |
| Endpoint probe | Safe to retry because it is read-mostly. |
| Handoff manifest | Pure function from instance plus profile selection; safe to repeat. |
| Benchmark service activation | Back up original remote service once per `run_id`; record backup path and checksum. |
| Benchmark harness run | Use deterministic run label and ledger path; do not rerun full suite unless the workflow state says it is safe. |
| Restore service | Safe to retry if original backup content and env are known. |
| Destroy | Treat missing/not-found as success after provider reconciliation. |

This is especially important for `create_instance()` and benchmark restoration. A retry that creates a second H200 or fails to restore interactive mode can create real cost and operator confusion.

## Pattern 4: Activity Timeouts And Heartbeats

Temporal's activity docs emphasize timeouts and heartbeats for long-running activity executions. That maps directly to GPU work.

Recommended policy matrix:

| Activity | Start-to-close | Schedule-to-close | Heartbeat | Retry |
|---|---:|---:|---:|---|
| `list_instances` | 30 seconds | 2 minutes | No | Short exponential retry. |
| `create_instance` | 10 minutes | 30 minutes | Optional status heartbeat if provider supports polling. | Retry only on transient provider errors. |
| `deploy_remote_vllm` | 45 minutes | 90 minutes | Yes, every observed stage and periodic health wait. | Retry carefully; avoid duplicate service rewrites without checksums. |
| `probe_endpoint` | 30 seconds | 10 minutes | No | Retry warming, unreachable, 5xx; do not retry wrong model forever. |
| `run_benchmark_smoke` | Per harness timeout plus margin | Whole smoke budget | Yes, per task or per harness. | Retry only operational failures, not model quality failures. |
| `run_benchmark_full` | Per suite timeout plus margin | Whole suite budget | Yes, per task. | Usually no automatic full rerun unless operator requests. |
| `restore_interactive_service` | 10 minutes | 30 minutes | Yes during restart/health wait. | Retry; page/alert if still failing. |
| `destroy_instance` | 5 minutes | 30 minutes | Optional | Retry transient errors; not-found is success. |

Without Temporal, implement the same ideas as activity wrappers that emit `...Started`, `...Heartbeat`, `...Succeeded`, and `...Failed` events.

## Pattern 5: Signals, Updates, And Queries

Temporal workflows can receive messages. Queries are read-only, Signals are asynchronous writes, and Updates are synchronous tracked writes.

This maps cleanly to operator controls for live GPU runs.

Suggested queries:

- `get_status`
- `get_readiness`
- `get_cost_estimate`
- `get_handoff_manifest`
- `get_last_probe`
- `get_benchmark_progress`
- `get_restore_status`
- `get_destroy_status`
- `get_public_timeline`

Suggested signals:

- `request_cancel`
- `request_destroy`
- `extend_ttl`
- `force_probe`
- `activate_openrouter_fallback`
- `mark_operator_acknowledged`
- `pause_monitoring`
- `resume_monitoring`

Suggested updates:

- `approve_spend`
- `start_benchmark_matrix`
- `switch_to_benchmark_mode`
- `restore_interactive_service`
- `retry_failed_activity`
- `promote_endpoint_to_ready`

For the current Python repo, these could first be implemented as CLI commands over a local run ledger:

```bash
python main.py runs status gpusb-20260423-001
python main.py runs signal gpusb-20260423-001 extend-ttl --hours 2
python main.py runs update gpusb-20260423-001 start-benchmark --suite extreme100
python main.py runs timeline gpusb-20260423-001
```

Later, the same command vocabulary can call Temporal workflow handles.

## Pattern 6: Task Queues As Operational Routing Boundaries

Temporal Matching Service routes work through task queues. Workers poll when they have capacity. Task queues persist workflow and activity tasks while workers are unavailable.

This is a strong fit for GPU orchestration because not every machine should do every job.

Recommended task queues if Temporal is adopted:

- `gpu-control`: deterministic workflow tasks and lightweight orchestration.
- `provider-api`: cloud API calls for providers.
- `remote-vllm`: SSH and remote service deployment.
- `endpoint-probe`: endpoint health and model readiness probes.
- `benchmark`: long-running benchmark harness jobs.
- `monitor`: recurring probe and alert jobs.
- `destroy`: destructive cleanup and compensation.

Important rule: workers polling the same task queue should register compatible handlers. If different machines have different capabilities, use separate task queues. For example, a laptop worker should not accidentally run a production destroy activity, and a benchmark host should not accidentally own provider account cleanup unless explicitly configured.

## Pattern 7: Visibility And Search Attributes

Temporal Visibility lets operators list, filter, and search workflow executions. For this repo, visibility is a major missing control-plane capability.

Suggested safe search attributes:

- `Provider`
- `HardwareSlug`
- `ModelProfileId`
- `DeploymentProfileId`
- `HarnessProfileId`
- `InstanceId`
- `InstanceName`
- `ReadinessState`
- `EndpointClass`
- `ManagedByProvider`
- `FallbackActivated`
- `BenchmarkSuite`
- `BenchmarkRunLabel`
- `CostGuardrailState`
- `DestroyState`
- `RestoreState`

Do not include:

- API keys.
- SSH keys.
- Bearer tokens.
- Raw endpoint auth headers.
- Prompt text.
- Private IPs if those are considered sensitive in the deployment environment.
- Full provider error payloads if they may contain account data.

Immediate non-Temporal equivalent:

- Add a `run_state` projection table or JSON file keyed by `run_id`.
- Support `python main.py runs list --provider digitalocean --readiness verified-ready`.
- Support `python main.py runs list --benchmark-suite extreme100 --destroy-state pending`.

## Pattern 8: Durable Schedules For TTL And Monitoring

The current `scheduler.py` uses APScheduler. It handles TTL, uptime reporting, watchdog, fleet monitoring, readiness watches, and startup reconciliation. It already has good instincts, including startup reconciliation for live instances.

The limitation is that in-memory scheduled jobs are still process-local. If the process stops, only reconciliation logic can recover, and it may not know original creation time, original TTL, or exact operator intent.

Temporal-style schedules suggest moving timing intent into durable state:

- `DestroyAt` recorded when a deployment is created.
- `ReadinessProbeEvery` recorded while not ready.
- `StaleEndpointCheckEvery` recorded after first ready.
- `BenchmarkWindow` recorded for planned benchmark runs.
- `CleanupRetryAt` recorded after failed destroy.
- `RestoreRetryAt` recorded after failed service restore.

Immediate implementation without Temporal:

- Persist schedule rows in SQLite or JSONL.
- Reconcile pending schedules on process startup.
- Store original creation time and destroy deadline.
- Make "destroy is due" a state transition, not only a timer callback.

Temporal implementation later:

- Use workflow timers for per-run TTL and readiness waits.
- Use Temporal Schedules for recurring fleet checks or benchmark windows.
- Use schedule pause/resume notes for operator intent.

## Pattern 9: Compensation And Rollback

Temporal does not magically make side effects reversible. It gives the workflow a durable place to remember what happened and what compensation remains.

For `gpu-skill-builder`, compensation should be explicit:

| Failure point | Compensation |
|---|---|
| Provider create succeeds, remote deploy fails | Destroy instance or leave for operator based on policy. |
| Remote deploy succeeds, readiness never passes | Keep probing until timeout, then fallback, destroy, or operator decision. |
| Benchmark service activation succeeds, tunnel fails | Restore interactive service and stop local tunnel. |
| Smoke fails due to operational issue | Attempt repair or skip full benchmark for that harness. |
| Full benchmark fails | Save partial artifacts, restore interactive service, alert. |
| Destroy fails | Retry with backoff and mark cleanup as pending. |
| Provider list fails during monitor | Deduplicate alert and keep previous state until provider recovers. |

The H200 matrix runner already has some compensation behavior: it saves original service/env files, activates benchmark mode, starts a tunnel, runs smoke/full suites, and restores the original service by default. Temporal's contribution is making each stage durable and restartable.

## Pattern 10: Benchmark Matrix As A First Temporal Prototype

The DigitalOcean H200 `extreme100` matrix is the best candidate for a Temporal proof of concept because it is narrow but operationally rich.

It has:

- Clear input parameters.
- Remote service mutation.
- Health waits.
- A local tunnel.
- Smoke gates.
- Multiple harnesses.
- Optional repair attempts.
- Full benchmark runs.
- Artifact paths.
- Restore logic.
- Meaningful partial success and failure states.

Suggested workflow:

```text
BenchmarkMatrixWorkflow
  validate_inputs
  load_last_droplet
  capture_original_remote_service
  render_benchmark_service
  activate_benchmark_service
  wait_for_remote_health
  start_or_validate_tunnel
  preflight_endpoint
  for each harness:
    run_smoke
    classify_smoke
    if smoke passes:
      run_full_suite
    else:
      record_skip_or_repair
  run_optional_opencode_repair_path
  restore_interactive_service
  stop_tunnel
  return benchmark_summary
```

Activities:

- `load_last_droplet_activity`
- `read_remote_file_activity`
- `write_remote_file_activity`
- `systemctl_restart_activity`
- `wait_remote_health_activity`
- `start_tunnel_activity`
- `preflight_endpoint_activity`
- `run_named_suite_activity`
- `classify_smoke_activity`
- `clear_opencode_state_activity`
- `restore_remote_service_activity`
- `stop_tunnel_activity`

This prototype should run against a local Temporal dev server first. It should not become the default benchmark path until it proves that cancellation, restart, and restore behavior are safer than the current script.

## Pattern 11: Deployment Workflow Candidate

A production deployment workflow could look like this:

```text
GpuDeploymentWorkflow
  record DeploymentRequested
  resolve_runtime_selection
  check_spend_guardrail
  list_existing_instances
  if reusable instance exists:
    probe_existing_instance
    return handoff
  create_provider_instance
  if raw VM:
    deploy_remote_vllm
  wait_for_readiness
  create_handoff_manifest
  start_monitoring_or_schedule_probes
  wait for ttl, cancel, destroy, fallback, or extension
  destroy_or_finalize
```

Workflow queries:

- Current phase.
- Last event.
- Endpoint readiness.
- Handoff manifest if available.
- Destroy deadline.
- Cost estimate and elapsed runtime.

Workflow signals:

- Extend TTL.
- Destroy now.
- Cancel provisioning.
- Force fallback.
- Retry readiness probe.

Workflow updates:

- Approve spend above default limit.
- Start benchmark after deployment is ready.
- Convert a provisioned run to a monitored long-lived run.

## Pattern 12: Namespaces And Environment Isolation

Temporal namespaces isolate workflow executions, retention, and visibility. Even without Temporal, `gpu-skill-builder` should name environments explicitly.

Suggested environment dimensions:

- `local-dev`
- `test`
- `staging`
- `production`
- `benchmark`

Suggested isolation rules:

- Test runs cannot destroy production instances.
- Benchmark runs cannot run unless explicit spend and live flags are set.
- Production destroy requires a recorded operator or automation identity.
- Development workflows use fake providers by default.
- Search attributes and event ledgers include `environment`.

If Temporal is adopted, start with separate namespaces for `dev`, `staging`, and `prod` rather than relying only on workflow IDs.

## Pattern 13: Dynamic Config Versus Committed Profiles

Temporal has a large dynamic config system. The important lesson is not to copy its implementation. The important lesson is to separate:

- Versioned product/runtime contracts.
- Operational knobs that can change without code deploy.
- Test-only overrides.

In this repo:

- Committed `profiles/` should remain the canonical model/deployment/harness contract.
- Operational knobs should live in settings and possibly a validated dynamic config file.
- Test-only overrides should be explicit and blocked from production.

Candidate dynamic knobs:

- Readiness probe interval.
- Readiness timeout.
- Destroy retry policy.
- Provider API retry policy.
- Benchmark smoke count.
- Benchmark repair attempt count.
- Monitor stale threshold.
- Unhealthy auto-stop threshold.
- Default max deployment hours.
- Per-provider concurrency cap.

Do not make `vLLM` runtime arguments dynamically mutable without recording the profile version and rendered command in the run history. Otherwise, replaying or auditing a run becomes ambiguous.

## Pattern 14: Worker Versioning And Safe Changes

Temporal's current docs describe Worker Deployments and Worker Deployment Versions, including pinned and auto-upgrade workflows. The older `docs/worker-versioning.md` in the server repo is marked deprecated and pre-release, so current public docs should be preferred for implementation guidance.

The practical lesson for `gpu-skill-builder` is simple:

- A live deployment or benchmark run may outlive a code deploy.
- Workflow shape changes can break replay if using Temporal.
- Even without Temporal, changing orchestration behavior mid-run can confuse recovery.

Recommended local equivalent:

- Store `orchestrator_version` on each run.
- Store `deployment_profile_id` and a content hash of the selected profile.
- Store `remote_service_checksum` when writing `vLLM` service files.
- Store `benchmark_script_version` or git commit for benchmark runs.
- Avoid changing in-flight run behavior unless an operator explicitly migrates it.

If adopting Temporal:

- Use replay tests before deployment.
- Keep workflow code deterministic.
- Prefer activity changes for non-deterministic or side-effecting logic.
- Consider pinned workflow behavior for expensive long-running GPU workflows.
- Keep old workers available until in-flight pinned workflows finish or are migrated.

## Pattern 15: Testing Discipline

Temporal's development docs are valuable even if this repo never runs Temporal.

Applicable practices:

- Prefer fail-fast assertions for setup and invariants.
- Avoid raw sleeps; use eventual assertions with explicit deadlines.
- Use deterministic test identifiers.
- Create reusable helpers for workflow-like tests.
- Keep end-to-end tests isolated.
- Mark expensive or live-provider tests explicitly.
- Capture traces or event timelines for failed tests.

Suggested pytest improvements:

- Add `tests/helpers/runvars.py` for deterministic run IDs, instance names, task IDs, and benchmark labels.
- Add `tests/helpers/activity_fakes.py` for provider, SSH, probe, benchmark, and alert activities.
- Add `tests/helpers/event_assertions.py` for event ordering and no-secret checks.
- Add `pytest.mark.live_provider`, `pytest.mark.spend`, `pytest.mark.benchmark`, and `pytest.mark.temporal`.
- Add event-history tests for deployment state transitions.
- Add crash/restart tests for persisted schedule recovery.
- Add destroy compensation tests where provider "not found" is success.
- Add benchmark restore tests for failure at each stage.

The current tests already cover important pieces:

- Guardrails in `tests/test_guardrails.py`.
- Provider hardening in `tests/test_do_provider_hardening.py`.
- Endpoint probe classifications in `tests/test_endpoint_probe.py`.
- Monitor transitions in `tests/test_monitor.py`.
- Handoff secrecy in `tests/test_handoff_manifest.py`.
- Profile rendering in `tests/test_remote_vllm_profiles.py`.
- Benchmark runner behavior in `tests/test_bench_runner.py`.

The next layer is testing whole deployment histories, not just individual helper behavior.

## Proposed Python Package Shape For A Prototype

If a Temporal prototype is added, keep it isolated:

```text
gpu_orchestration/
  __init__.py
  models.py
  events.py
  state_store.py
  policies.py
  activities.py
  workflows.py
  worker.py
  client.py
  testing.py
```

Responsibilities:

- `models.py`: typed workflow inputs, activity inputs, and run state.
- `events.py`: event names, schemas, redaction rules, append helper.
- `state_store.py`: JSONL or SQLite storage for non-Temporal mode.
- `policies.py`: retry, timeout, heartbeat, and safety policies.
- `activities.py`: wrappers around existing provider, `remote_vllm`, probe, handoff, monitor, and benchmark functions.
- `workflows.py`: Temporal workflow definitions if the SDK is installed.
- `worker.py`: optional Temporal worker entrypoint.
- `client.py`: commands to start/query/signal/update workflows.
- `testing.py`: fake workers and replay/event assertion helpers.

Existing modules should not be rewritten first. Wrap them as activities.

## Suggested Activity Boundary Refactor

Start with wrappers that are useful with or without Temporal:

```python
async def create_provider_instance_activity(input: CreateProviderInstanceInput) -> CreateProviderInstanceResult:
    ...

async def deploy_remote_vllm_activity(input: DeployRemoteVllmInput) -> DeployRemoteVllmResult:
    ...

async def probe_endpoint_activity(input: ProbeEndpointInput) -> ProbeEndpointResult:
    ...

async def destroy_instance_activity(input: DestroyInstanceInput) -> DestroyInstanceResult:
    ...
```

Each wrapper should:

- Accept one typed input object.
- Return one typed result object.
- Emit redacted events.
- Include the `run_id`.
- Include the `attempt`.
- Classify errors into stable categories.
- Avoid reading global mutable state except through explicit settings.
- Be independently testable with fakes.

This gives us Temporal readiness without forcing Temporal into every path.

## How Temporal Would Change The Current `run_skill()` Flow

Today, `run_skill()` does orchestration directly. A Temporal-inspired flow would keep `run_skill()` as an API entrypoint but move orchestration into a run manager:

```text
run_skill()
  build request
  if temporal enabled:
    start GpuDeploymentWorkflow
    wait until handoff, fallback, or rejection
    return projected result
  else:
    start local DeploymentRunManager
    execute same activity sequence with local ledger
    return projected result
```

This lets the existing caller contract survive:

- MCP callers still get `GpuProvisionResult`.
- Interactive mode still works.
- Existing tests can be migrated gradually.
- Temporal is opt-in behind a feature flag.

## How Temporal Would Change Monitoring

Current monitoring is provider-polling plus state in `.do_state.json` and Telegram events.

Temporal-inspired monitoring would add:

- One durable run state per deployment.
- A monitor workflow or schedule per provider/environment.
- A per-instance readiness workflow while an endpoint is warming.
- Queryable state for readiness, stale status, runtime threshold, and destroy attempts.
- Alert sending as an activity so it can be retried or suppressed consistently.

The key improvement is that alerts become projections of state transitions, not independent facts. That makes deduplication, audit, and recovery easier.

## How Temporal Would Change The Handoff Contract

`handoff.py` already does the right thing by building a non-secret harness manifest from instance and profile metadata.

Temporal-style changes:

- Handoff is created only after a recorded readiness state or fallback state.
- Handoff includes `run_id`.
- Handoff includes `readiness_event_id`.
- Handoff includes `profile_hash`.
- Handoff can be queried later from the run.
- Handoff is invalidated or marked stale if health regresses.

Do not include bearer tokens in workflow history, search attributes, or handoff manifests.

## How Temporal Would Change The Benchmark Harness

The benchmark harness is currently artifact-oriented. That is good. Temporal would add durable stage state:

- `codex_smoke_started`
- `codex_smoke_passed`
- `codex_full_started`
- `codex_full_completed`
- `claude_smoke_started`
- `qwen_smoke_started`
- `opencode_repair_attempted`
- `interactive_restore_completed`

Artifacts remain on disk. The workflow stores paths and checksums, not large payloads.

Recommended benchmark run metadata:

- `run_id`
- `benchmark_run_label`
- `suite_id`
- `smoke_count`
- `harness_sequence`
- `optional_harness`
- `model_id`
- `base_url_redacted`
- `remote_host_ref`
- `service_backup_path`
- `results_paths`
- `restore_state`

## Observability Lessons

Temporal's server repo includes substantial telemetry, tracing, metrics, and test tracing guidance. The tracing docs emphasize service-specific tracer providers, gRPC instrumentation, shared attribute naming, and context propagation across durable handoffs.

For this repo:

- Emit OpenTelemetry spans for deployment runs if practical.
- Use consistent attributes: `run_id`, `provider`, `instance_id`, `hardware_slug`, `model_profile_id`, `deployment_profile_id`, `activity`, `attempt`, `readiness_state`, and `error_class`.
- Use span links or event references for benchmark subtasks when a single parent span is impractical.
- Keep logs as a human interface, not the only state source.
- Turn Telegram alerts into a reporter over structured events.

## Security And Secret Boundaries

Temporal histories and visibility can become long-lived operational records. The same caution applies to a local event ledger.

Rules:

- Secrets are passed by reference or through environment/config, not serialized into events.
- Handoff manifests list expected environment variable names, not values.
- Provider error payloads are redacted before persistence.
- SSH command logs are filtered for tokens.
- Search attributes contain identifiers, not credentials.
- Benchmark artifacts are checked for accidental secret output before publishing.

Add tests that inject fake secrets and assert they do not appear in:

- Event ledger files.
- State projections.
- Handoff manifests.
- Monitor alerts.
- Benchmark ledgers.
- Logs captured under tests.

## Proposed Work Items

| ID | Title | Touch points | Outcome |
|---|---|---|---|
| TMP-01 | Deployment run event schema | `gpu_orchestration/events.py`, tests | Every deployment and benchmark stage can emit redacted events. |
| TMP-02 | Local run ledger | `gpu_orchestration/state_store.py`, `.runs/` or SQLite | Runs survive process restart and can be queried. |
| TMP-03 | Activity wrappers | `gpu_orchestration/activities.py`, `skill.py`, `remote_vllm.py`, providers | Provider, SSH, probe, benchmark, and destroy work has explicit inputs/results. |
| TMP-04 | Activity policy registry | `gpu_orchestration/policies.py` | Retry, timeout, heartbeat, and idempotency rules are documented in code. |
| TMP-05 | Deployment state projection | `gpu_orchestration/models.py`, CLI | Operators can inspect state without reading logs. |
| TMP-06 | Durable schedule projection | `scheduler.py`, state store | TTL and readiness timing intent survives restart. |
| TMP-07 | Operator commands | `main.py` or new CLI module | Status/query/signal/update vocabulary exists before Temporal. |
| TMP-08 | Benchmark matrix state machine | `.bench/run_do_h200_extreme100_matrix.py`, orchestration package | H200 matrix stages become restartable and auditable. |
| TMP-09 | Temporal Python SDK prototype | optional dependency, `gpu_orchestration/workflows.py`, `worker.py`, `client.py` | One workflow runs against local Temporal dev server. |
| TMP-10 | Replay and event-history tests | tests | Workflow behavior is protected against unsafe changes. |
| TMP-11 | Search/visibility projection | CLI, state store | Runs can be filtered by provider, readiness, profile, and benchmark state. |
| TMP-12 | Secret redaction tests | tests | Durable history cannot leak credentials. |

## Recommended Roadmap

### Phase 0: Keep Current Runtime Stable

Do not replace `run_skill()` or the benchmark script yet. Add no mandatory service dependency. Keep current tests green.

Exit criteria:

- Existing provisioning API behavior remains unchanged.
- Docs state that Temporal analysis is design guidance, not current runtime truth.

### Phase 1: Add Temporal-Inspired Local Durability

Add event schema, run ledger, state projection, and activity policy registry.

Exit criteria:

- A fake deployment can produce an ordered event history.
- A projected run state can be reconstructed from events.
- Secret redaction tests pass.
- TTL intent is persisted with original deadline.

### Phase 2: Refactor Side Effects Behind Activity Wrappers

Wrap provider create/list/destroy, remote `vLLM`, probe, handoff, monitor alert, and benchmark subprocess work.

Exit criteria:

- Activity wrappers have typed inputs/results.
- Wrappers are tested with fakes.
- Existing `run_skill()` still returns the same public result.
- Errors classify into stable categories.

### Phase 3: Make Benchmark Matrix Restartable

Apply the event ledger to `.bench/run_do_h200_extreme100_matrix.py`.

Exit criteria:

- A dry run records all intended stages.
- A failure after benchmark service activation records restore pending.
- Restore can be retried from recorded backup data.
- Full benchmark cannot rerun accidentally without an operator command.

### Phase 4: Temporal Prototype

Add optional Temporal Python SDK prototype for one workflow.

Exit criteria:

- Local Temporal dev server can run the prototype.
- Worker can be started explicitly.
- Workflow can be queried and signaled.
- Cancellation and restore behavior are tested.
- No provider credentials are recorded in workflow history.

### Phase 5: Production Decision

Decide whether Temporal should become an optional or default orchestration backend.

Adopt only if:

- GPU deployment work is expected to run beyond one local process.
- Operators need durable queries, signals, schedules, and visibility.
- The team is comfortable operating Temporal or using Temporal Cloud.
- Replay and worker deployment practices are understood.

## Testing Strategy

Fast local tests:

```bash
pytest tests/test_guardrails.py tests/test_endpoint_probe.py tests/test_handoff_manifest.py
```

Activity wrapper tests:

```bash
pytest tests/test_orchestration_activities.py
```

Event ledger tests:

```bash
pytest tests/test_orchestration_events.py tests/test_orchestration_state_store.py
```

Benchmark state machine tests:

```bash
pytest tests/test_bench_runner.py tests/test_benchmark_workflow.py
```

Temporal prototype tests:

```bash
pytest -m temporal
```

Live provider tests:

```bash
GPU_SKILL_ALLOW_SPEND_TESTS=true pytest -m live_provider
```

Manual benchmark run:

```bash
python .bench/run_do_h200_extreme100_matrix.py --dry-run
```

The Temporal prototype should not require live provider credentials for its unit tests. Use fake activities and a local test server where possible.

## Evaluation Matrix

| Criterion | Temporal-inspired local ledger | Temporal Python SDK |
|---|---|---|
| Crash recovery | Good if implemented carefully | Strong built-in model |
| Retry policy | Custom code | Built-in workflow/activity semantics |
| Schedules | Custom persisted schedule table | Built-in schedules and timers |
| Operator query | Custom CLI/API | Built-in workflow queries plus visibility |
| Signals/updates | Custom command handling | Built-in workflow messaging |
| Local dev simplicity | High | Medium |
| Runtime dependency | Low | Higher |
| Operational maturity | Depends on implementation | High if Temporal is operated correctly |
| Cost of adoption | Low to medium | Medium to high |
| Best immediate use | All deployment paths | H200 benchmark prototype |

## Main Risks

Temporal-specific risks:

- Workflow determinism constraints are real and must be learned.
- Workflow histories can grow if high-volume progress is stored incorrectly.
- Activity idempotency mistakes can duplicate expensive side effects.
- Search attributes and histories can leak sensitive data if not redacted.
- Running Temporal adds operational dependencies.
- Worker versioning and safe deployment introduce new release discipline.

Local-ledger risks:

- A custom durable runner can become an incomplete reimplementation of Temporal.
- Without careful locking, local JSONL or SQLite state can corrupt under concurrency.
- Without a clear state machine, event logs can become just another set of logs.
- Without operator commands, durable state may not improve recovery.

Mitigation:

- Start small.
- Make side effects idempotent.
- Keep workflow state compact.
- Test failure and restart paths.
- Prototype Temporal only after the state model is explicit.

## Bottom Line

Temporal's core model fits `gpu-skill-builder` very well. GPU deployment, remote `vLLM` launch, endpoint readiness, benchmark orchestration, TTL cleanup, fallback activation, and restore logic are all durable workflow problems.

The best next move is not a full platform migration. The best next move is to make deployment runs explicit:

- Give every run an ID.
- Record every meaningful transition.
- Wrap side effects as activities.
- Define retry, timeout, heartbeat, and idempotency policy.
- Make state queryable.
- Make cancellation, destroy, TTL extension, fallback, benchmark start, and restore first-class commands.

After that, Temporal becomes a credible optional backend rather than a speculative dependency.

## Sources

Temporal upstream repository:

- `https://github.com/temporalio/temporal`
- `https://github.com/temporalio/temporal/tree/12e860ca7402ddc647a8735a8ed3524c181077df`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/README.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/architecture/README.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/architecture/history-service.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/architecture/matching-service.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/architecture/workflow-lifecycle.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/development/testing.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/development/tracing.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/docs/worker-versioning.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/AGENTS.md`
- `https://github.com/temporalio/temporal/blob/12e860ca7402ddc647a8735a8ed3524c181077df/CONTRIBUTING.md`

Temporal official docs checked during analysis:

- `https://docs.temporal.io/`
- `https://docs.temporal.io/workflows`
- `https://docs.temporal.io/activities`
- `https://docs.temporal.io/workers`
- `https://docs.temporal.io/task-queue`
- `https://docs.temporal.io/schedule`
- `https://docs.temporal.io/visibility`
- `https://docs.temporal.io/search-attribute`
- `https://docs.temporal.io/worker-versioning`
- `https://docs.temporal.io/develop/python`
- `https://docs.temporal.io/develop/safe-deployments`
- `https://docs.temporal.io/encyclopedia/workflow-message-passing`
- `https://docs.temporal.io/encyclopedia/detecting-activity-failures`

Local repo files considered:

- `skill.py`
- `scheduler.py`
- `monitor.py`
- `remote_vllm.py`
- `endpoint_probe.py`
- `handoff.py`
- `profile_registry.py`
- `profiles/`
- `.bench/BENCHMARKS.md`
- `.bench/run_do_h200_extreme100_matrix.py`
- `tests/`
- `docs/README.md`
- `docs/research/phoenix-framework-application/PHOENIX_APPLICABILITY_REPORT.md`
