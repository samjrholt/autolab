"""Integration tests for the wsl_demo example.

Skipped automatically if WSL is not available (CI without WSL).
All tests use the Lab directly (no TestClient) to avoid scheduler teardown
issues on Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.wsl_demo.wsl import wsl_available

# Skip the entire module if WSL is not reachable.
pytestmark = pytest.mark.skipif(
    not wsl_available(),
    reason="WSL not available on this machine",
)


@pytest.fixture
def wsl_lab(tmp_path):
    from examples.wsl_demo.bootstrap import bootstrap

    from autolab.lab import Lab

    with Lab(root=tmp_path / "lab") as lab:
        bootstrap(lab)
        yield lab


# ---------------------------------------------------------------------------
# Bootstrap registration
# ---------------------------------------------------------------------------


class TestBootstrapRegistration:
    def test_resource_registered(self, wsl_lab):
        names = [r.name for r in wsl_lab.resources.list()]
        assert "wsl-ubuntu" in names

    def test_capabilities_registered(self, wsl_lab):
        assert wsl_lab.tools.has("wsl_info")
        assert wsl_lab.tools.has("wsl_numpy_eval")

    def test_workflows_registered(self, wsl_lab):
        assert "wsl_health_check" in wsl_lab._workflows
        assert "wsl_compute_chain" in wsl_lab._workflows
        assert "wsl_wave_eval" in wsl_lab._workflows

    def test_compute_chain_has_input_mapping(self, wsl_lab):
        wf = wsl_lab._workflows["wsl_compute_chain"]
        root_step = next(s for s in wf.steps if s.step_id == "root")
        assert root_step.input_mappings.get("x") == "square.result"

    def test_idempotent(self, wsl_lab):
        from examples.wsl_demo.bootstrap import bootstrap

        bootstrap(wsl_lab)  # second call must not raise or duplicate
        names = [r.name for r in wsl_lab.resources.list()]
        assert names.count("wsl-ubuntu") == 1


# ---------------------------------------------------------------------------
# wsl_info operation
# ---------------------------------------------------------------------------


class TestWslInfo:
    @pytest.mark.asyncio
    async def test_returns_completed(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert r.status == "completed", r.outputs

    @pytest.mark.asyncio
    async def test_python_version_present(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert r.outputs["python"].startswith("3.")

    @pytest.mark.asyncio
    async def test_numpy_installed(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert r.outputs["numpy"] is not None, "numpy not in WSL pixi env"

    @pytest.mark.asyncio
    async def test_scipy_installed(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert r.outputs["scipy"] is not None

    @pytest.mark.asyncio
    async def test_cpus_is_positive(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert isinstance(r.outputs["cpus"], int)
        assert r.outputs["cpus"] > 0

    @pytest.mark.asyncio
    async def test_pixi_env_active(self):
        from examples.wsl_demo.operations import WslInfo

        r = await WslInfo().run({})
        assert r.outputs["pixi_env"] == "default"


# ---------------------------------------------------------------------------
# wsl_numpy_eval operation
# ---------------------------------------------------------------------------


class TestWslNumpyEval:
    @pytest.mark.asyncio
    async def test_pythagorean_identity(self):
        """sin^2(x) + cos^2(x) == 1 for any x."""
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"x": 1.234, "expression": "np.sin(x)**2 + np.cos(x)**2"})
        assert r.status == "completed"
        assert abs(r.outputs["result"] - 1.0) < 1e-10

    @pytest.mark.asyncio
    async def test_polynomial(self):
        from examples.wsl_demo.operations import WslNumpyEval

        # x^2 - 3x + 2 at x=4 = 16 - 12 + 2 = 6
        r = await WslNumpyEval().run({"x": 4.0, "expression": "x**2 - 3*x + 2"})
        assert r.status == "completed"
        assert abs(r.outputs["result"] - 6.0) < 1e-10

    @pytest.mark.asyncio
    async def test_numpy_sqrt(self):
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"x": 9.0, "expression": "np.sqrt(x)"})
        assert r.status == "completed"
        assert abs(r.outputs["result"] - 3.0) < 1e-10

    @pytest.mark.asyncio
    async def test_wave_function_range(self):
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"x": 1.15, "expression": "np.sin(x) * np.cos(x/2)"})
        assert r.status == "completed"
        assert 0.7 < r.outputs["result"] < 1.0

    @pytest.mark.asyncio
    async def test_missing_x_fails(self):
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"expression": "x**2"})
        assert r.status == "failed"

    @pytest.mark.asyncio
    async def test_bad_x_type_fails(self):
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"x": "not_a_number", "expression": "x**2"})
        assert r.status == "failed"

    @pytest.mark.asyncio
    async def test_x_echoed_in_outputs(self):
        from examples.wsl_demo.operations import WslNumpyEval

        r = await WslNumpyEval().run({"x": 5.5, "expression": "x"})
        assert r.status == "completed"
        assert abs(r.outputs["x"] - 5.5) < 1e-10
        assert abs(r.outputs["result"] - 5.5) < 1e-10


# ---------------------------------------------------------------------------
# Workflow chain (tests input_mapping wiring through Lab.run_campaign)
# ---------------------------------------------------------------------------


class TestWslComputeChain:
    @pytest.mark.asyncio
    async def test_sqrt_of_square_is_identity(self, wsl_lab):
        """sqrt(x^2) = x — tests that input_mapping wires square.result -> root.x."""
        from autolab import Campaign, Objective
        from autolab.planners.optuna import OptunaConfig, OptunaPlanner

        campaign = Campaign(
            name="wsl-chain-test",
            objective=Objective(key="result", direction="maximise"),
            budget=4,
        )
        planner = OptunaPlanner(
            OptunaConfig(
                operation="wsl_numpy_eval",
                search_space={"x": {"type": "float", "low": 2.0, "high": 5.0}},
                fixed_inputs={"expression": "x**2"},
                sampler="random",
                seed=42,
            )
        )
        summary = await wsl_lab.run_campaign(campaign, planner)
        recs = [
            r
            for r in summary.records
            if r.operation == "wsl_numpy_eval" and r.record_status == "completed"
        ]
        assert recs, "No completed wsl_numpy_eval records"
        # Verify: result = x^2 for each record
        for rec in recs:
            x = rec.inputs["x"]
            expected = x**2
            actual = rec.outputs["result"]
            assert abs(actual - expected) < 1e-4, f"x={x}, expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Full Optuna campaign optimising wave function in WSL
# ---------------------------------------------------------------------------


class TestWslOptunaCampaign:
    @pytest.mark.asyncio
    async def test_optuna_explores_wave_function(self, wsl_lab):
        """Random sampler explores the wave function in WSL via Optuna.

        Uses an unreachable acceptance threshold (result > 2.0, max is ~0.77)
        so HeuristicPolicyProvider never auto-accepts, forcing the campaign to
        run until budget. Verifies WSL executes reliably across multiple calls.
        """
        from autolab import AcceptanceCriteria, Campaign, Objective
        from autolab.planners.optuna import OptunaConfig, OptunaPlanner

        campaign = Campaign(
            name="wsl-wave-peak",
            objective=Objective(key="result", direction="maximise"),
            budget=8,
            # Acceptance threshold above the function maximum (~0.77) so the
            # campaign exhausts its budget rather than stopping early.
            acceptance=AcceptanceCriteria(rules={"result": {">": 2.0}}),
        )
        planner = OptunaPlanner(
            OptunaConfig(
                operation="wsl_numpy_eval",
                search_space={"x": {"type": "float", "low": 0.0, "high": 6.0}},
                fixed_inputs={"expression": "np.sin(x) * np.cos(x/2)"},
                sampler="random",
                batch_size=1,
                seed=42,
            )
        )
        summary = await wsl_lab.run_campaign(campaign, planner)
        completed = [
            r
            for r in summary.records
            if r.operation == "wsl_numpy_eval" and r.record_status == "completed"
        ]
        assert len(completed) >= 4, f"Expected >= 4 completed WSL evals, got {len(completed)}"
        results = [r.outputs["result"] for r in completed if r.outputs.get("result") is not None]
        # Wave function is always in [-1, 1]; at least one must be > -1.
        assert max(results) > -1.0, "All results were -1 — something went wrong"

    @pytest.mark.asyncio
    async def test_ledger_checksums_valid(self, wsl_lab):
        from autolab import AcceptanceCriteria, Campaign, Objective
        from autolab.planners.optuna import OptunaConfig, OptunaPlanner

        campaign = Campaign(
            name="wsl-checksums",
            objective=Objective(key="result", direction="maximise"),
            budget=4,
            acceptance=AcceptanceCriteria(rules={"result": {">": 2.0}}),
        )
        planner = OptunaPlanner(
            OptunaConfig(
                operation="wsl_numpy_eval",
                search_space={"x": {"type": "float", "low": 0.0, "high": 6.0}},
                fixed_inputs={"expression": "np.sin(x)"},
                sampler="random",
                seed=1,
            )
        )
        await wsl_lab.run_campaign(campaign, planner)
        assert wsl_lab.verify_ledger() == []
