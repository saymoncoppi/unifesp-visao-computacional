#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_dataset.py -- Generates a SYNTHETIC, balanced, and labeled dataset of
barcode printing defects (1D and 2D symbologies).

Each defect reproduces the visual signature described in the Zebra ZT411/ZT421
documentation (print quality troubleshooting). The goal is to train the
system's "physical defects agent" (the multi-agent inspection pipeline).

Output:
    <out>/
      images/<split>/<class>/<symbology>_<idx>.png
      labels.csv           (filename, split, classe, simbologia, payload, params)
      previews/<class>.png (contact sheet used in the article)

Usage:
    python -m config.generate_dataset --out dataset --per-class 90 --seed 42
Dependencies:
    pip install python-barcode segno pystrich pillow numpy
"""
import argparse
import csv
import io
import json
import os
import random
from pathlib import Path

import barcode
import numpy as np
import segno
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFilter
from pystrich.datamatrix import DataMatrixEncoder

# ----------------------------------------------------------------------
# PATHS
# ----------------------------------------------------------------------
# This script lives at ``src/config/generate_dataset.py``, so the src root
# (the directory added to ``sys.path`` / used as the working root for the
# ``config`` package) is one level up.
SRC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = SRC_ROOT / "config" / "datasets" / "dataset_sintetico"

# ----------------------------------------------------------------------
# CLASSES (confirmed taxonomy: 6 defects + no_defect)
# ----------------------------------------------------------------------
CLASSES = [
    "no_defect",
    "damaged_printhead_element",  # damaged printhead element -> vertical white lines
    "wrinkled_ribbon",            # thin, diagonal light bands
    "burnt_spot",                 # high darkness -> dark blotches
    "light_print",                # low darkness -> low contrast (faded)
    "uneven_pressure",            # directional smear on one side
    "dirty_printhead",            # voids -> pinpoint white gaps in the bars
]

# 1D symbologies (python-barcode) and 2D symbologies (segno / pystrich)
SYM_1D = ["code128", "code39", "ean13", "ean8", "itf"]
SYM_2D = ["qr", "datamatrix"]
ALL_SYM = SYM_1D + SYM_2D


# ----------------------------------------------------------------------
# CLEAN CODE GENERATORS (base)
# ----------------------------------------------------------------------
def _rand_payload(sym):
    """Generate a random payload string suitable for the given symbology.

    Args:
        sym: Symbology key (one of ``SYM_1D`` or ``SYM_2D``).

    Returns:
        str: A randomly generated payload. Fixed-length numeric strings for
        symbologies with strict length requirements (``ean13``, ``ean8``,
        ``itf``); alphanumeric strings otherwise.

    Side effects:
        None (uses the global ``random`` module state).
    """
    if sym == "ean13":
        return "".join(random.choice("0123456789") for _ in range(12))
    if sym == "ean8":
        return "".join(random.choice("0123456789") for _ in range(7))
    if sym == "itf":
        return "".join(random.choice("0123456789") for _ in range(random.choice([6, 8, 10])))
    if sym == "code39":
        return "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(random.randint(6, 10)))
    # code128 / qr / datamatrix accept free-form text
    return "CB" + "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(random.randint(6, 10)))


def gen_1d(sym, value, size=(560, 260)):
    """Render a clean 1D barcode as a grayscale image.

    Args:
        sym: 1D symbology key accepted by ``python-barcode`` (e.g. ``"code128"``).
        value: Payload string to encode.
        size: Target ``(width, height)`` in pixels for the resized output.

    Returns:
        PIL.Image.Image: An "L" (grayscale) mode image of the barcode.

    Side effects:
        None (renders entirely in memory via an in-memory buffer).

    Failure modes:
        Raises whatever exception ``barcode.get`` raises for an invalid
        ``sym``/``value`` combination (e.g. wrong payload length/charset).
    """
    writer = ImageWriter()
    obj = barcode.get(sym, value, writer=writer)
    buff = io.BytesIO()
    obj.write(buff, {"module_width": 0.4, "module_height": 12.0,
                     "font_size": 10, "quiet_zone": 4, "dpi": 200})
    im = Image.open(buff).convert("L").resize(size)
    return im


def gen_qr(value, size=(300, 300)):
    """Render a clean QR code as a grayscale image.

    Args:
        value: Payload string to encode.
        size: Target ``(width, height)`` in pixels for the resized output.

    Returns:
        PIL.Image.Image: An "L" (grayscale) mode image of the QR code,
        resized with nearest-neighbor interpolation to preserve sharp
        module edges.

    Side effects:
        None (renders entirely in memory via an in-memory buffer).
    """
    q = segno.make(value, error="m")
    buff = io.BytesIO()
    q.save(buff, kind="png", scale=8, border=4)
    return Image.open(buff).convert("L").resize(size, Image.NEAREST)


def gen_datamatrix(value, size=(300, 300)):
    """Render a clean DataMatrix code as a grayscale image.

    Args:
        value: Payload string to encode.
        size: Target ``(width, height)`` in pixels for the resized output.

    Returns:
        PIL.Image.Image: An "L" (grayscale) mode image of the DataMatrix
        code, resized with nearest-neighbor interpolation to preserve sharp
        module edges.

    Side effects:
        None (renders entirely in memory via an in-memory buffer).
    """
    enc = DataMatrixEncoder(value)
    im = Image.open(io.BytesIO(enc.get_imagedata(cellsize=6))).convert("L")
    return im.resize(size, Image.NEAREST)


def gen_clean(sym):
    """Generate a clean (defect-free) code image for the given symbology.

    Dispatches to :func:`gen_1d`, :func:`gen_qr`, or :func:`gen_datamatrix`
    depending on ``sym``, using a freshly generated random payload.

    Args:
        sym: Symbology key. Must be one of ``SYM_1D`` or ``SYM_2D``.

    Returns:
        tuple[PIL.Image.Image, str]: The generated grayscale image and the
        payload string that was encoded.

    Failure modes:
        Raises ``ValueError`` if ``sym`` is not a recognized symbology.
    """
    v = _rand_payload(sym)
    if sym in SYM_1D:
        return gen_1d(sym, v), v
    if sym == "qr":
        return gen_qr(v), v
    if sym == "datamatrix":
        return gen_datamatrix(v), v
    raise ValueError(sym)


# ----------------------------------------------------------------------
# DEFECTS (transformations with randomized parameters)
# ----------------------------------------------------------------------
def _np(im):
    """Convert a PIL image to a float32 numpy array."""
    return np.asarray(im).astype(np.float32)


def _im(a):
    """Convert a numpy array back to a clipped 8-bit grayscale PIL image."""
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "L")


def d_no_defect(im):
    """Pass an image through unchanged (the "no defect" class).

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The unmodified input image and an
        empty parameter dict.
    """
    return im, {}


def d_damaged_printhead_element(im):
    """Simulate a damaged printhead element.

    Draws 1-4 thin vertical white lines at random x-positions across the
    full height of the image, mimicking the vertical white streaks caused
    by one or more failed/damaged heating elements in the printhead.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``n_lines`` (int, number of lines drawn) and ``xs``
        (list[int], x-coordinates of the lines).
    """
    a = _np(im).copy()
    h, w = a.shape
    n = random.randint(1, 4)
    xs = sorted(random.sample(range(20, w - 20), n))
    for x in xs:
        thick = random.randint(1, 3)
        a[:, x:x + thick] = 255
    return _im(a), {"n_lines": n, "xs": xs}


def d_wrinkled_ribbon(im):
    """Simulate a wrinkled thermal transfer ribbon.

    Overlays 4-8 thin diagonal bands of increased brightness, mimicking the
    light diagonal streaks produced when the ribbon wrinkles during
    printing and loses even contact with the printhead.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``n_bands`` (int, number of diagonal bands) and ``slope``
        (float, rounded diagonal slope shared by all bands).
    """
    a = _np(im).copy()
    h, w = a.shape
    n = random.randint(4, 8)
    slope = random.uniform(0.08, 0.22)
    boost = random.uniform(70, 110)
    for _ in range(n):
        y0 = random.randint(0, h - 1)
        for x in range(w):
            yy = int(y0 + slope * x) % h
            a[yy, x] = min(255, a[yy, x] + boost)
    return _im(a), {"n_bands": n, "slope": round(slope, 3)}


def d_burnt_spot(im):
    """Simulate burnt spots from an excessively high darkness setting.

    Draws 5-12 small filled dark circles at random positions, mimicking the
    dark blotches produced when the print darkness parameter is set too
    high.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``n_spots`` (int, number of dark spots drawn).
    """
    a = _np(im).copy()
    h, w = a.shape
    n = random.randint(5, 12)
    for _ in range(n):
        cy, cx = random.randint(0, h - 1), random.randint(0, w - 1)
        r = random.randint(3, 9)
        y, x = np.ogrid[:h, :w]
        a[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = 0
    return _im(a), {"n_spots": n}


def d_light_print(im):
    """Simulate faded print from an excessively low darkness setting.

    Linearly rescales pixel intensities toward white, mimicking the low
    contrast/faded appearance produced when the print darkness parameter is
    set too low.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``factor`` (float, rounded multiplicative darkness
        factor applied before the additive brightness offset).
    """
    a = _np(im).copy()
    fac = random.uniform(0.35, 0.55)
    base = random.uniform(110, 140)
    return _im(a * fac + base), {"factor": round(fac, 2)}


def d_uneven_pressure(im):
    """Simulate uneven printhead pressure across the media width.

    Applies a Gaussian blur followed by a directional brightness gradient
    (randomly left-to-right or right-to-left), mimicking the progressive
    loss of sharpness/contrast on one side of the print caused by uneven
    printhead pressure.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``blur`` (float, rounded Gaussian blur radius applied).
    """
    blur = random.uniform(1.2, 2.2)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
    lo = random.uniform(0.5, 0.7)
    grad = np.linspace(1.0, lo, a.shape[1])[None, :]
    if random.random() < 0.5:
        grad = grad[:, ::-1]
    return _im(a * grad + 255 * (1 - grad) * 0.3), {"blur": round(blur, 2)}


def d_dirty_printhead(im):
    """Simulate a dirty printhead producing void defects.

    Draws 15-40 small filled white circles ("voids") at random positions,
    mimicking the pinpoint gaps left in printed bars/modules by debris
    stuck to the printhead.

    Args:
        im: Source PIL image.

    Returns:
        tuple[PIL.Image.Image, dict]: The transformed image and a params
        dict with ``n_voids`` (int, number of void spots drawn).
    """
    a = _np(im).copy()
    h, w = a.shape
    n = random.randint(15, 40)
    for _ in range(n):
        cy, cx = random.randint(0, h - 1), random.randint(0, w - 1)
        r = random.randint(1, 3)
        y, x = np.ogrid[:h, :w]
        a[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = 255
    return _im(a), {"n_voids": n}


DEFECTS = {
    "no_defect": d_no_defect,
    "damaged_printhead_element": d_damaged_printhead_element,
    "wrinkled_ribbon": d_wrinkled_ribbon,
    "burnt_spot": d_burnt_spot,
    "light_print": d_light_print,
    "uneven_pressure": d_uneven_pressure,
    "dirty_printhead": d_dirty_printhead,
}


# ----------------------------------------------------------------------
# CAPTURE AUGMENTATION (light, applied to all samples for realistic variability)
# ----------------------------------------------------------------------
def augment_capture(im):
    """Apply light, realistic capture augmentation to an image.

    Adds Gaussian noise, jitters brightness/contrast, and randomly (50%
    chance) applies a small rotation with a white fill, mimicking the minor
    variability introduced by a camera/scanner capturing a physical label.

    Args:
        im: Source PIL image (already defect-transformed).

    Returns:
        PIL.Image.Image: The augmented grayscale image.

    Side effects:
        Consumes randomness from both ``random`` and ``numpy.random``.
    """
    a = _np(im)
    a += np.random.normal(0, random.uniform(2, 7), a.shape)   # noise
    a = a * random.uniform(0.9, 1.1) + random.uniform(-8, 8)  # brightness/contrast
    im = _im(a)
    if random.random() < 0.5:
        im = im.rotate(random.uniform(-6, 6), expand=False, fillcolor=255)
    return im


# ----------------------------------------------------------------------
# GENERATION
# ----------------------------------------------------------------------
def split_of(i, per_class, ratios=(0.70, 0.15, 0.15)):
    """Determine the dataset split for the i-th sample of a class.

    Args:
        i: Zero-based sample index within its class.
        per_class: Total number of samples generated per class.
        ratios: ``(train, val, test)`` proportions; must sum to 1.0.

    Returns:
        str: One of ``"train"``, ``"val"``, or ``"test"``.
    """
    ntr = int(per_class * ratios[0])
    nva = int(per_class * ratios[1])
    return "train" if i < ntr else ("val" if i < ntr + nva else "test")


def main():
    """Generate the full synthetic dataset from command-line arguments.

    Parses CLI arguments (``--out``, ``--per-class``, ``--seed``,
    ``--only-1d``), seeds the random number generators, then for every
    class in ``CLASSES`` generates ``--per-class`` samples: a clean code of
    a randomly chosen symbology, a class-specific defect transformation
    (via ``DEFECTS``), and a light capture augmentation. Samples are
    assigned to train/val/test splits via :func:`split_of`.

    Side effects:
        - Creates ``<out>/images/<split>/<class>/`` directories and writes
          one PNG per generated sample.
        - Writes ``<out>/labels.csv`` with columns ``filename, split,
          classe, simbologia, payload, params`` (the ``classe`` column
          holds the English class key).
        - Creates ``<out>/previews/`` and writes one contact-sheet PNG per
          class (up to 6 thumbnails each).
        - Prints a summary of totals by class, symbology, and split.

    Failure modes:
        Propagates ``ValueError`` from :func:`gen_clean` if an unknown
        symbology is selected, and any I/O error raised while creating
        directories or writing files.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="output directory for the generated dataset")
    ap.add_argument("--per-class", type=int, default=90)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only-1d", action="store_true", help="ignore QR/DataMatrix (2D symbologies)")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    syms = SYM_1D if args.only_1d else ALL_SYM

    rows = []
    for cls in CLASSES:
        for i in range(args.per_class):
            sym = random.choice(syms)
            base, payload = gen_clean(sym)
            img, params = DEFECTS[cls](base)
            img = augment_capture(img)
            split = split_of(i, args.per_class)
            d = os.path.join(args.out, "images", split, cls)
            os.makedirs(d, exist_ok=True)
            fname = f"{sym}_{i:03d}.png"
            img.save(os.path.join(d, fname))
            rows.append({"filename": f"images/{split}/{cls}/{fname}", "split": split,
                         "classe": cls, "simbologia": sym, "payload": payload,
                         "params": json.dumps(params, ensure_ascii=False)})

    # labels.csv
    with open(os.path.join(args.out, "labels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "split", "classe", "simbologia", "payload", "params"])
        w.writeheader()
        w.writerows(rows)

    # previews (one contact sheet per class)
    prevdir = os.path.join(args.out, "previews")
    os.makedirs(prevdir, exist_ok=True)
    for cls in CLASSES:
        ex = [r for r in rows if r["classe"] == cls][:6]
        thumbs = [Image.open(os.path.join(args.out, r["filename"])).convert("L").resize((180, 110)) for r in ex]
        sheet = Image.new("L", (len(thumbs) * 190, 130), 255)
        for j, t in enumerate(thumbs):
            sheet.paste(t, (j * 190 + 5, 10))
        sheet.save(os.path.join(prevdir, f"{cls}.png"))

    # summary
    from collections import Counter
    by_cls = Counter(r["classe"] for r in rows)
    by_sym = Counter(r["simbologia"] for r in rows)
    by_split = Counter(r["split"] for r in rows)
    print(f"Total: {len(rows)} images in '{args.out}'")
    print("By class:", dict(by_cls))
    print("By symbology:", dict(by_sym))
    print("By split:", dict(by_split))


if __name__ == "__main__":
    main()
