"""Testes de inspetor.ferramentas (pipeline direto, degradação graciosa).

``analisar_imagem`` é o baseline monolítico: NUNCA levanta por biblioteca ausente
(cv2/pyzbar/torch). Sem essas libs, ele apenas acumula avisos em ``erros`` e ainda
devolve o dicionário do laudo completo.
"""
from __future__ import annotations

from inspetor import ferramentas


def test_analisar_imagem_retorna_dict_com_chaves(imagem_teste):
    laudo = ferramentas.analisar_imagem(str(imagem_teste))

    assert isinstance(laudo, dict)
    for chave in ("legivel", "defeito", "causa_provavel", "erros"):
        assert chave in laudo, f"chave ausente no laudo: {chave}"

    assert isinstance(laudo["erros"], list)
    assert isinstance(laudo["defeito"], dict)


def test_analisar_imagem_nao_levanta_com_caminho_inexistente():
    # Mesmo com um caminho inválido, degrada graciosamente (não levanta exceção).
    laudo = ferramentas.analisar_imagem("/caminho/que/nao/existe/xyz.png")
    assert isinstance(laudo, dict)
    for chave in ("legivel", "defeito", "causa_provavel", "erros"):
        assert chave in laudo
    assert isinstance(laudo["erros"], list)


def test_buscar_documentacao_zebra_retorna_str():
    texto = ferramentas.buscar_documentacao_zebra("ribbon")
    assert isinstance(texto, str)
    assert texto.strip() != ""
