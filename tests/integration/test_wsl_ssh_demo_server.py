from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.wsl_ssh_demo.ssh import ssh_available

pytestmark = pytest.mark.skipif(
    not ssh_available(),
    reason="ssh wsl2 is not reachable on this machine",
)


@pytest.fixture
def http_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "wsl_ssh_demo")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from autolab.server.app import app

    with TestClient(app) as client:
        yield client


def test_wsl_resource_metadata_visible_in_status(http_client):
    body = http_client.get("/status").json()
    wsl = next(resource for resource in body["resources"] if resource["name"] == "wsl")
    assert wsl["capabilities"]["backend"] == "ssh"
    assert wsl["capabilities"]["ssh_host"] == "wsl2"
    assert wsl["capabilities"]["remote_root"] == "/home/sam/autolab-wsl"


def test_wsl_workflow_and_planner_visible_in_status(http_client):
    body = http_client.get("/status").json()
    workflows = [workflow["name"] for workflow in body["workflows"]]
    tools = [tool["capability"] for tool in body["tools"]]
    planners = body["planners_available"]

    assert "add_two_then_cube" in workflows
    assert "add_two" in tools
    assert "cube" in tools
    assert "wsl_ssh_add_cube_optuna" in planners
