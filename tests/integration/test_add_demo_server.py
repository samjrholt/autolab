"""Integration tests for the add_demo example.

Three layers:
  1. HTTP API shape (TestClient, no campaigns — avoids scheduler teardown issues).
  2. Model-level unit regressions (direction spelling, capability name).
  3. Campaign end-to-end (Lab.run_campaign directly — reliable, same code path).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixture: TestClient with add_demo bootstrap (NO campaigns submitted)
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "add_demo")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from autolab.server.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def add_demo_lab(tmp_path):
    """Bare Lab with add_demo bootstrap — for campaign tests."""
    from autolab.lab import Lab
    from examples.add_demo.bootstrap import bootstrap
    with Lab(root=tmp_path / "lab") as lab:
        bootstrap(lab)
        yield lab


# ---------------------------------------------------------------------------
# 1. HTTP API shape — bootstrap visible in /status and /tools
# ---------------------------------------------------------------------------

class TestBootstrapViaHTTP:
    def test_wsl_local_resource_in_status(self, http_client):
        names = [r["name"] for r in http_client.get("/status").json()["resources"]]
        assert "wsl-local" in names

    def test_add_two_in_status(self, http_client):
        caps = [t["capability"] for t in http_client.get("/status").json()["tools"]]
        assert "add_two" in caps

    def test_add_three_in_status(self, http_client):
        caps = [t["capability"] for t in http_client.get("/status").json()["tools"]]
        assert "add_three" in caps

    def test_workflow_in_status(self, http_client):
        names = [w["name"] for w in http_client.get("/status").json()["workflows"]]
        assert "add_two_then_three" in names

    def test_workflow_step_ids(self, http_client):
        wf = next(w for w in http_client.get("/status").json()["workflows"]
                  if w["name"] == "add_two_then_three")
        step_ids = [s["step_id"] for s in wf["steps"]]
        assert "add_two" in step_ids
        assert "add_three" in step_ids

    def test_workflow_input_mapping(self, http_client):
        wf = next(w for w in http_client.get("/status").json()["workflows"]
                  if w["name"] == "add_two_then_three")
        add_three = next(s for s in wf["steps"] if s["step_id"] == "add_three")
        assert add_three["input_mappings"].get("x") == "add_two.result"

    def test_ledger_returns_envelope(self, http_client):
        """GET /ledger must return {total, records:[]} not a bare list."""
        body = http_client.get("/ledger").json()
        assert "records" in body, f"Missing 'records': {list(body.keys())}"
        assert "total" in body
        assert isinstance(body["records"], list)

    def test_tools_endpoint_returns_list(self, http_client):
        body = http_client.get("/tools").json()
        assert isinstance(body, list)
        assert any(t["capability"] == "add_two" for t in body)


# ---------------------------------------------------------------------------
# 2. Capability name normalisation regression (HTTP, no campaigns)
# ---------------------------------------------------------------------------

class TestCapabilityNameNormalisation:
    def test_capability_only_no_name_accepted(self, http_client):
        """Regression: POST with only capability= used to return 400 'name'."""
        r = http_client.post("/tools/register-yaml", json={
            "capability": "test_cap_only",
            "adapter": "dynamic",
            "module": "test.v1",
            "inputs": {},
            "outputs": {},
        })
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        assert r.json()["capability"] == "test_cap_only"

    def test_name_only_no_capability_accepted(self, http_client):
        r = http_client.post("/tools/register-yaml", json={
            "name": "test_name_only",
            "adapter": "dynamic",
            "module": "test.v1",
            "inputs": {},
            "outputs": {},
        })
        assert r.status_code == 200, r.text

    def test_registered_cap_in_tools_list(self, http_client):
        http_client.post("/tools/register-yaml", json={
            "capability": "roundtrip_cap",
            "adapter": "dynamic",
            "module": "test.v1",
            "inputs": {},
            "outputs": {},
        })
        caps = [t["capability"] for t in http_client.get("/tools").json()]
        assert "roundtrip_cap" in caps


# ---------------------------------------------------------------------------
# 2b. Objective direction validation — pure Pydantic, no HTTP needed
# ---------------------------------------------------------------------------

class TestObjectiveDirection:
    def test_maximise_british_valid(self):
        from autolab.models import Objective
        obj = Objective(key="result", direction="maximise")
        assert obj.direction == "maximise"

    def test_minimise_british_valid(self):
        from autolab.models import Objective
        obj = Objective(key="result", direction="minimise")
        assert obj.direction == "minimise"

    def test_maximize_american_rejected(self):
        """Regression: UI was sending 'maximize' which silently produced wrong direction."""
        from pydantic import ValidationError
        from autolab.models import Objective
        with pytest.raises(ValidationError):
            Objective(key="result", direction="maximize")

    def test_minimize_american_rejected(self):
        from pydantic import ValidationError
        from autolab.models import Objective
        with pytest.raises(ValidationError):
            Objective(key="result", direction="minimize")



# ---------------------------------------------------------------------------
# 3. Campaign end-to-end (via Lab.run_campaign — reliable on all platforms)
# ---------------------------------------------------------------------------

class TestAddDemoCampaignDirect:

    @pytest.mark.asyncio
    async def test_campaign_completes(self, add_demo_lab):
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-completes",
            objective=Objective(key="result", direction="maximise"),
            budget=10,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        assert summary.status in ("accepted", "budget_exhausted")
        assert summary.steps_run > 0

    @pytest.mark.asyncio
    async def test_add_two_records_produced(self, add_demo_lab):
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-add-two",
            objective=Objective(key="result", direction="maximise"),
            budget=8,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        recs = [r for r in summary.records if r.operation == "add_two" and r.record_status == "completed"]
        assert len(recs) > 0

    @pytest.mark.asyncio
    async def test_add_three_records_produced_via_react(self, add_demo_lab):
        """Core regression: react() must chain add_three after every add_two."""
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-add-three",
            objective=Objective(key="result", direction="maximise"),
            budget=8,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        recs = [r for r in summary.records if r.operation == "add_three" and r.record_status == "completed"]
        assert len(recs) > 0, "react() chain broken — add_three never ran"

    @pytest.mark.asyncio
    async def test_equal_trial_counts(self, add_demo_lab):
        """Every add_two must produce exactly one add_three."""
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-counts",
            objective=Objective(key="result", direction="maximise"),
            budget=8,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        n2 = sum(1 for r in summary.records if r.operation == "add_two" and r.record_status == "completed")
        n3 = sum(1 for r in summary.records if r.operation == "add_three" and r.record_status == "completed")
        assert n2 == n3, f"add_two={n2} vs add_three={n3}"

    @pytest.mark.asyncio
    async def test_chain_arithmetic_x_plus_five(self, add_demo_lab):
        """add_three(x) must equal x+3; since x=add_two.result=original+2, total=original+5."""
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-arithmetic",
            objective=Objective(key="result", direction="maximise"),
            budget=8,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        for rec in summary.records:
            if rec.operation == "add_three" and rec.record_status == "completed":
                x_in = rec.inputs.get("x")
                result = rec.outputs.get("result")
                if x_in is not None and result is not None:
                    assert abs(result - (x_in + 3)) < 1e-6

    @pytest.mark.asyncio
    async def test_optuna_converges_near_optimal(self, add_demo_lab):
        """Optuna must find x close to 10 → result close to 15."""
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-convergence",
            objective=Objective(key="result", direction="maximise"),
            budget=22,
        )
        summary = await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        results = [
            r.outputs["result"]
            for r in summary.records
            if r.operation == "add_three"
            and r.record_status == "completed"
            and "result" in (r.outputs or {})
        ]
        assert results
        assert max(results) >= 14.0, f"Optuna did not converge: best={max(results):.2f}/15.0"

    @pytest.mark.asyncio
    async def test_ledger_checksums_valid(self, add_demo_lab):
        """Every record must have a valid checksum — provenance integrity."""
        from autolab import Campaign, Objective
        from examples.add_demo.planner import WorkflowChainOptimizer
        campaign = Campaign(
            name="e2e-checksums",
            objective=Objective(key="result", direction="maximise"),
            budget=6,
        )
        await add_demo_lab.run_campaign(campaign, WorkflowChainOptimizer())
        failures = add_demo_lab.verify_ledger()
        assert failures == [], f"Checksum failures: {failures}"
