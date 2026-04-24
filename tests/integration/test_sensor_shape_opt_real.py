"""Real-backend smoke test for the sensor shape-opt demo workflow.

Skipped unless:
- ``AUTOLAB_VM_PIXI_PROJECT`` points at a real MaMMoS pixi environment, AND
- ``AUTOLAB_SMOKE_REAL_MAMMOS=1`` is set.

The test posts a single one-off workflow run and asserts that both
steps completed against real backends (``mammos_spindynamics`` and
``ubermag``) — NOT surrogate. Takes ~15-30 s on a modern laptop.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wsl_env_available() -> bool:
    if os.environ.get("AUTOLAB_SMOKE_REAL_MAMMOS", "") != "1":
        return False
    # The server's bootstrap probe handles unreachable WSL gracefully; we just
    # want this test to stay opt-in so it doesn't run on CI.
    return bool(os.environ.get("AUTOLAB_VM_PIXI_PROJECT"))


pytestmark = pytest.mark.skipif(
    not _wsl_env_available(),
    reason="Set AUTOLAB_SMOKE_REAL_MAMMOS=1 + WSL pixi env to exercise real backends",
)


@pytest.fixture
def http_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOLAB_ROOT", str(tmp_path / "lab"))
    monkeypatch.setenv("AUTOLAB_BOOTSTRAP", "mammos")
    # Strict mode — no surrogate fallback allowed.
    monkeypatch.delenv("AUTOLAB_MAMMOS_ALLOW_SURROGATE", raising=False)
    monkeypatch.delenv("AUTOLAB_MAMMOS_FORCE_SURROGATE", raising=False)
    from fastapi.testclient import TestClient

    from autolab.server.app import app

    with TestClient(app) as client:
        yield client


def test_sensor_shape_opt_runs_real_ubermag(http_client):
    from examples.mammos_sensor.workflow import default_sensor_shape_overrides

    # Short sweep — still real OOMMF, just fewer field points.
    overrides = default_sensor_shape_overrides(
        material="Ni80Fe20", temperature_K=300.0,
        sx_nm=40.0, sy_nm=30.0, n_exp=2.0, thickness_nm=5.0,
        region_L_nm=100.0, mesh_n=40,
        H_max_mT=200.0, n_steps=15,
    )
    r = http_client.post(
        "/workflows/sensor_shape_opt/run",
        json={"input_overrides": overrides},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, body

    steps_by_op = {s["operation"]: s for s in body["steps"]}
    mat = steps_by_op["mammos.sensor_material_at_T"]
    fom = steps_by_op["mammos.sensor_shape_fom"]
    assert mat["status"] == "completed"
    assert fom["status"] == "completed"

    # Pull the Records and check the backend stamps.
    mat_rec = http_client.get(f"/records/{mat['record_id']}").json()["record"]
    fom_rec = http_client.get(f"/records/{fom['record_id']}").json()["record"]
    assert mat_rec["outputs"]["backend"] == "mammos_spindynamics"
    assert fom_rec["outputs"]["backend"] == "ubermag"

    # Physical sanity: Permalloy Ms(300K) ≈ 830 kA/m.
    ms = mat_rec["outputs"]["Ms_A_per_m"]
    assert 750_000 <= ms <= 900_000, f"Ms(Permalloy, 300K) out of range: {ms}"
    hmax = fom_rec["outputs"]["Hmax_A_per_m"]
    assert hmax > 0, f"Hmax must be positive: {hmax}"
