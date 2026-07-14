"""Ferramentas do inspetor: funções-ferramenta para o ADK e o pipeline direto.

Este módulo expõe quatro funções pensadas para serem usadas como *tools* pelo
Agent Development Kit (o ADK usa a docstring de cada função como descrição
apresentada ao modelo) e uma quinta função — ``analisar_imagem`` — que executa o
pipeline completo **sem** o ADK. Esse pipeline direto é o núcleo robusto usado por
CLI/API e serve de baseline monolítico: nunca levanta por biblioteca ausente,
apenas acumula avisos em ``laudo["erros"]``.

Todos os imports pesados (OpenCV, PyTorch, pyzbar, Tesseract, Gemini) ficam
encapsulados nos módulos ``inspetor.visao`` / ``inspetor.rede`` / etc., que
importam suas dependências de forma preguiçosa. Aqui no topo só entram stdlib e
imports de módulos do próprio pacote.
"""
from __future__ import annotations

from inspetor import visao, rede, diagnostico, kb, config  # noqa: F401  (config p/ consistência)
from inspetor.laudo import montar_laudo


# ---------------------------------------------------------------------------
# Ferramentas (uma por especialista) — usadas pelo ADK e pelo pipeline direto.
# ---------------------------------------------------------------------------
def decodificar_codigo(caminho_imagem: str) -> dict:
    """Decodifica o código de barras de uma etiqueta e faz o OCR do texto legível.

    Recebe o CAMINHO de uma imagem de etiqueta, decodifica o código de barras
    (simbologia + conteúdo) com ``visao.decodificar`` e acrescenta o campo
    ``texto_ocr`` com o texto humano-legível extraído por ``visao.ocr_texto``.

    Retorna um dicionário com as chaves: ``legivel`` (bool|None), ``simbologia``
    (str|None), ``conteudo`` (str|None), ``n_simbolos`` (int), ``erro`` (str|None)
    e ``texto_ocr`` (str). O OCR é complementar: se estiver indisponível, o campo
    ``texto_ocr`` vem vazio sem interromper a decodificação.
    """
    resultado = visao.decodificar(caminho_imagem)
    if not isinstance(resultado, dict):
        resultado = {
            "legivel": None,
            "simbologia": None,
            "conteudo": None,
            "n_simbolos": 0,
            "erro": "retorno inesperado de visao.decodificar",
        }

    texto_ocr = ""
    try:
        imagem = visao.carregar_imagem(caminho_imagem)
        texto_ocr = visao.ocr_texto(imagem)
    except Exception:
        # OCR é opcional; falha aqui não deve derrubar a leitura do código.
        texto_ocr = ""

    resultado["texto_ocr"] = texto_ocr or ""
    return resultado


def estimar_indicadores(caminho_imagem: str) -> dict:
    """Estima indicadores de qualidade de impressão de uma etiqueta.

    Recebe o CAMINHO de uma imagem, carrega-a em tons de cinza
    (``visao.carregar_imagem`` seguido de ``visao.para_cinza``) e calcula, via
    ``visao.indicadores``, três índices em [0, 1]: ``contraste``,
    ``uniformidade`` e ``nitidez``.

    Retorna ``{"contraste": float, "uniformidade": float, "nitidez": float}``.
    """
    imagem = visao.carregar_imagem(caminho_imagem)
    cinza = visao.para_cinza(imagem)
    return visao.indicadores(cinza)


def classificar_defeito(caminho_imagem: str) -> dict:
    """Classifica o defeito de impressão da etiqueta entre as 7 classes do modelo.

    Recebe o CAMINHO de uma imagem e usa a CNN (``rede.prever``) para prever a
    classe do defeito de impressão.

    Retorna ``{"classe": str|None, "classe_pt": str|None, "confianca": float,
    "probs": {classe: float}, "erro": str|None}``. Se o PyTorch ou o arquivo do
    modelo estiverem ausentes, ``classe`` vem nula e ``erro`` é preenchido.
    """
    return rede.prever(caminho_imagem)


def buscar_documentacao_zebra(sintomas: str) -> str:
    """Consulta a base de conhecimento Zebra e devolve as entradas relevantes.

    Recebe uma descrição textual dos ``sintomas`` (por exemplo: a classe do
    defeito prevista somada aos indicadores anômalos observados) e recupera, via
    ``kb.buscar``, as entradas da documentação Zebra mais pertinentes. Formata o
    resultado em um texto legível com aparência, causa provável, ação corretiva,
    parâmetros e fonte de cada entrada — pronto para embasar o diagnóstico.

    Retorna sempre uma string (nunca levanta).
    """
    try:
        itens = kb.buscar(sintomas)
    except Exception as exc:  # degradação graciosa: kb pode não estar disponível.
        return f"Não foi possível consultar a base de conhecimento Zebra: {exc}"

    if not itens:
        return ("Nenhuma entrada da documentação Zebra correspondeu aos sintomas "
                f"informados: {sintomas!r}.")

    blocos: list[str] = []
    for i, item in enumerate(itens, start=1):
        parametros = item.get("parametros") or []
        parametros_txt = ", ".join(str(p) for p in parametros) if parametros else "—"
        blocos.append(
            f"[{i}] Classe: {item.get('classe', '—')}\n"
            f"    Aparência: {item.get('aparencia', '—')}\n"
            f"    Causa provável: {item.get('causa_provavel', '—')}\n"
            f"    Ação corretiva: {item.get('acao_corretiva', '—')}\n"
            f"    Parâmetros: {parametros_txt}\n"
            f"    Fonte: {item.get('fonte', '—')}"
        )
    return "\n\n".join(blocos)


# ---------------------------------------------------------------------------
# Pipeline direto (sem ADK) — baseline monolítico robusto.
# ---------------------------------------------------------------------------
def analisar_imagem(caminho_imagem: str, usar_gemini: bool = True,
                    idioma: str = config.IDIOMA_PADRAO) -> dict:
    """Executa a análise completa de uma etiqueta SEM o ADK (pipeline direto).

    Encadeia, em sequência: decodificação + OCR, verificação da PRESENÇA de um
    código de barras e — só quando há código — indicadores de qualidade,
    classificação do defeito, diagnóstico da causa/correção e, por fim, a
    consolidação no laudo (``laudo.montar_laudo(...).to_dict()``). Sem código
    detectado, retorna um laudo mínimo (apenas o aviso), sem rodar a CNN nem
    chamar o LLM — economiza processamento e chamadas de API.

    É o núcleo robusto usado por CLI/API e serve de baseline monolítico: cada
    etapa é isolada em ``try/except`` e NUNCA levanta por biblioteca ausente —
    falhas e degradações são acumuladas na lista ``erros`` do laudo retornado.

    Recebe o CAMINHO da imagem e retorna o dicionário do laudo (ver
    ``inspetor.laudo.Laudo``). ``usar_gemini`` escolhe o motor de diagnóstico
    (LLM Gemini vs. base de conhecimento Zebra por regras) e ``idioma`` define a
    língua do texto do diagnóstico.
    """
    erros: list[str] = []

    def _add_erro(msg) -> None:
        """Acumula um aviso/erro na lista, deduplicando e preservando a ordem."""
        if msg is None:
            return
        texto = str(msg).strip()
        if texto and texto not in erros:
            erros.append(texto)

    # 1) Leitura do código de barras (+ OCR).
    leitura: dict = {}
    try:
        leitura = decodificar_codigo(caminho_imagem)
        if isinstance(leitura, dict) and leitura.get("erro"):
            _add_erro(f"leitura: {leitura['erro']}")
    except Exception as exc:
        _add_erro(f"leitura: {exc}")
        leitura = {}

    # 2) PRESENÇA de código de barras — decidida ANTES da inspeção pesada.
    #    Legível já implica presente; senão, tenta detectar a partir do cinza.
    codigo_detectado = bool(isinstance(leitura, dict) and leitura.get("legivel") is True)
    if not codigo_detectado:
        try:
            imagem = visao.carregar_imagem(caminho_imagem)
            cinza = visao.para_cinza(imagem)
            codigo_detectado = bool(visao.ha_codigo_de_barras(cinza)[0])
        except Exception as exc:
            _add_erro(f"codigo_detectado: {exc}")

    # 2a) CURTO-CIRCUITO: sem código de barras não há o que inspecionar.
    #     Evita rodar a CNN e chamar o LLM (Gemini) à toa e não devolve um laudo
    #     com falsa aparência de resultado útil — só o aviso.
    if not codigo_detectado:
        _add_erro("Nenhum código de barras detectado na imagem.")
        try:
            laudo = montar_laudo(
                leitura=leitura, indicadores={}, defeito={}, diagnostico={},
                codigo_detectado=False, erros=erros,
            )
            return laudo.to_dict()
        except Exception as exc:  # salvaguarda: montagem nunca derruba o pipeline
            _add_erro(f"laudo: {exc}")
            return {
                "legivel": leitura.get("legivel") if isinstance(leitura, dict) else None,
                "codigo_detectado": False,
                "simbologia": None,
                "conteudo": None,
                "texto_ocr": (leitura.get("texto_ocr", "") if isinstance(leitura, dict) else "") or "",
                "indicadores": {},
                "defeito": {},
                "causa_provavel": "",
                "correcao_sugerida": "",
                "fundamentacao": "",
                "fonte": "",
                "via_diagnostico": "",
                "confianca_geral": 0.0,
                "erros": erros,
            }

    # 3) Indicadores de qualidade de impressão.
    indicadores: dict = {}
    try:
        indicadores = estimar_indicadores(caminho_imagem)
        if isinstance(indicadores, dict) and indicadores.get("erro"):
            _add_erro(f"indicadores: {indicadores['erro']}")
    except Exception as exc:
        _add_erro(f"indicadores: {exc}")
        indicadores = {}

    # 4) Classificação do defeito (CNN).
    defeito: dict = {}
    try:
        defeito = classificar_defeito(caminho_imagem)
        if isinstance(defeito, dict) and defeito.get("erro"):
            _add_erro(f"defeito: {defeito['erro']}")
    except Exception as exc:
        _add_erro(f"defeito: {exc}")
        defeito = {}

    # 5) Diagnóstico da causa provável e correção (Gemini com fallback por regras).
    diag: dict = {}
    try:
        diag = diagnostico.diagnosticar(
            defeito=defeito, leitura=leitura, indicadores=indicadores,
            usar_gemini=usar_gemini, idioma=idioma,
        )
        if isinstance(diag, dict) and diag.get("erro"):
            _add_erro(f"diagnostico: {diag['erro']}")
    except Exception as exc:
        _add_erro(f"diagnostico: {exc}")
        diag = {}

    # 6) Consolidação no laudo.
    try:
        laudo = montar_laudo(
            leitura=leitura,
            indicadores=indicadores,
            defeito=defeito,
            diagnostico=diag,
            codigo_detectado=codigo_detectado,
            erros=erros,
        )
        return laudo.to_dict()
    except Exception as exc:
        # Salvaguarda final: montagem do laudo jamais deve derrubar o pipeline.
        _add_erro(f"laudo: {exc}")
        return {
            "legivel": leitura.get("legivel") if isinstance(leitura, dict) else None,
            "codigo_detectado": codigo_detectado,
            "simbologia": leitura.get("simbologia") if isinstance(leitura, dict) else None,
            "conteudo": leitura.get("conteudo") if isinstance(leitura, dict) else None,
            "texto_ocr": (leitura.get("texto_ocr", "") if isinstance(leitura, dict) else "") or "",
            "indicadores": indicadores or {},
            "defeito": defeito or {},
            "causa_provavel": diag.get("causa_provavel", "") if isinstance(diag, dict) else "",
            "correcao_sugerida": diag.get("correcao_sugerida", "") if isinstance(diag, dict) else "",
            "fundamentacao": diag.get("fundamentacao", "") if isinstance(diag, dict) else "",
            "fonte": diag.get("fonte", "") if isinstance(diag, dict) else "",
            "via_diagnostico": diag.get("via", "") if isinstance(diag, dict) else "",
            "confianca_geral": round(float(defeito.get("confianca", 0.0) or 0.0), 3)
            if isinstance(defeito, dict) else 0.0,
            "erros": erros,
        }
