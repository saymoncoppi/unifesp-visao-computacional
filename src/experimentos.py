"""Harness de experimentos para o classificador de defeitos de impressão.

Roda, de forma reprodutível, os experimentos de rigor pedidos na avaliação do
artigo:

  E1  - split fixo (treino/val/teste do ``labels.csv``): treina cada arquitetura,
        seleciona o melhor por acurácia de validação e mede no teste as métricas
        completas (acurácia, precisão/revocação/F1 por classe e macro, e a matriz
        de confusão). Guarda as predições do teste para os testes estatísticos.

  E-BASE  - comparação com baselines (ResNet18 e EfficientNet-B0) sob protocolo
        idêntico ao da nossa CNN (MobileNetV3-Small): mesmos dados, splits,
        augmentação e hiperparâmetros. Reporta também nº de parâmetros e latência
        média de inferência (CPU).

  E-KFOLD - validação cruzada estratificada em k dobras sobre as 630 imagens
        (agregando todos os splits), reportando média ± desvio de acurácia e F1
        macro por arquitetura.

  E-STAT  - teste de McNemar (binomial exato) entre a nossa CNN e cada baseline,
        sobre o conjunto de teste fixo, para verificar significância estatística.

O experimento E3 (multiagente ADK x monolítico) NÃO é executado aqui: o caminho
orquestrado depende de uma chave ``GOOGLE_API_KEY`` (Gemini), ausente no ambiente
de avaliação. A classificação é idêntica nos dois caminhos (mesma ferramenta CNN);
a comparação de orquestração fica registrada como limitação/trabalho futuro.

Uso:
    python -m experimentos [--epocas N] [--lr LR] [--batch B] [--kfolds K]
                           [--seed S] [--rapido] [--saida DIR]

Todos os imports pesados (torch/torchvision/PIL) são LAZY.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

from inspetor import config

RESULTADOS_DIR = config.RAIZ / "resultados"

# Arquiteturas avaliadas: rótulo -> (nome torchvision, é a nossa proposta?)
ARQUITETURAS = [
    ("MobileNetV3-Small", "mobilenet_v3_small", True),
    ("ResNet18", "resnet18", False),
    ("EfficientNet-B0", "efficientnet_b0", False),
]


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
def ler_linhas(dataset_dir=config.DATASET_DIR) -> list[dict]:
    """Lê ``labels.csv`` e devolve as linhas com filename/split/classe."""
    dataset_dir = Path(dataset_dir)
    csv_path = dataset_dir / "labels.csv"
    linhas = []
    with open(csv_path, newline="", encoding="utf-8") as arq:
        for linha in csv.DictReader(arq):
            linhas.append(linha)
    return linhas


class DatasetEmLinhas:
    """Dataset map-style a partir de uma lista de linhas do CSV.

    Compatível por duck typing com ``torch.utils.data.DataLoader`` (implementa
    ``__len__`` e ``__getitem__``), como o restante do projeto.
    """

    def __init__(self, linhas, dataset_dir, treino: bool):
        from inspetor import rede

        self.linhas = linhas
        self.dataset_dir = Path(dataset_dir)
        self.transform = rede.transformacoes(treino=treino)
        self.classe_para_indice = {c: i for i, c in enumerate(config.CLASSES)}

    def __len__(self):
        return len(self.linhas)

    def __getitem__(self, i):
        from PIL import Image

        linha = self.linhas[i]
        img = Image.open(self.dataset_dir / linha["filename"]).convert("RGB")
        return self.transform(img), self.classe_para_indice[linha["classe"]]


def _loader(linhas, dataset_dir, treino, batch_size, num_workers=2):
    from torch.utils.data import DataLoader

    return DataLoader(
        DatasetEmLinhas(linhas, dataset_dir, treino),
        batch_size=batch_size,
        shuffle=treino,
        num_workers=num_workers,
    )


# ---------------------------------------------------------------------------
# Modelo (nossa CNN + baselines) sob o MESMO protocolo
# ---------------------------------------------------------------------------
def construir(nome_tv: str, num_classes: int, pretreinado: bool = True):
    """Constrói uma arquitetura torchvision com a cabeça trocada p/ num_classes."""
    import torch.nn as nn
    from torchvision import models

    if nome_tv == "mobilenet_v3_small":
        pesos = models.MobileNet_V3_Small_Weights.DEFAULT if pretreinado else None
        m = models.mobilenet_v3_small(weights=pesos)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
    elif nome_tv == "resnet18":
        pesos = models.ResNet18_Weights.DEFAULT if pretreinado else None
        m = models.resnet18(weights=pesos)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
    elif nome_tv == "efficientnet_b0":
        pesos = models.EfficientNet_B0_Weights.DEFAULT if pretreinado else None
        m = models.efficientnet_b0(weights=pesos)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
    else:
        raise ValueError(f"arquitetura desconhecida: {nome_tv}")
    return m


def _num_parametros(m) -> int:
    return sum(p.numel() for p in m.parameters())


def _semear(seed: int):
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def treinar_e_prever(nome_tv, treino, val, teste, dataset_dir,
                     epocas, lr, batch, seed):
    """Treina (fine-tuning completo) e devolve predições no ``teste``.

    Seleciona o melhor estado pela acurácia de validação (quando ``val`` é dado);
    caso contrário usa o estado final. Retorna dict com y_true, y_pred, val_acc e
    latência média de inferência por imagem (ms).
    """
    import torch
    import torch.nn as nn

    _semear(seed)
    disp = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = len(config.CLASSES)

    modelo = construir(nome_tv, num_classes, pretreinado=True).to(disp)
    criterio = nn.CrossEntropyLoss()
    otimizador = torch.optim.Adam(modelo.parameters(), lr=lr)  # fine-tuning completo

    ld_treino = _loader(treino, dataset_dir, True, batch)
    ld_val = _loader(val, dataset_dir, False, batch) if val else None
    ld_teste = _loader(teste, dataset_dir, False, batch)

    def acuracia(loader):
        modelo.eval()
        certos = total = 0
        with torch.no_grad():
            for x, y in loader:
                x, y = x.to(disp), y.to(disp)
                p = modelo(x).argmax(1)
                certos += int((p == y).sum().item())
                total += int(y.size(0))
        return certos / total if total else 0.0

    melhor_val = -1.0
    melhor_estado = None
    for _ in range(epocas):
        modelo.train()
        for x, y in ld_treino:
            x, y = x.to(disp), y.to(disp)
            otimizador.zero_grad()
            perda = criterio(modelo(x), y)
            perda.backward()
            otimizador.step()
        if ld_val is not None:
            va = acuracia(ld_val)
            if va > melhor_val:
                melhor_val = va
                melhor_estado = {k: v.detach().cpu().clone() for k, v in modelo.state_dict().items()}

    if melhor_estado is not None:
        modelo.load_state_dict(melhor_estado)

    # Predições no teste + latência de inferência.
    modelo.eval()
    y_true, y_pred = [], []
    t0 = time.perf_counter()
    n_imgs = 0
    with torch.no_grad():
        for x, y in ld_teste:
            x = x.to(disp)
            p = modelo(x).argmax(1).cpu().tolist()
            y_pred.extend(p)
            y_true.extend(y.tolist())
            n_imgs += len(y)
    latencia_ms = 1000.0 * (time.perf_counter() - t0) / max(n_imgs, 1)

    return {
        "y_true": y_true,
        "y_pred": y_pred,
        "val_acc": round(melhor_val, 4) if melhor_val >= 0 else None,
        "n_parametros": _num_parametros(modelo),
        "latencia_ms": round(latencia_ms, 2),
    }


# ---------------------------------------------------------------------------
# Métricas (numpy puro — sem sklearn)
# ---------------------------------------------------------------------------
def matriz_confusao(y_true, y_pred, k):
    import numpy as np

    M = np.zeros((k, k), dtype=int)
    for t, p in zip(y_true, y_pred):
        M[t, p] += 1
    return M


def metricas(y_true, y_pred):
    """Acurácia, P/R/F1 por classe e macro, e matriz de confusão."""
    import numpy as np

    k = len(config.CLASSES)
    M = matriz_confusao(y_true, y_pred, k)
    total = M.sum()
    acc = float(np.trace(M) / total) if total else 0.0

    por_classe = {}
    precisoes, revocacoes, f1s = [], [], []
    for i in range(k):
        tp = int(M[i, i])
        fp = int(M[:, i].sum() - tp)
        fn = int(M[i, :].sum() - tp)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rev = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rev / (prec + rev) if (prec + rev) else 0.0
        por_classe[config.CLASSES[i]] = {
            "precisao": round(prec, 4), "revocacao": round(rev, 4),
            "f1": round(f1, 4), "n": int(M[i, :].sum()),
        }
        precisoes.append(prec); revocacoes.append(rev); f1s.append(f1)

    return {
        "acuracia": round(acc, 4),
        "macro_precisao": round(float(np.mean(precisoes)), 4),
        "macro_revocacao": round(float(np.mean(revocacoes)), 4),
        "macro_f1": round(float(np.mean(f1s)), 4),
        "por_classe": por_classe,
        "matriz_confusao": M.tolist(),
    }


def mcnemar(y_true, pred_a, pred_b):
    """Teste de McNemar (binomial exato bicaudal) entre dois classificadores.

    b = A acerta e B erra; c = A erra e B acerta. p-valor exato via binomial
    (n=b+c, p=0.5). Robusto para amostras pequenas (não exige scipy).
    """
    b = c = 0
    for t, a, bb in zip(y_true, pred_a, pred_b):
        a_ok, b_ok = (a == t), (bb == t)
        if a_ok and not b_ok:
            b += 1
        elif b_ok and not a_ok:
            c += 1
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_valor": 1.0}
    menor = min(b, c)
    # p bicaudal = 2 * P(X <= menor), X ~ Binomial(n, 0.5), truncado em 1.0
    cauda = sum(math.comb(n, i) for i in range(menor + 1)) / (2 ** n)
    p = min(1.0, 2 * cauda)
    return {"b": b, "c": c, "p_valor": round(p, 5)}


# ---------------------------------------------------------------------------
# k-fold estratificado (manual)
# ---------------------------------------------------------------------------
def dobras_estratificadas(linhas, k, seed):
    """Divide as linhas em k dobras estratificadas por classe."""
    import random

    rng = random.Random(seed)
    por_classe: dict[str, list] = {}
    for ln in linhas:
        por_classe.setdefault(ln["classe"], []).append(ln)

    dobras = [[] for _ in range(k)]
    for classe, itens in por_classe.items():
        itens = itens[:]
        rng.shuffle(itens)
        for idx, item in enumerate(itens):
            dobras[idx % k].append(item)
    return dobras


# ---------------------------------------------------------------------------
# Orquestração dos experimentos
# ---------------------------------------------------------------------------
def rodar(epocas, lr, batch, kfolds, seed, saida_dir, rapido=False, kfold_todos=False):
    saida_dir = Path(saida_dir)
    saida_dir.mkdir(parents=True, exist_ok=True)

    linhas = ler_linhas()
    treino = [l for l in linhas if l["split"] == "train"]
    val = [l for l in linhas if l["split"] == "val"]
    teste = [l for l in linhas if l["split"] == "test"]

    arqs = ARQUITETURAS[:1] if rapido else ARQUITETURAS

    resultado = {
        "config": {
            "epocas": epocas, "lr": lr, "batch": batch, "kfolds": kfolds,
            "seed": seed, "n_treino": len(treino), "n_val": len(val),
            "n_teste": len(teste), "classes": config.CLASSES,
        },
        "split_fixo": {},
        "kfold": {},
        "mcnemar": {},
    }

    # ---- E1 + baselines no split fixo ----
    predicoes = {}
    for rotulo, nome_tv, _ in arqs:
        print(f"[split-fixo] treinando {rotulo} ...", flush=True)
        t0 = time.time()
        r = treinar_e_prever(nome_tv, treino, val, teste, config.DATASET_DIR,
                             epocas, lr, batch, seed)
        m = metricas(r["y_true"], r["y_pred"])
        m.update({
            "val_acc": r["val_acc"], "n_parametros": r["n_parametros"],
            "latencia_ms": r["latencia_ms"], "tempo_treino_s": round(time.time() - t0, 1),
        })
        resultado["split_fixo"][rotulo] = m
        predicoes[rotulo] = (r["y_true"], r["y_pred"])
        print(f"[split-fixo] {rotulo}: acc={m['acuracia']} macroF1={m['macro_f1']} "
              f"({m['tempo_treino_s']}s)", flush=True)
        # salva incremental
        (saida_dir / "resultados.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- McNemar: nossa CNN vs cada baseline (mesmo teste) ----
    if "MobileNetV3-Small" in predicoes:
        yt, yp_nosso = predicoes["MobileNetV3-Small"]
        for rotulo, (_, yp_base) in predicoes.items():
            if rotulo == "MobileNetV3-Small":
                continue
            resultado["mcnemar"][f"MobileNetV3-Small vs {rotulo}"] = mcnemar(yt, yp_nosso, yp_base)

    # ---- E-KFOLD estratificado ----
    # Por padrão, valida por k-fold apenas a arquitetura proposta (estabilidade do
    # nosso modelo); os baselines são comparados no teste fixo + McNemar. Use
    # --kfold-todos para rodar k-fold em todas (bem mais custoso em CPU).
    arqs_kfold = arqs if kfold_todos else [a for a in arqs if a[2]]
    dobras = dobras_estratificadas(linhas, kfolds, seed)
    for rotulo, nome_tv, _ in arqs_kfold:
        accs, f1s = [], []
        for i in range(kfolds):
            teste_f = dobras[i]
            treino_f = [x for j in range(kfolds) if j != i for x in dobras[j]]
            print(f"[kfold] {rotulo} dobra {i + 1}/{kfolds} ...", flush=True)
            r = treinar_e_prever(nome_tv, treino_f, None, teste_f, config.DATASET_DIR,
                                 epocas, lr, batch, seed + i)
            m = metricas(r["y_true"], r["y_pred"])
            accs.append(m["acuracia"]); f1s.append(m["macro_f1"])
        import numpy as np
        resultado["kfold"][rotulo] = {
            "acuracia_media": round(float(np.mean(accs)), 4),
            "acuracia_desvio": round(float(np.std(accs)), 4),
            "f1_media": round(float(np.mean(f1s)), 4),
            "f1_desvio": round(float(np.std(f1s)), 4),
            "acuracias": [round(a, 4) for a in accs],
            "f1s": [round(f, 4) for f in f1s],
        }
        print(f"[kfold] {rotulo}: acc={resultado['kfold'][rotulo]['acuracia_media']}"
              f"±{resultado['kfold'][rotulo]['acuracia_desvio']}", flush=True)
        (saida_dir / "resultados.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    (saida_dir / "resultados.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados salvos em {saida_dir / 'resultados.json'}", flush=True)
    return resultado


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Experimentos de rigor do classificador.")
    p.add_argument("--epocas", type=int, default=40)
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--kfolds", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rapido", action="store_true", help="só a nossa CNN (debug/timing)")
    p.add_argument("--kfold-todos", action="store_true",
                   help="roda k-fold em todas as arquiteturas (custoso em CPU)")
    p.add_argument("--saida", type=str, default=str(RESULTADOS_DIR))
    a = p.parse_args()
    rodar(a.epocas, a.lr, a.batch, a.kfolds, a.seed, a.saida, a.rapido, a.kfold_todos)
