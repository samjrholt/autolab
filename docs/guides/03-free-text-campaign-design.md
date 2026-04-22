# Designing a Campaign from free text

A scientist should not have to write Python to start a campaign. The
Campaign Designer turns a sentence or paragraph into a draft
`Campaign` plus an optional `WorkflowTemplate`, surfaced for human
approval before anything runs.

## The two-step contract

autolab never silently executes LLM output. The designer is explicitly
*propose → approve → submit*:

1. **Propose.** `POST /campaigns/design` with `{"text": "…"}`. Claude
   reads the Lab's registered tools and resources, then returns a draft
   Campaign JSON plus notes. Every call is persisted as a `claim`
   Annotation on a `designer:draft` pseudo-record, so the reasoning
   trail is auditable even if you don't submit the draft.
2. **Approve.** The Console shows the draft as editable JSON. You can
   nudge the objective, budget, or acceptance rules by hand.
3. **Submit.** `POST /campaigns` with the (possibly edited) draft.
   The scheduler picks it up on its next tick.

Goal mutation is not allowed once a Campaign has started. If the
scientist wants to chase a different objective, they cancel this
Campaign and launch a new one. This is a locked design decision in
[CLAUDE.md](../../CLAUDE.md).

## From the Console

Scroll to **Design campaign from free text**. Type something like:

> "Find a composition and geometry that maximises the small-signal
> sensitivity of the demo quadratic tool. Stop once score ≥ 0.9. Use a
> simple Bayesian optimiser."

Click *Design campaign*. A JSON preview appears. Click *Approve &
submit* to enqueue it.

If the Console's top-right badge reads `claude: offline stub`, the
designer is returning a scripted response. Set `ANTHROPIC_API_KEY` and
restart the server for real LLM proposals.

## From the REST API

```bash
curl -X POST http://localhost:8000/campaigns/design \
  -H 'content-type: application/json' \
  -d '{"text":"Maximise sensor sensitivity; stop at score >= 0.9"}'
```

Response shape:

```json
{
  "campaign": { "name": "...", "objective": {...}, "acceptance": {...}, "budget": 16 },
  "workflow": { "name": "...", "steps": [...] },
  "notes": "Short Claude rationale (why this objective, this budget, etc.)",
  "model": "claude-opus-4-7",
  "offline": false,
  "prompt_sha256": "..."
}
```

Submit the draft (optionally after editing):

```bash
curl -X POST http://localhost:8000/campaigns \
  -H 'content-type: application/json' \
  -d '{
    "name":"sensor-sensitivity",
    "objective":{"key":"score","direction":"maximise"},
    "acceptance":{"rules":{"score":{">=":0.9}}},
    "budget":16,
    "planner":"heuristic",
    "use_claude_policy":true
  }'
```

## What Claude sees

The designer is given:

- The user's goal text verbatim.
- The full catalogue of registered tools (capability name, resource,
  inputs, outputs).
- Every registered Resource (name, kind, capabilities).

That's it — no free training data, no conversational history. Claude's
only job is to propose something that matches the Lab's actual
capabilities.

## What Claude cannot do

- Register new tools. If the Lab doesn't have a `pxrd` capability and
  the user asks for one, the draft `notes` field will say so; the
  Campaign will not run.
- Mutate an in-flight Campaign's objective.
- Skip the provenance layer. Every designer call, accepted or rejected,
  lands as an Annotation Record. So does every Planner `react()` call.

## Tuning the designer

- Tighten the prompt by editing the `_DESIGNER_SYSTEM` constant in
  [`src/autolab/agents/claude.py`](../../src/autolab/agents/claude.py).
  Shorter, stricter prompts give more predictable JSON.
- If the draft is missing an acceptance criterion, tell the designer
  explicitly in free text (e.g. "Accept at ≥ 0.9"). It respects literal
  thresholds.
- If a vertical needs different objective keys, you are almost certainly
  missing an Operation's `Outputs` schema. Fix the tool; the designer
  will see the new key automatically.

## Offline mode

Without `ANTHROPIC_API_KEY`, both the designer and the Claude
PolicyProvider fall back to a deterministic scripted response. The
Console marks them as *offline stub*. Tests run entirely offline — this
is how the integration suite stays self-contained.
