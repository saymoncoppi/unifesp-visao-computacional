#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_dataset.py -- Unified builder for a labeled dataset of barcode
printing defects (1D and 2D symbologies).

This is the OFFICIAL dataset generator for the inspection pipeline. It builds a
balanced, labeled dataset in which every defect reproduces the visual signature
documented in the Zebra print-quality troubleshooting manuals and cross-checked
against the real reference photos in ``outros-arquivos/imgs_zebra/``.

Two families of *base* (clean) images are supported and can be mixed:

  * SYNTHETIC bases  -- barcodes rendered on the fly (python-barcode / segno /
    pystrich). Infinite scale, perfectly clean, but a synthetic texture.
  * REAL bases       -- clean real barcode crops the user supplies via
    ``--bases-dir`` (e.g. images downloaded from BarBeR or Roboflow). Applying
    the same synthetic defects on top of real barcode texture is what narrows
    the synthetic->real *domain gap*, so prefer a healthy ``--real-fraction``
    once real bases are available.

Every sample gets a class-specific defect at a randomized *severity*
(low / medium / high), plus a light capture augmentation.

Output:
    <out>/
      images/<split>/<class>/<symbology>_<idx>.png
      labels.csv           (see COLUMNS below)
      previews/<class>.png  (contact sheet used in the article)

labels.csv COLUMNS (superset of the legacy schema; the extra columns are
appended, so the existing DictReader-based loader keeps working):
    filename, split, classe, simbologia, payload, params,
    source, severity, is_scannable

Usage:
    # synthetic-only (legacy behaviour, just richer/realistic)
    python -m config.generate_dataset --out dataset --per-class 200 --seed 42

    # mix in real clean barcodes as bases (domain-gap reduction)
    python -m config.generate_dataset --per-class 400 \
        --bases-dir config/datasets/real_bases --real-fraction 0.5

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

# Standard canvas every base (synthetic or real) is fit onto, so defect
# geometry is consistent regardless of source resolution.
CANVAS = (560, 260)

# ----------------------------------------------------------------------
# CLASSES (expanded taxonomy: 9 defects + no_defect)
# ORDER defines the CNN index and MUST match config/inspector/settings.py.
# The first 7 keep their historical index; smear/cutoff/registration_shift
# are the expansion (each backed by a real Zebra reference photo/figure).
# ----------------------------------------------------------------------
CLASSES = [
    "no_defect",
    "damaged_printhead_element",  # vertical white lines (dead heating element)
    "wrinkled_ribbon",            # single clean diagonal light crease
    "burnt_spot",                 # high darkness -> dark blotches / bleed
    "light_print",                # low darkness -> global faded, mottled
    "uneven_pressure",            # lateral density gradient (one side fades)
    "dirty_printhead",            # voids -> pinpoint white gaps in the bars
    "smear",                      # NEW: multiple dragged diagonal smudges
    "cutoff",                     # NEW: straight-edge truncation to white
    "registration_shift",         # NEW: content translated / misregistered
]

# 1D symbologies (python-barcode) and 2D symbologies (segno / pystrich)
SYM_1D = ["code128", "code39", "ean13", "ean8", "itf"]
SYM_2D = ["qr", "datamatrix"]
ALL_SYM = SYM_1D + SYM_2D

SEVERITIES = ["low", "medium", "high"]
# Numeric intensity per severity level, used to scale each defect.
SEV_K = {"low": 0.35, "medium": 0.65, "high": 1.0}

# Classes that must NOT be drawn from real crops. A random real barcode crop is
# not guaranteed to be defect-free, so using one as a "no_defect" sample would
# mislabel a genuinely defective code as clean and poison the control class.
# These classes always use synthetic (guaranteed-clean) bases.
SYNTHETIC_ONLY_CLASSES = {"no_defect"}


# ----------------------------------------------------------------------
# CLEAN CODE GENERATORS (synthetic base)
# ----------------------------------------------------------------------
def _rand_payload(sym):
    """Generate a random payload string suitable for the given symbology.

    Args:
        sym: Symbology key (one of ``SYM_1D`` or ``SYM_2D``).

    Returns:
        str: A randomly generated payload. Fixed-length numeric strings for
        symbologies with strict length requirements (``ean13``, ``ean8``,
        ``itf``); alphanumeric strings otherwise.
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


def gen_1d(sym, value, size=CANVAS):
    """Render a clean 1D barcode as a grayscale image (see module docs)."""
    writer = ImageWriter()
    obj = barcode.get(sym, value, writer=writer)
    buff = io.BytesIO()
    obj.write(buff, {"module_width": 0.4, "module_height": 12.0,
                     "font_size": 10, "quiet_zone": 4, "dpi": 200})
    im = Image.open(buff).convert("L").resize(size)
    return im


def gen_qr(value, size=(300, 300)):
    """Render a clean QR code as a grayscale image (nearest-neighbor resize)."""
    q = segno.make(value, error="m")
    buff = io.BytesIO()
    q.save(buff, kind="png", scale=8, border=4)
    return Image.open(buff).convert("L").resize(size, Image.NEAREST)


def gen_datamatrix(value, size=(300, 300)):
    """Render a clean DataMatrix code as a grayscale image."""
    enc = DataMatrixEncoder(value)
    im = Image.open(io.BytesIO(enc.get_imagedata(cellsize=6))).convert("L")
    return im.resize(size, Image.NEAREST)


def _fit_canvas(im, size=CANVAS, bg=255, fill=0.92):
    """Scale a grayscale image to FILL a fixed white canvas, preserving aspect.

    The code is scaled so its larger dimension reaches ``fill`` of the canvas
    (enlarging small real crops, shrinking oversized ones), then centered. This
    is critical for REAL bases: Roboflow crops are often small, and if merely
    centered at native size the barcode would occupy a tiny central patch --
    global defects (vertical lines, spots, voids) would then land on the white
    margin instead of on the code.
    """
    im = im.convert("L")
    w, h = size
    iw, ih = im.size
    if iw == 0 or ih == 0:
        return Image.new("L", size, bg)
    scale = min(w / iw, h / ih) * fill
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    im = im.resize((nw, nh), Image.BILINEAR)
    canvas = Image.new("L", size, bg)
    canvas.paste(im, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def gen_clean(sym):
    """Generate a clean synthetic code image + payload for ``sym``."""
    v = _rand_payload(sym)
    if sym in SYM_1D:
        return gen_1d(sym, v), v
    if sym == "qr":
        return _fit_canvas(gen_qr(v)), v
    if sym == "datamatrix":
        return _fit_canvas(gen_datamatrix(v)), v
    raise ValueError(sym)


# ----------------------------------------------------------------------
# REAL BASES (clean real barcodes supplied by the user)
# ----------------------------------------------------------------------
def load_real_bases(bases_dir):
    """Index usable image files under ``bases_dir`` for use as clean bases.

    Args:
        bases_dir: Directory containing clean real barcode images (any depth).

    Returns:
        list[Path]: Sorted list of image paths (empty if the dir is missing).
    """
    if not bases_dir:
        return []
    root = Path(bases_dir)
    if not root.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in exts)


def load_real_clean(path):
    """Load a real base image as a fixed-size grayscale canvas.

    Returns ``(image, symbology)`` where ``symbology`` is inferred from the
    immediate parent folder name (so ``real_bases/qr/xxx.png`` -> ``"qr"``),
    defaulting to ``"real"``.
    """
    im = Image.open(path)
    sym = path.parent.name.lower()
    if sym not in ALL_SYM:
        sym = "real"
    return _fit_canvas(im), sym


# ----------------------------------------------------------------------
# LOW-LEVEL HELPERS
# ----------------------------------------------------------------------
def _np(im):
    """Convert a PIL image to a float32 numpy array."""
    return np.asarray(im).astype(np.float32)


def _im(a):
    """Convert a numpy array back to a clipped 8-bit grayscale PIL image."""
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "L")


def _shift(a, dy, dx, fill=255.0):
    """Shift a 2D array by (dy, dx) with a constant fill (no wrap-around)."""
    out = np.full_like(a, fill)
    h, w = a.shape
    y0s, y0d = (max(0, -dy), max(0, dy))
    x0s, x0d = (max(0, -dx), max(0, dx))
    hh = h - abs(dy)
    ww = w - abs(dx)
    if hh <= 0 or ww <= 0:
        return out
    out[y0d:y0d + hh, x0d:x0d + ww] = a[y0s:y0s + hh, x0s:x0s + ww]
    return out


def _directional_smear(a, angle_deg, length):
    """Average ``length`` copies of ``a`` shifted along ``angle_deg``.

    Produces a directional motion blur that drags the ink, matching the smear
    signature (paralell diagonal streaks) rather than an isotropic blur.
    """
    rad = np.deg2rad(angle_deg)
    dx, dy = np.cos(rad), np.sin(rad)
    acc = np.zeros_like(a)
    for t in range(length):
        acc += _shift(a, int(round(dy * t)), int(round(dx * t)), fill=255.0)
    return acc / max(1, length)


def _mottle(a, strength):
    """Multiply by a smooth low-frequency mask to fake uneven ink deposition.

    ``strength`` in [0,1]: 0 leaves ``a`` unchanged; higher values lighten the
    valleys of the mask, giving the granular/washed-out look of low darkness.
    """
    h, w = a.shape
    small = np.random.rand(max(2, h // 20), max(2, w // 20)).astype(np.float32)
    up = _np(Image.fromarray((small * 255).astype("uint8")).resize((w, h), Image.BILINEAR)) / 255.0
    return a * (1.0 - strength * (1.0 - up)) + 255.0 * strength * (1.0 - up)


def _pick_severity(sev):
    """Return a concrete severity, sampling uniformly when ``sev`` is None."""
    return sev if sev in SEV_K else random.choice(SEVERITIES)


# ----------------------------------------------------------------------
# DEFECTS (each takes an image + severity, returns (image, params))
# ----------------------------------------------------------------------
def d_no_defect(im, sev):
    """Pass an image through unchanged (the "no defect" class)."""
    return im, {}


def _ink_columns(a, margin_frac=0.06):
    """Return a per-column ink (darkness) weight, zeroed at the side margins.

    Used to place vertical defects where the code actually is, so a thin white
    line crosses the bars (visible) instead of landing on the white margin
    (invisible after the CNN's 224px downscale).
    """
    w = a.shape[1]
    col = (255.0 - a).sum(axis=0)
    m = int(w * margin_frac)
    col[:m] = 0.0
    col[w - m:] = 0.0
    return col


def d_damaged_printhead_element(im, sev):
    """Damaged printhead element -> thick continuous vertical WHITE lines.

    Ref: imgs_zebra/PrintLines.jpg. Lines are perfectly vertical, span the full
    height, and are placed on high-ink columns so they clearly cut across the
    bars. Thickness (2-5px) is chosen to survive the 224px CNN downscale.
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    h, w = a.shape
    n = 2 + int(round(k * 3))                      # 2..5 lines
    col = _ink_columns(a)
    usable = int((col > 0).sum())
    if usable >= n and col.sum() > 0:
        xs = np.random.choice(w, size=n, replace=False, p=col / col.sum())
        xs = sorted(int(x) for x in xs)
    else:
        m = max(1, int(w * 0.06))
        xs = sorted(random.sample(range(m, w - m), min(n, w - 2 * m)))
    thick = 2 + int(round(k * 3))                  # 2..5 px
    for x in xs:
        x0 = max(0, x - thick // 2)
        a[:, x0:x0 + thick] = 255
    return _im(a), {"n_lines": len(xs), "thick": thick}


def d_wrinkled_ribbon(im, sev):
    """Wrinkled ribbon -> 1-2 SHARP, bright diagonal creases (vectorized).

    Ref: imgs_zebra/Wrinkle.jpeg. A single sharp, bright diagonal crease (the
    fold of the ribbon), distinct from smear's many blurred streaks. The crease
    is thick (2-4px) and high-contrast so it survives the 224px downscale.
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    h, w = a.shape
    n = 1 + (1 if k > 0.7 else 0)
    thick = 2 + int(round(k * 2))                  # 2..4 px
    xs = np.arange(w)
    for _ in range(n):
        slope = random.uniform(0.15, 0.6) * random.choice([-1, 1])
        y0 = random.randint(int(h * 0.25), int(h * 0.75))
        ys = (y0 + slope * xs).astype(int)
        for t in range(-thick, thick + 1):
            yy = np.clip(ys + t, 0, h - 1)
            a[yy, xs] = np.minimum(255, a[yy, xs] + 175)
    return _im(a), {"n_creases": n, "thick": thick}


def d_burnt_spot(im, sev):
    """High darkness -> dark blotches and slight ink bleed.

    Ref: dark/darkness-too-high. Dark spots grow and the bars thicken (bleed).
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    h, w = a.shape
    # ink bleed: darken a dilated version of the dark regions
    dark = _np(_im(a).filter(ImageFilter.MinFilter(3)))
    a = np.minimum(a, dark + (1 - k) * 40)
    n = 4 + int(round(k * 10))
    for _ in range(n):
        cy, cx = random.randint(0, h - 1), random.randint(0, w - 1)
        r = random.randint(2, 4 + int(round(k * 6)))
        y, x = np.ogrid[:h, :w]
        a[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = 0
    return _im(a), {"n_spots": n}


def d_light_print(im, sev):
    """Low darkness -> global fade + mottled, incomplete burn-in.

    Ref: imgs_zebra/LightPrint_Large.jpeg. Blacks lift toward gray, with a
    granular/washed texture (never solid black anywhere).
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    fac = 0.65 - 0.35 * k          # contrast crush
    base = 90 + 60 * k             # lift toward white
    a = a * fac + base
    a = _mottle(a, 0.25 + 0.35 * k)
    return _im(a), {"factor": round(fac, 2), "base": round(base, 1)}


def d_uneven_pressure(im, sev):
    """Uneven printhead pressure -> smooth lateral density gradient.

    Ref: imgs_zebra/Increase pressure on the {left,right}.jpg. One side prints
    solid; the opposite side fades to mottled gray. Smooth ramp, no hard edge.
    """
    k = SEV_K[sev]
    blur = 1.0 + 1.4 * k
    a = _np(im.filter(ImageFilter.GaussianBlur(blur)))
    lo = 0.75 - 0.55 * k
    grad = np.linspace(1.0, lo, a.shape[1])[None, :]
    if random.random() < 0.5:
        grad = grad[:, ::-1]
    a = a * grad + 255.0 * (1.0 - grad)
    # mottle only the weak side (where grad is small)
    weak = _mottle(a, 0.4 * k)
    a = a * grad + weak * (1.0 - grad)
    return _im(a), {"blur": round(blur, 2), "lo": round(lo, 2)}


def d_dirty_printhead(im, sev):
    """Dirty printhead -> white voids punched into the PRINTED elements.

    Ref: voids. Debris on the head leaves pinpoint gaps in the bars/modules.
    Voids are placed only on ink (dark) pixels -- a void on the white margin is
    invisible -- and are scattered blobs (distinct from the continuous vertical
    line of a damaged element).
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    h, w = a.shape
    n = 25 + int(round(k * 55))                    # 25..80 voids
    dark_y, dark_x = np.where(a < 128)
    if len(dark_x) == 0:
        return _im(a), {"n_voids": 0}
    picks = np.random.randint(0, len(dark_x), size=n)
    for j in picks:
        cy, cx = int(dark_y[j]), int(dark_x[j])
        r = random.randint(1, 2 + int(round(k * 2)))          # 1..4 px
        y0, y1 = max(0, cy - r), min(h, cy + r + 1)
        x0, x1 = max(0, cx - r), min(w, cx + r + 1)
        yg, xg = np.ogrid[y0:y1, x0:x1]
        a[y0:y1, x0:x1][(xg - cx) ** 2 + (yg - cy) ** 2 <= r * r] = 255
    return _im(a), {"n_voids": n}


def d_smear(im, sev):
    """Smear -> several dragged diagonal smudges (ink pulled while wet).

    Ref: imgs_zebra/Smear.jpeg. A directional motion blur drags the ink, plus
    a few bright parallel scratch streaks. Distinct from wrinkle (single clean
    crease) and from uneven_pressure (smooth gradient).
    """
    k = SEV_K[sev]
    angle = random.uniform(20, 70) * random.choice([-1, 1])
    length = 4 + int(round(k * 14))
    a = _directional_smear(_np(im), angle, length)
    # a few bright drag streaks along the same direction
    h, w = a.shape
    rad = np.deg2rad(angle)
    slope = np.tan(rad)
    for _ in range(2 + int(round(k * 3))):
        y0 = random.randint(0, h - 1)
        boost = random.uniform(60, 120)
        for x in range(0, w, 1):
            yy = int(y0 + slope * (x - w / 2))
            if 0 <= yy < h:
                a[yy, x] = min(255, a[yy, x] + boost)
    return _im(a), {"angle": round(angle, 1), "length": length}


def d_cutoff(im, sev):
    """Cutoff -> the print is truncated by a hard straight edge to white.

    Ref: imgs_zebra/Cutoff_large.jpeg. Everything beyond a straight vertical or
    horizontal line is blank; no gradient. Severity = how much is removed.
    """
    k = SEV_K[sev]
    a = _np(im).copy()
    h, w = a.shape
    vertical = random.random() < 0.5
    frac = 0.15 + 0.35 * k         # fraction of the image cut away
    if vertical:
        cut = int(w * frac)
        if random.random() < 0.5:
            a[:, w - cut:] = 255
        else:
            a[:, :cut] = 255
    else:
        cut = int(h * frac)
        if random.random() < 0.5:
            a[h - cut:, :] = 255
        else:
            a[:cut, :] = 255
    return _im(a), {"vertical": vertical, "frac": round(frac, 2)}


def d_registration_shift(im, sev):
    """Registration loss -> the whole print is translated / misregistered.

    Ref: perda de registro (article figure). Content is intact but shifted off
    its expected position, exposing white on one side. Larger offset = higher
    severity. Unlike cutoff, the print is translated, not sliced mid-content.
    """
    k = SEV_K[sev]
    a = _np(im)
    h, w = a.shape
    dx = int(random.uniform(-0.20, 0.20) * w * (0.4 + k))
    dy = int(random.uniform(-0.20, 0.20) * h * (0.4 + k))
    a = _shift(a, dy, dx, fill=255.0)
    return _im(a), {"dx": dx, "dy": dy}


DEFECTS = {
    "no_defect": d_no_defect,
    "damaged_printhead_element": d_damaged_printhead_element,
    "wrinkled_ribbon": d_wrinkled_ribbon,
    "burnt_spot": d_burnt_spot,
    "light_print": d_light_print,
    "uneven_pressure": d_uneven_pressure,
    "dirty_printhead": d_dirty_printhead,
    "smear": d_smear,
    "cutoff": d_cutoff,
    "registration_shift": d_registration_shift,
}

# Structurally destructive defects: unreadable even at low severity.
_DESTRUCTIVE = {"cutoff", "registration_shift", "damaged_printhead_element"}


def scannability(cls, sev):
    """Rough heuristic label for whether the code likely still scans."""
    if cls == "no_defect":
        return "yes"
    if cls in _DESTRUCTIVE:
        return "no"
    return "yes" if sev == "low" else "no"


# ----------------------------------------------------------------------
# CAPTURE AUGMENTATION (light, applied to all samples)
# ----------------------------------------------------------------------
def augment_capture(im):
    """Apply light, realistic capture augmentation (noise/brightness/rotation)."""
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
    """Determine the train/val/test split for the i-th sample of a class."""
    ntr = int(per_class * ratios[0])
    nva = int(per_class * ratios[1])
    return "train" if i < ntr else ("val" if i < ntr + nva else "test")


def make_base(syms, real_bases, real_fraction):
    """Produce one clean base image + (symbology, payload, source).

    Chooses a real base with probability ``real_fraction`` when real bases are
    available; otherwise renders a synthetic code of a random symbology.
    """
    if real_bases and random.random() < real_fraction:
        path = random.choice(real_bases)
        base, sym = load_real_clean(path)
        return base, sym, path.stem, "real"
    sym = random.choice(syms)
    base, payload = gen_clean(sym)
    return _fit_canvas(base), sym, payload, "synthetic"


def main():
    """Generate the full dataset from command-line arguments (see module docs)."""
    ap = argparse.ArgumentParser(description="Unified barcode-defect dataset generator")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="output directory")
    ap.add_argument("--per-class", type=int, default=200, help="samples per class")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only-1d", action="store_true", help="ignore QR/DataMatrix")
    ap.add_argument("--bases-dir", default=None,
                    help="directory of clean REAL barcode images to use as bases")
    ap.add_argument("--real-fraction", type=float, default=0.5,
                    help="fraction of samples drawn from real bases (if available)")
    ap.add_argument("--severity", choices=SEVERITIES, default=None,
                    help="fix a single severity (default: random per sample)")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    syms = SYM_1D if args.only_1d else ALL_SYM

    real_bases = load_real_bases(args.bases_dir)
    if args.bases_dir:
        print(f"Real bases found in '{args.bases_dir}': {len(real_bases)}")
        if not real_bases:
            print("  (none usable -> falling back to synthetic-only)")

    rows = []
    for cls in CLASSES:
        # the control class never uses (possibly-dirty) real crops
        cls_real_fraction = 0.0 if cls in SYNTHETIC_ONLY_CLASSES else args.real_fraction
        for i in range(args.per_class):
            base, sym, payload, source = make_base(syms, real_bases, cls_real_fraction)
            sev = _pick_severity(args.severity) if cls != "no_defect" else "none"
            img, params = DEFECTS[cls](base, sev if sev != "none" else "low")
            img = augment_capture(img)
            split = split_of(i, args.per_class)
            d = os.path.join(args.out, "images", split, cls)
            os.makedirs(d, exist_ok=True)
            fname = f"{sym}_{i:04d}.png"
            img.save(os.path.join(d, fname))
            rows.append({
                "filename": f"images/{split}/{cls}/{fname}", "split": split,
                "classe": cls, "simbologia": sym, "payload": payload,
                "params": json.dumps(params, ensure_ascii=False),
                "source": source, "severity": sev,
                "is_scannable": scannability(cls, sev),
            })

    # labels.csv (legacy columns first, new columns appended)
    cols = ["filename", "split", "classe", "simbologia", "payload", "params",
            "source", "severity", "is_scannable"]
    with open(os.path.join(args.out, "labels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # previews (one contact sheet per class)
    prevdir = os.path.join(args.out, "previews")
    os.makedirs(prevdir, exist_ok=True)
    for cls in CLASSES:
        ex = [r for r in rows if r["classe"] == cls][:6]
        thumbs = [Image.open(os.path.join(args.out, r["filename"])).convert("L").resize((180, 110)) for r in ex]
        sheet = Image.new("L", (max(1, len(thumbs)) * 190, 130), 255)
        for j, t in enumerate(thumbs):
            sheet.paste(t, (j * 190 + 5, 10))
        sheet.save(os.path.join(prevdir, f"{cls}.png"))

    # summary
    from collections import Counter
    by_cls = Counter(r["classe"] for r in rows)
    by_sym = Counter(r["simbologia"] for r in rows)
    by_split = Counter(r["split"] for r in rows)
    by_source = Counter(r["source"] for r in rows)
    print(f"Total: {len(rows)} images in '{args.out}'")
    print("By class:", dict(by_cls))
    print("By symbology:", dict(by_sym))
    print("By split:", dict(by_split))
    print("By source:", dict(by_source))


if __name__ == "__main__":
    main()
