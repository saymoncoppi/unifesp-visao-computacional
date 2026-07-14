"""API HTTP do inspetor de etiquetas (FastAPI).

Sobe um servidor que serve a interface de chat e expõe o pipeline de análise.

Rotas:
    GET  /          -> página de chat (app/chat.html)
    GET  /saude     -> {"status": "ok"}
    POST /analisar  -> recebe uma imagem (campo `imagem`) e devolve o laudo JSON.
                       Query opcional `adk=true` usa o grafo multiagente (ADK).

Rodar:
    # uvicorn app.api:app --reload
"""
from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from inspetor import config
from inspetor.ferramentas import analisar_imagem

# Caminho da página de chat, ao lado deste módulo.
_CHAT_HTML = Path(__file__).resolve().parent / "chat.html"

app = FastAPI(
    title="Inspetor de Etiquetas",
    description="Analisa etiquetas de código de barras e emite um laudo de defeitos.",
    version="0.1.0",
)

# Arquivos estáticos (htmx local, etc.). Servidos em /static.
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _modelo_ativo_js() -> str:
    """Nome do modelo LLM ativo (só quando há Gemini configurado), seguro p/ JS."""
    if not config.tem_gemini():
        return ""
    modelo = config.GEMINI_MODEL or ""
    # O valor vem da config/ambiente (confiável), mas remove aspas/barras por segurança
    # já que é injetado dentro de uma string JS na página.
    return modelo.replace("\\", "").replace('"', "").replace("'", "").strip()


@app.get("/", response_class=HTMLResponse)
def raiz() -> HTMLResponse:
    """Serve a interface de chat (HTML autossuficiente).

    Injeta na página o modelo LLM ativo (para o seletor "Inspetor") substituindo
    os marcadores ``__MODELO_ATIVO__`` e ``__TEM_GEMINI__``.
    """
    try:
        pagina = _CHAT_HTML.read_text(encoding="utf-8")
    except OSError as exc:
        return HTMLResponse(
            f"<h1>Interface indisponível</h1><p>{exc}</p>",
            status_code=500,
        )
    pagina = pagina.replace("__MODELO_ATIVO__", _modelo_ativo_js()).replace(
        "__TEM_GEMINI__", "true" if config.tem_gemini() else "false"
    )
    return HTMLResponse(pagina)


@app.get("/saude")
def saude() -> dict:
    """Verificação de saúde do serviço."""
    return {"status": "ok"}


@app.post("/analisar")
async def analisar(imagem: UploadFile = File(...), adk: bool = False) -> JSONResponse:
    """Recebe uma imagem, roda a análise e devolve o laudo.

    A imagem é gravada em um arquivo temporário (o pipeline trabalha com caminhos
    de arquivo) e removida ao final, independentemente do resultado.
    """
    sufixo = Path(imagem.filename or "").suffix or ".png"
    caminho_temp = None
    try:
        conteudo = await imagem.read()
        with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
            tmp.write(conteudo)
            caminho_temp = tmp.name

        if adk:
            try:
                from inspetor.agentes import analisar_via_adk

                laudo = await analisar_via_adk(caminho_temp)
            except Exception as exc:  # noqa: BLE001 - fallback deliberado
                laudo = analisar_imagem(caminho_temp)
                laudo.setdefault("erros", []).append(
                    f"ADK indisponível ({exc}); usado pipeline direto."
                )
        else:
            laudo = analisar_imagem(caminho_temp)

        return JSONResponse(laudo)
    except Exception as exc:  # noqa: BLE001 - não vazar stacktrace ao cliente
        return JSONResponse(
            {"erro": f"Falha ao analisar a imagem: {exc}"},
            status_code=500,
        )
    finally:
        if caminho_temp:
            try:
                os.remove(caminho_temp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# HTMX — fragmento HTML (cartão do laudo, estética shadcn/ui).
# ---------------------------------------------------------------------------
# Rótulos fixos do cartão, por idioma. O conteúdo dinâmico (causa/correção)
# já vem traduzido do pipeline (ver inspetor.diagnostico).
_LABELS = {
    "pt-BR": {
        "laudo_titulo": "Laudo de inspeção",
        "legivel": "Legível",
        "ilegivel": "Ilegível",
        "leitura_indisponivel": "Leitura indisponível",
        "sem_codigo": "Nenhum código de barras detectado na imagem.",
        "leitura": "Leitura",
        "texto_ocr": "Texto (OCR):",
        "nao_decodificado": "Não foi possível decodificar o código.",
        "indicadores": "Indicadores de qualidade",
        "ind_contraste": "Contraste",
        "ind_uniformidade": "Uniformidade",
        "ind_nitidez": "Nitidez",
        "defeito": "Defeito",
        "confianca": "Confiança:",
        "causa": "Causa provável",
        "correcao": "Correção sugerida",
        "fonte": "Fonte:",
        "via_regras": "regras",
        "avisos": "Avisos",
        "falha_analise": "Falha ao analisar a imagem:",
    },
    "en-US": {
        "laudo_titulo": "Inspection report",
        "legivel": "Readable",
        "ilegivel": "Unreadable",
        "leitura_indisponivel": "Reading unavailable",
        "sem_codigo": "No barcode detected in the image.",
        "leitura": "Reading",
        "texto_ocr": "Text (OCR):",
        "nao_decodificado": "The code could not be decoded.",
        "indicadores": "Quality indicators",
        "ind_contraste": "Contrast",
        "ind_uniformidade": "Uniformity",
        "ind_nitidez": "Sharpness",
        "defeito": "Defect",
        "confianca": "Confidence:",
        "causa": "Probable cause",
        "correcao": "Suggested correction",
        "fonte": "Source:",
        "via_regras": "rules",
        "avisos": "Warnings",
        "falha_analise": "Failed to analyze the image:",
    },
}

# Ordem de exibição dos indicadores e a chave de rótulo de cada um.
_INDICADORES = (
    ("contraste", "ind_contraste"),
    ("uniformidade", "ind_uniformidade"),
    ("nitidez", "ind_nitidez"),
)


def _lbl(idioma: str, chave: str) -> str:
    """Rótulo fixo do cartão no idioma pedido (fallback: pt-BR e a própria chave)."""
    tabela = _LABELS.get(config.normalizar_idioma(idioma), _LABELS["pt-BR"])
    return tabela.get(chave) or _LABELS["pt-BR"].get(chave, chave)


def _esc(valor) -> str:
    """Escapa qualquer valor vindo do servidor para inserção segura no HTML."""
    if valor is None:
        return ""
    return html.escape(str(valor))


def _pct(valor) -> str:
    """Formata uma fração [0,1] como porcentagem inteira; '—' se não numérica."""
    if isinstance(valor, (int, float)):
        return f"{round(valor * 100)}%"
    return "—"


def _largura_pct(valor) -> int:
    """Converte uma fração em largura de barra (0–100), com recorte defensivo."""
    if not isinstance(valor, (int, float)):
        return 0
    return max(0, min(100, round(valor * 100)))


def _cartao_laudo_html(laudo: dict, idioma: str = config.IDIOMA_PADRAO) -> str:
    """Monta o cartão (fragmento HTML) do laudo, no estilo dos cards shadcn/ui.

    Todo dado proveniente do laudo é escapado com ``html.escape`` antes de entrar
    no HTML. As classes CSS usadas aqui são as mesmas definidas em ``chat.html``.
    Os rótulos fixos seguem ``idioma`` (o conteúdo dinâmico já vem traduzido do
    pipeline).
    """
    idioma = config.normalizar_idioma(idioma)
    partes: list[str] = []
    partes.append('<div class="msg msg-bot">')
    partes.append('<div class="avatar">IE</div>')
    partes.append('<div class="card laudo">')

    # -- Cabeçalho do card + selo de legibilidade -------------------------
    legivel = laudo.get("legivel")
    if legivel is True:
        selo = f'<span class="badge badge-ok">{_esc(_lbl(idioma, "legivel"))}</span>'
    elif legivel is False:
        selo = f'<span class="badge badge-bad">{_esc(_lbl(idioma, "ilegivel"))}</span>'
    else:
        selo = (f'<span class="badge badge-muted">'
                f'{_esc(_lbl(idioma, "leitura_indisponivel"))}</span>')
    partes.append(
        '<div class="card-header">'
        f'<h3 class="card-title">{_esc(_lbl(idioma, "laudo_titulo"))}</h3>'
        f"{selo}"
        "</div>"
    )

    # -- Aviso destacado: nenhum código de barras na imagem ---------------
    if laudo.get("codigo_detectado") is False:
        partes.append(
            '<div class="alert alert-nocode"><div class="alert-title">'
            f"⚠️ {_esc(_lbl(idioma, 'sem_codigo'))}"
            "</div></div>"
        )
        # Sem código detectado, o laudo se resume ao aviso: nada de leitura,
        # indicadores, defeito ou diagnóstico (o pipeline nem os calcula).
        partes.append("</div>")  # .card
        partes.append("</div>")  # .msg
        return "".join(partes)

    # -- Leitura (simbologia / conteúdo / OCR) ----------------------------
    leitura_html = [
        '<div class="section"><div class="section-label">'
        f'{_esc(_lbl(idioma, "leitura"))}</div>'
    ]
    if legivel is True:
        simbologia = _esc(laudo.get("simbologia") or "?")
        conteudo = _esc(laudo.get("conteudo") or "")
        leitura_html.append(
            f'<div class="kv"><span class="k">{simbologia}:</span> '
            f'<span class="mono">{conteudo}</span></div>'
        )
    ocr = (laudo.get("texto_ocr") or "").strip()
    if ocr:
        leitura_html.append(
            f'<div class="ocr">{_esc(_lbl(idioma, "texto_ocr"))} {_esc(ocr)}</div>'
        )
    if legivel is not True and not ocr:
        leitura_html.append(
            f'<div class="section-body">{_esc(_lbl(idioma, "nao_decodificado"))}</div>'
        )
    leitura_html.append("</div>")
    partes.append("".join(leitura_html))

    # -- Indicadores (barras) --------------------------------------------
    indicadores = laudo.get("indicadores") or {}
    chaves = [(k, lbl) for k, lbl in _INDICADORES
              if isinstance(indicadores.get(k), (int, float))]
    if chaves:
        ind_html = [
            '<div class="section"><div class="section-label">'
            f'{_esc(_lbl(idioma, "indicadores"))}</div>'
        ]
        for k, lbl in chaves:
            v = indicadores.get(k)
            ind_html.append(
                '<div class="meter">'
                '<div class="meter-head">'
                f"<span>{_esc(_lbl(idioma, lbl))}</span>"
                f'<span class="val">{_pct(v)}</span>'
                "</div>"
                f'<div class="track"><span class="fill" style="width:{_largura_pct(v)}%"></span></div>'
                "</div>"
            )
        ind_html.append("</div>")
        partes.append("".join(ind_html))

    # -- Defeito (nome localizado + confiança) ---------------------------
    defeito = laudo.get("defeito") or {}
    classe = defeito.get("classe")
    if classe:
        nome = config.nome_classe(classe, idioma)
    else:
        nome = defeito.get("classe_pt") or "—"
    def_html = [
        '<div class="section"><div class="section-label">'
        f'{_esc(_lbl(idioma, "defeito"))}</div>',
        f'<div class="defect-name">{_esc(nome)}</div>',
    ]
    if isinstance(defeito.get("confianca"), (int, float)):
        def_html.append(
            f'<div class="defect-conf">{_esc(_lbl(idioma, "confianca"))} '
            f'{_pct(defeito.get("confianca"))}</div>'
        )
    def_html.append("</div>")
    partes.append("".join(def_html))

    # -- Causa provável ---------------------------------------------------
    partes.append(
        '<div class="section"><div class="section-label">'
        f'{_esc(_lbl(idioma, "causa"))}</div>'
        f'<div class="section-body">{_esc(laudo.get("causa_provavel") or "—")}</div></div>'
    )

    # -- Correção sugerida ------------------------------------------------
    partes.append(
        '<div class="section"><div class="section-label">'
        f'{_esc(_lbl(idioma, "correcao"))}</div>'
        f'<div class="section-body">{_esc(laudo.get("correcao_sugerida") or "—")}</div></div>'
    )

    # -- Fonte / via ------------------------------------------------------
    fonte = laudo.get("fonte")
    via = laudo.get("via_diagnostico")
    if fonte or via:
        rodape = []
        if fonte:
            rodape.append(f'{_lbl(idioma, "fonte")} {_esc(fonte)}')
        if via:
            via_txt = "Gemini" if via == "gemini" else (
                _lbl(idioma, "via_regras") if via == "regras" else via
            )
            rodape.append(f"via {_esc(via_txt)}")
        partes.append(f'<div class="card-footer">{"  •  ".join(rodape)}</div>')

    # -- Avisos (erros) ---------------------------------------------------
    erros = laudo.get("erros")
    if isinstance(erros, list) and erros:
        itens = "".join(f"<li>{_esc(e)}</li>" for e in erros)
        partes.append(
            '<div class="alert"><div class="alert-title">'
            f'{_esc(_lbl(idioma, "avisos"))}</div>'
            f"<ul>{itens}</ul></div>"
        )

    partes.append("</div>")  # .card
    partes.append("</div>")  # .msg
    return "".join(partes)


def _cartao_erro_html(mensagem: str) -> str:
    """Bolha de erro (fragmento) para falhas na análise."""
    return (
        '<div class="msg msg-bot">'
        '<div class="avatar">IE</div>'
        f'<div class="bubble is-error">⚠️ {_esc(mensagem)}</div>'
        "</div>"
    )


@app.post("/analisar-htmx", response_class=HTMLResponse)
async def analisar_htmx(
    imagem: UploadFile = File(...),
    idioma: str = Form(config.IDIOMA_PADRAO),
    inspetor: str = Form("llm"),
) -> HTMLResponse:
    """Versão HTMX: recebe uma imagem e devolve o cartão do laudo em HTML.

    Salva a imagem em um arquivo temporário, roda ``analisar_imagem`` e retorna
    um FRAGMENTO HTML (cartão shadcn) para ser anexado ao chat. O arquivo
    temporário é sempre removido no ``finally``.

    ``idioma`` define a língua do laudo (pt-BR/en-US) e ``inspetor`` escolhe o
    motor: ``"kb"`` força a base de conhecimento Zebra (regras); ``"llm"`` e
    ``"auto"`` dão preferência ao Gemini quando disponível, caindo nas regras
    caso contrário (o ``"auto"`` só é oferecido na UI quando há LLM configurado).
    """
    idioma = config.normalizar_idioma(idioma)
    usar_gemini = inspetor != "kb"
    sufixo = Path(imagem.filename or "").suffix or ".png"
    caminho_temp = None
    try:
        conteudo = await imagem.read()
        with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
            tmp.write(conteudo)
            caminho_temp = tmp.name

        laudo = analisar_imagem(caminho_temp, usar_gemini=usar_gemini, idioma=idioma)
        return HTMLResponse(_cartao_laudo_html(laudo, idioma))
    except Exception as exc:  # noqa: BLE001 - não vazar stacktrace ao cliente
        return HTMLResponse(
            _cartao_erro_html(f"{_lbl(idioma, 'falha_analise')} {exc}"),
            status_code=500,
        )
    finally:
        if caminho_temp:
            try:
                os.remove(caminho_temp)
            except OSError:
                pass


# uvicorn app.api:app --reload
