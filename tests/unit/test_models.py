"""Unit tests for the core Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autolab import (
    AcceptanceCriteria,
    Action,
    ActionType,
    Campaign,
    CampaignSummary,
    Objective,
)


class TestObjective:
    def test_direction_default_is_maximise(self):
        obj = Objective(key="score")
        assert obj.direction == "maximise"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValidationError):
            Objective(key="score", direction="neither")  # type: ignore[arg-type]


class TestCampaign:
    def test_minimal_campaign_round_trips_as_json(self):
        c = Campaign(name="c", objective=Objective(key="score"))
        blob = c.model_dump_json()
        round_tripped = Campaign.model_validate_json(blob)
        assert round_tripped.id == c.id
        assert round_tripped.objective == c.objective

    def test_immutable_id_is_generated(self):
        a = Campaign(name="a", objective=Objective(key="k"))
        b = Campaign(name="b", objective=Objective(key="k"))
        assert a.id != b.id
        assert a.id.startswith("camp-")

    def test_acceptance_criteria_attaches(self):
        c = Campaign(
            name="c",
            objective=Objective(key="score"),
            acceptance=AcceptanceCriteria(rules={"score": {">=": 1.0}}),
        )
        assert c.acceptance is not None
        assert c.acceptance.rules == {"score": {">=": 1.0}}

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            Campaign(name="c", objective=Objective(key="k"), not_a_field=42)  # type: ignore[call-arg]


class TestCampaignSummary:
    def test_roundtrip_with_no_records(self):
        s = CampaignSummary(
            campaign_id="camp-x",
            status="budget_exhausted",
            reason="out of budget",
            steps_run=3,
        )
        assert s.records == []
        assert s.best_outputs is None


class TestAction:
    def test_action_type_is_closed_set(self):
        with pytest.raises(ValidationError):
            Action(type="teleport", reason="nope")  # type: ignore[arg-type]

    def test_accept_action_round_trip(self):
        a = Action(type=ActionType.ACCEPT, reason="gate passed")
        assert a.type is ActionType.ACCEPT
        assert a.reason == "gate passed"
