"""Orquestração multiagente com o ADK (Google Agent Development Kit).

Monta o grafo de agentes do inspetor de etiquetas:

    ┌────────────────── ParallelAgent ──────────────────┐
    │  LlmAgent leitura      (tool: decodificar_codigo)  │
    │  LlmAgent indicadores  (tool: estimar_indicadores) │  → em paralelo
    │  LlmAgent defeito      (tool: classificar_defeito) │
    └────────────────────────────────────────────────────┘
                              │
                    LlmAgent diagnóstico   (tool: buscar_documentacao_zebra)
                              │
                    LlmAgent laudo         (consolida em JSON)

O ``SequentialAgent`` raiz executa: [paralelo] → [diagnóstico] → [laudo].

Todo import de ``google.adk`` / ``google.genai`` é PREGUIÇOSO (feito dentro das
funções), de modo que o módulo importa mesmo sem o ADK instalado e o
``python -m py_compile`` passa. As ferramentas vêm de ``inspetor.ferramentas``.
"""
from __future__ import annotations

import inspect
import json

from inspetor import config
from inspetor.ferramentas import (
    buscar_documentacao_zebra,
    classificar_defeito,
    decodificar_codigo,
    estimar_indicadores,
)

# Modelo Gemini usado por todos os LlmAgent do grafo.
MODEL = config.GEMINI_MODEL

# Identificadores da aplicação/sessão do Runner.
_APP_NAME = "inspetor_etiquetas"
_USER_ID = "usuario"
_SESSION_ID = "sessao"


# ---------------------------------------------------------------------------
# Construção do grafo de agentes.
# ---------------------------------------------------------------------------
def construir_root_agent():
    """Constrói e retorna o ``SequentialAgent`` raiz do inspetor.

    Estrutura: um ``ParallelAgent`` com os três especialistas de percepção
    (leitura, indicadores, defeito), seguido de um ``LlmAgent`` de diagnóstico e
    de um ``LlmAgent`` que consolida o laudo em JSON. Cada especialista grava o
    resultado no estado da sessão via ``output_key``; os agentes seguintes leem
    esse estado pelos marcadores ``{leitura}`` / ``{indicadores}`` / ``{defeito}``
    / ``{diagnostico}``.

    Levanta ``ImportError`` (com dica de instalação) se o ADK não estiver
    disponível.
    """
    try:
        from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
    except ImportError as exc:
        raise ImportError(
            "google-adk não está instalado. Instale com: pip install google-adk"
        ) from exc

    # --- Especialistas de percepção (rodam em paralelo) ---------------------
    agente_leitura = LlmAgent(
        name="especialista_leitura",
        model=MODEL,
        description="Decodifica o código de barras e faz o OCR do texto da etiqueta.",
        instruction=(
            "Você é o especialista em LEITURA de códigos de barras. O usuário "
            "fornece o CAMINHO de um arquivo de imagem de etiqueta. Chame a "
            "ferramenta `decodificar_codigo` passando exatamente esse caminho "
            "como argumento. Depois, relate de forma objetiva: se o código é "
            "legível, a simbologia, o conteúdo decodificado e o texto_ocr. Não "
            "invente valores; use apenas o que a ferramenta retornar."
        ),
        tools=[decodificar_codigo],
        output_key="leitura",
    )

    agente_indicadores = LlmAgent(
        name="especialista_indicadores",
        model=MODEL,
        description="Estima contraste, uniformidade e nitidez da impressão.",
        instruction=(
            "Você é o especialista em INDICADORES DE QUALIDADE de impressão. O "
            "usuário fornece o CAMINHO de uma imagem de etiqueta. Chame a "
            "ferramenta `estimar_indicadores` passando esse caminho e relate os "
            "valores de contraste, uniformidade e nitidez (cada um entre 0 e 1). "
            "Aponte quais indicadores parecem baixos/anômalos."
        ),
        tools=[estimar_indicadores],
        output_key="indicadores",
    )

    agente_defeito = LlmAgent(
        name="especialista_defeito",
        model=MODEL,
        description="Classifica o defeito de impressão entre as 7 classes do modelo.",
        instruction=(
            "Você é o especialista em CLASSIFICAÇÃO DE DEFEITO de impressão. O "
            "usuário fornece o CAMINHO de uma imagem de etiqueta. Chame a "
            "ferramenta `classificar_defeito` passando esse caminho e relate a "
            "classe prevista (classe e classe_pt) com a respectiva confiança. Se "
            "a ferramenta retornar um erro, relate o erro sem inventar a classe."
        ),
        tools=[classificar_defeito],
        output_key="defeito",
    )

    analise_paralela = ParallelAgent(
        name="analise_perceptual_paralela",
        sub_agents=[agente_leitura, agente_indicadores, agente_defeito],
    )

    # --- Diagnóstico (consome o estado dos três especialistas) --------------
    agente_diagnostico = LlmAgent(
        name="especialista_diagnostico",
        model=MODEL,
        description="Determina a causa provável e a correção com base na documentação Zebra.",
        instruction=(
            "Você é o especialista em DIAGNÓSTICO de defeitos de impressão de "
            "etiquetas. Considere as evidências já coletadas:\n"
            "- Leitura do código: {leitura?}\n"
            "- Indicadores de qualidade: {indicadores?}\n"
            "- Defeito classificado: {defeito?}\n\n"
            "Monte uma descrição curta dos sintomas (classe do defeito + "
            "indicadores anômalos) e chame a ferramenta `buscar_documentacao_zebra` "
            "passando essa descrição. Com base no que a ferramenta retornar, "
            "informe: causa_provavel, correcao_sugerida, uma breve fundamentacao e "
            "a fonte citada. Baseie-se apenas na documentação recuperada."
        ),
        tools=[buscar_documentacao_zebra],
        output_key="diagnostico",
    )

    # --- Laudo final (consolida tudo em JSON) -------------------------------
    agente_laudo = LlmAgent(
        name="consolidador_laudo",
        model=MODEL,
        description="Consolida leitura, indicadores, defeito e diagnóstico em um laudo JSON.",
        instruction=(
            "Você consolida o LAUDO FINAL da inspeção. Reúna todas as evidências:\n"
            "- Leitura: {leitura?}\n"
            "- Indicadores: {indicadores?}\n"
            "- Defeito: {defeito?}\n"
            "- Diagnóstico: {diagnostico?}\n\n"
            "Produza um ÚNICO objeto JSON válido, sem texto antes ou depois e sem "
            "cercas de código (```), contendo exatamente estas chaves: "
            "legivel, simbologia, conteudo, texto_ocr, indicadores, defeito, "
            "causa_provavel, correcao_sugerida, fundamentacao, fonte, "
            "via_diagnostico, confianca_geral, erros. Use os valores das "
            "evidências acima; para campos ausentes use null, \"\", {} ou []. O "
            "campo via_diagnostico deve refletir a origem do diagnóstico e "
            "confianca_geral a confiança do defeito classificado."
        ),
        output_key="laudo",
    )

    root = SequentialAgent(
        name="inspetor_etiquetas_root",
        sub_agents=[analise_paralela, agente_diagnostico, agente_laudo],
    )
    return root


# ---------------------------------------------------------------------------
# Execução do grafo via Runner.
# ---------------------------------------------------------------------------
async def analisar_via_adk(caminho_imagem: str) -> dict:
    """Executa a análise da etiqueta ATRAVÉS do grafo ADK e retorna o laudo (dict).

    Cria um ``Runner`` com ``InMemorySessionService``, envia o caminho da imagem
    como mensagem do usuário, roda o grafo raiz e devolve o laudo consolidado
    (JSON emitido pelo agente de laudo, convertido em ``dict``).

    Levanta ``ImportError`` com mensagem clara se o ADK / SDK do Gemini não
    estiverem disponíveis (o pipeline direto ``ferramentas.analisar_imagem``
    continua funcionando nesse caso).
    """
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise ImportError(
            "ADK/Gemini indisponíveis para execução via agentes. "
            "Instale com: pip install google-adk google-genai "
            "(ou use o pipeline direto ferramentas.analisar_imagem)."
        ) from exc

    root_agent_local = construir_root_agent()

    servico_sessao = InMemorySessionService()
    # create_session é assíncrono nas versões recentes do ADK e síncrono nas
    # antigas — tratamos ambos os casos.
    criacao = servico_sessao.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=_SESSION_ID
    )
    if inspect.isawaitable(criacao):
        await criacao

    runner = Runner(
        agent=root_agent_local,
        app_name=_APP_NAME,
        session_service=servico_sessao,
    )

    mensagem = types.Content(
        role="user",
        parts=[types.Part(text=caminho_imagem)],
    )

    texto_final = ""
    async for evento in runner.run_async(
        user_id=_USER_ID, session_id=_SESSION_ID, new_message=mensagem
    ):
        if evento.is_final_response() and evento.content and evento.content.parts:
            partes = [p.text for p in evento.content.parts if getattr(p, "text", None)]
            if partes:
                texto_final = "".join(partes)

    return _texto_para_laudo(texto_final)


def _texto_para_laudo(texto: str) -> dict:
    """Converte o texto final do agente de laudo em ``dict``.

    Tolera cercas de código (```json ... ```) e texto avulso ao redor do JSON.
    Se não for possível interpretar como JSON, devolve um laudo mínimo com o
    texto bruto registrado em ``erros``.
    """
    bruto = (texto or "").strip()

    # 1) tentativa direta.
    try:
        return json.loads(bruto)
    except Exception:
        pass

    # 2) remove cercas de código e tenta de novo.
    limpo = bruto
    if limpo.startswith("```"):
        linhas = limpo.splitlines()
        if linhas and linhas[0].startswith("```"):
            linhas = linhas[1:]
        if linhas and linhas[-1].strip().startswith("```"):
            linhas = linhas[:-1]
        limpo = "\n".join(linhas).strip()
        try:
            return json.loads(limpo)
        except Exception:
            pass

    # 3) extrai o primeiro bloco {...} do texto.
    inicio = limpo.find("{")
    fim = limpo.rfind("}")
    if 0 <= inicio < fim:
        try:
            return json.loads(limpo[inicio:fim + 1])
        except Exception:
            pass

    # 4) fallback: laudo mínimo com o texto bruto preservado.
    return {
        "legivel": None,
        "simbologia": None,
        "conteudo": None,
        "texto_ocr": "",
        "indicadores": {},
        "defeito": {},
        "causa_provavel": "",
        "correcao_sugerida": "",
        "fundamentacao": bruto,
        "fonte": "",
        "via_diagnostico": "gemini",
        "confianca_geral": 0.0,
        "erros": ["laudo ADK não retornou JSON válido"],
    }


# ---------------------------------------------------------------------------
# Agente raiz exposto para `adk web` / `adk run`.
# Protegido por try/except: se o ADK faltar, `root_agent` fica None e o módulo
# ainda importa normalmente.
# ---------------------------------------------------------------------------
try:
    root_agent = construir_root_agent()
except Exception:
    root_agent = None
