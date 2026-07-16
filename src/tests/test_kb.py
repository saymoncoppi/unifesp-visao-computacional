"""Tests for config.inspector.kb (Zebra knowledge base)."""
from __future__ import annotations

from config.inspector import settings, kb


def test_search_by_class_for_all_classes():
    for defect_class in settings.CLASSES:
        item = kb.search_by_class(defect_class)
        assert isinstance(item, dict), f"class missing a KB entry: {defect_class}"
        assert item.get("class") == defect_class
        # Probable cause and corrective action must be filled in (including no_defect).
        assert kb.localized_field(item, "probable_cause", settings.DEFAULT_LANGUAGE).strip() != ""
        assert kb.localized_field(item, "corrective_action", settings.DEFAULT_LANGUAGE).strip() != ""


def test_search_by_class_unknown_returns_none():
    assert kb.search_by_class("class_that_does_not_exist") is None
    assert kb.search_by_class("") is None


def test_search_ribbon_includes_wrinkled_ribbon():
    results = kb.search("ribbon")
    assert isinstance(results, list)
    classes = {item.get("class") for item in results}
    assert "wrinkled_ribbon" in classes


def test_search_empty_returns_empty_list():
    assert kb.search("") == []


def test_context_for_llm_returns_str():
    context = kb.context_for_llm(
        "wrinkled_ribbon",
        {"contrast": 0.4, "uniformity": 0.5, "sharpness": 0.6},
        {"readable": True, "symbology": "CODE128", "content": "CB123"},
    )
    assert isinstance(context, str)
    assert context.strip() != ""

    # Must tolerate an unknown class and empty dicts without raising.
    context2 = kb.context_for_llm("unknown_class", {}, {})
    assert isinstance(context2, str)
    assert context2.strip() != ""
