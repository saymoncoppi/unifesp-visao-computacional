#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_barber.py -- Turn the raw BarBeR dataset into clean base crops for the
defect generator (``generate_dataset.py --bases-dir``).

BarBeR provides real barcode images with VGG/VIA 2.x annotations
(``_via_img_metadata[id] = {filename, size, regions[...]}``), where each region
carries a polygon and attributes ``Type`` (symbology), ``PPE`` and ``String``.

This tool, for every annotated region:
  1. crops the barcode's bounding box (with a quiet-zone margin so it stays
     decodable);
  2. routes the crop into a per-symbology folder under ``--out`` (all crops --
     the general pool of real bases for the DEFECT classes);
  3. runs pyzbar on the crop and, if it DECODES, also copies it under
     ``--clean-out`` (verified-clean pool -- the bases for the ``no_defect``
     control class, which must not be drawn from possibly-defective crops).

Note: pyzbar (ZBar) decodes 1D + QR but not DataMatrix/PDF417/Aztec, so the
clean pool is dominated by 1D/QR -- which is exactly what a clean control needs.

BarBeR is third-party data (per-source licenses, citation required): the crops
are gitignored and must NOT be redistributed in the app.

Usage:
    python -m config.prepare_barber \
        --barber-dir config/datasets/barber_raw \
        --out config/datasets/real_bases \
        --clean-out config/datasets/real_bases_clean
Dependencies:
    pip install pillow pyzbar   (system: libzbar0)
"""
import argparse
import json
from pathlib import Path

from PIL import Image

SRC_ROOT = Path(__file__).resolve().parents[1]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def _register_local_libzbar():
    """Point pyzbar at the bundled ``src/.native-libs/libzbar.so.0`` (no sudo).

    Linux's ``ctypes.util.find_library`` ignores ``LD_LIBRARY_PATH``, so we
    monkeypatch it to return the bundled library path for ``zbar``.
    """
    import ctypes.util
    lib = SRC_ROOT / ".native-libs" / "libzbar.so.0"
    if not lib.exists():
        return
    original = ctypes.util.find_library
    if getattr(original, "_zbar_patched", False):
        return

    def _find(name):
        return str(lib) if name == "zbar" else original(name)

    _find._zbar_patched = True
    ctypes.util.find_library = _find


_register_local_libzbar()

# Normalize BarBeR ``Type`` values to the generator's symbology folder names
# (recognized ones map to a real symbology; the rest keep a lowercased label).
SYM_MAP = {
    "EAN13": "ean13", "EAN8": "ean8", "EAN5": "ean13", "EAN2": "ean13",
    "UPCA": "upc", "UPCE": "upc", "UPCS": "upc", "UPC": "upc",
    "C128": "code128", "CODE128": "code128",
    "C39": "code39", "CODE39": "code39",
    "I25": "itf", "ITF": "itf", "INTERLEAVED25": "itf",
    "QR": "qr", "QRCODE": "qr",
    "DATAMATRIX": "datamatrix", "DM": "datamatrix",
    "PDF417": "pdf417", "AZTEC": "aztec",
    "1D": "mixed_1d", "2D": "mixed_2d",
}


def norm_symbology(t):
    """Map a BarBeR ``Type`` string to a symbology folder name."""
    if not t:
        return "mixed"
    key = str(t).strip().upper().replace("-", "").replace("_", "")
    return SYM_MAP.get(key, key.lower() or "mixed")


def bbox_from_shape(sa):
    """Return ``(x0, y0, x1, y1)`` from a VIA ``shape_attributes`` region."""
    if not sa:
        return None
    name = sa.get("name")
    if name == "polygon" and sa.get("all_points_x"):
        xs, ys = sa["all_points_x"], sa["all_points_y"]
        return min(xs), min(ys), max(xs), max(ys)
    if name == "rect":
        x, y = sa.get("x", 0), sa.get("y", 0)
        return x, y, x + sa.get("width", 0), y + sa.get("height", 0)
    if name == "ellipse":
        cx, cy, rx, ry = sa.get("cx", 0), sa.get("cy", 0), sa.get("rx", 0), sa.get("ry", 0)
        return cx - rx, cy - ry, cx + rx, cy + ry
    return None


def pad_clamp(box, w, h, pad):
    """Expand a box by ``pad`` (fraction of its longer side) and clamp to image."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    m = int(round(pad * max(bw, bh)))
    return (max(0, int(x0 - m)), max(0, int(y0 - m)),
            min(w, int(x1 + m)), min(h, int(y1 + m)))


def index_annotations(barber_dir):
    """Build ``{filename: [(bbox_shape, Type), ...]}`` from all VIA JSONs.

    Returns the map plus the number of JSON files parsed.
    """
    ann_dirs = list(Path(barber_dir).rglob("Annotations"))
    jsons = []
    for d in ann_dirs:
        jsons += list(d.rglob("*.json"))
    by_file = {}
    for jf in jsons:
        try:
            data = json.loads(jf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        meta = data.get("_via_img_metadata")
        if not isinstance(meta, dict):
            continue
        for m in meta.values():
            fn = m.get("filename")
            if not fn:
                continue
            for r in (m.get("regions") or []):
                by_file.setdefault(fn, []).append(
                    (r.get("shape_attributes"), (r.get("region_attributes") or {}).get("Type")))
    return by_file, len(jsons)


def _decodes(img):
    """True if pyzbar can decode at least one symbol in the grayscale image."""
    try:
        from pyzbar.pyzbar import decode
    except Exception:  # noqa: BLE001 - missing lib -> treat as "cannot verify"
        return None
    try:
        return len(decode(img)) > 0
    except Exception:  # noqa: BLE001
        return False


def main():
    ap = argparse.ArgumentParser(description="Prepare BarBeR crops as generator bases")
    ap.add_argument("--barber-dir", default=str(SRC_ROOT / "config" / "datasets" / "barber_raw"))
    ap.add_argument("--out", default=str(SRC_ROOT / "config" / "datasets" / "real_bases"))
    ap.add_argument("--clean-out", default=str(SRC_ROOT / "config" / "datasets" / "real_bases_clean"))
    ap.add_argument("--pad", type=float, default=0.10, help="quiet-zone margin (fraction of box)")
    ap.add_argument("--min-size", type=int, default=24, help="skip crops smaller than this (px)")
    ap.add_argument("--subdir", default="barber", help="symbology parent folder name under the pools")
    args = ap.parse_args()

    by_file, n_json = index_annotations(args.barber_dir)
    imgs = {p.name: p for p in Path(args.barber_dir).rglob("*") if p.suffix.lower() in IMG_EXTS}
    print(f"Parsed {n_json} VIA files -> {len(by_file)} annotated filenames; {len(imgs)} images on disk")

    n_all = n_clean = n_skip = n_miss = 0
    zbar_missing = False
    for fn, regions in by_file.items():
        img_path = imgs.get(fn)
        if not img_path:
            n_miss += 1
            continue
        try:
            base = Image.open(img_path).convert("L")
        except Exception:  # noqa: BLE001
            continue
        w, h = base.size
        for i, (sa, typ) in enumerate(regions):
            box = bbox_from_shape(sa)
            if not box:
                continue
            x0, y0, x1, y1 = pad_clamp(box, w, h, args.pad)
            if x1 - x0 < args.min_size or y1 - y0 < args.min_size:
                n_skip += 1
                continue
            crop = base.crop((x0, y0, x1, y1))
            sym = norm_symbology(typ)
            stem = f"{img_path.stem}_{i}"
            dst = Path(args.out) / args.subdir / sym
            dst.mkdir(parents=True, exist_ok=True)
            crop.save(dst / f"{stem}.png")
            n_all += 1
            dec = _decodes(crop)
            if dec is None:
                zbar_missing = True
            elif dec:
                cdst = Path(args.clean_out) / args.subdir / sym
                cdst.mkdir(parents=True, exist_ok=True)
                crop.save(cdst / f"{stem}.png")
                n_clean += 1

    print(f"\nDone. crops(all)={n_all}  crops(clean/decodable)={n_clean}"
          f"  skipped_small={n_skip}  images_missing={n_miss}")
    if zbar_missing:
        print("WARNING: pyzbar/ZBar unavailable -> clean pool NOT built. "
              "Install libzbar0 + pyzbar and re-run.")
    print(f"All bases  -> {Path(args.out) / args.subdir}/<symbology>/")
    print(f"Clean bases-> {Path(args.clean_out) / args.subdir}/<symbology>/  (use for no_defect)")


if __name__ == "__main__":
    main()
