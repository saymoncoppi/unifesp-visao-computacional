"""Tests for config.inspector.diagnosis (rule-based diagnosis, no Gemini)."""
from __future__ import annotations

from config.inspector import diagnosis


def test_diagnose_by_rules_wrinkled_ribbon():
    result = diagnosis.diagnose(
        {"class": "wrinkled_ribbon"},
        {},
        {"contrast": 0.4},
        use_gemini=False,
    )
    assert isinstance(result, dict)
    assert result.get("method") == "rules"
    assert result.get("probable_cause", "").strip() != ""
    assert result.get("corrective_action", "").strip() != ""
    assert result.get("source", "").strip() != ""


def test_diagnose_nonexistent_class_does_not_raise():
    result = diagnosis.diagnose(
        {"class": "class_that_does_not_exist"},
        {},
        {},
        use_gemini=False,
    )
    assert isinstance(result, dict)
    assert result.get("method") == "rules"
    # Even without a match in the KB, generic non-empty cause/correction are returned.
    assert result.get("probable_cause", "").strip() != ""
    assert result.get("corrective_action", "").strip() != ""


def test_diagnose_empty_defect_does_not_raise():
    result = diagnosis.diagnose({}, {}, {}, use_gemini=False)
    assert isinstance(result, dict)
    assert result.get("method") == "rules"
