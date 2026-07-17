"""Tests for config.inspector.report (report schema and assembly)."""
from __future__ import annotations

from config.inspector.report import Report, build_report


def test_build_report_fills_fields():
    reading = {
        "readable": True,
        "symbology": "CODE128",
        "content": "CB123",
    }
    indicators = {"contrast": 0.82, "uniformity": 0.74, "sharpness": 0.6}
    defect = {
        "class": "wrinkled_ribbon",
        "class_label": "Wrinkled ribbon",
        "confidence": 0.91,
        "probs": {"wrinkled_ribbon": 0.91},
    }
    diagnosis = {
        "probable_cause": "Ribbon tension/alignment",
        "corrective_action": "Adjust the ribbon tension",
        "rationale": "reasoning",
        "source": "Zebra Technologies (2024)",
        "method": "rules",
    }

    report = build_report(
        reading=reading,
        indicators=indicators,
        defect=defect,
        diagnosis=diagnosis,
        errors=["warning"],
    )

    assert isinstance(report, Report)
    assert report.readable is True
    assert report.symbology == "CODE128"
    assert report.content == "CB123"
    assert report.indicators == indicators
    assert report.defect == defect
    assert report.probable_cause == "Ribbon tension/alignment"
    assert report.corrective_action == "Adjust the ribbon tension"
    assert report.reasoning == "reasoning"
    assert report.source == "Zebra Technologies (2024)"
    assert report.diagnosis_method == "rules"
    assert report.overall_confidence == 0.91
    assert report.errors == ["warning"]


def test_build_report_tolerates_missing_fields():
    report = build_report(reading={}, indicators={}, defect={}, diagnosis={})
    assert isinstance(report, Report)
    assert report.readable is None
    assert report.indicators == {}
    assert report.defect == {}
    assert report.overall_confidence == 0.0
    assert report.errors == []


def test_to_dict_is_dict():
    d = Report().to_dict()
    assert isinstance(d, dict)
    # Must contain the keys of the report contract.
    for key in ("readable", "defect", "probable_cause", "errors", "indicators"):
        assert key in d


def test_summary_is_non_empty_str():
    summary = Report().summary()
    assert isinstance(summary, str)
    assert summary.strip() != ""

    report = build_report(
        reading={"readable": True, "symbology": "CODE128", "content": "CB123"},
        indicators={},
        defect={"class_label": "Wrinkled ribbon", "confidence": 0.9},
        diagnosis={"probable_cause": "x", "corrective_action": "y"},
    )
    summary2 = report.summary()
    assert isinstance(summary2, str)
    assert summary2.strip() != ""
