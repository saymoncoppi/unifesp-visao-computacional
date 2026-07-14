"""Testes de inspetor.diagnostico (diagnóstico por regras, sem Gemini)."""
from __future__ import annotations

from inspetor import diagnostico


def test_diagnostico_por_regras_ribbon_enrugado():
    resultado = diagnostico.diagnosticar(
        {"classe": "ribbon_enrugado"},
        {},
        {"contraste": 0.4},
        usar_gemini=False,
    )
    assert isinstance(resultado, dict)
    assert resultado.get("via") == "regras"
    assert resultado.get("causa_provavel", "").strip() != ""
    assert resultado.get("correcao_sugerida", "").strip() != ""
    assert resultado.get("fonte", "").strip() != ""


def test_diagnostico_classe_inexistente_nao_levanta():
    resultado = diagnostico.diagnosticar(
        {"classe": "classe_que_nao_existe"},
        {},
        {},
        usar_gemini=False,
    )
    assert isinstance(resultado, dict)
    assert resultado.get("via") == "regras"
    # Mesmo sem correspondência na KB, retorna causa/correção genéricas não vazias.
    assert resultado.get("causa_provavel", "").strip() != ""
    assert resultado.get("correcao_sugerida", "").strip() != ""


def test_diagnostico_defeito_vazio_nao_levanta():
    resultado = diagnostico.diagnosticar({}, {}, {}, usar_gemini=False)
    assert isinstance(resultado, dict)
    assert resultado.get("via") == "regras"
