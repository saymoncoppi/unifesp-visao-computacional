"""Tests for config.inspector.tools (direct pipeline, graceful degradation).

``analyze_image`` is the monolithic baseline: it NEVER raises due to a missing
library (cv2/pyzbar/torch). Without those libs, it simply accumulates
warnings in ``errors`` and still returns the full report dict.
"""
from __future__ import annotations

from config.inspector import tools


def test_analyze_image_returns_dict_with_keys(test_image):
    report = tools.analyze_image(str(test_image))

    assert isinstance(report, dict)
    for key in ("readable", "defect", "probable_cause", "errors"):
        assert key in report, f"missing key in report: {key}"

    assert isinstance(report["errors"], list)
    assert isinstance(report["defect"], dict)


def test_analyze_image_does_not_raise_with_nonexistent_path():
    # Even with an invalid path, it degrades gracefully (does not raise).
    report = tools.analyze_image("/path/that/does/not/exist/xyz.png")
    assert isinstance(report, dict)
    for key in ("readable", "defect", "probable_cause", "errors"):
        assert key in report
    assert isinstance(report["errors"], list)


def test_search_zebra_docs_returns_str():
    text = tools.search_zebra_docs("ribbon")
    assert isinstance(text, str)
    assert text.strip() != ""
