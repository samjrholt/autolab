"""Strict-mode is the default for the MaMMoS sensor demo.

If the real backends (``mammos-*``, ``ubermag``, OOMMF) aren't installed
inside the VM, every Operation must return ``status="failed"`` with an
actionable error — never a silent surrogate. This is a one-way rule:
users who want the old fallback opt in with
``AUTOLAB_MAMMOS_ALLOW_SURROGATE=1`` (see
``examples/mammos_sensor/_strict.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from autolab import Lab, Resource
from autolab.orchestrator import CampaignRun

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.mammos_sensor.operations import ALL_OPERATIONS  # noqa: E402
from examples.mammos_sensor.vm import ScriptError, VMConfig, VMExecutor  # noqa: E402
from examples.mammos_sensor.workflow import (  # noqa: E402
    MAMMOS_SENSOR_WORKFLOW,
    default_input_overrides,
)


class _AlwaysScriptError:
    """Stand-in VMExecutor that always raises ScriptError.

    Simulates a VM that is reachable but has no real backends installed —
    the state every laptop starts in before the WSL pixi setup.
    """

    def __init__(self) -> None:
        self.config = VMConfig.from_env()

    def run_python(self, *_a, **_kw):  # noqa: D401
        raise ScriptError(
            "real backend not installed (synthetic)",
            returncode=2,
            stderr="ImportError: No module named 'mammos_mumag'",
        )


def _boot_lab(tmp_path: Path, vm) -> Lab:
    lab = Lab(tmp_path, lab_id="lab-strict-test")
    lab.register_resource(
        Resource(
            name="vm-test",
            kind="vm",
            capabilities={"reachable": True, "has_full_mammos_chain": False},
            description="test vm (strict)",
            typical_operation_durations={
                c.capability: c.typical_duration or 0 for c in ALL_OPERATIONS
            },
        )
    )
    for cls in ALL_OPERATIONS:
        lab.register_operation(cls)

    async def _attach_vm(ctx, _state):
        ctx.metadata.setdefault("vm_executor", vm)

    lab.orchestrator.add_pre_hook(_attach_vm)
    lab.register_workflow(MAMMOS_SENSOR_WORKFLOW)
    return lab


@pytest.mark.asyncio
async def test_strict_default_fails_cleanly_without_real_backends(tmp_path, monkeypatch):
    """Without AUTOLAB_MAMMOS_ALLOW_SURROGATE, a VM with no real backend must
    produce a failed Record carrying a setup hint — not a surrogate result."""
    monkeypatch.delenv("AUTOLAB_MAMMOS_ALLOW_SURROGATE", raising=False)
    monkeypatch.delenv("AUTOLAB_MAMMOS_FORCE_SURROGATE", raising=False)

    lab = _boot_lab(tmp_path, _AlwaysScriptError())
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="c1", session=session)
    result = await lab.run_workflow(
        MAMMOS_SENSOR_WORKFLOW.name,
        run,
        input_overrides=default_input_overrides(),
    )

    # First step runs, fails clean; downstream steps are skipped (missing deps).
    assert not result.completed
    first = result.steps[0].record
    assert first.record_status == "failed"
    assert "AUTOLAB_MAMMOS_ALLOW_SURROGATE" in (first.error or "")
    # No surrogate outputs leaked into the record.
    assert first.outputs.get("backend") != "surrogate"


@pytest.mark.asyncio
async def test_opt_in_surrogate_env_restores_fallback(tmp_path, monkeypatch):
    """With the escape hatch set, the existing surrogate path runs again."""
    monkeypatch.setenv("AUTOLAB_MAMMOS_ALLOW_SURROGATE", "1")

    lab = _boot_lab(tmp_path, _AlwaysScriptError())
    session = lab.new_session()
    run = CampaignRun(lab_id=lab.lab_id, campaign_id="c2", session=session)
    result = await lab.run_workflow(
        MAMMOS_SENSOR_WORKFLOW.name,
        run,
        input_overrides=default_input_overrides(),
    )

    # Every step should complete via surrogate; the Record stamps it honestly.
    assert result.completed, f"skipped={result.skipped_step_ids}"
    for step in result.steps:
        assert step.record.record_status == "completed"
        assert step.record.outputs.get("backend") in ("surrogate", "analytic")


def test_server_default_bootstrap_is_mammos(tmp_path, monkeypatch):
    """Fresh boot with no env override registers the mammos workflow + VM resource."""
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.delenv("AUTOLAB_BOOTSTRAP", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Don't require VM to actually reach — probe_vm handles unreachable gracefully.
    from fastapi.testclient import TestClient
    from autolab.server.app import app

    with TestClient(app) as client:
        body = client.get("/status").json()
    resources = {r["name"] for r in body["resources"]}
    workflows = {w["name"] for w in body["workflows"]}
    tools = {t["capability"] for t in body["tools"]}

    assert "this-pc" in resources
    assert "vm-primary" in resources
    assert MAMMOS_SENSOR_WORKFLOW.name in workflows
    assert {"mammos.sensor_mesh", "mammos.micromagnetic_hysteresis"} <= tools
    assert body["planners_available"] == ["optuna", "claude"]
