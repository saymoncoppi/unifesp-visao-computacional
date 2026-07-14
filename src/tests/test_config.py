"""Testes de inspetor.config (constantes centrais)."""
from __future__ import annotations

from inspetor import config


def test_classes_tem_sete_elementos():
    assert len(config.CLASSES) == 7


def test_classes_sem_duplicatas():
    assert len(set(config.CLASSES)) == len(config.CLASSES)


def test_toda_classe_tem_rotulo_pt():
    for classe in config.CLASSES:
        assert classe in config.CLASSE_PT
        assert isinstance(config.CLASSE_PT[classe], str)
        assert config.CLASSE_PT[classe].strip() != ""


def test_num_classes():
    assert config.num_classes() == 7
    assert config.num_classes() == len(config.CLASSES)
