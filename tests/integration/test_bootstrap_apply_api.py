from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def http_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "none")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from autolab.server.app import app

    with TestClient(app) as client:
        yield client


def test_apply_add_demo_bootstrap_to_running_lab(http_client):
    before = http_client.get("/status").json()
    # Every lab auto-registers "this-pc" — it is always present, even under
    # AUTOLAB_BOOTSTRAP=none. No other resources before the add_demo apply.
    before_names = {r["name"] for r in before["resources"]}
    assert before_names == {"this-pc"}
    assert before["workflows"] == []

    applied = http_client.post("/bootstraps/apply", json={"mode": "add_demo"})
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["ok"] is True
    assert "wsl-local" in body["resources"]
    assert "add_two" in body["capabilities"]
    assert "add_two_then_three" in body["workflows"]

    after = http_client.get("/status").json()
    assert any(resource["name"] == "wsl-local" for resource in after["resources"])
    assert any(tool["capability"] == "add_two" for tool in after["tools"])
    assert any(workflow["name"] == "add_two_then_three" for workflow in after["workflows"])


def test_apply_bootstrap_emits_refresh_events(http_client):
    with http_client.websocket_connect("/events") as ws:
        hello = ws.receive_json()
        assert hello["kind"] == "hello"

        applied = http_client.post("/bootstraps/apply", json={"mode": "add_demo"})
        assert applied.status_code == 200, applied.text

        # add_demo bootstrap emits ≥4 events: the Lab.register_* calls each
        # publish their own event, and POST /bootstraps/apply publishes a diff
        # summary on top. Drain generously to see all three kinds.
        kinds: set[str] = set()
        need = {"resource.registered", "tool.registered", "workflow.registered"}
        for _ in range(16):
            if need <= kinds:
                break
            kinds.add(ws.receive_json()["kind"])
        assert need <= kinds, f"missing {need - kinds}; got {kinds}"
