# Running WorkflowTemplates

A `WorkflowTemplate` is a typed DAG of Operations with input wiring.
Campaigns use them for the *deterministic* part of an experiment — the
fixed chain of steps a single candidate runs through. The Planner picks
the next candidate; the workflow runs it to completion.

There are two execution modes:

- **One-off workflow run:** `POST /workflows/{name}/run` executes a
  registered template once and returns every step result.
- **Workflow-backed campaign:** `POST /campaigns` may include a
  `workflow` object. The Planner still proposes one tunable operation,
  but the CampaignRunner executes the whole DAG for each proposal.

## Running from the Console

Workflows appear in the **Library → Workflows** section. Boot with a
bootstrap that registers a workflow, for example:

```bash
AUTOLAB_BOOTSTRAP=mammos pixi run serve
```

Open the Console and navigate to **Library → Workflows** to see the
registered `mammos_sensor` template and inspect its steps. To execute
it, use the REST API (below) — the Console currently shows the workflow
definition and step graph but does not have a GUI launcher. Once a run
is in progress you can navigate to **Campaigns** to watch the plan tree
and resource lanes fill live, and open any campaign to see physics
artefact cards as steps complete.

## From the REST API

### One-off workflow run

```bash
curl -X POST http://localhost:8000/workflows/mammos_sensor/run \
  -H 'content-type: application/json' \
  -d '{
    "input_overrides": {
      "relax":        {"composition": {"Fe": 0.5, "Co": 0.5}, "prototype": "FeCo"},
      "intrinsic_0k": {"prototype": "FeCo"},
      "finite_t":     {"prototype": "FeCo", "target_temp_k": 300},
      "mesh":         {"a_nm": 120, "b_nm": 80, "n": 2.5, "thickness_nm": 5, "cell_size_nm": 3},
      "hysteresis":   {"H_max_A_per_m": 80000, "n_steps": 41},
      "fom":          {}
    },
    "max_parallel": 2
  }'
```

Response shape:

```json
{
  "ok": true,
  "campaign_id": "wf-abcdef0123",
  "workflow": "mammos_sensor",
  "steps": [
    {"step_id": "relax",        "record_id": "rec-…", "status": "completed", "gate": "pass"},
    {"step_id": "intrinsic_0k", "record_id": "rec-…", "status": "completed", "gate": "pass"},
    … one per step …
  ],
  "skipped": []
}
```

### Workflow-backed campaign

Submit a campaign with both `planner_config.operation` and an inline
`workflow`. The planner operation identifies the workflow step that receives
the proposed inputs and whose Record is reported back to the planner.

```json
{
  "name": "sensor-shape-opt",
  "objective": {"key": "Hmax_A_per_m", "direction": "maximise"},
  "budget": 12,
  "parallelism": 1,
  "planner": "optuna",
  "planner_config": {
    "operation": "mammos.sensor_shape_fom",
    "search_space": {
      "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
      "sy_nm": {"type": "float", "low": 5.0, "high": 70.0}
    }
  },
  "workflow": {
    "name": "sensor_shape_opt",
    "steps": [
      {"step_id": "material", "operation": "mammos.sensor_material_at_T"},
      {
        "step_id": "fom",
        "operation": "mammos.sensor_shape_fom",
        "depends_on": ["material"],
        "input_mappings": {
          "Ms_A_per_m": "material.Ms_A_per_m",
          "A_J_per_m": "material.A_J_per_m"
        }
      }
    ]
  },
  "autostart": false
}
```

To let Claude drive the same bounded optimisation, keep the same
`planner_config.operation` and `search_space` but switch the planner:

```json
{
  "planner": "claude",
  "planner_config": {
    "operation": "mammos.sensor_shape_fom",
    "search_space": {
      "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
      "sy_nm": {"type": "float", "low": 5.0, "high": 70.0}
    },
    "batch_size": 1
  },
  "use_claude_policy": true
}
```

The server validates Claude's proposed inputs against the configured
search space before dispatching the workflow, so the LLM can reason about
the next candidate without breaking the operation contract.

For every trial, the CampaignRunner:

- runs all dependencies before the planner-targeted step;
- overlays the planner's proposed inputs onto matching workflow steps;
- stamps planner decision metadata, such as Optuna `trial_number` or
  Claude `method: "llm"`, onto the target step's Record;
- reacts to the target step's `GateVerdict`;
- counts budget by planner trials, not by internal workflow steps.

If no acceptance criteria are configured, completed trials continue until
budget exhaustion. Add `acceptance` when a campaign should stop early on a
threshold.

## Writing your own WorkflowTemplate

`WorkflowTemplate` is a Pydantic model (`autolab.models`). Build it in
Python and register with `lab.register_workflow(...)`, or POST to
`/workflows` from any client:

```python
from autolab.models import WorkflowStep, WorkflowTemplate

tmpl = WorkflowTemplate(
    name="sinter_and_measure",
    steps=[
        WorkflowStep(step_id="weigh",   operation="weighing"),
        WorkflowStep(step_id="mill",    operation="milling",   depends_on=["weigh"]),
        WorkflowStep(step_id="sinter",  operation="sintering", depends_on=["mill"],
                     input_mappings={"mass_g": "weigh.mass_g"}),
        WorkflowStep(step_id="xrd",     operation="xrd",       depends_on=["sinter"]),
    ],
)
```

- `input_mappings` wire an upstream step's `outputs[key]` into this
  step's `inputs[key]`. Runtime values win over the step's `inputs`
  dict when both are present.
- Steps with no `depends_on` run immediately. Every other step waits
  until all of its dependencies reach `completed` or `soft_fail`.
- Failed branches are skipped and listed in the `WorkflowResult`; independent
  branches keep running.

## Exporting a completed workflow

The run is a campaign; export its records as RO-Crate or PROV:

```bash
curl "http://localhost:8000/export/ro-crate?campaign_id=wf-abcdef0123" > crate.json
# Or, offline, via the CLI:
pixi run autolab export --root .autolab-runs/default --fmt prov --campaign wf-abcdef0123
```

RO-Crate hits ELN Consortium interop (Chemotion, eLabFTW, RSpace,
Kadi4Mat all round-trip `.eln`). PROV gives you a W3C-shaped graph
view for downstream research-object tooling.

## Anti-patterns

- **Reactive steps inside a workflow.** Workflows are deterministic —
  they don't replan. If a step's recipe should change mid-workflow,
  that's a Planner concern (`react()` emits an `add_step` Action), not
  a workflow concern.
- **Cross-campaign shared state.** A `WorkflowTemplate` is a recipe;
  each instance runs inside one campaign's `experiment_id`. Don't try
  to share state between workflow instances — use the ledger for
  anything that crosses invocations.
- **Writing your own scheduler inside a step.** Operations are atomic.
  If one "step" really spawns sub-jobs, split it into multiple steps
  connected by `depends_on`.
