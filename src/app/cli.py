"""Interface de linha de comando do inspetor de etiquetas.

Uso:
    python -m app.cli CAMINHO [--adk] [--json]

Sem ``--adk`` executa o pipeline direto (``inspetor.ferramentas.analisar_imagem``).
Com ``--adk`` tenta o grafo multiagente (``inspetor.agentes.analisar_via_adk``) e,
se ele falhar por qualquer motivo (lib ausente, erro de execução), cai de volta
para o pipeline direto — a análise nunca deixa de acontecer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from inspetor.ferramentas import analisar_imagem


def _pct(valor) -> str:
    """Formata um número em [0, 1] como porcentagem legível; '—' se ausente."""
    if isinstance(valor, (int, float)):
        return f"{valor:.0%}"
    return "—"


def _barra(valor, largura: int = 20) -> str:
    """Barrinha textual simples para um indicador em [0, 1]."""
    try:
        fracao = max(0.0, min(1.0, float(valor)))
    except (TypeError, ValueError):
        return "—"
    cheios = int(round(fracao * largura))
    return "█" * cheios + "░" * (largura - cheios)


def formatar_resumo(laudo: dict) -> str:
    """Monta um resumo amigável e legível do laudo (dicionário)."""
    legivel = laudo.get("legivel")
    if legivel:
        estado = "legível"
    elif legivel is None:
        estado = "leitura indisponível"
    else:
        estado = "ilegível"

    linha_leitura = f"Leitura: {estado}"
    if legivel:
        simbologia = laudo.get("simbologia") or "?"
        conteudo = laudo.get("conteudo") or ""
        linha_leitura += f" — {simbologia}: {conteudo}"

    texto_ocr = (laudo.get("texto_ocr") or "").strip()

    indicadores = laudo.get("indicadores") or {}
    linhas_indicadores = []
    rotulos = {
        "contraste": "Contraste",
        "uniformidade": "Uniformidade",
        "nitidez": "Nitidez",
    }
    for chave, rotulo in rotulos.items():
        if chave in indicadores:
            valor = indicadores.get(chave)
            linhas_indicadores.append(f"    {rotulo:<12} {_barra(valor)} {_pct(valor)}")

    defeito = laudo.get("defeito") or {}
    classe = defeito.get("classe_pt") or defeito.get("classe") or "—"
    conf = defeito.get("confianca")

    partes = [
        "=" * 52,
        "  LAUDO DE INSPEÇÃO — Inspetor de Etiquetas",
        "=" * 52,
    ]
    # Aviso destacado, no topo, quando não há código de barras na imagem.
    if laudo.get("codigo_detectado") is False:
        partes.append("⚠ Nenhum código de barras detectado na imagem.")
        partes.append("-" * 52)
    partes.append(linha_leitura)
    if texto_ocr:
        partes.append(f"Texto (OCR): {texto_ocr}")
    if linhas_indicadores:
        partes.append("Indicadores de qualidade:")
        partes.extend(linhas_indicadores)
    partes.extend([
        f"Defeito: {classe} ({_pct(conf)})",
        f"Causa provável: {laudo.get('causa_provavel') or '—'}",
        f"Correção sugerida: {laudo.get('correcao_sugerida') or '—'}",
    ])

    fonte = laudo.get("fonte")
    via = laudo.get("via_diagnostico")
    if fonte or via:
        rodape = "Fonte: " + (fonte or "—")
        if via:
            rodape += f"  |  via: {via}"
        partes.append(rodape)

    erros = laudo.get("erros") or []
    if erros:
        partes.append("Avisos:")
        partes.extend(f"    - {erro}" for erro in erros)

    partes.append("=" * 52)
    return "\n".join(partes)


def _executar(caminho: str, usar_adk: bool) -> dict:
    """Roda a análise, com fallback do ADK para o pipeline direto."""
    if usar_adk:
        try:
            from inspetor.agentes import analisar_via_adk

            return asyncio.run(analisar_via_adk(caminho))
        except Exception as exc:  # noqa: BLE001 - fallback deliberado e amplo
            print(
                f"[aviso] Análise via ADK indisponível ({exc}); "
                "usando pipeline direto.",
                file=sys.stderr,
            )
    return analisar_imagem(caminho)


def main(argv: list[str] | None = None) -> int:
    # Limpa a tela do terminal ao executar (só quando a saída é um terminal).
    if sys.stdout.isatty():
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:  # noqa: BLE001 - limpeza é conveniência, nunca crítica
            pass

    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="Analisa a imagem de uma etiqueta de código de barras e emite um laudo.",
    )
    parser.add_argument("caminho", help="Caminho da imagem da etiqueta a inspecionar.")
    parser.add_argument(
        "--adk",
        action="store_true",
        help="Usa o grafo multiagente (ADK/Gemini); cai para o pipeline direto se falhar.",
    )
    parser.add_argument(
        "--json",
        dest="como_json",
        action="store_true",
        help="Imprime o laudo completo em JSON (indentado).",
    )
    args = parser.parse_args(argv)

    laudo = _executar(args.caminho, args.adk)

    if args.como_json:
        print(json.dumps(laudo, indent=2, ensure_ascii=False))
    else:
        print(formatar_resumo(laudo))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
