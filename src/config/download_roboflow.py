#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_roboflow.py -- Download real barcode datasets from Roboflow Universe.

Two intended roles (``--role``):

  * ``bases`` -- clean/mixed real barcode images used as BASES for the synthetic
    defect generator (``generate_dataset.py --bases-dir ...``). Applying our
    Zebra-faithful defects on top of REAL barcode texture is what narrows the
    synthetic->real domain gap. Images are flattened into
    ``<out>/real_bases/<symbology>/`` (symbology folder = the generator's hint;
    unknown -> ``mixed``).

  * ``test`` -- a real DEFECT dataset kept aside as a generalization TEST set
    (never mixed into training). Left in Roboflow's native ``folder`` layout
    under ``<out>/roboflow_test/<project>/``.

Roboflow projects each carry their OWN license (many are CC BY 4.0, some are
not). ALWAYS open the project page and record its license before using the
images -- this script does not and cannot verify it for you.

Usage:
    export ROBOFLOW_API_KEY=xxxxxxxx
    # clean bases to feed the generator
    python -m config.download_roboflow --workspace o-xfs34 \
        --project barcode-detection-tvdug --version 1 --role bases

    # a real-defect set as the generalization test
    python -m config.download_roboflow --workspace <ws> \
        --project <defect-project> --version 1 --role test

Dependencies:
    pip install roboflow
"""
import argparse
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# This file lives at src/config/download_roboflow.py -> src root is one up.
SRC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = SRC_ROOT / "config" / "datasets"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


# Export formats we can consume (we only need the images). Ordered by
# preference; used as fallbacks when the requested format is rejected for the
# project type (e.g. 'folder' is classification-only, invalid for detection).
_FALLBACK_FORMATS = ["voc", "coco", "yolov8", "multiclass", "folder"]


def _allowed_formats_from_error(msg):
    """Parse the 'Please use one of: a, b, c' list out of a Roboflow error."""
    marker = "use one of:"
    if marker not in msg:
        return []
    tail = msg.split(marker, 1)[1]
    tail = tail.split("}")[0].split('"')[0]
    return [t.strip().strip('.').strip() for t in tail.split(",") if t.strip()]


def download(api_key, workspace, project, version, fmt, dest):
    """Download a Roboflow dataset version into ``dest`` (native export layout).

    Tries ``fmt`` first; if Roboflow rejects it as invalid for the project
    type, retries with the first compatible format from ``_FALLBACK_FORMATS``
    (we only need the images, so any valid export works).

    Returns the path Roboflow wrote the dataset to.

    Failure modes:
        Exits with a message if the ``roboflow`` package is missing or the
        API/download call fails (bad key, unknown slug/version, no network).
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        sys.exit("ERROR: the 'roboflow' package is not installed. Run: pip install roboflow")

    try:
        rf = Roboflow(api_key=api_key)
        proj = rf.workspace(workspace).project(project)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERROR: Roboflow connection/project failed: {exc}")

    candidates = []
    for c in [fmt] + _FALLBACK_FORMATS:
        if c not in candidates:
            candidates.append(c)

    tried, allowed, last_exc = [], None, None
    for candidate in candidates:
        if allowed is not None and candidate not in allowed:
            continue  # project already told us this format is invalid
        try:
            ds = proj.version(version).download(candidate, location=str(dest))
            if candidate != fmt:
                print(f"NOTE: format '{fmt}' invalid for this project; used '{candidate}' instead.")
            return Path(getattr(ds, "location", dest))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            tried.append(candidate)
            parsed = _allowed_formats_from_error(str(exc))
            if parsed:
                allowed = parsed
    hint = f" Project accepts: {', '.join(allowed)}." if allowed else ""
    sys.exit(f"ERROR: Roboflow download failed (tried {tried}): {last_exc}.{hint}")


def iter_images(root):
    """Yield every image file under ``root`` (any depth)."""
    for p in Path(root).rglob("*"):
        if p.suffix.lower() in IMG_EXTS:
            yield p


def _pad_box(x0, y0, x1, y1, w, h, pad):
    """Expand a box by ``pad`` (fraction of its longer side) and clamp to image.

    Barcodes need their quiet zone to stay decodable, so we never crop tight to
    the bars -- we add a margin proportional to the box size.
    """
    bw, bh = x1 - x0, y1 - y0
    m = int(round(pad * max(bw, bh)))
    return (max(0, x0 - m), max(0, y0 - m), min(w, x1 + m), min(h, y1 + m))


def _save_crop(img, box, dst, stem, idx):
    """Crop ``box`` from a PIL image and save it; return 1 on success, else 0."""
    x0, y0, x1, y1 = box
    if x1 - x0 < 8 or y1 - y0 < 8:      # skip degenerate boxes
        return 0
    img.crop((x0, y0, x1, y1)).convert("L").save(dst / f"{stem}_{idx}.png")
    return 1


def crop_voc(src_root, dst, pad):
    """Crop every annotated box from a Pascal VOC export into ``dst``.

    Roboflow's VOC export writes one ``.xml`` next to each image. Returns the
    number of crops written.
    """
    from PIL import Image
    n = 0
    for xml in Path(src_root).rglob("*.xml"):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        # resolve the image: <filename>, then same stem with a known extension
        img_path = None
        fn = root.findtext("filename")
        if fn and (xml.parent / fn).exists():
            img_path = xml.parent / fn
        else:
            for ext in IMG_EXTS:
                cand = xml.with_suffix(ext)
                if cand.exists():
                    img_path = cand
                    break
        if not img_path:
            continue
        try:
            img = Image.open(img_path)
        except Exception:  # noqa: BLE001
            continue
        w, h = img.size
        for i, obj in enumerate(root.findall("object")):
            bb = obj.find("bndbox")
            if bb is None:
                continue
            try:
                box = _pad_box(int(float(bb.findtext("xmin"))), int(float(bb.findtext("ymin"))),
                               int(float(bb.findtext("xmax"))), int(float(bb.findtext("ymax"))),
                               w, h, pad)
            except (TypeError, ValueError):
                continue
            n += _save_crop(img, box, dst, img_path.stem, i)
    return n


def crop_coco(src_root, dst, pad):
    """Crop every annotated box from a COCO export into ``dst``.

    Roboflow's COCO export writes ``_annotations.coco.json`` per split folder,
    with bboxes as ``[x, y, width, height]``. Returns the number of crops.
    """
    from PIL import Image
    n = 0
    for jf in Path(src_root).rglob("_annotations.coco.json"):
        try:
            data = json.loads(jf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        images = {im["id"]: im for im in data.get("images", [])}
        by_img = {}
        for ann in data.get("annotations", []):
            by_img.setdefault(ann["image_id"], []).append(ann.get("bbox"))
        for img_id, boxes in by_img.items():
            meta = images.get(img_id)
            if not meta:
                continue
            img_path = jf.parent / meta["file_name"]
            if not img_path.exists():
                continue
            try:
                img = Image.open(img_path)
            except Exception:  # noqa: BLE001
                continue
            w, h = img.size
            for i, bbox in enumerate(boxes):
                if not bbox or len(bbox) < 4:
                    continue
                x, y, bw, bh = bbox
                box = _pad_box(int(x), int(y), int(x + bw), int(y + bh), w, h, pad)
                n += _save_crop(img, box, dst, img_path.stem, i)
    return n


def crop_to_bases(src_root, bases_dir, symbology, pad):
    """Crop annotated barcodes (VOC or COCO) from ``src_root`` into bases.

    Returns ``(dst, n_crops)``. ``n_crops == 0`` means no annotations were
    found (the caller should fall back to copying whole images).
    """
    dst = Path(bases_dir) / symbology
    dst.mkdir(parents=True, exist_ok=True)
    n = crop_voc(src_root, dst, pad)
    if n == 0:
        n = crop_coco(src_root, dst, pad)
    return dst, n


def flatten_to_bases(src_root, bases_dir, symbology):
    """Copy all images under ``src_root`` into ``bases_dir/<symbology>/``.

    The generator infers the symbology from the parent folder name, so pass a
    concrete symbology (``qr``, ``code128``, ...) when the project is
    single-type, or ``mixed`` when it is not.
    """
    dst = Path(bases_dir) / symbology
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for img in iter_images(src_root):
        # keep names unique across sub-splits (train/valid/test)
        target = dst / f"{img.parent.name}_{img.name}"
        shutil.copy2(img, target)
        n += 1
    return dst, n


def main():
    """Parse CLI args, download the dataset, and organize it by ``--role``."""
    ap = argparse.ArgumentParser(description="Download real barcode datasets from Roboflow Universe")
    ap.add_argument("--api-key", default=os.environ.get("ROBOFLOW_API_KEY"),
                    help="Roboflow API key (or set ROBOFLOW_API_KEY).")
    ap.add_argument("--workspace", required=True, help='Workspace slug (rf.workspace("...")).')
    ap.add_argument("--project", required=True, help='Project slug (.project("...")).')
    ap.add_argument("--version", type=int, default=1, help="Dataset version number (.version(N)).")
    ap.add_argument("--format", default="folder", dest="fmt",
                    help="Roboflow export format (default: folder; e.g., coco, yolov8, voc, ...).")
    ap.add_argument("--role", choices=["bases", "test"], default="bases",
                    help="'bases' = clean bases for the generator; 'test' = real defect test set.")
    ap.add_argument("--symbology", default="mixed",
                    help="Symbology folder name for --role bases (qr/code128/.../mixed).")
    ap.add_argument("--crop", action="store_true",
                    help="Crop each annotated barcode (VOC/COCO) instead of copying whole images.")
    ap.add_argument("--pad", type=float, default=0.08,
                    help="Quiet-zone margin around each crop, as a fraction of the box (default: 0.08).")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="Base output directory (default: config/datasets).")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("ERROR: no API key. Pass --api-key or set ROBOFLOW_API_KEY.")

    # cropping needs boxes: 'folder'/classification exports have none, so prefer
    # an annotated format (VOC first -- per-image XML, easiest to parse).
    if args.crop and args.fmt == "folder":
        args.fmt = "voc"

    out = Path(args.out)
    raw = out / "roboflow_raw" / f"{args.project}-v{args.version}"
    try:
        # Only create the PARENT. Roboflow treats a pre-existing destination as
        # "already downloaded" and SKIPS extraction, leaving it empty -- so the
        # destination itself must not exist yet. Drop it if it's an empty stub.
        raw.parent.mkdir(parents=True, exist_ok=True)
        if raw.exists() and not any(raw.iterdir()):
            raw.rmdir()
    except OSError as exc:
        sys.exit(f"ERROR: could not prepare output directory '{raw}': {exc}")

    location = download(args.api_key, args.workspace, args.project, args.version, args.fmt, raw)
    print(f"Downloaded '{args.project}' v{args.version} -> {location}")

    if args.role == "bases":
        bases_root = out / "real_bases"
        if args.crop:
            dst, n = crop_to_bases(location, bases_root, args.symbology, args.pad)
            if n == 0:
                print("WARNING: no VOC/COCO annotations found to crop; copying whole images instead.")
                dst, n = flatten_to_bases(location, bases_root, args.symbology)
            else:
                print(f"Cropped {n} barcode(s) into {dst}")
        else:
            dst, n = flatten_to_bases(location, bases_root, args.symbology)
            print(f"Prepared {n} base images in {dst}")
        print("Next: python -m config.generate_dataset --bases-dir "
              f"{bases_root} --real-fraction 0.5 --per-class 400")
    else:  # test
        dst = out / "roboflow_test" / args.project
        dst.mkdir(parents=True, exist_ok=True)
        if location.resolve() != dst.resolve():
            for item in location.iterdir():
                shutil.move(str(item), str(dst / item.name))
        print(f"Real defect TEST set ready at {dst} (keep OUT of training).")

    print("\nREMINDER: record this project's LICENSE from its Roboflow page before use.")


if __name__ == "__main__":
    main()
