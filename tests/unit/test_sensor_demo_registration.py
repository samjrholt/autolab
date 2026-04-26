"""Tests for the sensor-demo registration helper."""

from __future__ import annotations

from scripts.register_sensor_demo import SHAPE_SEARCH_SPACE, _campaign_body, _selected_planners


def test_selected_planners_defaults_to_comparison_pair():
    assert _selected_planners("both") == ["optuna", "claude"]
    assert _selected_planners("optuna") == ["optuna"]
    assert _selected_planners("claude") == ["claude"]


def test_optuna_and_claude_campaigns_share_comparison_contract():
    workflow = {"name": "sensor_shape_opt", "steps": []}

    optuna = _campaign_body("optuna", workflow)
    claude = _campaign_body("claude", workflow)

    assert (
        optuna["objective"]
        == claude["objective"]
        == {
            "key": "Hmax_A_per_m",
            "direction": "maximise",
        }
    )
    assert optuna["budget"] == claude["budget"] == 12
    assert optuna["workflow"] == claude["workflow"] == workflow
    assert optuna["planner_config"]["search_space"] == SHAPE_SEARCH_SPACE
    assert claude["planner_config"]["search_space"] == SHAPE_SEARCH_SPACE
    assert optuna["planner"] == "optuna"
    assert claude["planner"] == "claude"
