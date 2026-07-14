#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_dataset.py — Gera um dataset SINTETICO, balanceado e rotulado de
defeitos de impressao de codigos de barras (1D e 2D).

Cada defeito reproduz a assinatura visual descrita na documentacao Zebra
ZT411/ZT421 (troubleshooting de qualidade de impressao). O objetivo e
treinar o "agente de defeitos fisicos" do sistema multiagente.

Saida:
    <out>/
      images/<split>/<classe>/<simbologia>_<idx>.png
      labels.csv           (filename, split, classe, simbologia, payload, params)
      previews/<classe>.png (montagem para o artigo)

Uso:
    python gerar_dataset.py --out dataset --per-class 90 --seed 42
Dependencias:
    pip install python-barcode segno pystrich pillow numpy
"""
import os, io, csv, math, json, random, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import barcode
from barcode.writer import ImageWriter
import segno
from pystrich.datamatrix import DataMatrixEncoder

# ----------------------------------------------------------------------
# CLASSES (taxonomia confirmada: 6 defeitos + sem_defeito)
# ----------------------------------------------------------------------
CLASSES = [
    "sem_defeito",
    "cabeca_queimada",     # elemento da cabeca danificado -> linhas brancas verticais
    "ribbon_enrugado",     # faixas claras finas e diagonais
    "ponto_queimado",      # darkness alto -> manchas escuras
    "impressao_clara",     # darkness baixo -> baixo contraste (faded)
    "pressao_desigual",    # borrao direcional em um lado
    "cabeca_suja",         # voids -> falhas brancas pontuais nas barras
]

# Simbologias 1D (python-barcode) e 2D (segno / pystrich)
SYM_1D = ["code128", "code39", "ean13", "ean8", "itf"]
SYM_2D = ["qr", "datamatrix"]
ALL_SYM = SYM_1D + SYM_2D

# ----------------------------------------------------------------------
# GERADORES DE CODIGO LIMPO (base)
# ----------------------------------------------------------------------
def _rand_payload(sym):
    if sym == "ean13":  return "".join(random.choice("0123456789") for _ in range(12))
    if sym == "ean8":   return "".join(random.choice("0123456789") for _ in range(7))
    if sym == "itf":    return "".join(random.choice("0123456789") for _ in range(random.choice([6, 8, 10])))
    if sym == "code39": return "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(random.randint(6, 10)))
    # code128 / qr / datamatrix aceitam texto livre
    return "CB" + "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(random.randint(6, 10)))

def gen_1d(sym, value, size=(560, 260)):
    writer = ImageWriter()
    obj = barcode.get(sym, value, writer=writer)
    buff = io.BytesIO()
    obj.write(buff, {"module_width": 0.4, "module_height": 12.0,
                     "font_size": 10, "quiet_zone": 4, "dpi": 200})
    im = Image.open(buff).convert("L").resize(size)
    return im

def gen_qr(value, size=(300, 300)):
    q = segno.make(value, error="m")
    buff = io.BytesIO(); q.save(buff, kind="png", scale=8, border=4)
    return Image.open(buff).convert("L").resize(size, Image.NEAREST)

def gen_datamatrix(value, size=(300, 300)):
    enc = DataMatrixEncoder(value)
    im = Image.open(io.BytesIO(enc.get_imagedata(cellsize=6))).convert("L")
    return im.resize(size, Image.NEAREST)

def gen_clean(sym):
    v = _rand_payload(sym)
    if sym in SYM_1D:      return gen_1d(sym, v), v
    if sym == "qr":        return gen_qr(v), v
    if sym == "datamatrix":return gen_datamatrix(v), v
    raise ValueError(sym)

# ----------------------------------------------------------------------
# DEFEITOS (transformacoes com parametros aleatorios)
# ----------------------------------------------------------------------
def _np(im): return np.asarray(im).astype(np.float32)
def _im(a):  return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "L")

def d_sem_defeito(im):
    return im, {}

def d_cabeca_queimada(im):
    a = _np(im).copy(); h, w = a.shape
    n = random.randint(1, 4)
    xs = sorted(random.sample(range(20, w - 20), n))
    for x in xs:
        thick = random.randint(1, 3); a[:, x:x + thick] = 255
    return _im(a), {"n_linhas": n, "xs": xs}

def d_ribbon_enrugado(im):
    a = _np(im).copy(); h, w = a.shape
    n = random.randint(4, 8); slope = random.uniform(0.08, 0.22); boost = random.uniform(70, 110)
    for _ in range(n):
        y0 = random.randint(0, h - 1)
        for x in range(w):
            yy = int(y0 + slope * x) % h
            a[yy, x] = min(255, a[yy, x] + boost)
    return _im(a), {"n_faixas": n, "slope": round(slope, 3)}

def d_ponto_queimado(im):
    a = _np(im).copy(); h, w = a.shape
    n = random.randint(5, 12)
    for _ in range(n):
        cy, cx = random.randint(0, h - 1), random.randint(0, w - 1); r = random.randint(3, 9)
        y, x = np.ogrid[:h, :w]; a[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = 0
    return _im(a), {"n_manchas": n}

def d_impressao_clara(im):
    a = _np(im).copy(); fac = random.uniform(0.35, 0.55); base = random.uniform(110, 140)
    return _im(a * fac + base), {"fator": round(fac, 2)}

def d_pressao_desigual(im):
    blur = random.uniform(1.2, 2.2)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
    lo = random.uniform(0.5, 0.7); grad = np.linspace(1.0, lo, a.shape[1])[None, :]
    if random.random() < 0.5: grad = grad[:, ::-1]
    return _im(a * grad + 255 * (1 - grad) * 0.3), {"blur": round(blur, 2)}

def d_cabeca_suja(im):
    a = _np(im).copy(); h, w = a.shape
    n = random.randint(15, 40)
    for _ in range(n):
        cy, cx = random.randint(0, h - 1), random.randint(0, w - 1); r = random.randint(1, 3)
        y, x = np.ogrid[:h, :w]; a[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = 255
    return _im(a), {"n_voids": n}

DEFECTS = {
    "sem_defeito": d_sem_defeito,
    "cabeca_queimada": d_cabeca_queimada,
    "ribbon_enrugado": d_ribbon_enrugado,
    "ponto_queimado": d_ponto_queimado,
    "impressao_clara": d_impressao_clara,
    "pressao_desigual": d_pressao_desigual,
    "cabeca_suja": d_cabeca_suja,
}

# ----------------------------------------------------------------------
# AUMENTO DE CAPTURA (leve, aplicado a todas para variabilidade realista)
# ----------------------------------------------------------------------
def augment_capture(im):
    a = _np(im)
    a += np.random.normal(0, random.uniform(2, 7), a.shape)         # ruido
    a = a * random.uniform(0.9, 1.1) + random.uniform(-8, 8)        # brilho/contraste
    im = _im(a)
    if random.random() < 0.5:
        im = im.rotate(random.uniform(-6, 6), expand=False, fillcolor=255)
    return im

# ----------------------------------------------------------------------
# GERACAO
# ----------------------------------------------------------------------
def split_of(i, per_class, ratios=(0.70, 0.15, 0.15)):
    ntr = int(per_class * ratios[0]); nva = int(per_class * ratios[1])
    return "train" if i < ntr else ("val" if i < ntr + nva else "test")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dataset")
    ap.add_argument("--per-class", type=int, default=90)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only-1d", action="store_true", help="ignora QR/DataMatrix")
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed)
    syms = SYM_1D if args.only_1d else ALL_SYM

    rows = []
    for cls in CLASSES:
        for i in range(args.per_class):
            sym = random.choice(syms)
            base, payload = gen_clean(sym)
            img, params = DEFECTS[cls](base)
            img = augment_capture(img)
            split = split_of(i, args.per_class)
            d = os.path.join(args.out, "images", split, cls); os.makedirs(d, exist_ok=True)
            fname = f"{sym}_{i:03d}.png"; img.save(os.path.join(d, fname))
            rows.append({"filename": f"images/{split}/{cls}/{fname}", "split": split,
                         "classe": cls, "simbologia": sym, "payload": payload,
                         "params": json.dumps(params, ensure_ascii=False)})

    # labels.csv
    with open(os.path.join(args.out, "labels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "split", "classe", "simbologia", "payload", "params"])
        w.writeheader(); w.writerows(rows)

    # previews (uma montagem por classe)
    prevdir = os.path.join(args.out, "previews"); os.makedirs(prevdir, exist_ok=True)
    for cls in CLASSES:
        ex = [r for r in rows if r["classe"] == cls][:6]
        thumbs = [Image.open(os.path.join(args.out, r["filename"])).convert("L").resize((180, 110)) for r in ex]
        sheet = Image.new("L", (len(thumbs) * 190, 130), 255)
        for j, t in enumerate(thumbs): sheet.paste(t, (j * 190 + 5, 10))
        sheet.save(os.path.join(prevdir, f"{cls}.png"))

    # resumo
    from collections import Counter
    by_cls = Counter(r["classe"] for r in rows); by_sym = Counter(r["simbologia"] for r in rows)
    by_split = Counter(r["split"] for r in rows)
    print(f"Total: {len(rows)} imagens em '{args.out}'")
    print("Por classe:", dict(by_cls))
    print("Por simbologia:", dict(by_sym))
    print("Por split:", dict(by_split))

if __name__ == "__main__":
    main()
