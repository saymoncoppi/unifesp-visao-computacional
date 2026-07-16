"""Tests for config.inspector.settings (central constants)."""
from __future__ import annotations

from config.inspector import settings


def test_classes_has_seven_elements():
    assert len(settings.CLASSES) == 7


def test_classes_has_no_duplicates():
    assert len(set(settings.CLASSES)) == len(settings.CLASSES)


def test_every_class_has_pt_label():
    for defect_class in settings.CLASSES:
        assert defect_class in settings.CLASS_LABELS_PT
        assert isinstance(settings.CLASS_LABELS_PT[defect_class], str)
        assert settings.CLASS_LABELS_PT[defect_class].strip() != ""


def test_num_classes():
    assert settings.num_classes() == 7
    assert settings.num_classes() == len(settings.CLASSES)
