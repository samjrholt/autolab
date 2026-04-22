# Onboarding Wizard + Remote Execution — From Zero to First Record

**Status:** Design, pending implementation plan
**Date:** 2026-04-22
**Subsystem:** 2 + 3 of 6 (following the shell spec; precedes the mammos integration, equipment connectors, and Playwright coverage)

## Context

After a fresh `autolab serve`, a user should be able to go from empty lab to a real Record produced by a real Capability running on a real remote host (WSL or SSH or local) in one guided session, without writing YAML or editing config files. This spec covers the entire first-run experience *and* the execution primitives it relies on — they are two sides of the same user story.

Per CLAUDE.md: the Lab is a long-running FastAPI service, `ssh-agent` is the credential boundary we lean on, and provenance is framework-enforced (Operations never write records directly). This spec picks the concrete choices consistent with those invariants.

## Goals

1. First-time users reach a populated Ledger (one real Record, one real Capability run on a real Resource) in a guided conversational flow, without ever seeing YAML.
2. The mechanical layer (SSH execution, file staging, workdir management) is uniform across WSL, SSH, and local backends — one code path, not three.
3. Adding a new Capability (either pre-existing or hand-crafted from a local repo) happens inside the Assistant conversation, iteratively, with clarification — not by form-filling.
4. autolab never owns secrets. API keys live in env / config files the OS already protects; SSH creds live in `ssh-agent` / `~/.ssh/config`. No bespoke credential store.
5. The Resource, Capability, and RemoteWorkdir abstractions admit a SLURM backend as a one-file future addition (interface stub present now), and admit user-written `custom` backends via a small `ResourceBackend` protocol.

## Non-Goals

- Real `mammos-*` Capabilities — built with the tools defined here, but specified in subsystem 4.
- A curated starter Capability registry. We ship only `shell_command` (and a thin `local_python_script` preset). Everything else is user-authored via the Assistant.
- Multi-lab / lab federation. Single-lab only.
- Running SLURM end-to-end this week. Interface stub + Resources-page representation only.
- Physical instruments as a first-class backend — users wrap them via MCP or a custom backend (see subsystem 5).

## User-Facing Vocabulary

Lock these words; use them exactly in UI copy, docs, logs, and errors.

- **Capability** — "what the lab can do." A registered noun: `sintering`, `xrd`, `micromagnetics_hysteresis`, `shell_command`. Backed by one YAML file under `autolab/capabilities/<name>.yaml` + a small adapter. Scientist-shaped; reads naturally for both computational and experimental work. Replaces the term "Tool" throughout the product; the implementation dir is renamed from `autolab/tools/` to `autolab/capabilities/`.
- **Operation** — an *invocation* of a Capability at a moment in time. Appears as a pill in the Gantt while running. Has a record hash that is also the remote workdir name.
- **Record** — the ledger entry produced by an Operation. Append-only, hashed.
- **Resource** — a thing that can execute Operations. Has a backend type, a `tags` dict, and liveness.
- **Workflow** — a reusable DAG of Capability invocations.
- **Campaign** — a goal-driven run that chooses Workflows and Operations as it goes.

Collapsing "Tool" into "Capability" everywhere removes the class/instance confusion that plagued earlier iterations.

## Resource Model

Every Resource has:

```
name: str                   # user-facing alias, e.g. "wsl-dev"
backend: BackendType        # ssh_exec | local | mcp | slurm | custom
address: str                # backend-specific connection string (ssh alias, url, …)
tags: dict[str, Any]        # single flat dict, see below
```

**Tags — single flat dict.** No separate "capabilities" vs "labels" buckets. Keys the scheduler matches against (`gpu_count: 4`, `has_mammos: true`, `max_temp: 2000`) live next to human-readable metadata (`team: "sam"`, `note: "noisy psu"`). An Operation's `requires: dict` is satisfied when every key it names is present and equal (or for numeric values, ≥) in the Resource's tags. That is the entire matching rule — no DSL, no operators beyond equality / ≥ on numerics.

**Backend types.**

| Backend | Status this week | Semantics |
|---|---|---|
| `ssh_exec` | built-in, primary demo path | Single-slot lane; acquire-run-release over an `asyncssh` connection. |
| `local` | built-in | Same semantics as `ssh_exec` but runs as a subprocess on the autolab host. Useful for dev and the `local_python_script` starter. |
| `mcp` | built-in | Resource points at an MCP server URL; each tool the server exposes becomes a callable Capability on this Resource. The ingress surface for "any externally-defined capability," including wrappers around physical instruments. |
| `slurm` | interface stub | Multi-slot queue-backed lane. Method shape defined; implementation raises `NotImplementedError`. Resources page renders the state (queued / running / avg wait) but scheduler won't route to it this week. |
| `custom` | extension point | A Python class implementing `ResourceBackend` (~4 methods: `connect`, `submit`, `fetch`, `close`), registered via entry point. One worked example in docs. This is how users plug in SCPI rigs, vendor SDKs, or anything else we don't want to know about. |

**Liveness.** Every non-`local` Resource is pinged every ~10 s over its existing connection. Binary indicator: `● live` green / `● unreachable` red. No probing of installed software (no `which mammos-mumag`); autolab does not snoop remote hosts. Capabilities that need a feature assert it via `requires` — if the Resource's tags don't declare it, the scheduler won't route there.

**Resources page (matches subsystem 1's list-page pattern).** Columns: Name · Backend badge · Liveness · State · Tags (chips) · ⋯. State is backend-specific: `ssh_exec` / `local` show "idle" or "running `op-abc123…`"; `slurm` shows "2 queued · 1 running · ~4m wait"; `mcp` shows "N tools" with hover-to-expand.

## Credentials Story

autolab reads credentials from places the OS already protects. It never stores secrets of its own.

- **SSH.** `ssh-agent` and `~/.ssh/config` are the entire story. A Resource's `address` is an ssh alias (e.g. `wsl-dev`); the rest (keys, port, user) lives in the user's ssh config. Users without an existing setup are walked through `ssh-keygen` → `ssh-copy-id` (or the WSL `sshd`-enable steps) by the Assistant, live. The outcome is standard ssh config that works with every other ssh tool they own.
- **Anthropic API key.** Read from `ANTHROPIC_API_KEY` env var, falling back to `~/.autolab/env` (a simple KEY=VALUE file with `chmod 600` on POSIX, ACL-restricted on Windows). Setting this is the blocking gate before the Assistant becomes available. Manual-only paths (registering Resources from the UI form) work without it.
- **MCP server credentials.** Whatever the MCP server itself documents — MCP transports handle their own auth. We pass through.
- **What we never have.** Plaintext passwords, vendor API tokens, anything secret in SQLite, anything secret in `.jsonl` records. If a Capability's adapter needs a secret, it reads from env just like the app does.

## RemoteWorkdir — the File Staging Primitive

Every Operation gets a remote working directory whose name *is* the record hash. This is the load-bearing uniformity that lets the framework enforce provenance.

```
~/.autolab-work/<record-hash>/
  ├─ inputs.json       # uploaded before the Operation runs
  ├─ outputs.json      # downloaded after
  ├─ <declared artefact files>   # e.g. hysteresis.png, results.csv
  ├─ stdout.log
  ├─ stderr.log
  └─ meta.json         # backend-specific (slurm job id, pid, walltime, …)
```

One `RemoteWorkdir` class per Operation lifecycle, same shape for every backend (even `local`, where it lives under `~/.autolab-work/` on the autolab host). Lifecycle:

1. **Open** on Operation start: create the dir, `inputs.json` is SFTP-uploaded, the write-ahead Record is persisted.
2. **Run** the adapter, which reads `inputs.json`, does its thing, writes `outputs.json` + any declared artefact files.
3. **Fetch** declared outputs back, hash each, link them in the Record.
4. **Close**: do not delete immediately. Workdirs persist until the owning Campaign ends; `autolab replay` reads from them; a nightly pruner removes workdirs for Records older than the retention window (default 30 days). A Record can mark `keep_forever: true` for debug.
5. **Size limit**: when fetching outputs, any declared file exceeding 500 MB is rejected before download; the Record completes as `failed` with reason `output_too_large`. No silent OOMs on the autolab side.

Adapters (the code written per-Capability) are tiny because of this — they just read `inputs.json`, call their tool, write `outputs.json`. A mammos-mumag adapter is ~30 lines, not ~80. Adapters cannot skip provenance because they never touch the Record directly.

**Repo-backed Capability provenance.** When a Capability declares `source.repo: <path>` (see "Repo-backed Capabilities" below), every Record of that Capability additionally captures the repo's `git rev-parse HEAD` at invocation time. If the working tree is dirty, that fact is recorded too. `autolab replay` warns if the commit is gone or the tree diverged.

## The Assistant — Scope and Tools

The Setup Assistant is Claude Opus 4.7 invoked inside autolab, with a tightly-scoped tool set:

- `read_file(path)` — read files the user has named in the conversation, plus `~/.autolab/**`. Refuses paths outside these roots. Every call logged to the ledger.
- `list_directory(path)` — same scoping.
- `run_command(command, cwd=None, resource=None)` — runs a command; locally if `resource=None`, otherwise on the named Resource. Every call logged; the user sees each command before it runs and approves it (approvals batched when the same command sequence was pre-outlined, per CLAUDE.md's "gateway logs before it calls" rule).
- `register_resource(name, backend, address, tags)` — proposes a Resource; persisted only after user approval.
- `register_capability(yaml_content)` — proposes a Capability declaration; persisted only after user approval. The YAML is generated by the Assistant from the conversation, shown to the user as a rendered form (inputs/outputs schema), not as raw YAML.
- `run_smoke_test(capability, inputs, resource)` — runs one Operation and returns its Record for the Assistant to narrate.

The Assistant cannot silently modify the ledger, write to arbitrary paths, or run arbitrary shell commands without the user seeing them. It's a pair programmer, not an autonomous operator.

## The Onboarding Wizard

A five-step conversational flow. Step 0 is a blocking pre-wizard gate; steps 1–4 happen inside the Assistant's chat surface, which takes the full main-content area (the sidebar stays visible but dimmed until onboarding completes). Users can skip to any step and pick up later — progress is persisted per-lab so a half-finished wizard resumes.

**Step 0 — API key.** Full-page pre-wizard: "To use the Setup Assistant, paste your Anthropic API key." Three accept paths: paste into form (writes `~/.autolab/env`), set `ANTHROPIC_API_KEY` and reload, or "skip and set up manually" (drops to the Resources page with only form-based registration available). Nothing happens on disk before this.

**Step 1 — Intro.** Assistant: *"Hi — I'll help you set up this lab. Tell me about what compute and equipment you have. Natural language is fine."* User answers in free form. The Assistant parses and summarises back what it heard, asks for confirmation.

**Step 2 — Host connection.** Assistant proposes one or more Resources based on Step 1. For each:

- Summarises the proposed Resource (name, backend, address, tags).
- If the host isn't yet reachable, walks the user through the prerequisites live: `sshd` in WSL2, `ssh-keygen` if they have no key, `ssh-copy-id` to authorise. Each step is a shell snippet the user runs themselves; the Assistant waits for "done" and then runs `ssh <alias> hostname` to verify.
- On verify success, calls `register_resource` (user approves), then pings once more to set liveness green.
- Persists progress after each Resource — a user who walks away mid-step-2 comes back to their half-populated Resources list.

**Step 3 — Capability authoring.** Assistant: *"What do you want this lab to be able to do? You can describe a capability, or point me at a repo you already run."* Three paths, all fully conversational:

1. **Repo-backed.** User: *"I have a simulation at `~/code/my-mumag-sweep` that I run with `pixi run simulate`."* Assistant uses `read_file` / `list_directory` to examine `pixi.toml`, `pyproject.toml`, the entry-point script. It proposes the Capability: name, inputs (parameters it detected from the script / config), outputs (files the script writes). Iterates with clarifying questions — "which of these inputs should be parameterised per-run?", "I see SLURM sbatch headers in your script, should this Capability run on a queue or directly?" — until the declaration is complete. Offers to run it once as a smoke test. On success, calls `register_capability`.
2. **Described from scratch.** User describes a capability in natural language without a repo. Assistant asks about inputs, outputs, how it's invoked, where it runs. Same iterative refinement.
3. **MCP-imported.** User: *"Point me at an MCP server at `https://…`."* Assistant introspects the server, proposes one Capability per MCP tool, user approves selectively.

Raw-YAML authoring is available for power users under Settings → Import → Advanced, but the wizard never shows or accepts YAML text.

Users can declare zero Capabilities in this step — `shell_command` is always available as a fallback and is what Step 4 uses. The Assistant says *"You can always add more later from the Capabilities page,"* and moves on.

**Step 4 — Smoke test.** Assistant proposes a trivial Workflow: one `shell_command` Operation (`hostname && uname -a`) on the connected Resource. User approves, Operation runs, Record appears in the Gantt and Ledger in real time, Assistant narrates what happened, wizard completes. Sidebar undims; the user is now on the Campaigns page with one populated Ledger row linked from an empty-state message: *"Your first Record is in the Ledger. Start a real campaign from here."*

## Repo-Backed Capabilities — the Common Computational Pattern

The demo's most common authoring path, so it's spec'd explicitly. A repo-backed Capability is declared with:

```yaml
# autolab/capabilities/my_mumag_sweep.yaml  (user never sees this directly)
name: my_mumag_sweep
version: 1
source:
  repo: "~/code/my-mumag-sweep"
  pixi_task: "simulate"
  # OR:
  # command: "pixi run simulate --config {config_file}"
inputs:
  mesh_size:   {type: float, required: true}
  K1:          {type: float, required: true}
  Ms:          {type: float, required: true}
  alpha:       {type: float, default: 0.02}
outputs:
  results_json: {path: "results/summary.json", type: json}
  loop_png:     {path: "results/loop.png",    type: image/png}
requires:
  python: true         # any tag on the Resource satisfies this
# If absent, runs directly via ssh_exec. If present, wraps in sbatch on a slurm Resource.
slurm:
  partition: "gpu"
  walltime:  "02:00:00"
  gpus: 1
```

At invocation time, the adapter:

1. Ensures the repo exists at the remote's `~/.autolab-work/<record>/repo/` (rsync from local or git clone if repo has a remote URL).
2. Writes the per-run config (e.g. `config.yaml`) from `inputs.json` into the workdir.
3. Runs the declared command (`pixi run simulate --config …`) from the repo root, captures stdout/stderr.
4. Reads the declared output paths, puts them in `outputs.json` metadata + uploads the declared files back.
5. Records the repo's `git rev-parse HEAD` into the Record's `source_commit` field. If the working tree at `source.repo` is dirty, records that too.

**Input sweeps are the Campaign's job, not the Capability's.** The Capability exposes *what* is parameterisable; a Campaign chooses *what to sweep*. The user's "I change inputs and see how outputs change" workflow is therefore: write the Capability once via the Assistant, then start a Campaign that sweeps the parameters.

## Scheduler Implications

Out of scope for this subsystem's implementation (the scheduler lives in a later subsystem), but the shape it needs from us:

- `ssh_exec` / `local` Resources behave as single-slot lanes with a mutex.
- `slurm` Resources behave as N-slot lanes where N is the user's concurrent-job cap on the partition; queued Operations appear as faded pills in the Gantt that slide right as position-in-queue decreases.
- `mcp` Resources are treated as single-slot by default, with a tag `mcp_concurrency: N` allowing higher parallelism if the server tolerates it.
- `custom` Resources declare their slot count via a method on the `ResourceBackend` protocol.

## Components and Isolation

| Unit | Purpose | Depends on |
|---|---|---|
| `ResourceBackend` (protocol) | The four-method contract every backend implements | — |
| `SshExecBackend` | `asyncssh`-backed `ResourceBackend` for `ssh_exec` and `local` | `asyncssh`, `RemoteWorkdir` |
| `McpBackend` | MCP client implementation of `ResourceBackend` | mcp SDK, `RemoteWorkdir` |
| `SlurmBackend` | Stub raising `NotImplementedError` | — |
| `RemoteWorkdir` | Workdir lifecycle (open/run/fetch/close) shared by all backends | backend's transport handle |
| `ResourceRegistry` | Persistence of registered Resources, liveness monitor | store |
| `CapabilityRegistry` | Persistence of registered Capabilities (YAML files + adapter wiring) | filesystem |
| `Assistant` | Orchestrates the onboarding conversation; owns the tool set | anthropic SDK, registries, `ResourceBackend` |
| `AssistantChatView` | React surface hosting the Assistant conversation | websocket, assistant REST endpoints |
| `WizardProgress` | Per-lab persistence of "where is the user in onboarding" | store |

Adapters per user-authored Capability live under `autolab/capabilities/<name>.py` (or are a thin wrapper over `shell_command` and live only as YAML). No adapter imports the orchestrator.

## Data / Event Flow

1. User messages to the Assistant → `POST /assistant/messages`; response streamed back over the shared `WS /stream`'s `agent-messages` channel so the message timeline appears in both the wizard view and, later, the Campaign Reasoning rail.
2. Tool calls the Assistant makes → executed server-side, results round-tripped into the conversation context; every call creates a Record tagged `kind: assistant_tool`.
3. Resource liveness → independent poll loop, publishes to `resource-state` WS channel; the Resources table auto-updates.
4. Every Operation → write-ahead Record in SQLite + `.jsonl`, then the adapter runs inside the `RemoteWorkdir`; completion updates the Record with outputs + hashes.

## Error Handling

- **Unreachable Resource during setup.** Assistant pauses, surfaces the exact error from `ssh <alias> hostname`, offers diagnostics (is `sshd` running in WSL? is the key loaded in `ssh-agent`?). User fixes, Assistant retries on command.
- **Failed Operation during smoke test.** Treated like any failure — Record with `status: "failed"` plus the adapter's stderr. Assistant narrates the failure and proposes a fix (e.g. missing dependency → *"should I install it via `pixi install`?"*).
- **Dirty working tree on a repo-backed run.** Warning in the Record, not a failure. User can configure a stricter policy later.
- **Assistant loses connection mid-wizard.** `WizardProgress` snapshots after each Resource registration / Capability registration / smoke test, so reloading resumes the conversation with prior state intact. The message history itself is persisted as Records.
- **API key missing.** Wizard route redirects to Step 0; manual Resource form still works.

## Testing

Unit: `RemoteWorkdir` lifecycle (open/run/fetch/close), `SshExecBackend` against a throwaway localhost sshd in CI, `tags` matching logic.
Integration: full smoke test — spin up a lab, run the Step 4 `hostname` Operation against `local`, assert a Record with matching hash exists.
Assistant scenarios: handful of scripted transcripts covering the three capability-authoring paths (repo, described, mcp) with a mocked Anthropic client, asserting the resulting registered Capability YAML matches fixtures.
Playwright full-flow: deferred to subsystem 6.

## Rollout / Migration

- Rename `autolab/tools/` → `autolab/capabilities/` in the same PR as the backend work. No user code depends on this yet (pre-code repo).
- Rename all user-facing strings "Tool" → "Capability" in the new shell (the shell spec already anticipates this — it uses "Tools" in subsystem 1's sidebar table, which rolls forward to "Capabilities" here).
- No backwards-compat shims needed.

## Open Questions Deferred to Later Subsystems

- What tags a Capability contributes to a Resource when installed (vs static declaration) — may revisit in subsystem 4 as `mammos-*` Capabilities are authored.
- SLURM backend implementation details — subsystem 4 or post-hackathon.
- The full `ResourceBackend` protocol signature — finalise during implementation of the Python interface file; the four-method sketch here is the shape, not the final typing.
- Whether the Assistant streaming surface (Step 1–4 chat) shares one React component with the Campaign Reasoning rail or is two separate views with a shared transport — called during implementation.
