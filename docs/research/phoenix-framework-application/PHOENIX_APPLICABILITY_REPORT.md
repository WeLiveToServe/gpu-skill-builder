# Phoenix Framework Applicability Report For gpu-skill-builder

Analysis date: 2026-04-23

Upstream analyzed:

- Repository: `phoenixframework/phoenix`
- Tagline: "Peace of mind from prototype to production"
- Local analysis checkout: `6ceade4288188651c189ce2ef15b0197e5507df7`
- Phoenix version observed in `mix.exs`: `1.8.5`
- Repo shape observed in the checkout: `469` files, `74` `lib/` files, `120` test/integration/client test files, `44` guide files, and `83` installer template files

Local project analyzed:

- Repository: `gpu-skill-builder`
- Current purpose: provision GPU inference endpoints, load compatible open-source models, and emit OpenAI-compatible handoff metadata for coding harnesses
- Current runtime truth: root `README.md` plus committed profile manifests under `profiles/`
- Current planning truth: `docs/research/production-grade-gpu-deployment/`

## Executive Summary

Phoenix is not primarily useful to `gpu-skill-builder` as a web framework dependency. The strongest lesson is not "rewrite this in Elixir" or "wrap everything in Phoenix." The strongest lesson is that Phoenix earns production confidence by combining a small number of durable patterns:

- Generated, reviewable scaffolds that create implementation and tests together.
- Strong boundaries between core domain modules, web/runtime edges, and deployment artifacts.
- Test helpers that turn complex subsystems into repeatable case templates.
- First-class telemetry events rather than ad hoc logging.
- Real-time PubSub and socket abstractions where live operational state matters.
- Release, runtime configuration, and secret-handling conventions that make deployment reproducible.
- Documentation that teaches by short build-and-verify cycles.

For `gpu-skill-builder`, the best application is a "Phoenix-inspired operating model" for GPU endpoint orchestration:

- Keep the Python provisioning core.
- Add generator-like commands for providers, deployment profiles, readiness probes, and harness handoffs.
- Add pytest case templates that mirror Phoenix's `ConnCase`, `ChannelCase`, and generated fixtures.
- Add evented telemetry for provision, remote launch, probe, monitor, fallback, and destroy phases.
- Optionally add a separate Phoenix/LiveView control plane only when a real-time dashboard or multi-user operations UI is needed.
- Avoid a full Phoenix migration until the project needs durable multi-user web operations enough to justify Elixir/BEAM adoption.

The immediate payoff is a stronger test architecture. Phoenix's generated tests and `CaseTemplate` approach map cleanly onto this repo's current tests for providers, probes, profile resolution, monitor state transitions, and benchmark orchestration. The most valuable next step is to standardize those tests into reusable pytest fixtures and command-generated acceptance suites.

## What Phoenix Actually Is

Phoenix describes itself as a high-productivity, high-performance Elixir web framework with familiar MVC concepts plus real-time channels, precompiled templates, and production deployment guidance. The official overview also frames the documentation around introduction, core concepts, data modelling, auth, real-time components, testing, deployment, and how-to guides.

That matters because Phoenix is not one thing. It is a production-oriented system composed of:

- A request lifecycle: Endpoint, Router, Controllers, Plugs, verified routes, templates/components.
- A real-time layer: Sockets, Channels, PubSub, Presence, reconnect behavior, long-poll fallback.
- A generator layer: `phx.new`, `phx.gen.auth`, `phx.gen.context`, `phx.gen.html`, `phx.gen.json`, `phx.gen.live`, `phx.gen.channel`, `phx.gen.release`.
- A test layer: generated tests, reusable test cases, integration tests, client JS tests, channel assertions.
- A telemetry layer: `:telemetry` events, metric definitions, reporters, route/request/controller/channel instrumentation.
- A deployment layer: runtime env config, secret handling, asset/release build steps, releases, Docker guidance, clustering guidance.

The upstream repo structure supports that reading. The checkout contains production code under `lib/`, a source installer under `installer/`, generated templates under `installer/templates/`, integration tests, JS client tests, extensive guides, and usage rules for generated projects.

## Current gpu-skill-builder Fit

`gpu-skill-builder` already has several Phoenix-like ingredients:

- A stable domain goal in `README.md`: provision GPUs, load compatible models, and wire endpoints into harnesses.
- Provider boundaries under `providers/`.
- Typed contracts in `models.py` and `profile_registry.py`.
- Runtime manifests under `profiles/`.
- A readiness/probe boundary in `endpoint_probe.py`.
- A monitor and scheduler split in `monitor.py`, `monitor_alerts.py`, and `scheduler.py`.
- Remote service rendering in `remote_vllm.py`.
- Harness handoff contracts in `handoff.py`.
- Tests covering guardrails, provider hardening, profiles, probes, monitor state transitions, handoffs, and benchmark runner behavior.

The project is already moving toward a durable deployment system. The gaps are less about missing features and more about production shape:

- Test patterns are present, but not yet organized as explicit reusable "case templates."
- Runtime events exist as logs and Telegram messages, but not as a coherent telemetry schema.
- Profile manifests exist, but there is no generator/scaffold workflow that creates profile, docs, and tests together.
- The MCP server exists, but there is not yet a first-class API/control-plane service with route introspection, auth, metrics, and live state.
- The docs are strong, but there is not yet a Phoenix-style "small step, run command, verify output" path for each supported provider/profile.

Phoenix's best contribution is to help the project mature these existing instincts into a repeatable operating model.

## Recommendation: Do Not Rewrite The Core In Phoenix

The Python core should stay Python for now.

Reasons:

- The repo is already deeply integrated with Python packages: `pydantic`, `httpx`, `tenacity`, `apscheduler`, provider SDKs, Modal, Streamlit, MCP, pytest, and local benchmark scripts.
- The runtime problem is GPU provisioning and OpenAI-compatible endpoint validation, not HTML rendering.
- The riskiest parts are cloud APIs, SSH remote launch, `vLLM` flags, endpoint readiness, spend guardrails, and benchmark reliability. Rewriting those in Elixir would increase risk before it reduces risk.
- The current test suite already covers the Python contracts that matter.

Phoenix becomes attractive later if the project needs a long-running, multi-user control plane with:

- Real-time dashboard state for endpoints, runs, probes, and spend.
- Live operator workflows for launch, rollback, destroy, and handoff.
- Durable event streams across multiple agents and machines.
- Presence-style visibility into who or what is using each GPU endpoint.
- WebSocket/SSE-style state propagation without hand-rolling it in Python.

That should be treated as a separate app that orchestrates the Python core, not as a replacement for it.

## Phoenix Pattern 1: Generated Contracts Plus Generated Tests

Phoenix's generators are a major production-confidence tool. They do not only create code. They create a coherent slice:

- Domain/context module.
- Schema or interface artifact.
- Web/API layer where applicable.
- Tests.
- Fixtures.
- Instructions for what to add next.

This maps extremely well onto `gpu-skill-builder` profiles.

### Application To This Repo

Add a generator-like command for new runtime targets:

```bash
python scripts/gen_profile.py \
  --provider digitalocean \
  --hardware gpu-h200x1-141gb \
  --model openai/gpt-oss-120b \
  --profile interactive-stable
```

The command should generate or update:

- `profiles/models/<model-id>.json`
- `profiles/deployments/<provider-model-hardware-profile>.json`
- `profiles/harnesses/<harness>.json` only when a new harness is introduced
- `tests/test_profile_registry.py` cases for selection and validation
- `tests/test_remote_vllm_profiles.py` cases for rendered `vLLM` flags
- A short docs snippet or checklist entry

The generator should be conservative and explicit. If it cannot know a value safely, it should leave a placeholder that fails validation with a useful message. That is more Phoenix-like than silently guessing.

### Why It Helps

Right now, profile changes can be correct but incomplete. A Phoenix-style generator would make "complete" mean:

- The profile validates.
- The profile resolves.
- The remote service rendering has expected flags.
- The readiness policy is explicit.
- The docs mention how to use it.
- The generated test fails if any future refactor breaks it.

### Concrete Work Item

`PHX-01 Profile Scaffold Generator`

Deliverables:

- `scripts/gen_profile.py`
- generated pytest fixtures for model/deployment/harness profile coverage
- docs explaining the scaffold workflow
- refusal to generate unsafe defaults for large MoE targets without an explicit `--experimental` flag

Acceptance:

- A new profile cannot be added without a matching validation and render test.
- Existing profile tests can be regenerated without overwriting unrelated hand edits.

## Phoenix Pattern 2: Case Templates For Testing Complex Edges

Phoenix generated apps use test support modules such as `ConnCase`, `DataCase`, and `ChannelCase`. These provide setup, imports, shared fixtures, and helper behavior so individual tests remain focused.

`gpu-skill-builder` already has repeated testing patterns:

- Fake providers.
- Fake `httpx.AsyncClient` responses.
- Fake DigitalOcean API state.
- Fake endpoint probe responses.
- Fake monitor state and Telegram events.
- Fake subprocess/SSH behavior for `remote_vllm`.
- Repeated instance and hardware builders.

Those are good candidates for pytest equivalents of Phoenix cases.

### Application To This Repo

Add test support modules:

- `tests/support/provider_case.py`
- `tests/support/endpoint_case.py`
- `tests/support/monitor_case.py`
- `tests/support/remote_vllm_case.py`
- `tests/support/profile_case.py`
- `tests/support/handoff_case.py`

These do not need a framework. They can be plain helper modules and pytest fixtures. The key is that each test file should say, in effect, "this is a provider contract test" or "this is a monitor state-machine test" without rebuilding all fake infrastructure locally.

### Suggested Case Responsibilities

`ProviderCase`

- Build valid `GpuProvisionRequest` objects.
- Build fake `HardwareTier` lists.
- Build active/warming/terminal `InstanceInfo` objects.
- Patch provider maps safely.
- Assert idempotency, concurrency, fallback, and destroy semantics.

`EndpointCase`

- Build fake `/health`, `/v1/models`, and `/v1/chat/completions` response sets.
- Assert `ProbeClassification` values.
- Support wrong-model, warming, provider-error, unreachable, and Modal scaled-to-zero cases.

`MonitorCase`

- Create isolated monitor state stores.
- Capture emitted `MonitorEvent` payloads.
- Advance fake clocks.
- Assert readiness transition, regression, stale threshold, provider-list dedupe, and auto-stop behavior.

`RemoteVllmCase`

- Render service units from deployment profiles.
- Assert shell args without SSH.
- Fake subprocess output for `MODEL_SWAP_OK`.
- Assert dangerous model IDs and tokens are rejected.

`ProfileCase`

- Load temporary profile directories.
- Assert invalid references fail.
- Assert generated fallback profile behavior.
- Assert harness model-name resolution.

### Concrete Work Item

`PHX-02 Pytest Case Template Refactor`

Deliverables:

- `tests/support/` package
- migration of duplicated fixtures out of individual test files
- tags/markers for live-provider and slow tests

Acceptance:

- Existing tests remain green.
- Adding a provider or profile test requires fewer than 10 lines of setup in the test body.
- Live cloud tests are impossible to run accidentally in default local `pytest`.

## Phoenix Pattern 3: Test Tags, Randomization, Partitioning, And Live Gates

Phoenix's testing guide emphasizes running by file/line, using tags, excluding slow or special tests by default, randomized test order, and CI partitioning.

The direct pytest equivalents for `gpu-skill-builder` are:

- `@pytest.mark.live_provider`
- `@pytest.mark.requires_do`
- `@pytest.mark.requires_modal`
- `@pytest.mark.requires_hf`
- `@pytest.mark.requires_gpu`
- `@pytest.mark.slow`
- `@pytest.mark.benchmark`
- `@pytest.mark.spend_risk`
- `pytest-randomly` or equivalent randomization if the project wants to catch order coupling
- CI job partitioning by unit, contract, docs, benchmark dry-run, and live-gated suites

### Application To This Repo

The repo's root README says automated tests are green and the DigitalOcean H200 benchmark orchestrator has only been dry-run locally. That distinction should become test metadata, not only prose.

Default local `pytest` should run:

- Pure model validation tests.
- Pure profile resolution tests.
- Pure probe classification tests with fake HTTP.
- Provider contract tests with fake clients.
- Remote `vLLM` render tests without SSH.
- Monitor state-machine tests with fake providers and fake event sends.
- Benchmark dry-run and selection tests.

Explicit opt-in should be required for:

- Real cloud provider API calls.
- Real droplet creation.
- Real Modal deployment.
- Real Hugging Face endpoint changes.
- Live `vLLM` smoke probes against rented GPUs.
- Full H200 benchmark matrix.

### Concrete Work Item

`PHX-03 Test Marker And CI Partition Policy`

Deliverables:

- pytest markers in `pytest.ini`
- `tests/README.md` explaining local, contract, slow, live, and benchmark suites
- CI commands for each suite
- environment guard that refuses spend-risk tests unless `GPU_SKILL_ALLOW_SPEND_TESTS=true`

Acceptance:

- `pytest` cannot spend money.
- `pytest -m live_provider` cannot run unless explicit credentials and allow flags are present.
- CI can run fast tests independently from live smoke gates.

## Phoenix Pattern 4: Telemetry As A Runtime Contract

Phoenix uses `:telemetry` events as a first-class instrumentation substrate. The important idea is that events are named, measured, tagged, documented, and consumed by reporters.

`gpu-skill-builder` currently has logs and deterministic Telegram events. Those are useful, but they are downstream effects. The project would benefit from a central event schema that can feed logs, Telegram, Prometheus, OpenTelemetry, JSONL files, and future dashboards.

### Proposed Event Namespace

Use a Python event naming convention inspired by Phoenix:

- `gpu_skill.provision.start`
- `gpu_skill.provision.stop`
- `gpu_skill.provision.exception`
- `gpu_skill.provider.request.start`
- `gpu_skill.provider.request.stop`
- `gpu_skill.provider.request.exception`
- `gpu_skill.remote_vllm.deploy.start`
- `gpu_skill.remote_vllm.deploy.stop`
- `gpu_skill.remote_vllm.deploy.exception`
- `gpu_skill.endpoint_probe.start`
- `gpu_skill.endpoint_probe.stop`
- `gpu_skill.endpoint_probe.exception`
- `gpu_skill.monitor.instance_detected`
- `gpu_skill.monitor.readiness_passed`
- `gpu_skill.monitor.readiness_timeout`
- `gpu_skill.monitor.health_regressed`
- `gpu_skill.monitor.stale_endpoint`
- `gpu_skill.monitor.auto_stop_attempted`
- `gpu_skill.fallback.activated`
- `gpu_skill.instance.destroy.start`
- `gpu_skill.instance.destroy.stop`
- `gpu_skill.instance.destroy.exception`
- `gpu_skill.handoff.created`
- `gpu_skill.benchmark.run.start`
- `gpu_skill.benchmark.run.stop`
- `gpu_skill.benchmark.run.exception`

Each event should carry:

- `provider`
- `instance_id`
- `instance_name`
- `hardware_slug`
- `model_profile_id`
- `deployment_profile_id`
- `harness_profile_id`
- `runtime_kind`
- `endpoint_class`
- `readiness_state`
- `probe_classification`
- `duration_ms`
- `attempt`
- `error_class`
- `error_detail_sanitized`
- `spend_risk`

### Application To This Repo

Implement a lightweight `telemetry.py` module first:

- `emit(event_name, measurements=None, metadata=None)`
- `span(event_prefix, metadata=None)` context manager/decorator
- reporters for logging and JSONL
- optional Prometheus/OpenTelemetry reporters later

Wire it into:

- `skill.run_skill`
- `ensure_active_endpoint`
- provider methods
- `remote_vllm.deploy_vllm_remote`
- `endpoint_probe.probe_openai_compatible_endpoint`
- `monitor.run_monitor_once`
- scheduler destroy/watchdog paths
- benchmark runner start/stop

The project can then keep Telegram as one reporter, not as the only event model.

### Concrete Work Item

`PHX-04 Telemetry Event Schema`

Deliverables:

- `telemetry.py`
- documented event names and metadata
- JSONL reporter
- tests asserting event emission on success and failure paths

Acceptance:

- A failed launch can be reconstructed from event spans without scraping arbitrary logs.
- Telegram notifications are derived from structured events.
- Future Prometheus/OpenTelemetry adoption does not require changing business logic.

## Phoenix Pattern 5: Real-Time Channels, PubSub, And Presence For Operations

Phoenix Channels are designed for soft real-time communication over long-lived connections. They rely on topics and PubSub. Phoenix Presence tracks process/user presence on topics and broadcasts joins/leaves/diffs.

This maps naturally to GPU endpoint operations:

- Endpoint lifecycle events are topic-based.
- Benchmark runs are stream-like.
- Agents/harnesses attach to an endpoint and later detach.
- Operators care who or what is actively using an expensive GPU.
- Readiness and stale endpoint transitions should update a dashboard immediately.

### Possible Topics

If the project later adds a Phoenix control plane:

- `instances:<provider>:<instance_id>`
- `providers:<provider>`
- `profiles:<deployment_profile_id>`
- `benchmarks:<run_id>`
- `harnesses:<harness_name>`
- `spend:<provider>`
- `alerts`

### Possible Presence Metadata

For each attached agent/harness:

- `client_id`
- `harness_name`
- `model_name`
- `base_url_hash`
- `connected_at`
- `last_request_at`
- `session_label`
- `expected_ttl`
- `readiness_state_at_attach`

### Why This Matters

The current repo can provision expensive GPUs for agent workflows. The operational question is not only "is the endpoint healthy?" It is also:

- Is anyone still using it?
- Which harness is connected?
- Is the current endpoint safe to destroy?
- Did a benchmark finish, hang, or lose its tunnel?
- Did a fallback activate because the primary regressed?

Phoenix-style PubSub/Presence would make those questions visible without polling every local process manually.

### Recommendation

Do not build this immediately unless the project needs a multi-user dashboard. But design the Python telemetry schema so a future Phoenix control plane can subscribe to or ingest the same events.

### Concrete Work Item

`PHX-05 Event Stream Adapter`

Deliverables:

- JSONL or HTTP event sink from Python core
- stable event schema from `PHX-04`
- proof-of-concept WebSocket/SSE dashboard consumer, either Python-native or Phoenix/LiveView

Acceptance:

- The event stream can replay a launch lifecycle.
- A dashboard can show instance state without calling cloud providers directly.

## Phoenix Pattern 6: Supervision And Restart Discipline

Phoenix sits on the BEAM/OTP model, where processes are supervised and restart behavior is explicit. `gpu-skill-builder` is Python, so it does not inherit OTP, but it can adopt the discipline:

- Every long-running process has a parent responsibility.
- Restart and cancellation behavior is explicit.
- State needed after restart is persisted.
- Runtime actions are idempotent.
- Failure modes become state transitions, not mystery crashes.

The repo already has parts of this:

- `scheduler.py` handles TTL, uptime reporting, stuck-pending watchdog, fleet monitoring, and readiness watches.
- `monitor.py` persists monitor state under `.do_state.json`.
- `skill.py` enforces cost, idempotency, concurrency, and fallback.
- `remote_vllm.py` writes a `systemd` unit and restarts `vllm.service`.

### Application To This Repo

Tighten the supervision model in docs and code:

- Define `gpu_monitor_daemon.py` as the local supervisor for monitor jobs.
- Define remote `systemd` as the supervisor for `vLLM`.
- Define provider APIs as infrastructure state sources, not trusted readiness sources.
- Define `.do_state.json` as a recovery cache, not an authoritative source.
- Add a startup reconciliation path for readiness watches, not only TTL.
- Add a process lifecycle table to docs.

### Concrete Work Item

`PHX-06 Process Supervision Map`

Deliverables:

- `docs/operations/PROCESS_SUPERVISION.md`
- diagram/table of local process, remote service, owner, state source, restart policy, and failure mode
- tests for scheduler reconciliation semantics where feasible

Acceptance:

- A maintainer can tell which process owns each lifecycle action.
- Restarting the local monitor does not orphan readiness, TTL, or stale endpoint handling.

## Phoenix Pattern 7: Runtime Configuration And Secret Boundaries

Phoenix deployment docs strongly emphasize runtime environment configuration and secret handling. The important transferable rule is simple: build artifacts should be reusable; secrets and environment-specific settings should be supplied at runtime.

`gpu-skill-builder` already follows much of this:

- `.env` is local.
- Provider-scoped env vars are documented.
- Handoff manifests are non-secret.
- The README warns not to overload `OPENAI_API_KEY` for OpenRouter.

### Application To This Repo

Add a more formal runtime config boundary:

- `config.py` remains the only place that reads process/local/shared env.
- Providers receive settings, not raw env reads scattered through provider code.
- Remote service templates explicitly separate secret env lines from rendered service args.
- Handoff manifests include expected env key names but never values.
- Test helpers assert that secrets are never serialized into handoff manifests or telemetry events.

### Concrete Work Item

`PHX-07 Secret Boundary Tests`

Deliverables:

- tests that scan `HarnessHandoffManifest` and telemetry events for known fake secret values
- docs stating what can be logged, what can be persisted, and what must remain env-only
- optional runtime redaction helper used by all event/reporting paths

Acceptance:

- Fake secrets injected into settings never appear in handoff manifests, logs under test, or event metadata.

## Phoenix Pattern 8: Route And Contract Introspection

Phoenix has `mix phx.routes` and verified route concepts. The transferable idea is introspection: operators should be able to ask the system what it knows and what it will do.

For `gpu-skill-builder`, route introspection becomes contract introspection:

- Which providers are supported?
- Which hardware tiers are known?
- Which model profiles exist?
- Which deployment profiles are compatible with a model/provider/hardware tuple?
- Which harness env keys will be emitted?
- Which readiness gates will be enforced?
- Which `vLLM` args will be rendered?
- Which tests cover this profile?

### Application To This Repo

Add CLI commands:

```bash
python main.py profiles list
python main.py profiles explain digitalocean-gpt-oss-120b-h200x1
python main.py profiles render-vllm digitalocean-gpt-oss-120b-h200x1
python main.py providers list
python main.py handoff explain cli-harness-openai-compatible
```

If `main.py` should remain interactive-only, create `scripts/gpu_skill_inspect.py`.

### Concrete Work Item

`PHX-08 Contract Introspection CLI`

Deliverables:

- profile list/explain/render commands
- JSON output mode for agents
- tests for output stability

Acceptance:

- An agent can inspect the deployment contract before spending money.
- Rendered `vLLM` args can be reviewed without creating a droplet.

## Phoenix Pattern 9: Usage Rules For Agents

Phoenix's repo now includes `usage-rules/` files for generated projects. This is directly relevant because `gpu-skill-builder` is agent-callable and contains expensive operations.

### Application To This Repo

Create agent usage rules:

- `usage-rules/gpu-skill-builder.md`
- `usage-rules/providers.md`
- `usage-rules/profiles.md`
- `usage-rules/benchmarks.md`
- `usage-rules/secrets.md`

These rules should be short, prescriptive, and machine-readable enough for agents to follow.

Examples:

- Never launch spend-risk infrastructure unless the user requested a live launch or an allow flag is present.
- Always call `ensure_active_endpoint()` before handing an endpoint to a long-running harness.
- Never write provider credentials into harness repos.
- Prefer committed profiles over ad hoc runtime flags.
- Treat research docs as planning material unless the root README says a behavior is runtime truth.
- Do not modify `.bench/` live-run artifacts unless working on benchmark orchestration.

### Concrete Work Item

`PHX-09 Agent Usage Rules`

Deliverables:

- `usage-rules/` directory
- README link to usage rules
- tests or docs checks that key warnings remain present

Acceptance:

- A new agent can understand project safety constraints before calling `run_skill()`.

## Phoenix Pattern 10: CI Matrix And Pinned Dependencies

Phoenix's CI covers multiple Elixir/OTP combinations, JS client tests, installer tests, and integration tests with backing services. It also pins GitHub Actions by commit SHA in the observed workflow.

The direct lesson is not to copy the exact matrix. It is to split confidence by layer.

### Proposed gpu-skill-builder CI Matrix

Fast unit contract:

```bash
pytest tests/test_models.py tests/test_profile_registry.py tests/test_handoff_manifest.py
```

Provider/probe/monitor fake integration:

```bash
pytest tests/test_guardrails.py tests/test_do_provider_hardening.py tests/test_endpoint_probe.py tests/test_monitor.py
```

Remote render contract:

```bash
pytest tests/test_remote_vllm_profiles.py
```

Docs/runtime consistency:

```bash
pytest tests/test_readme_consistency.py
```

Benchmark dry-run:

```bash
pytest tests/test_bench_runner.py
```

Live gated smoke:

```bash
GPU_SKILL_ALLOW_SPEND_TESTS=true pytest -m live_provider
```

### Concrete Work Item

`PHX-10 CI Layering`

Deliverables:

- `.github/workflows/ci.yml`
- separate jobs for fast tests, provider fake integration, docs consistency, benchmark dry-run
- optional/manual live-provider workflow
- pinned GitHub Actions versions

Acceptance:

- Pull requests get fast feedback without spending money.
- Live smoke tests are explicit, labeled, and manually triggered.

## Optional Architecture: Phoenix As A Separate Control Plane

If the project later needs a real web operations surface, Phoenix could be a strong fit as a separate control-plane app.

### What Phoenix Would Own

- Operator UI with LiveView.
- Live instance list.
- Launch forms backed by profile introspection.
- Readiness timeline.
- Benchmark run timeline.
- Alerts and acknowledgements.
- Presence of attached agents/harnesses.
- RBAC for expensive operations.
- Event ingestion and replay.

### What Python Would Keep

- Provider SDK integrations.
- `run_skill()` and `ensure_active_endpoint()`.
- Profile registry.
- Remote `vLLM` rendering and SSH deploy.
- Endpoint probes.
- Benchmark runners.
- MCP server integration unless deliberately replaced.

### Integration Boundary

The safest boundary is API/event based:

- Phoenix sends "launch request" to Python service or command worker.
- Python emits telemetry events to Phoenix.
- Phoenix stores and displays state.
- Python remains the executor for provider calls and remote deploys.

### Why Not Now

The repo's biggest immediate risks are still:

- Live validation of the H200 benchmark matrix.
- Provider profile-driven live launches.
- Remote `vLLM` stability and rollback.
- Observability and test gates.

A Phoenix control plane should wait until those are boring enough that a UI will amplify reliability instead of masking unfinished contracts.

## Applied Roadmap

### Phase 0: Testing And Contract Hygiene

Priority: immediate

- Add pytest markers for live/spend/benchmark tests.
- Add `tests/support/` case-template helpers.
- Add profile scaffold generator design, even if the first version only validates and creates tests.
- Add contract introspection CLI for profiles and rendered `vLLM` args.

Outcome:

- Safer local development.
- Less duplicated test setup.
- More confidence that profiles and rendered commands stay aligned.

### Phase 1: Telemetry Foundation

Priority: next

- Add `telemetry.py`.
- Emit structured events from provision, probe, monitor, remote deploy, fallback, destroy, and benchmark paths.
- Convert Telegram monitor events into a reporter over structured events.
- Add JSONL output for postmortem replay.

Outcome:

- Launch failures become explainable.
- Metrics and dashboards can be added without reworking core logic.

### Phase 2: Deployment And Supervision Discipline

Priority: after telemetry

- Document process ownership and restart policy.
- Standardize remote service templates and rollback metadata.
- Persist enough local state to recover readiness watches and monitor transitions after restart.
- Add tests around scheduler reconciliation and no-secret serialization.

Outcome:

- Fewer orphaned expensive resources.
- Clearer operational recovery story.

### Phase 3: Event Stream And Dashboard Prototype

Priority: optional

- Prototype an event-stream consumer.
- Start Python-native if fastest.
- Consider Phoenix/LiveView if the UI needs real-time multi-user operations, PubSub, and Presence.

Outcome:

- Operators can see live endpoint state, not only logs.

### Phase 4: Phoenix Control Plane Decision

Priority: later

Adopt Phoenix only if at least two of these are true:

- Multiple people/agents need concurrent operational visibility.
- GPU endpoint usage needs presence tracking.
- Benchmark and readiness events need live replay.
- Expensive launch/destroy operations need RBAC and audit trails.
- A browser UI becomes a primary workflow, not a nice-to-have.

Outcome:

- Phoenix adoption becomes a response to real operational needs rather than a premature rewrite.

## Proposed Work Item Backlog

| ID | Title | Primary files | Why it matters |
|---|---|---|---|
| `PHX-01` | Profile scaffold generator | `scripts/gen_profile.py`, `profiles/`, `tests/test_profile_registry.py`, `tests/test_remote_vllm_profiles.py` | New runtime targets come with tests and docs by default. |
| `PHX-02` | Pytest case templates | `tests/support/`, existing tests | Reduces fixture duplication and makes subsystem tests easier to add. |
| `PHX-03` | Test marker and CI partition policy | `pytest.ini`, `tests/README.md`, CI config | Prevents accidental spend and separates fast confidence from live validation. |
| `PHX-04` | Telemetry event schema | `telemetry.py`, `skill.py`, `endpoint_probe.py`, `monitor.py`, `remote_vllm.py` | Makes launches, probes, and failures observable as structured events. |
| `PHX-05` | Event stream adapter | `telemetry.py`, optional service/dashboard | Prepares for future real-time dashboard without rewriting core logic. |
| `PHX-06` | Process supervision map | `docs/operations/PROCESS_SUPERVISION.md`, `scheduler.py` | Clarifies ownership, restart, and recovery semantics. |
| `PHX-07` | Secret boundary tests | `tests/`, `handoff.py`, `monitor_alerts.py`, future telemetry reporters | Prevents credentials from leaking into handoffs, logs, or events. |
| `PHX-08` | Contract introspection CLI | `main.py` or `scripts/gpu_skill_inspect.py` | Lets humans and agents inspect profiles before launching. |
| `PHX-09` | Agent usage rules | `usage-rules/`, `README.md` | Gives agents explicit safety and runtime-truth instructions. |
| `PHX-10` | CI layering | `.github/workflows/ci.yml` | Provides Phoenix-like confidence without live cloud side effects by default. |

## Testing Strategy In Detail

### Default Local Suite

Default `pytest` should be safe, fast, and offline:

- Profile validation and resolution.
- Pydantic model validation.
- Provider guardrails with fakes.
- Endpoint probe classifications with fake HTTP.
- Monitor state transitions with fake events.
- Remote `vLLM` render and safety tests.
- Handoff manifest tests.
- README consistency tests.
- Benchmark selection/dry-run tests.

This suite should never:

- Call a cloud provider.
- Create a droplet.
- Start a Modal app.
- Create a Hugging Face endpoint.
- SSH into a host.
- Run a full benchmark matrix.

### Contract Suite

Use contract tests to define provider behavior without live APIs:

- `list_hardware()` returns normalized `HardwareTier`.
- `create_instance()` returns valid `InstanceInfo`.
- `get_instance()` preserves saved runtime metadata.
- `destroy_instance()` clears runtime metadata on success.
- Provider failures classify into stable user-facing messages.

### Probe Suite

Probe tests should cover:

- Health OK, models OK, smoke OK -> `ready`.
- Missing expected model -> `wrong_model`.
- Smoke 500 -> `unhealthy` or `warming` depending on status.
- Request error during warming -> `warming`.
- Request error during running -> `unreachable`.
- HF endpoint without token -> `provider_error`.
- Modal stopped endpoint -> `scaled_to_zero`.

### Monitor Suite

Monitor tests should cover:

- First detection emits `instance_detected`.
- First ready emits `readiness_passed`.
- Non-ready beyond threshold emits `readiness_timeout`.
- Ready-to-non-ready emits `health_regressed`.
- Ready-then-stale emits `stale_endpoint`.
- Unhealthy threshold can auto-stop only when configured.
- Provider list failure dedupes repeated identical errors.
- Missing instance removes state and cancels readiness watch.

### Remote vLLM Suite

Remote tests should cover:

- Rendered service includes selected model, served name, port, TP/PP, max length, max sequences, batched tokens, chunked prefill, prefix caching, expert parallel, and EPLB as appropriate.
- Harness-eval profile disables prefix caching and lowers concurrency.
- Unsafe model IDs and tokens are rejected.
- SSH command path does not require live SSH in default tests.
- Failure output is summarized without leaking secrets.

### Live Gated Suite

Live tests should exist, but only with explicit opt-in:

- One provider smoke per provider.
- One remote `vLLM` deploy smoke for a small safe model.
- One H200 profile smoke only when intentionally budgeted.
- One full matrix benchmark only under a manual workflow or local explicit command.

The Phoenix lesson is that tests should be easy to run, easy to target, and hard to misuse.

## Design Notes For A Future Phoenix/LiveView Dashboard

If adopted later, a Phoenix app could provide:

- `/instances`: live fleet view.
- `/instances/:id`: endpoint timeline with readiness, probe, fallback, and destroy events.
- `/profiles`: manifest browser and rendered `vLLM` preview.
- `/benchmarks`: live benchmark matrix status.
- `/alerts`: monitor events and acknowledgements.
- `/harnesses`: attached harness sessions using Presence.
- `/launch`: form that calls Python only after profile validation and spend confirmation.

The Phoenix app should not run `vLLM`, SSH, or provider SDKs directly at first. It should call the Python core or consume its event stream. That keeps the current domain logic in one place.

## Risks And Tradeoffs

### Risk: Phoenix Control Plane Adds Stack Complexity

Adding Elixir/Phoenix means adding BEAM, Mix releases, deployment, ops knowledge, and a second language. That is only worth it if real-time multi-user operations become a core need.

Mitigation:

- Keep Phoenix optional and separate.
- Build telemetry/event contracts first.
- Prototype dashboard consumption before committing to a second production stack.

### Risk: Generators Can Hide Complexity

Bad generators create boilerplate nobody understands.

Mitigation:

- Generate minimal, reviewable files.
- Make generated tests explicit.
- Require unsafe/experimental flags for uncertain model/provider combos.

### Risk: More Test Markers Can Fragment Confidence

Too many markers can make it unclear what "green" means.

Mitigation:

- Define one default suite.
- Define one contract suite.
- Define one manual live suite.
- Document exactly what each suite proves.

### Risk: Telemetry Schema Becomes Too Large

Over-instrumentation can produce noisy data.

Mitigation:

- Start with provision, probe, monitor, remote deploy, fallback, and destroy events only.
- Keep metadata stable and sanitized.
- Add reporters after the schema has proven useful.

## Bottom Line

Phoenix is valuable to `gpu-skill-builder` as a production design reference more than as an immediate runtime dependency. The most useful ideas are:

- Generate contracts with tests.
- Make test setup reusable and subsystem-specific.
- Treat live/spend tests as opt-in.
- Emit structured telemetry events.
- Use real-time PubSub/Presence only when live operations justify it.
- Separate control-plane concerns from inference-plane execution.
- Make runtime config and secret boundaries explicit.
- Teach workflows through small build-and-verify docs.

The recommended next move is not "build a Phoenix app." It is:

1. Add Phoenix-style pytest case templates.
2. Add profile scaffold generation.
3. Add test markers and CI partitioning.
4. Add structured telemetry events.
5. Add contract introspection.
6. Revisit Phoenix/LiveView later as a separate dashboard/control-plane option.

That path applies Phoenix's "prototype to production" mindset while preserving the Python core that already works for this repo.

## Sources

- Phoenix GitHub repository: https://github.com/phoenixframework/phoenix
- Phoenix README and repo structure observed at commit `6ceade4288188651c189ce2ef15b0197e5507df7`: https://github.com/phoenixframework/phoenix/tree/6ceade4288188651c189ce2ef15b0197e5507df7
- Phoenix `mix.exs` version, dependency, docs, and module grouping metadata: https://github.com/phoenixframework/phoenix/blob/6ceade4288188651c189ce2ef15b0197e5507df7/mix.exs
- Phoenix CI workflow: https://github.com/phoenixframework/phoenix/blob/6ceade4288188651c189ce2ef15b0197e5507df7/.github/workflows/ci.yml
- Phoenix official overview: https://hexdocs.pm/phoenix/overview.html
- Phoenix testing guide: https://hexdocs.pm/phoenix/testing.html
- Phoenix channel testing guide: https://hexdocs.pm/phoenix/testing_channels.html
- Phoenix telemetry guide: https://hexdocs.pm/phoenix/telemetry.html
- Phoenix channels guide: https://hexdocs.pm/phoenix/channels.html
- Phoenix deployment guide: https://hexdocs.pm/phoenix/deployment.html
- Phoenix releases guide: https://hexdocs.pm/phoenix/releases.html
- Phoenix PubSub docs: https://hexdocs.pm/phoenix_pubsub/Phoenix.PubSub.html
- Phoenix Presence docs: https://hexdocs.pm/phoenix/Phoenix.Presence.html
