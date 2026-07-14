#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baixar_roboflow.py — Baixa datasets do Roboflow Universe para uso como
conjunto de TESTE de generalização (sintético -> real) do inspetor de
etiquetas.

Objetivo: obter imagens REAIS de "barcode damage" / "barcode defect" /
"label print quality" para avaliar se o modelo treinado no dataset
sintético (src/gerar_dataset.py) generaliza para fotos reais.

O download exige uma chave de API GRATUITA do Roboflow:
    https://app.roboflow.com/settings/api

------------------------------------------------------------------------
Como descobrir --workspace / --project / --version
------------------------------------------------------------------------
Na página do dataset no Roboflow (universe.roboflow.com):
    1. Abra a aba "Download Dataset".
    2. Clique em "show download code" (mostrar código de download).
    3. O snippet Python revela os três valores, no formato:

           rf.workspace("MEU-WORKSPACE").project("barcode-damage")
           project.version(1).download("folder")
                     ^^^^^^^^^^^^^^^^          ^^^^^^^^^     ^
                     --project                 --version    --format
           rf.workspace("MEU-WORKSPACE")  ->  --workspace

------------------------------------------------------------------------
Exemplos de uso
------------------------------------------------------------------------
    # Chave via argumento
    python baixar_roboflow.py \\
        --api-key SUA_CHAVE \\
        --workspace EXEMPLO \\
        --project barcode-damage \\
        --version 1 \\
        --out datasets/roboflow_barcode

    # Chave via variável de ambiente (recomendado)
    export ROBOFLOW_API_KEY=SUA_CHAVE
    python baixar_roboflow.py --workspace EXEMPLO --project barcode-damage --version 1

Dependências:
    uv pip install roboflow        # apenas o pacote
    uv sync --extra datasets       # ou via extra do pyproject.toml
"""
import os
import sys
import argparse


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Baixa um dataset do Roboflow Universe (ex.: barcode damage).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--api-key",
        default=None,
        help="Chave de API do Roboflow. Se omitida, usa a variável de "
             "ambiente ROBOFLOW_API_KEY. Obtenha em "
             "https://app.roboflow.com/settings/api",
    )
    ap.add_argument("--workspace", required=True,
                    help="Slug do workspace (rf.workspace(\"...\")).")
    ap.add_argument("--project", required=True,
                    help="Slug do projeto (.project(\"...\")).")
    ap.add_argument("--version", required=True, type=int,
                    help="Número da versão do dataset (.version(N)).")
    ap.add_argument("--format", default="folder",
                    help="Formato de exportação do Roboflow "
                         "(padrão: folder; ex.: coco, yolov8, voc, ...).")
    ap.add_argument("--out", default="datasets/roboflow",
                    help="Diretório de saída (padrão: datasets/roboflow).")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # 1) Resolve a chave de API (argumento tem prioridade sobre a env) ----------
    chave = args.api_key or os.environ.get("ROBOFLOW_API_KEY")
    if not chave:
        print(
            "ERRO: nenhuma chave de API informada.\n"
            "  - Passe --api-key SUA_CHAVE, ou\n"
            "  - Defina a variável de ambiente ROBOFLOW_API_KEY.\n"
            "Obtenha uma chave gratuita em: "
            "https://app.roboflow.com/settings/api",
            file=sys.stderr,
        )
        return 2

    # 2) Import LAZY de roboflow (só é necessário se de fato formos baixar) -----
    try:
        from roboflow import Roboflow
    except ImportError:
        print(
            "ERRO: o pacote 'roboflow' não está instalado.\n"
            "Instale com: uv pip install roboflow\n"
            "         ou: uv sync --extra datasets",
            file=sys.stderr,
        )
        return 3

    # 3) Prepara o diretório de saída ------------------------------------------
    destino = os.path.abspath(args.out)
    try:
        os.makedirs(destino, exist_ok=True)
    except OSError as e:
        print(f"ERRO: não foi possível criar o diretório de saída "
              f"'{destino}': {e}", file=sys.stderr)
        return 4

    # 4) Conecta, seleciona o projeto/versão e baixa ---------------------------
    try:
        rf = Roboflow(api_key=chave)
        proj = rf.workspace(args.workspace).project(args.project)
        ds = proj.version(args.version).download(args.format, location=destino)
    except Exception as e:  # a lib do Roboflow lança tipos variados
        print(
            "ERRO ao baixar o dataset do Roboflow:\n"
            f"  {type(e).__name__}: {e}\n"
            "Verifique se:\n"
            "  - a chave de API está correta e ativa "
            "(https://app.roboflow.com/settings/api);\n"
            "  - --workspace, --project e --version batem com o código exibido "
            "em 'Download Dataset' -> 'show download code' na página do dataset;\n"
            "  - o --format é suportado por este dataset (ex.: folder, coco, yolov8);\n"
            "  - há conexão com a internet.",
            file=sys.stderr,
        )
        return 5

    local = getattr(ds, "location", destino)
    print(f"OK: dataset baixado em '{local}'.")
    print("Use estas imagens reais como conjunto de TESTE de generalização "
          "(sintético -> real).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
