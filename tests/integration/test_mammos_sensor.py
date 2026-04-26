"""Integration tests for the MaMMoS sensor demonstrator.

All tests force the surrogate path (``AUTOLAB_MAMMOS_FORCE_SURROGATE=1``)
so they are fully deterministic and require no WSL / VM / mammos install.
A separate test gates on VM availability and is skipped unless a real
VM is reachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from examples.mammos_sensor.operations import ALL_OPERATIONS
from examples.mammos_sensor.vm import VMConfig, VMExecutor, probe_vm
from examples.mammos_sensor.workflow import (
    MAMMOS_SENSOR_WORKFLOW,
    default_input_overrides,
)

from autolab import Lab, Resource
from autolab.dataset import DatasetBuilder
from autolab.orchestrator import CampaignRun


@pytest.fixture
def force_surrogate(monkeypatch):
    """Force every MaMMoS operation onto its surrogate path.

    Strict mode is the default at run time — real backends required. These
    integration tests explicitly opt back into the surrogate fallback so they
    stay deterministic on CI machines without a WSL pixi env.
    """
    monkeypatch.setenv("AUTOLAB_MAMMOS_FORCE_SURROGATE", "1")
    monkeypatch.setenv("AUTOLAB_MAMMOS_ALLOW_SURROGATE", "1")
    yield


def _build_vm_with_surrogate() -> VMExecutor:
    """Return a VMExecutor with force_surrogate=True, independent of env."""
    cfg = VMConfig.from_env()
    cfg.force_surrogate = True
    return VMExecutor(cfg)


def _boot_lab(tmp_path: Path, vm: VMExecutor) -> Lab:
    """Create a Lab wired for the MaMMoS demonstrator with a surrogate VM."""
    lab = Lab(tmp_path, lab_id="lab-mammos-test")
    lab.register_resource(
        Resource(
            name="vm-test",
            kind="vm",
            capabilities={"reachable": True, "has_full_mammos_chain": False},
            description="test vm (force_surrogate=True)",
            typical_operation_durations={
                c.capability: c.typical_duration or 0 for c in ALL_OPERATIONS
            },
        )
    )
    for cls in ALL_OPERATIONS:
        lab.register_operation(cls)

    async def _attach_vm(ctx, state):
        ctx.metadata.setdefault("vm_executor", vm)

    lab.orchestrator.add_pre_hook(_attach_vm)
    lab.register_workflow(MAMMOS_SENSOR_WORKFLOW)
    return lab


# ---------------------------------------------------------------------------
# Surrogate-path end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_workflow_runs_on_surrogate(tmp_path, force_surrogate):
    """End-to-end workflow execution with every step on the surrogate backend."""
    vm = _build_vm_with_surrogate()
    with _boot_lab(tmp_path, vm) as lab:
        session = lab.new_session()
        run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-test", session=session)

        result = await lab.run_workflow(
            "mammos_sensor",
            run,
            input_overrides=default_input_overrides(
                composition={"Fe": 0.5, "Co": 0.5},
                prototype="FeCo",
                a_nm=120.0,
                b_nm=80.0,
                n=2.5,
                thickness_nm=5.0,
            ),
        )

        assert result.completed, f"workflow did not complete: skipped={result.skipped_step_ids}"
        assert [s.step_id for s in result.steps] == [
            "relax",
            "intrinsic_0k",
            "finite_t",
            "mesh",
            "hysteresis",
            "fom",
        ] or set(s.step_id for s in result.steps) == {
            "relax",
            "intrinsic_0k",
            "finite_t",
            "mesh",
            "hysteresis",
            "fom",
        }

        # Every step stamped `backend` on its record.
        for sr in result.steps:
            assert "backend" in sr.record.outputs
            # Surrogate, or analytic for the FOM step.
            assert sr.record.outputs["backend"] in ("surrogate", "analytic")

        # The FOM step emits sensitivity + linear range + Hc.
        fom = result.get("fom")
        assert fom is not None
        for k in ("sensitivity_per_T", "linear_range_T", "Mr_over_Ms", "Hc_A_per_m"):
            assert k in fom.record.outputs, f"FOM missing {k}"
        assert fom.record.outputs["sensitivity_per_T"] > 0

        # Ledger integrity.
        assert lab.verify_ledger() == []


@pytest.mark.asyncio
async def test_input_mappings_propagate_material_parameters(tmp_path, force_surrogate):
    """The hysteresis step must receive Ms(T) from finite_t, not Ms(0)."""
    vm = _build_vm_with_surrogate()
    with _boot_lab(tmp_path, vm) as lab:
        session = lab.new_session()
        run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-wire", session=session)

        overrides = default_input_overrides(prototype="Nd2Fe14B", target_temp_k=300.0)
        result = await lab.run_workflow("mammos_sensor", run, input_overrides=overrides)

        ft = result.get("finite_t").record
        hyst = result.get("hysteresis").record

        # Hysteresis inputs should be the temperature-dependent ones.
        assert hyst.inputs["Ms_A_per_m"] == pytest.approx(ft.outputs["Ms_T_A_per_m"])
        assert hyst.inputs["K1_J_per_m3"] == pytest.approx(ft.outputs["K1_T_J_per_m3"])
        assert hyst.inputs["Aex_J_per_m"] == pytest.approx(ft.outputs["Aex_T_J_per_m"])


@pytest.mark.asyncio
async def test_different_geometry_changes_sensor_fom(tmp_path, force_surrogate):
    """Different free-layer geometries should produce different sensitivities."""
    vm = _build_vm_with_surrogate()
    with _boot_lab(tmp_path, vm) as lab:
        session = lab.new_session()

        foms = []
        for a, b in [(100.0, 100.0), (200.0, 60.0)]:
            run = CampaignRun(
                lab_id=lab.lab_id, campaign_id=f"camp-{a:.0f}-{b:.0f}", session=session
            )
            overrides = default_input_overrides(a_nm=a, b_nm=b, n=2.5, thickness_nm=5.0)
            result = await lab.run_workflow("mammos_sensor", run, input_overrides=overrides)
            foms.append(result.get("fom").record.outputs["sensitivity_per_T"])

        # Two very different aspect ratios → meaningfully different sensitivities.
        assert abs(foms[0] - foms[1]) > 1e-3


@pytest.mark.asyncio
async def test_records_carry_backend_stamp_and_declaration_hash(tmp_path, force_surrogate):
    """Every Record for a surrogate run carries backend=surrogate and a hash."""
    vm = _build_vm_with_surrogate()
    with _boot_lab(tmp_path, vm) as lab:
        session = lab.new_session()
        run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-prov", session=session)
        await lab.run_workflow("mammos_sensor", run, input_overrides=default_input_overrides())

        records = list(lab.ledger.iter_records(campaign_id="camp-prov"))
        mammos_records = [r for r in records if r.operation.startswith("mammos.")]
        assert len(mammos_records) == 6

        for rec in mammos_records:
            assert rec.tool_declaration_hash is not None
            backend = rec.outputs.get("backend")
            # fom is pure analytic; all other ops are on the surrogate path.
            if rec.operation == "mammos.sensor_fom":
                assert backend == "analytic"
            else:
                assert backend == "surrogate", f"{rec.operation} did not stamp surrogate backend"


@pytest.mark.asyncio
async def test_dataset_builder_exports_workflow_runs(tmp_path, force_surrogate):
    """DatasetBuilder should flatten the workflow into one row per step."""
    pytest.importorskip("pandas")
    vm = _build_vm_with_surrogate()
    with _boot_lab(tmp_path, vm) as lab:
        session = lab.new_session()
        run = CampaignRun(lab_id=lab.lab_id, campaign_id="camp-df", session=session)
        await lab.run_workflow("mammos_sensor", run, input_overrides=default_input_overrides())

        df = DatasetBuilder(lab.ledger).for_campaign("camp-df").only_completed().to_dataframe()
        assert len(df) == 6
        assert "outputs.backend" in df.columns
        assert "operation" in df.columns


# ---------------------------------------------------------------------------
# Real-VM gate (skipped unless a VM is actually reachable)
# ---------------------------------------------------------------------------


def _vm_reachable() -> bool:
    """Best-effort check: is there a VM we can actually talk to?"""
    if os.environ.get("AUTOLAB_VM_KIND") == "local":
        return True
    if os.environ.get("AUTOLAB_VM_SSH_HOST"):
        return True
    info = probe_vm()
    return bool(info.get("reachable"))


@pytest.mark.skipif(not _vm_reachable(), reason="No VM reachable; real-backend test skipped")
@pytest.mark.asyncio
async def test_vm_probe_reports_python_version(tmp_path):
    """If a VM is reachable, the probe must at least return a python version."""
    info = probe_vm()
    assert info.get("reachable") is True
    assert info.get("python_version")
