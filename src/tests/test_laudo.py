"""Testes de inspetor.laudo (esquema do laudo e montagem)."""
from __future__ import annotations

from inspetor.laudo import Laudo, montar_laudo


def test_montar_laudo_preenche_campos():
    leitura = {
        "legivel": True,
        "simbologia": "CODE128",
        "conteudo": "CB123",
        "texto_ocr": "CB123",
    }
    indicadores = {"contraste": 0.82, "uniformidade": 0.74, "nitidez": 0.6}
    defeito = {
        "classe": "ribbon_enrugado",
        "classe_pt": "Ribbon enrugado",
        "confianca": 0.91,
        "probs": {"ribbon_enrugado": 0.91},
    }
    diagnostico = {
        "causa_provavel": "Tensão/alinhamento do ribbon",
        "correcao_sugerida": "Ajustar a tensão do ribbon",
        "fundamentacao": "raciocínio",
        "fonte": "Zebra Technologies (2024)",
        "via": "regras",
    }

    laudo = montar_laudo(
        leitura=leitura,
        indicadores=indicadores,
        defeito=defeito,
        diagnostico=diagnostico,
        erros=["aviso"],
    )

    assert isinstance(laudo, Laudo)
    assert laudo.legivel is True
    assert laudo.simbologia == "CODE128"
    assert laudo.conteudo == "CB123"
    assert laudo.texto_ocr == "CB123"
    assert laudo.indicadores == indicadores
    assert laudo.defeito == defeito
    assert laudo.causa_provavel == "Tensão/alinhamento do ribbon"
    assert laudo.correcao_sugerida == "Ajustar a tensão do ribbon"
    assert laudo.fundamentacao == "raciocínio"
    assert laudo.fonte == "Zebra Technologies (2024)"
    assert laudo.via_diagnostico == "regras"
    assert laudo.confianca_geral == 0.91
    assert laudo.erros == ["aviso"]


def test_montar_laudo_tolera_campos_ausentes():
    laudo = montar_laudo(leitura={}, indicadores={}, defeito={}, diagnostico={})
    assert isinstance(laudo, Laudo)
    assert laudo.legivel is None
    assert laudo.indicadores == {}
    assert laudo.defeito == {}
    assert laudo.confianca_geral == 0.0
    assert laudo.erros == []


def test_to_dict_e_dict():
    d = Laudo().to_dict()
    assert isinstance(d, dict)
    # Deve conter as chaves do contrato do laudo.
    for chave in ("legivel", "defeito", "causa_provavel", "erros", "indicadores"):
        assert chave in d


def test_resumo_e_str_nao_vazia():
    resumo = Laudo().resumo()
    assert isinstance(resumo, str)
    assert resumo.strip() != ""

    laudo = montar_laudo(
        leitura={"legivel": True, "simbologia": "CODE128", "conteudo": "CB123"},
        indicadores={},
        defeito={"classe_pt": "Ribbon enrugado", "confianca": 0.9},
        diagnostico={"causa_provavel": "x", "correcao_sugerida": "y"},
    )
    resumo2 = laudo.resumo()
    assert isinstance(resumo2, str)
    assert resumo2.strip() != ""
