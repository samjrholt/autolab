"""Unit tests for AcceptanceCriteria evaluation and its per-rule details."""

from __future__ import annotations

from autolab import AcceptanceCriteria, evaluate


class TestEvaluate:
    def test_no_rules_auto_passes(self):
        verdict = evaluate(None, {"x": 1})
        assert verdict.result == "pass"
        assert verdict.details == {}

    def test_empty_rules_auto_passes(self):
        verdict = evaluate(AcceptanceCriteria(rules={}), {"x": 1})
        assert verdict.result == "pass"

    def test_all_rules_pass(self):
        crit = AcceptanceCriteria(rules={"score": {">=": 0.5}, "err": {"<=": 0.1}})
        verdict = evaluate(crit, {"score": 0.9, "err": 0.05})
        assert verdict.result == "pass"
        assert set(verdict.details) == {"score", "err"}
        assert all(d.passed for d in verdict.details.values())

    def test_single_hard_failure_reports_details(self):
        crit = AcceptanceCriteria(rules={"score": {">=": 1.0}})
        verdict = evaluate(crit, {"score": 0.5})
        assert verdict.result == "fail"
        detail = verdict.details["score"]
        assert detail.passed is False
        assert detail.operator == ">="
        assert detail.threshold == 1.0
        assert detail.actual == 0.5
        assert "fails" in detail.reason

    def test_missing_output_key_is_hard_fail(self):
        crit = AcceptanceCriteria(rules={"score": {">=": 0.5}})
        verdict = evaluate(crit, {})
        assert verdict.result == "fail"
        assert verdict.details["score"].operator == "missing"
        assert verdict.details["score"].actual is None

    def test_soft_fail_key_escalates_only_when_alone(self):
        crit = AcceptanceCriteria(rules={"score": {">=": 1.0}, "err": {"<=": 0.01}})
        # Only the soft-fail key fails → soft_fail.
        verdict = evaluate(crit, {"score": 1.2, "err": 0.5}, soft_fail_keys={"err"})
        assert verdict.result == "soft_fail"
        assert verdict.details["err"].passed is False
        assert verdict.details["score"].passed is True

        # Hard key also fails → hard fail wins.
        verdict2 = evaluate(crit, {"score": 0.1, "err": 0.5}, soft_fail_keys={"err"})
        assert verdict2.result == "fail"

    def test_in_and_not_in_operators(self):
        crit = AcceptanceCriteria(
            rules={"phase": {"in": ["L10", "L12"]}, "defect": {"not_in": ["crack"]}}
        )
        assert evaluate(crit, {"phase": "L10", "defect": "void"}).result == "pass"
        assert evaluate(crit, {"phase": "B2", "defect": "void"}).result == "fail"

    def test_unknown_operator_is_hard_fail(self):
        crit = AcceptanceCriteria(rules={"score": {"~=": 1.0}})
        verdict = evaluate(crit, {"score": 1.0})
        assert verdict.result == "fail"
        assert "unknown operator" in verdict.details["score"].reason
