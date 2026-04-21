"""Unit tests for the DatasetBuilder flattener."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autolab import Feature, FeatureView, Record
from autolab.dataset import DatasetBuilder, record_to_row


def _make_record(**overrides):
    base = dict(
        lab_id="lab-test",
        session_id="ses-test",
        operation="stub",
        record_status="completed",
        inputs={"x": 1, "nested": {"a": 2}},
        outputs={"score": 0.9},
        decision={"planner": "bo", "trial_number": 3},
        finalised_at=datetime.now(UTC),
        duration_ms=42,
        gate_result="pass",
        features=FeatureView(fields={"score": Feature(kind="scalar", value=0.9)}),
    )
    base.update(overrides)
    return Record(**base)


class TestRecordToRow:
    def test_fixed_columns_present(self):
        row = record_to_row(_make_record())
        for col in (
            "record_id",
            "campaign_id",
            "session_id",
            "operation",
            "module",
            "record_status",
            "gate_result",
        ):
            assert col in row

    def test_inputs_outputs_features_decision_flattened(self):
        row = record_to_row(_make_record())
        assert row["inputs.x"] == 1
        assert row["inputs.nested.a"] == 2
        assert row["outputs.score"] == 0.9
        assert row["features.score"] == 0.9
        assert row["decision.planner"] == "bo"
        assert row["decision.trial_number"] == 3


class TestDatasetBuilder:
    def test_narrowing_by_campaign_id(self):
        rec_a = _make_record(campaign_id="camp-a")
        rec_b = _make_record(campaign_id="camp-b")
        rows = DatasetBuilder([rec_a, rec_b]).for_campaign("camp-a").rows()
        assert len(rows) == 1
        assert rows[0]["campaign_id"] == "camp-a"

    def test_only_completed_filter(self):
        rec_pending = _make_record(record_status="pending")
        rec_done = _make_record(record_status="completed")
        rows = DatasetBuilder([rec_pending, rec_done]).only_completed().rows()
        assert len(rows) == 1

    def test_to_dataframe(self):
        pd = pytest.importorskip("pandas")
        rec = _make_record()
        df = DatasetBuilder([rec]).to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "outputs.score" in df.columns
        assert df["outputs.score"].iloc[0] == 0.9

    def test_empty_dataframe_has_fixed_schema(self):
        pytest.importorskip("pandas")
        df = DatasetBuilder([]).to_dataframe()
        assert "record_id" in df.columns
        assert len(df) == 0
