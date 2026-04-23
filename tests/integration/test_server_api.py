"""End-to-end HTTP tests for the FastAPI surface.

Uses FastAPI's TestClient with the server's own lifespan so the whole
stack — Lab, Scheduler, EventBus — is exercised.
"""

from __future__ import annotations

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
    r = client.post("/campaigns/design", json={"text": "Maximise score on the demo quadratic"})
    assert r.status_code == 200
    body = r.json()
    assert body["offline"] is True
    assert "name" in body["campaign"]


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
