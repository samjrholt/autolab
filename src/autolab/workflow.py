"""WorkflowEngine — execute a WorkflowTemplate as a DAG of Operations.

A :class:`WorkflowTemplate` describes a reusable standard operating
procedure: a directed acyclic graph of :class:`~autolab.models.WorkflowStep`
nodes that each map to an Operation capability.  The engine topologically
sorts the DAG, runs steps as soon as all their dependencies have completed,
and wires upstream outputs into downstream inputs via ``input_mappings``.

Design
------

The engine is deliberately thin.  It does not contain a planner or a
policy — it only materialises a pre-specified workflow.  Adaptive replanning
(``react()``) is the Planner's domain; the WorkflowEngine handles the
deterministic part of the execution.

Each step is submitted to the Orchestrator as a :class:`~autolab.models.ProposedStep`
with an ``experiment_id`` scoped to the workflow run.  Results are
collected into a ``WorkflowResult`` carrying per-step records and the
full audit trail.

Parallelism
-----------

Steps with independent dependencies run concurrently, bounded by the
``max_parallel`` argument (default: unlimited within the available
Resources).  In practice the ResourceManager's per-instance locks are
the binding constraint — two sintering steps still cannot share one tube
furnace.

Input wiring
------------

``WorkflowStep.input_mappings``::

    {"inputs_key": "upstream_step_id.output_key"}

Example: the magnetometry step needs the grain size measured by XRD::

    WorkflowStep(
        step_id="mag",
        operation="magnetometry",
        depends_on=["xrd"],
        input_mappings={"grain_size_nm": "xrd.grain_size_nm"},
    )

If both ``inputs`` and ``input_mappings`` provide the same key,
``input_mappings`` (runtime value from the upstream step) wins.

Failure handling
----------------

If a step fails, subsequent steps that depend on it are skipped with
``record_status="proposed"`` and a note in their decision dict.  Steps
with no dependency on the failed branch continue running.  The
``WorkflowResult.completed`` flag is ``False`` if any step ended with
``record_status="failed"``.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from autolab.acceptance import GateVerdict
from autolab.models import (
    AcceptanceCriteria,
    ProposedStep,
    Record,
    Sample,
    WorkflowStep,
    WorkflowTemplate,
)
from autolab.orchestrator import CampaignRun, Orchestrator


@dataclass
class StepResult:
    """Outcome of one workflow step."""

    step_id: str
    record: Record
    gate: GateVerdict
    sample: Sample | None = None


@dataclass
class WorkflowResult:
    """Aggregate result of a full workflow run."""

    workflow_name: str
    campaign_id: str
    steps: list[StepResult] = field(default_factory=list)
    skipped_step_ids: list[str] = field(default_factory=list)
    completed: bool = False

    def get(self, step_id: str) -> StepResult | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    @property
    def records(self) -> list[Record]:
        return [s.record for s in self.steps]


class WorkflowEngine:
    """Execute a :class:`~autolab.models.WorkflowTemplate` against an Orchestrator.

    The engine is stateless — each ``run()`` call is an independent execution.
    Register it with the Lab via ``lab.register_workflow(template)`` and
    run it with ``await lab.run_workflow("template_name", ...)``.
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def run(
        self,
        template: WorkflowTemplate,
        run: CampaignRun,
        *,
        input_overrides: dict[str, dict[str, Any]] | None = None,
        acceptance: AcceptanceCriteria | None = None,
        upstream_sample: Sample | None = None,
        max_parallel: int | None = None,
    ) -> WorkflowResult:
        """Execute all steps in topological order.

        Parameters
        ----------
        template:
            The WorkflowTemplate to execute.
        run:
            CampaignRun identity bundle (lab_id, campaign_id, session).
        input_overrides:
            ``{step_id: {input_key: value}}`` — override step inputs at
            call time (e.g. composition parameters for a synthesis workflow).
        acceptance:
            Campaign-level AcceptanceCriteria applied to every step that
            has no step-level criteria.
        upstream_sample:
            The starting Sample, if the first step(s) require one.
        max_parallel:
            Cap concurrent steps. ``None`` = no cap beyond resources.
        """
        overrides = input_overrides or {}
        order = _topological_sort(template.steps)
        result = WorkflowResult(workflow_name=template.name, campaign_id=run.campaign_id)

        # Maps step_id → StepResult (once the step completes).
        done: dict[str, StepResult] = {}
        # Maps step_id → current upstream sample (propagated through chain).
        step_sample: dict[str, Sample | None] = {}
        # Steps that failed — their dependants are skipped.
        failed_steps: set[str] = set()

        sem = asyncio.Semaphore(max_parallel) if max_parallel else None

        async def run_step(step: WorkflowStep) -> None:
            # Collect upstream samples from depends_on chain.
            parent_samples: list[Sample] = []
            for dep_id in step.depends_on:
                s = step_sample.get(dep_id)
                if s is not None:
                    parent_samples.append(s)
            if not parent_samples and upstream_sample is not None:
                parent_samples = [upstream_sample]

            # Wire input_mappings: pull values from upstream step outputs.
            wired_inputs: dict[str, Any] = {}
            for my_key, ref in step.input_mappings.items():
                dep_id, _, out_key = ref.partition(".")
                sr = done.get(dep_id)
                if sr is not None and out_key in sr.record.outputs:
                    wired_inputs[my_key] = sr.record.outputs[out_key]

            # Merge: step.inputs < input_overrides < wired (runtime wins).
            merged = {**step.inputs, **overrides.get(step.step_id, {}), **wired_inputs}

            proposed = ProposedStep(
                operation=step.operation,
                inputs=merged,
                experiment_id=f"{run.campaign_id}-wf-{step.step_id}",
                decision={
                    "workflow": template.name,
                    "step_id": step.step_id,
                    "branch_id": step.branch_id,
                },
            )

            gate_criteria = step.acceptance or acceptance

            if sem:
                async with sem:
                    rec, gate = await self.orchestrator.run_step(
                        proposed,
                        run,
                        acceptance=gate_criteria,
                        upstream_samples=parent_samples or None,
                    )
            else:
                rec, gate = await self.orchestrator.run_step(
                    proposed,
                    run,
                    acceptance=gate_criteria,
                    upstream_samples=parent_samples or None,
                )

            sr = StepResult(step_id=step.step_id, record=rec, gate=gate)
            done[step.step_id] = sr
            result.steps.append(sr)

            # Track the new sample if the step produced one.
            from autolab.models import Sample as _Sample

            if rec.sample_id:
                step_sample[step.step_id] = _Sample(
                    id=rec.sample_id,
                    parent_sample_ids=rec.parent_sample_ids,
                )
            else:
                # Propagate from the last parent that had a sample.
                for dep_id in reversed(step.depends_on):
                    if dep_id in step_sample:
                        step_sample[step.step_id] = step_sample[dep_id]
                        break

            if rec.record_status == "failed":
                failed_steps.add(step.step_id)

        # Walk in topological order, launching batches of ready steps.
        for batch in order:
            # Skip steps whose dependencies failed.
            runnable = []
            for step_id in batch:
                step = next(s for s in template.steps if s.step_id == step_id)
                if any(dep in failed_steps for dep in step.depends_on):
                    result.skipped_step_ids.append(step_id)
                    failed_steps.add(step_id)  # propagate skip
                else:
                    runnable.append(step)

            if runnable:
                await asyncio.gather(*[run_step(s) for s in runnable])

        result.completed = len(result.skipped_step_ids) == 0 and all(
            sr.record.record_status == "completed" for sr in result.steps
        )
        return result


def _topological_sort(steps: list[WorkflowStep]) -> list[list[str]]:
    """Kahn's algorithm — returns batches of step_ids in execution order.

    Each batch contains steps that can run in parallel (all their
    dependencies are in earlier batches).
    """
    step_map = {s.step_id: s for s in steps}
    in_degree: dict[str, int] = defaultdict(int)
    dependants: dict[str, list[str]] = defaultdict(list)

    for step in steps:
        if step.step_id not in in_degree:
            in_degree[step.step_id] = 0
        for dep in step.depends_on:
            in_degree[step.step_id] += 1
            dependants[dep].append(step.step_id)

    batches: list[list[str]] = []
    ready = [sid for sid, deg in in_degree.items() if deg == 0]

    while ready:
        batches.append(sorted(ready))
        next_ready: list[str] = []
        for sid in ready:
            for dep_id in dependants[sid]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    next_ready.append(dep_id)
        ready = next_ready

    if sum(len(b) for b in batches) != len(steps):
        raise ValueError("WorkflowTemplate contains a cycle — step dependencies must form a DAG")
    return batches


__all__ = ["StepResult", "WorkflowEngine", "WorkflowResult"]
