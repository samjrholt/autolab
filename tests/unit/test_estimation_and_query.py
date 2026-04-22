"""Tests for EstimationEngine, query DSL, and offline Claude agents."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from autolab import query
from autolab.agents.claude import (
    CampaignDesigner,
    ClaudePolicyProvider,
    ClaudeTransport,
)
from autolab.estimation import EstimationEngine
from autolab.models import ActionType, Record


# ---------------------------------------------------------------------------
# Query DSL
# ---------------------------------------------------------------------------


def _rec(**kw) -> Record:
    defaults = dict(
        lab_id="lab-x",
        session_id="ses-x",
        operation="demo",
        record_status="completed",
        inputs={},
        outputs={},
        tags=[],
    )
    defaults.update(kw)
    return Record(**defaults)


def test_query_simple_equality():
    rs = [
        _rec(operation="a", outputs={"score": 0.1}),
        _rec(operation="b", outputs={"score": 0.9}),
    ]
    got = query.apply(rs, "record.operation = 'b'")
    assert [r.operation for r in got] == ["b"]


def test_query_and_with_numeric():
    rs = [
        _rec(operation="a", outputs={"score": 0.1}),
        _rec(operation="b", outputs={"score": 0.9}),
        _rec(operation="b", outputs={"score": 1.5}),
    ]
    got = query.apply(rs, "record.operation = 'b' and outputs.score >= 1.0")
    assert [r.outputs["score"] for r in got] == [1.5]


def test_query_tags_membership():
    rs = [
        _rec(tags=["sensor"]),
        _rec(tags=["magnet"]),
        _rec(tags=["sensor", "demo"]),
    ]
    got = query.apply(rs, "tags = 'sensor'")
    assert len(got) == 2


def test_query_tags_list():
    rs = [_rec(tags=["a"]), _rec(tags=["b"]), _rec(tags=["c"])]
    got = query.apply(rs, "tags in ['a','c']")
    assert len(got) == 2


def test_query_bad_filter_raises():
    with pytest.raises(query.QueryError):
        query.apply([_rec()], "bogus")


# ---------------------------------------------------------------------------
# EstimationEngine
# ---------------------------------------------------------------------------


def test_estimation_uses_declared_then_default(make_lab):
    with make_lab() as lab:
        eng = EstimationEngine(lab)
        est = eng.estimate("stub")
        # Stub tool registered via conftest has no typical_duration_s → default.
        assert est.source in ("declared", "default")


def test_estimation_median_from_history(make_lab):
    with make_lab() as lab:
        # Manually inject completed records through the ledger so the engine has samples.
        session = lab.new_session()
        for ms in (1000, 2000, 3000):
            rec = Record(
                lab_id=lab.lab_id,
                session_id=session.id,
                operation="demo_q",
                record_status="completed",
                resource_name="pc-1",
                duration_ms=ms,
                finalised_at=datetime.now(UTC),
                outputs={"score": 0.5},
            )
            asyncio.run(lab.ledger.append(rec))
        eng = EstimationEngine(lab)
        est = eng.estimate("demo_q", resource_name="pc-1")
        assert est.source == "measured"
        assert est.seconds == pytest.approx(2.0, abs=0.001)
        assert est.n_samples == 3


def test_eta_projection(make_lab):
    with make_lab() as lab:
        session = lab.new_session()
        # One running record + one pending on the same resource → must sum.
        running = Record(
            lab_id=lab.lab_id,
            campaign_id="camp-eta",
            session_id=session.id,
            operation="demo_q",
            record_status="running",
            resource_name="pc-1",
            created_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        pending = Record(
            lab_id=lab.lab_id,
            campaign_id="camp-eta",
            session_id=session.id,
            operation="demo_q",
            record_status="pending",
            resource_name="pc-1",
        )
        asyncio.run(lab.ledger.append(running))
        asyncio.run(lab.ledger.append(pending))
        eng = EstimationEngine(lab)
        eta = eng.eta_for_campaign("camp-eta")
        assert eta["pending_records"] == 1
        assert eta["running_records"] == 1
        assert eta["remaining_seconds"] >= 0.0


# ---------------------------------------------------------------------------
# Offline Claude agents — must not require ANTHROPIC_API_KEY.
# ---------------------------------------------------------------------------


def test_claude_policy_offline_falls_back_to_heuristic():
    from autolab.acceptance import GateVerdict
    from autolab.planners.base import DecisionContext

    transport = ClaudeTransport(offline=True)
    policy = ClaudePolicyProvider(transport=transport)
    rec = _rec(record_status="completed", outputs={"score": 1.0})
    ctx = DecisionContext(
        campaign_id="c1",
        record=rec,
        gate=GateVerdict(result="pass", reason="ok"),
        history=[],
        allowed_actions=(ActionType.CONTINUE, ActionType.ACCEPT),
    )
    action = policy.decide(ctx)
    # Offline transport returns {"action": "continue"}; policy enforces allowed set.
    assert action.type in (ActionType.CONTINUE, ActionType.ACCEPT)


def test_campaign_designer_offline_returns_draft():
    transport = ClaudeTransport(offline=True)
    designer = CampaignDesigner(transport=transport)
    out = designer.design("Maximise a sensor's sensitivity")
    assert "name" in out.campaign_json
    assert out.raw.offline is True
