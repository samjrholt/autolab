"""Boot script for the MaMMoS sensor demonstrator.

What this script does:

1. Creates a :class:`~autolab.Lab` (persistent, hashed, append-only ledger).
2. Probes the VM for mammos packages and registers it as a Resource.
3. Registers all six :class:`~autolab.Operation` classes via the
   Python-first ``lab.register_operation(cls)`` API — no YAML.
4. Registers the :data:`~examples.mammos_sensor.workflow.MAMMOS_SENSOR_WORKFLOW`
   template.
5. Runs one of three modes, selectable on the command line:

   ``--mode single``
       Execute the workflow once for a single geometry (no Planner).
       Fastest demo — one hashed run through the full chain.

   ``--mode bo``
       Run a BO Campaign that optimises free-layer geometry for maximum
       sensitivity. Each trial = one full workflow execution. Budget
       ``--budget`` (default 8).

   ``--mode optuna``
       Same as ``bo`` but with an Optuna TPE sampler.

Run from the repo root::

    pixi run python -m examples.mammos_sensor.run --mode single
    pixi run python -m examples.mammos_sensor.run --mode bo --budget 8
    pixi run python -m examples.mammos_sensor.run --mode optuna --sampler tpe

VM configuration
----------------

Default: WSL's default distro with ``python3``. Override with
``AUTOLAB_VM_KIND``, ``AUTOLAB_VM_DISTRO``, ``AUTOLAB_VM_PYTHON``, or
``AUTOLAB_VM_SSH_HOST`` (see :mod:`examples.mammos_sensor.vm`).

Force the surrogate path (skip any real mammos backend)::

    AUTOLAB_MAMMOS_FORCE_SURROGATE=1 pixi run python -m examples.mammos_sensor.run
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from autolab import Campaign, Lab, Resource
from autolab.orchestrator import CampaignRun
from autolab.planners.base import Planner

from examples.mammos_sensor.campaign import (
    build_bo_campaign,
    build_bo_planner,
    build_optuna_planner,
    build_single_run_campaign,
)
from examples.mammos_sensor.operations import ALL_OPERATIONS
from examples.mammos_sensor.vm import VMExecutor, probe_vm
from examples.mammos_sensor.workflow import (
    MAMMOS_SENSOR_WORKFLOW,
    default_input_overrides,
)


HERE = Path(__file__).parent


def _register_vm_resource(lab: Lab) -> tuple[Resource, VMExecutor]:
    """Probe the VM, register it as a Resource, stamp capabilities + diagnostic."""
    vm = VMExecutor()
    probe = probe_vm(vm)
    _print_probe_diagnostic(vm, probe)

    resource = Resource(
        name="vm-primary",
        kind="vm",
        capabilities={
            "reachable": probe.get("reachable", False),
            "python_version": probe.get("python_version"),
            "has_full_mammos_chain": probe.get("has_full_mammos_chain", False),
            "has_ubermag_chain": probe.get("has_ubermag_chain", False),
            "has_mace": probe.get("has_mace", False),
            "oommf_binary": probe.get("oommf_binary"),
            "mammos_mumag": probe.get("mammos_mumag"),
            "mammos_spindynamics": probe.get("mammos_spindynamics"),
            "mammos_ai": probe.get("mammos_ai"),
            "ubermag": probe.get("ubermag"),
        },
        description=f"MaMMoS execution VM: {vm.description}",
        asset_id=probe.get("hostname") or "vm-primary",
        typical_operation_durations={
            "mammos.relax_structure": 180,
            "mammos.intrinsic_magnetics_0k": 240,
            "mammos.finite_temperature_magnetics": 420,
            "mammos.sensor_mesh": 30,
            "mammos.micromagnetic_hysteresis": 900,
            "mammos.sensor_fom": 5,
        },
    )
    lab.register_resource(resource)
    return resource, vm


def _print_probe_diagnostic(vm: VMExecutor, probe: dict) -> None:
    """Print a per-package table showing what will run real vs surrogate.

    When nothing real is available, print concrete install commands the
    user can paste into their WSL shell to light up each backend.
    """
    if not probe.get("reachable"):
        print(f"VM NOT reachable ({probe.get('error')!r}); all steps will run via surrogate")
        return

    print(f"VM: {vm.description}  python={probe.get('python_version')}")
    print("Backend availability:")
    rows = [
        # (package, status, what-it-enables)
        ("mace / mace_torch", probe.get("mace"), "StructureRelax -> real MLIP"),
        ("mammos_ai", probe.get("mammos_ai"), "IntrinsicMagnetics0K -> pre-trained DFT surrogate"),
        (
            "mammos_spindynamics",
            probe.get("mammos_spindynamics"),
            "FiniteTemperatureMagnetics -> UppASD + Kuzmin fit",
        ),
        ("ubermag (df+mm+oommfc)", probe.get("ubermag"), "SensorMesh + MicromagneticHysteresis -> ubermag/OOMMF"),
        ("mammos_mumag", probe.get("mammos_mumag"), "MicromagneticHysteresis -> finite-element (preferred)"),
        (
            "OOMMF (binary or pip)",
            probe.get("oommf_binary") or probe.get("oommf_pip_package"),
            "required by ubermag to run OOMMF",
        ),
    ]
    for name, present, note in rows:
        mark = f"[OK] {present}" if present else "[--] NOT INSTALLED"
        print(f"  {name:28s} {mark:35s}  {note}")

    any_real = (
        probe.get("has_full_mammos_chain")
        or probe.get("has_ubermag_chain")
        or probe.get("has_mace")
    )
    if any_real:
        print()
        return

    # Nothing real is available -- tell the user how to install it.
    print()
    print("No real backends available -- every step will run on a labelled surrogate.")
    print("To get a real micromagnetic simulation, install ubermag + OOMMF inside the VM:")
    print()
    print("  # inside WSL:")
    print("  python3 -m pip install --user ubermag discretisedfield micromagneticmodel oommfc")
    print("  sudo apt-get install -y oommf-cli    # or compile OOMMF from https://math.nist.gov/oommf/")
    print()
    print("To get full MaMMoS (MLIP relax + ab-initio magnetics):")
    print("  python3 -m pip install --user mammos-entity mammos-mumag mammos-spindynamics mammos-ai")
    print("  python3 -m pip install --user mace-torch ase       # for StructureRelax")
    print()


def _register_operations(lab: Lab, vm: VMExecutor) -> None:
    """Register the six MaMMoS operations via the Python-first API.

    We hook into the Orchestrator's pre-hook to attach ``vm_executor`` into
    each Operation's context so the ops know which VM to use.
    """
    for cls in ALL_OPERATIONS:
        lab.register_operation(cls)

    async def _attach_vm(ctx, state):
        ctx.metadata.setdefault("vm_executor", vm)

    lab.orchestrator.add_pre_hook(_attach_vm)


async def _run_single(lab: Lab, vm: VMExecutor) -> None:
    """One full workflow execution for a default geometry."""
    campaign = build_single_run_campaign()
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id=campaign.id, session=session)

    result = await lab.run_workflow(
        "mammos_sensor",
        run,
        input_overrides=default_input_overrides(),
    )

    _print_workflow_summary(result, lab)


async def _run_optimisation(lab: Lab, vm: VMExecutor, campaign: Campaign, planner: Planner) -> None:
    """Run a BO / Optuna loop where each trial is a full workflow instance.

    We bypass ``lab.run_campaign`` here because we want each trial to
    materialise a workflow (not a single operation). The Planner's
    ``ProposedStep`` inputs become workflow input overrides.
    """
    from autolab.acceptance import evaluate
    from autolab.models import Annotation, ProposedStep, Record

    runner_session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id=campaign.id, session=runner_session)

    best: tuple[float, Record | None] = (float("-inf"), None)
    for trial in range(campaign.budget or 1):
        history = list(lab.ledger.iter_records(campaign_id=campaign.id))
        from autolab.planners.base import PlanContext

        ctx = PlanContext(
            campaign_id=campaign.id,
            objective=campaign.objective,
            history=history,
            resources=lab.resources.list(),
            acceptance=campaign.acceptance,
            remaining_budget=(campaign.budget or 1) - trial,
        )
        proposals = planner.plan(ctx)
        if not proposals:
            print(f"[trial {trial}] planner exhausted — stopping")
            break

        # Unpack the planner's geometry proposal into workflow overrides.
        step_inputs = proposals[0].inputs
        overrides = default_input_overrides(
            a_nm=step_inputs["a_nm"],
            b_nm=step_inputs["b_nm"],
            n=step_inputs["n"],
            thickness_nm=step_inputs["thickness_nm"],
        )
        print(
            f"[trial {trial}] a={step_inputs['a_nm']:.1f} b={step_inputs['b_nm']:.1f} "
            f"n={step_inputs['n']:.2f} thickness={step_inputs['thickness_nm']:.1f}"
        )

        result = await lab.run_workflow("mammos_sensor", run, input_overrides=overrides)

        # Mirror the fom outputs onto a virtual Record so the Planner's
        # history-read in plan() can see them next iteration.
        fom = next((s for s in result.steps if s.step_id == "fom"), None)
        if fom is None:
            print(f"[trial {trial}] fom step missing — skipping")
            continue
        gate = evaluate(campaign.acceptance, fom.record.outputs)
        # Stamp the planner's geometry onto the fom record as a decision trail.
        await lab.ledger.annotate(
            Annotation(
                target_record_id=fom.record.id,
                kind="claim",
                body={
                    "planner": planner.name,
                    "trial": trial,
                    "geometry": step_inputs,
                    "gate_result": gate.result,
                    "gate_reason": gate.reason,
                },
                author=planner.name,
            )
        )
        # Synthetic "trial" record so the planner's history sees the right inputs/outputs.
        trial_record = Record(
            lab_id=lab.lab_id,
            campaign_id=campaign.id,
            session_id=runner_session.id,
            operation="mammos.workflow.sensor",
            module="workflow.v0",
            inputs=dict(step_inputs),
            outputs=dict(fom.record.outputs),
            record_status="completed",
            decision={
                "planner": planner.name,
                "trial_number": trial,
                "workflow_name": "mammos_sensor",
                "fom_record_id": fom.record.id,
            },
            gate_result=gate.result,
        )
        await lab.ledger.append(trial_record)

        score = fom.record.outputs.get(campaign.objective.key)
        if score is None:
            continue
        print(
            f"  → sensitivity={fom.record.outputs.get('sensitivity_per_T'):.3f}/T  "
            f"linear_range={fom.record.outputs.get('linear_range_T') * 1e3:.2f}mT  "
            f"Hc={fom.record.outputs.get('Hc_mT'):.2f}mT  gate={gate.result}"
        )
        if float(score) > best[0]:
            best = (float(score), trial_record)
        if gate.result == "pass":
            print(f"  ✓ acceptance gate passed at trial {trial}")
            break

    print("\n=== Campaign summary ===")
    print(f"best sensitivity: {best[0]:.3f}/T")
    if best[1] is not None:
        print(f"best geometry:    {best[1].inputs}")
    bad = lab.verify_ledger()
    print(f"ledger verify:    {'OK' if not bad else f'BAD: {bad}'}")


def _print_workflow_summary(result, lab: Lab) -> None:
    print("\n=== Workflow summary ===")
    for sr in result.steps:
        outs = sr.record.outputs
        backend = outs.get("backend", "?")
        status = sr.record.record_status
        print(f"  {sr.step_id:14s} {status:10s}  backend={backend:10s}  ", end="")
        # Print one or two characteristic outputs per step.
        if sr.step_id == "relax":
            print(f"a={outs.get('a_ang'):.3f}A  E={outs.get('energy_ev_per_atom'):.3f}eV/atom")
        elif sr.step_id == "intrinsic_0k":
            print(f"Ms0={outs.get('Ms0_A_per_m'):.2e}A/m  K10={outs.get('K1_0_J_per_m3'):.2e}")
        elif sr.step_id == "finite_t":
            print(f"Ms(T)={outs.get('Ms_T_A_per_m'):.2e}  Tc={outs.get('Tc_K'):.0f}K")
        elif sr.step_id == "mesh":
            print(f"area={outs.get('area_nm2'):.0f}nm^2  aspect={outs.get('aspect_ratio'):.2f}")
        elif sr.step_id == "hysteresis":
            print(f"Hc={outs.get('Hc_A_per_m'):.0f}A/m  Mr={outs.get('Mr_A_per_m'):.2e}")
        elif sr.step_id == "fom":
            print(
                f"sensitivity={outs.get('sensitivity_per_T'):.3f}/T  "
                f"linear={outs.get('linear_range_T') * 1e3:.2f}mT  "
                f"Hc={outs.get('Hc_mT'):.2f}mT"
            )
    bad = lab.verify_ledger()
    print(f"\nledger verify: {'OK' if not bad else f'BAD: {bad}'}")
    print(f"records: {len(list(lab.ledger.iter_records()))}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MaMMoS sensor demonstrator.")
    parser.add_argument("--root", type=Path, default=Path("./.autolab-runs/mammos-sensor"))
    parser.add_argument("--mode", choices=("single", "bo", "optuna"), default="single")
    parser.add_argument("--budget", type=int, default=8, help="BO/Optuna trial budget")
    parser.add_argument("--sampler", default="tpe", help="Optuna sampler (tpe, cmaes, gp, random)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with Lab(args.root, lab_id="lab-mammos-sensor") as lab:
        _, vm = _register_vm_resource(lab)
        _register_operations(lab, vm)
        lab.register_workflow(MAMMOS_SENSOR_WORKFLOW)

        if args.mode == "single":
            await _run_single(lab, vm)
        elif args.mode == "bo":
            campaign = build_bo_campaign(budget=args.budget)
            planner = build_bo_planner(seed=args.seed)
            await _run_optimisation(lab, vm, campaign, planner)
        else:
            campaign = build_bo_campaign(budget=args.budget)
            planner = build_optuna_planner(sampler=args.sampler, seed=args.seed)
            await _run_optimisation(lab, vm, campaign, planner)


if __name__ == "__main__":
    asyncio.run(main())
