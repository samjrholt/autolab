"""End-to-end HTTP tests for the FastAPI surface.

Uses FastAPI's TestClient with the server's own lifespan so the whole
stack — Lab, Scheduler, EventBus — is exercised.
"""

from __future__ import annotations

import sys
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "demo_quadratic")
    # Force offline Claude so tests don't call the real API.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from autolab.server.app import app

    with TestClient(app) as c:
        yield c


def test_status_and_bootstrap(client):
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["lab_id"].startswith("lab-")
    # Bootstrap demo registers exactly one resource + tool.
    assert any(t["name"] == "demo_quadratic" for t in body["tools"])
    assert any(c["name"] == "demo_quadratic" for c in body["capabilities"])
    assert any(r["name"] == "local-computer" for r in body["resources"])
    assert any(r["name"] == "pc-1" for r in body["resources"])


def test_add_resource_roundtrip(client):
    r = client.post(
        "/resources",
        json={
            "name": "cluster-gpu",
            "kind": "slurm",
            "capabilities": {"gpu_count": 4, "mem_gb": 80},
        },
    )
    assert r.status_code == 200
    r = client.get("/resources")
    names = [row["name"] for row in r.json()]
    assert "cluster-gpu" in names

    r = client.delete("/resources/cluster-gpu")
    assert r.status_code == 200
    r = client.get("/resources")
    assert "cluster-gpu" not in [row["name"] for row in r.json()]


def test_resource_registration_accepts_backend_connection_shape(client):
    r = client.post(
        "/resources",
        json={
            "name": "login-submit",
            "backend": "slurm",
            "connection": {
                "host": "cluster-login",
                "remote_root": "~/.autolab-work",
            },
            "tags": {"scheduler": "slurm", "role": "login_node"},
            "description": "Generic Slurm submit host",
        },
    )
    assert r.status_code == 200
    rows = client.get("/resources").json()
    row = next(item for item in rows if item["name"] == "login-submit")
    assert row["kind"] == "computer"
    assert row["backend"] == "slurm"
    assert row["connection"]["host"] == "cluster-login"
    assert row["tags"]["scheduler"] == "slurm"


def test_capability_registration_preserves_resource_kind_and_aliases(client):
    r = client.post(
        "/capabilities/register",
        json={
            "capability": "run_python_script",
            "resource_kind": "computer",
            "resource_requirements": {"backend": "local"},
            "adapter": "dynamic",
            "module": "run_python_script.stub.v1",
            "inputs": {"script": "str"},
            "outputs": {"stdout": "str"},
            "typical_duration_s": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capability"] == "run_python_script"
    assert body["resource_kind"] == "computer"
    assert body["requires"] == {"backend": "local"}
    assert body["typical_duration_s"] == 10


def test_campaign_submit_runs_and_completes(client):
    r = client.post(
        "/campaigns",
        json={
            "name": "http-smoke",
            "objective": {"key": "score", "direction": "maximise"},
            "acceptance": {"rules": {"score": {">=": 0.95}}},
            "budget": 3,
            "planner": "optuna",
            "planner_config": {
                "operation": "demo_quadratic",
                "search_space": {"x": {"type": "float", "low": 0.0, "high": 1.0}},
            },
        },
    )
    assert r.status_code == 200
    cid = r.json()["campaign_id"]

    # Wait briefly for it to complete (demo op sleeps ~0.5s per step).
    deadline = time.time() + 15
    while time.time() < deadline:
        time.sleep(0.3)
        s = client.get(f"/campaigns/{cid}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            break
    assert s["status"] in ("completed", "failed", "cancelled")


def test_ledger_filter_dsl(client):
    # Submit a tiny campaign so the ledger has data.
    cid = client.post(
        "/campaigns",
        json={
            "name": "filter-data",
            "objective": {"key": "score", "direction": "maximise"},
            "budget": 2,
            "planner": "optuna",
            "planner_config": {
                "operation": "demo_quadratic",
                "search_space": {"x": {"type": "float", "low": 0.0, "high": 1.0}},
            },
        },
    ).json()["campaign_id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        time.sleep(0.3)
        s = client.get(f"/campaigns/{cid}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            break

    # Filter for completed records only.
    r = client.get("/ledger", params={"filter": "record.record_status = 'completed'"})
    assert r.status_code == 200
    for rec in r.json()["records"]:
        assert rec["record_status"] == "completed"


def test_designer_offline(client):
    r = client.post(
        "/campaigns/design",
        json={"text": "Use demo_quadratic to maximise score by varying x in [0, 1]"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert "name" in body["campaign"]


def test_campaign_designer_asks_generic_questions_for_underspecified_request(client):
    r = client.post(
        "/campaigns/design",
        json={"text": "I want to start a campaign around this problem"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert body["ready_to_apply"] is False
    assert body["questions"] == [
        "Which operation or workflow should autolab run?",
        "Which output or metric should the campaign optimise?",
    ]
    assert body["campaign"] == {}


def test_campaign_designer_asks_only_for_missing_details_in_partial_request(client):
    r = client.post(
        "/campaigns/design",
        json={"text": "Maximise score with demo_quadratic"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert body["ready_to_apply"] is False
    assert body["campaign"] == {}
    assert body["questions"] == [
        "Which inputs, search ranges, or fixed conditions should define the campaign?"
    ]


def test_campaign_designer_refinement_can_move_from_questions_to_ready(client):
    initial = client.post(
        "/campaigns/design",
        json={"text": "I want to start a campaign around this problem"},
    )
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["ready_to_apply"] is False

    refined = client.post(
        "/campaigns/design",
        json={
            "text": "I want to start a campaign around this problem",
            "previous": initial_body["campaign"],
            "instruction": (
                "Use demo_quadratic, optimise score, and vary x between 0 and 1."
            ),
        },
    )
    assert refined.status_code == 200
    refined_body = refined.json()
    assert refined_body["ready_to_apply"] is True
    assert refined_body["questions"] == []
    assert refined_body["campaign"]


def test_campaign_designer_handles_physics_style_prompt_with_registered_tool(client):
    registered = client.post(
        "/tools/register",
        json={
            "capability": "anneal_scan",
            "resource_kind": "furnace",
            "module": "anneal_scan.stub.v1",
            "description": "Anneal a sample and return coercivity.",
            "inputs": {"temp_k": "float", "dwell_h": "float"},
            "outputs": {"coercivity_kAm": "float"},
            "produces_sample": False,
            "destructive": False,
            "typical_duration_s": 60,
        },
    )
    assert registered.status_code == 200

    r = client.post(
        "/campaigns/design",
        json={"text": "Use anneal_scan to maximise coercivity_kAm by varying temp_k between 900 and 1200."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ready_to_apply"] is True
    assert body["campaign"]["objective"]["key"] == "coercivity_kAm"
    assert body["workflow"]["steps"][0]["operation"] == "anneal_scan"


def test_campaign_designer_handles_automated_lab_prompt_with_registered_tool(client):
    registered = client.post(
        "/tools/register",
        json={
            "capability": "plate_reader_scan",
            "resource_kind": "robot",
            "module": "plate_reader_scan.stub.v1",
            "description": "Run a plate reader assay and return fluorescence.",
            "inputs": {"ph": "float", "temperature_c": "float"},
            "outputs": {"fluorescence": "float"},
            "produces_sample": False,
            "destructive": False,
            "typical_duration_s": 60,
        },
    )
    assert registered.status_code == 200

    r = client.post(
        "/campaigns/design",
        json={"text": "Run plate_reader_scan to maximise fluorescence while varying ph from 6 to 8."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ready_to_apply"] is True
    assert body["campaign"]["objective"]["key"] == "fluorescence"
    assert body["workflow"]["steps"][0]["operation"] == "plate_reader_scan"


def test_lab_setup_asks_questions_before_proposal(client):
    r = client.post("/lab/setup", json={"text": "I want to set up a lab"})
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert body["ready_to_apply"] is False
    assert body["questions"]
    assert body["resources"] == []
    assert body["operations"] == []


def test_lab_setup_slurm_login_node_asks_connection_and_smoke_test_questions(client):
    r = client.post("/lab/setup", json={"text": "A server login node with Slurm"})
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert body["ready_to_apply"] is False
    questions = " ".join(body["questions"]).lower()
    assert "ssh" in questions
    assert "working directory" in questions
    assert "python" in questions
    assert "partition" in questions
    assert "smoke-test" in questions


def test_resource_designer_slurm_login_node_is_not_ready_to_apply(client):
    r = client.post("/resources/design", json={"text": "A server login node with Slurm"})
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert body["ready_to_apply"] is False
    assert body["resource"]["backend"] == "slurm"
    questions = " ".join(body["questions"]).lower()
    assert "ssh" in questions
    assert "smoke-test" in questions


def test_lab_setup_apply_registers_resources_tools_and_workflow(client):
    draft = client.post(
        "/lab/setup",
        json={
            "text": (
                "I have a local computer and a simulation script. "
                "Run it with x and collect a score."
            )
        },
    )
    assert draft.status_code == 200
    body = draft.json()
    assert body["ready_to_apply"] is True
    assert body["resources"]
    assert body["operations"]
    assert body["workflow"]

    applied = client.post("/lab/setup/apply", json=body)
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert "local-workstation" in applied_body["registered_resources"]
    assert "run_simulation" in applied_body["registered_operations"]
    assert "simulation-workflow" in applied_body["registered_workflows"]

    status = client.get("/status").json()
    assert any(r["name"] == "local-workstation" for r in status["resources"])
    assert any(t["capability"] == "run_simulation" for t in status["tools"])
    assert any(w["name"] == "simulation-workflow" for w in status["workflows"])


def test_command_backed_capability_smoke_test_creates_real_record(client):
    resource = client.post(
        "/resources",
        json={
            "name": "local-runner",
            "kind": "local_runner",
            "backend": "local",
            "connection": {"working_dir": ".autolab-work/test-local-runner"},
        },
    )
    assert resource.status_code == 200
    capability = client.post(
        "/capabilities/register",
        json={
            "capability": "say_hello",
            "resource_kind": "local_runner",
            "adapter": "shell_command",
            "module": "say_hello.command.v1",
            "command_template": f"{sys.executable} -c \"print('smoke-ok')\"",
            "outputs": {"stdout": "str", "stderr": "str", "exit_code": "int"},
            "typical_duration_s": 1,
        },
    )
    assert capability.status_code == 200

    r = client.post("/capabilities/say_hello/smoke-test", json={"inputs": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["record"]["record_status"] == "completed"
    assert body["record"]["resource_name"] == "local-runner"
    assert body["outputs"]["exit_code"] == 0
    assert "smoke-ok" in body["outputs"]["stdout"]


def test_analysis_query_offline(client):
    r = client.post(
        "/analysis/query",
        json={"prompt": "Compare campaign objectives over trial number"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "chart" in body
    assert "spec" in body
    assert body["offline"] is True


def test_verify_endpoint(client):
    r = client.get("/verify")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_estimate_workflow_endpoint(client):
    r = client.post(
        "/estimate/workflow",
        json={"operations": ["demo_quadratic", "demo_quadratic"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_seconds"] > 0
    assert len(body["steps"]) == 2


def test_annotation_endpoint(client):
    # Need a record to annotate — run a tiny campaign.
    cid = client.post(
        "/campaigns",
        json={
            "name": "annotate",
            "objective": {"key": "score", "direction": "maximise"},
            "budget": 1,
            "planner": "optuna",
            "planner_config": {
                "operation": "demo_quadratic",
                "search_space": {"x": {"type": "float", "low": 0.0, "high": 1.0}},
            },
        },
    ).json()["campaign_id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        time.sleep(0.3)
        s = client.get(f"/campaigns/{cid}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            break
    ledger = client.get("/ledger", params={"campaign_id": cid}).json()["records"]
    assert ledger, "expected at least one record"
    rid = ledger[0]["id"]
    r = client.post(f"/records/{rid}/annotate", json={"note": "manual test note"})
    assert r.status_code == 200
    detail = client.get(f"/records/{rid}").json()
    # Regression: RecordDetail.jsx crashed because the component treated the
    # envelope {record, history, annotations} as a flat record.
    assert "record" in detail, f"Expected envelope with 'record' key, got: {list(detail.keys())}"
    assert "history" in detail
    assert "annotations" in detail
    assert "operation" in detail["record"]
    assert "record_status" in detail["record"]
    assert any(
        a.get("body", {}).get("note") == "manual test note" for a in detail["annotations"]
    )


def test_websocket_hello(client):
    with client.websocket_connect("/events") as ws:
        first = ws.receive_json()
        assert first["kind"] == "hello"
