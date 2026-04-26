"""POST /campaigns with autostart=false creates a prepared campaign.

The Console uses this path to let the user *review* a campaign before
kicking it off — the register_sensor_demo script creates the demo
campaign this way. Tests:

1. ``autostart=false`` → campaign exists in status="queued" and no task runs.
2. ``POST /campaigns/{id}/start`` launches a queued campaign.
3. Calling start on an already-running campaign is idempotent.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "demo_quadratic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from autolab.server.app import app

    with TestClient(app) as c:
        yield c


def _submit_optuna(client, *, autostart: bool):
    return client.post(
        "/campaigns",
        json={
            "name": f"prep-{autostart}",
            "objective": {"key": "score", "direction": "maximise"},
            "budget": 2,
            "planner": "optuna",
            "planner_config": {
                "operation": "demo_quadratic",
                "search_space": {"x": {"type": "float", "low": 0.0, "high": 1.0}},
            },
            "autostart": autostart,
        },
    )


def test_autostart_false_leaves_campaign_queued(client):
    r = _submit_optuna(client, autostart=False)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    cid = body["campaign_id"]

    # Nothing should advance while the campaign is queued. Sleep just enough
    # that a misconfigured autostart would reveal itself.
    time.sleep(1.0)
    state = client.get(f"/campaigns/{cid}").json()
    assert state["status"] == "queued", state


def test_start_endpoint_launches_queued_campaign(client):
    cid = _submit_optuna(client, autostart=False).json()["campaign_id"]
    assert client.get(f"/campaigns/{cid}").json()["status"] == "queued"

    r = client.post(f"/campaigns/{cid}/start")
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("running", "completed")

    # Campaign should reach a terminal state quickly — demo_quadratic is ~0.5s/step.
    deadline = time.time() + 15
    while time.time() < deadline:
        time.sleep(0.3)
        s = client.get(f"/campaigns/{cid}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            break
    assert s["status"] in ("completed", "failed", "cancelled")


def test_start_is_idempotent_on_running_or_terminal(client):
    cid = _submit_optuna(client, autostart=True).json()["campaign_id"]
    # Immediately fire start; should return OK regardless of running/terminal.
    r = client.post(f"/campaigns/{cid}/start")
    assert r.status_code == 200, r.text
    # Wait for terminal, then call start again — still 200.
    deadline = time.time() + 15
    while time.time() < deadline:
        time.sleep(0.3)
        s = client.get(f"/campaigns/{cid}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            break
    r = client.post(f"/campaigns/{cid}/start")
    assert r.status_code == 200, r.text


def test_start_on_unknown_campaign_404s(client):
    r = client.post("/campaigns/does-not-exist/start")
    assert r.status_code == 404
