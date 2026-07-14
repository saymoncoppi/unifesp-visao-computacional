"""Testes de inspetor.kb (base de conhecimento Zebra)."""
from __future__ import annotations

from inspetor import config, kb


def test_buscar_por_classe_para_todas_as_classes():
    for classe in config.CLASSES:
        item = kb.buscar_por_classe(classe)
        assert isinstance(item, dict), f"classe sem entrada na KB: {classe}"
        assert item.get("classe") == classe
        # causa e ação devem estar preenchidas (inclusive sem_defeito).
        assert item.get("causa_provavel", "").strip() != ""
        assert item.get("acao_corretiva", "").strip() != ""


def test_buscar_por_classe_inexistente_retorna_none():
    assert kb.buscar_por_classe("classe_que_nao_existe") is None
    assert kb.buscar_por_classe("") is None


def test_buscar_ribbon_inclui_ribbon_enrugado():
    resultados = kb.buscar("ribbon")
    assert isinstance(resultados, list)
    classes = {item.get("classe") for item in resultados}
    assert "ribbon_enrugado" in classes


def test_buscar_vazio_retorna_lista_vazia():
    assert kb.buscar("") == []


def test_contexto_para_llm_retorna_str():
    contexto = kb.contexto_para_llm(
        "ribbon_enrugado",
        {"contraste": 0.4, "uniformidade": 0.5, "nitidez": 0.6},
        {"legivel": True, "simbologia": "CODE128", "conteudo": "CB123"},
    )
    assert isinstance(contexto, str)
    assert contexto.strip() != ""

    # Deve tolerar classe desconhecida e dicts vazios sem levantar.
    contexto2 = kb.contexto_para_llm("classe_inexistente", {}, {})
    assert isinstance(contexto2, str)
    assert contexto2.strip() != ""
