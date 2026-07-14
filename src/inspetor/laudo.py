"""Esquema do laudo (resposta estruturada da análise de uma etiqueta)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Laudo:
    """Resultado consolidado da inspeção de uma etiqueta de código de barras."""
    legivel: bool | None = None                 # o código pôde ser decodificado?
    codigo_detectado: bool | None = None        # a imagem plausivelmente contém um código?
    simbologia: str | None = None               # ex.: "CODE128", "EAN13", "QRCODE"
    conteudo: str | None = None                 # payload decodificado
    texto_ocr: str = ""                         # texto humano-legível (Tesseract)
    indicadores: dict = field(default_factory=dict)   # {contraste, uniformidade, nitidez}
    defeito: dict = field(default_factory=dict)       # {classe, classe_pt, confianca, probs}
    causa_provavel: str = ""
    correcao_sugerida: str = ""
    fundamentacao: str = ""                     # trecho/raciocínio que embasa o diagnóstico
    fonte: str = ""                             # referência (ex.: Zebra Technologies, 2024)
    via_diagnostico: str = ""                   # "gemini" | "regras"
    confianca_geral: float = 0.0
    erros: list = field(default_factory=list)   # avisos/degradações (libs ausentes etc.)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumo(self) -> str:
        """Texto curto e amigável (para o chat/CLI)."""
        leg = "legível" if self.legivel else ("ilegível" if self.legivel is not None else "leitura indisponível")
        cls = self.defeito.get("classe_pt") or self.defeito.get("classe") or "—"
        conf = self.defeito.get("confianca")
        conf_txt = f" ({conf:.0%})" if isinstance(conf, (int, float)) else ""
        linhas = [
            f"Leitura: {leg}" + (f" — {self.simbologia}: {self.conteudo}" if self.legivel else ""),
            f"Defeito: {cls}{conf_txt}",
            f"Causa provável: {self.causa_provavel or '—'}",
            f"Correção sugerida: {self.correcao_sugerida or '—'}",
        ]
        if self.codigo_detectado is False:
            linhas.append("Aviso: nenhum código de barras detectado na imagem.")
        return "\n".join(linhas)


def montar_laudo(*, leitura: dict, indicadores: dict, defeito: dict,
                 diagnostico: dict, codigo_detectado: bool | None = None,
                 erros: list | None = None) -> Laudo:
    """Agrega as saídas dos especialistas em um Laudo.

    Espera dicionários no formato produzido por inspetor.ferramentas / visao / rede /
    diagnostico. Campos ausentes são tolerados.
    """
    conf_def = float(defeito.get("confianca", 0.0) or 0.0)
    return Laudo(
        legivel=leitura.get("legivel"),
        codigo_detectado=codigo_detectado,
        simbologia=leitura.get("simbologia"),
        conteudo=leitura.get("conteudo"),
        texto_ocr=leitura.get("texto_ocr", "") or "",
        indicadores=indicadores or {},
        defeito=defeito or {},
        causa_provavel=diagnostico.get("causa_provavel", ""),
        correcao_sugerida=diagnostico.get("correcao_sugerida", ""),
        fundamentacao=diagnostico.get("fundamentacao", ""),
        fonte=diagnostico.get("fonte", ""),
        via_diagnostico=diagnostico.get("via", ""),
        confianca_geral=round(conf_def, 3),
        erros=erros or [],
    )
