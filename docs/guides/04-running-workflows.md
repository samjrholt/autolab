# Running WorkflowTemplates

A `WorkflowTemplate` is a typed DAG of Operations with input wiring.
Campaigns use them for the *deterministic* part of an experiment — the
fixed chain of steps a single candidate runs through. The Planner picks
the next candidate; the workflow runs it to completion.

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
- Failed branches are skipped (their downstream steps land with
  `record_status="proposed"` and a note in `decision`). Independent
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
