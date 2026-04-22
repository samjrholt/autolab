# Adding a Resource

A `Resource` is a named, capacity-limited instance of an instrument or
compute resource (an arc furnace, a tube furnace, a GPU partition). The
Scheduler acquires one free compatible `Resource` for every Operation
that declares a `resource_kind`.

Three ways to add one — pick whichever matches how you are working.

## 1. From the Console UI

The *Add resource* panel accepts four fields:

- `name` — unique within this Lab (e.g. `tube-furnace-A`).
- `kind` — the type string Operations will match against (e.g. `tube_furnace`).
- `description` — free text, stored as-is.
- `capabilities` — a JSON object the scheduler uses to match
  `Operation.requires`. Example: `{"max_temp_k": 1400, "atmosphere": "Ar"}`.

Click *Register resource*. The Console refreshes and the new Resource
appears as a lane in the Gantt panel, immediately available to new
campaigns.

## 2. From the REST API

```bash
curl -X POST http://localhost:8000/resources \
  -H 'content-type: application/json' \
  -d '{
    "name":"tube-furnace-A",
    "kind":"tube_furnace",
    "capabilities":{"max_temp_k":1400,"atmosphere":"Ar"},
    "asset_id":"TF-2024-001",
    "typical_operation_durations":{"sinter":7200}
  }'
```

The server calls `Lab.register_resource()` under the hood and publishes
a `resource.registered` event.

## 3. From Python (in-process Lab)

```python
from autolab import Lab, Resource

lab = Lab("./.autolab-runs/my-lab")
lab.register_resource(
    Resource(
        name="tube-furnace-A",
        kind="tube_furnace",
        capabilities={"max_temp_k": 1400, "atmosphere": "Ar"},
        asset_id="TF-2024-001",
        typical_operation_durations={"sinter": 7200},
    )
)
```

## Capability matching

`Operation.requires` is a dict of the same shape, optionally using an
operator map:

```python
class Sinter(Operation):
    resource_kind = "tube_furnace"
    requires = {"max_temp_k": {">=": 1300}, "atmosphere": "Ar"}
```

The `ResourceManager` finds every Resource with `kind == "tube_furnace"`
and picks the first one whose capabilities satisfy every operator.
Supported operators: `>=`, `<=`, `>`, `<`, `==`, `in`, `not_in`.
Bare values (no operator dict) are equality checks.

## State machine

A Resource carries one of: `idle`, `busy`, `cooling`, `warming`,
`calibrating`, `error`, `maintenance`. The scheduler only acquires
`idle` resources. Transient states (`cooling`, `warming`) can carry an
`available_after` timestamp, which is the Console's ETA source.

Set state from within an Operation by mutating the manager (advanced):

```python
lab.resources.set_state(
    "tube-furnace-A",
    ResourceState.COOLING,
    available_after=datetime.now(UTC) + timedelta(minutes=45),
)
```

## Unregistering

```bash
curl -X DELETE http://localhost:8000/resources/tube-furnace-A
```

Unregistration is immediate. A Resource with in-flight work cannot be
safely removed; the Scheduler keeps the reference until its holder exits.
