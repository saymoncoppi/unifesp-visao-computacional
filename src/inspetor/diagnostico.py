"""Diagnóstico da causa provável e da correção sugerida.

Combina o LLM (Gemini) com um fallback determinístico por regras sobre a base de
conhecimento Zebra. O Gemini é opcional: só é usado quando há chave de API
configurada e a biblioteca está disponível; qualquer falha cai graciosamente no
fallback por regras. O import de `google.genai` é sempre LAZY (dentro da função).
"""
from __future__ import annotations

import json

from inspetor import config, kb


def diagnosticar(defeito: dict, leitura: dict, indicadores: dict,
                 usar_gemini: bool = True, idioma: str = config.IDIOMA_PADRAO) -> dict:
    """Determina a causa provável e a correção sugerida para o defeito.

    Retorna um dicionário com as chaves:
    ``causa_provavel``, ``correcao_sugerida``, ``fundamentacao``, ``fonte`` e
    ``via`` ("gemini" ou "regras"). Nunca levanta exceção: em qualquer falha do
    LLM, recorre ao fallback por regras sobre a base de conhecimento.

    ``usar_gemini`` escolhe o motor: ``True`` tenta o LLM (Gemini) e cai nas
    regras se ele estiver indisponível; ``False`` força a base de conhecimento
    Zebra (regras). ``idioma`` define a língua do texto retornado.
    """
    defeito = defeito or {}
    classe = defeito.get("classe")
    idioma = config.normalizar_idioma(idioma)

    if usar_gemini and config.tem_gemini():
        resultado = _diagnosticar_com_gemini(classe, leitura, indicadores, idioma)
        if resultado is not None:
            return resultado

    return _diagnosticar_por_regras(classe, indicadores, idioma)


def _diagnosticar_com_gemini(classe: str | None, leitura: dict,
                             indicadores: dict,
                             idioma: str = config.IDIOMA_PADRAO) -> dict | None:
    """Tenta diagnosticar via Gemini. Retorna None em qualquer falha."""
    try:
        from google import genai   # import LAZY (só quando realmente for usar)

        contexto = kb.contexto_para_llm(classe, indicadores or {}, leitura or {})
        instrucao_idioma = (
            "Write your answer in English." if idioma == "en-US"
            else "Escreva em português."
        )
        prompt = (
            "Você é um especialista em impressão térmica de etiquetas Zebra.\n"
            "Com base na base de conhecimento e nos indicadores medidos abaixo, "
            "diagnostique a causa provável do defeito e a correção sugerida.\n\n"
            f"{contexto}\n\n"
            "Responda ESTRITAMENTE em JSON, sem texto extra, no formato:\n"
            '{"causa_provavel": "...", "correcao_sugerida": "...", '
            '"fundamentacao": "..."}\n'
            f"{instrucao_idioma}"
        )

        cliente = genai.Client()
        resposta = cliente.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        texto = (getattr(resposta, "text", None) or "").strip()
        dados = _extrair_json(texto)
        if not dados:
            return None

        causa = (dados.get("causa_provavel") or "").strip()
        correcao = (dados.get("correcao_sugerida") or "").strip()
        fundamentacao = (dados.get("fundamentacao") or "").strip()
        if not causa or not correcao:
            return None

        item = kb.buscar_por_classe(classe)
        fonte = item.get("fonte", kb.FONTE) if item else kb.FONTE
        return {
            "causa_provavel": causa,
            "correcao_sugerida": correcao,
            "fundamentacao": fundamentacao,
            "fonte": fonte,
            "via": "gemini",
        }
    except Exception:
        # Qualquer erro (lib ausente, rede, cota, JSON inválido) -> fallback.
        return None


def _extrair_json(texto: str) -> dict | None:
    """Extrai um objeto JSON do texto da resposta (tolerante a cercas ```)."""
    if not texto:
        return None
    try:
        return json.loads(texto)
    except Exception:
        pass
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio != -1 and fim != -1 and fim > inicio:
        try:
            return json.loads(texto[inicio:fim + 1])
        except Exception:
            return None
    return None


def _diagnosticar_por_regras(classe: str | None, indicadores: dict,
                             idioma: str = config.IDIOMA_PADRAO) -> dict:
    """Fallback determinístico usando a base de conhecimento Zebra."""
    en = config.normalizar_idioma(idioma) == "en-US"
    item = kb.buscar_por_classe(classe)
    if item is None:
        if en:
            return {
                "causa_provavel": "Cause not identified.",
                "correcao_sugerida": "Manually check the print parameters "
                                     "(darkness, speed, pressure) and the printhead "
                                     "cleanliness.",
                "fundamentacao": "Defect with no match in the Zebra knowledge base "
                                 f"(class: {classe or '—'}).",
                "fonte": kb.FONTE,
                "via": "regras",
            }
        return {
            "causa_provavel": "Causa não identificada.",
            "correcao_sugerida": "Verificar manualmente os parâmetros de impressão "
                                 "(darkness, velocidade, pressão) e a limpeza da "
                                 "cabeça.",
            "fundamentacao": "Defeito sem correspondência na base de conhecimento "
                             f"Zebra (classe: {classe or '—'}).",
            "fonte": kb.FONTE,
            "via": "regras",
        }

    ind = indicadores or {}
    aparencia = kb.campo_localizado(item, "aparencia", idioma)
    nome = config.nome_classe(classe, idioma)
    if en:
        fundamentacao = (
            f"Classification '{nome}' associated, in the Zebra knowledge base, with "
            f"the appearance: {aparencia or '—'} "
            f"Measured indicators — contrast={ind.get('contraste', '—')}, "
            f"uniformity={ind.get('uniformidade', '—')}, "
            f"sharpness={ind.get('nitidez', '—')}."
        )
    else:
        fundamentacao = (
            f"Classificação '{nome}' associada, na base de conhecimento Zebra, à "
            f"aparência: {aparencia or '—'} "
            f"Indicadores medidos — contraste={ind.get('contraste', '—')}, "
            f"uniformidade={ind.get('uniformidade', '—')}, "
            f"nitidez={ind.get('nitidez', '—')}."
        )
    return {
        "causa_provavel": kb.campo_localizado(item, "causa_provavel", idioma),
        "correcao_sugerida": kb.campo_localizado(item, "acao_corretiva", idioma),
        "fundamentacao": fundamentacao,
        "fonte": item.get("fonte", kb.FONTE),
        "via": "regras",
    }
