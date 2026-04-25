"""Spawn a fresh Claude campaign with autostart (after API overload)."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


status = get("/status")
wf = next(w for w in status["workflows"] if w["name"] == "sensor_shape_opt")

body = {
    "name": "sensor-shape-opt (claude-retry)",
    "description": "retry after API overload",
    "planner": "claude",
    "planner_config": {
        "operation": "mammos.sensor_shape_fom",
        "search_space": {
            "material": {"type": "categorical", "choices": ["Ni80Fe20", "FeCo"]},
            "sx_nm": {"type": "float", "low": 5.0, "high": 70.0},
            "sy_nm": {"type": "float", "low": 5.0, "high": 70.0},
        },
        "input_routing": {"material": "material", "sx_nm": "fom", "sy_nm": "fom"},
        "batch_size": 1,
    },
    "objective": {"key": "Hmax_A_per_m", "direction": "maximise"},
    "budget": 12,
    "parallelism": 1,
    "priority": 50,
    "workflow": wf,
    "autostart": True,
    "use_claude_policy": True,
}

resp = post("/campaigns", body)
print("NEW:", resp.get("campaign_id"), resp.get("status"))
