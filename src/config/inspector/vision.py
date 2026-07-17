"""Computer vision for label inspection (OpenCV + pyzbar).

Responsible for loading the image, locating the barcode region, decoding it
(symbology + content) and estimating print quality indicators (contrast,
uniformity, sharpness).

Project rules honored here:
- All heavy imports (cv2, numpy, pyzbar, PIL) are LAZY, done
  inside the functions — the module imports even without those libs installed.
- Graceful degradation: no function crashes the process due to a missing
  lib/binary; instead it returns neutral values or a filled error field.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Bundled libzbar (optional): makes the lib in ../.native-libs/ visible to
# pyzbar without requiring a system install. Linux's find_library does not use
# the LD_LIBRARY_PATH variable, so we point directly at the file, if it exists.
# This way decoding works without sudo (see README).
# ---------------------------------------------------------------------------
def _register_local_libzbar():
    import os
    import ctypes.util
    # vision.py lives at src/config/inspector/, and .native-libs is at the src
    # root, so we go up THREE levels (inspector -> config -> src).
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".native-libs")
    lib = os.path.join(base, "libzbar.so.0")
    if not os.path.exists(lib):
        return
    original = ctypes.util.find_library
    if getattr(original, "_zbar_patched", False):
        return
    def _find(name):
        return lib if name == "zbar" else original(name)
    _find._zbar_patched = True
    ctypes.util.find_library = _find


_register_local_libzbar()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _to_ndarray(path_or_img):
    """Convert the input (path, ndarray or PIL image) into an ndarray.

    If `path_or_img` is a file path, delegates to `load_image`.
    Otherwise, ensures the object becomes a `numpy.ndarray`.
    """
    if isinstance(path_or_img, (str, bytes)) or hasattr(path_or_img, "__fspath__"):
        return load_image(str(path_or_img))
    import numpy as np

    return np.asarray(path_or_img)


def _region(gray, roi):
    """Crop the region of interest from `roi`.

    `roi` can be a bbox (x, y, w, h), an already-cropped ndarray, or None (uses
    the whole image). Any inconsistency falls back to the whole image.
    """
    if roi is None:
        return gray
    # ROI is already an image (ndarray with at least 2 dimensions).
    if getattr(roi, "ndim", 0) >= 2:
        return roi
    try:
        x, y, w, h = (int(v) for v in roi)
        if w <= 0 or h <= 0:
            return gray
        crop = gray[y:y + h, x:x + w]
        if getattr(crop, "size", 0) == 0:
            return gray
        return crop
    except Exception:
        return gray


# ---------------------------------------------------------------------------
# Loading and conversion
# ---------------------------------------------------------------------------
def load_image(path: str):
    """Read the image from disk in BGR (via cv2.imread).

    Raises FileNotFoundError if the file cannot be read.
    """
    import cv2

    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def to_gray(img):
    """Convert the image to grayscale (accepts already-gray, BGR, or BGRA)."""
    import cv2
    import numpy as np

    arr = np.asarray(img)
    if arr.ndim == 2:
        return arr
    if arr.ndim == 3 and arr.shape[2] == 1:
        return arr[:, :, 0]
    if arr.ndim == 3 and arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------------------
# Code region segmentation
# ---------------------------------------------------------------------------
def _code_stripiness(region, cv2, np) -> float:
    """Confidence in [0, 1] that ``region`` is a periodic bar/module pattern.

    A barcode/2D-code is periodic (many black<->white transitions per row or
    column); flat clutter (a metal clip, a hand, a desk) is not. This gate lets
    :func:`segment_code` reject high-gradient but non-striped regions.
    """
    try:
        region = np.asarray(region)
        if region.ndim != 2 or region.size == 0:
            return 0.0
        h, w = region.shape[:2]
        if h < 8 or w < 16:
            return 0.0
        if region.dtype != np.uint8:
            region = cv2.normalize(region, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, b = cv2.threshold(region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        b = (b > 0).astype(np.int16)

        def axis_conf(binary):
            tr = np.abs(np.diff(binary, axis=1)).sum(axis=1)
            med = float(np.median(tr))
            striped = float(np.mean(tr >= 6))
            return striped * min(1.0, med / 12.0)

        return max(0.0, min(1.0, max(axis_conf(b), axis_conf(b.T))))
    except Exception:
        return 0.0


def segment_code(gray):
    """Detect the barcode / 2D-code region via gradient density + periodicity.

    Builds a 1D map (horizontal-gradient dominance ``|Sobelx|-|Sobely|``) and a
    2D map (``min(|Sobelx|,|Sobely|)``), closes each into candidate blobs, then
    ranks every candidate by stripiness x gradient energy x fill x size. The
    periodicity gate (:func:`_code_stripiness`) rejects non-code clutter (metal
    clips, hands, backgrounds) that fooled the previous largest-contour method.

    Returns (gray_roi, (x, y, w, h)) when a region is found, or (gray, None) if
    nothing plausible is located or a library is missing. Never raises.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return gray, None
    try:
        g = np.asarray(gray)
        if g.ndim != 2 or g.size == 0:
            return gray, None
        if g.dtype != np.uint8:
            g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        H, W = g.shape[:2]
        scale = 1.0
        long_side = max(H, W)
        if long_side > 640:
            scale = 640.0 / long_side
            work = cv2.resize(g, (max(1, int(round(W * scale))), max(1, int(round(H * scale)))),
                              interpolation=cv2.INTER_AREA)
        else:
            work = g
        wh, ww = work.shape[:2]
        area_img = float(wh * ww)
        work_s = cv2.GaussianBlur(work, (3, 3), 0)
        gx = cv2.Sobel(work_s, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(work_s, cv2.CV_32F, 0, 1, ksize=3)
        ax, ay = np.abs(gx), np.abs(gy)
        resp_1d = cv2.convertScaleAbs(cv2.subtract(ax, ay))
        resp_2d = cv2.convertScaleAbs(cv2.min(ax, ay) * 2.0)
        cands = []

        def collect(resp, kernel_wh, min_ar):
            blurred = cv2.blur(resp, (9, 9))
            _, th = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_wh)
            closed = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
            closed = cv2.erode(closed, None, iterations=2)
            closed = cv2.dilate(closed, None, iterations=2)
            found = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = found[0] if len(found) == 2 else found[1]
            integ = cv2.integral(resp.astype(np.float32))
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w < 12 or h < 12:
                    continue
                box_area = float(w * h)
                frac = box_area / area_img
                if frac < 0.0012:
                    continue
                fill = cv2.contourArea(c) / box_area
                if fill < 0.35:
                    continue
                ar = w / float(h)
                if not (min_ar <= ar <= 1.0 / min_ar):
                    continue
                s = (integ[y + h, x + w] - integ[y, x + w] - integ[y + h, x] + integ[y, x])
                mean_energy = float(s / box_area) / 255.0
                strip = _code_stripiness(work[y:y + h, x:x + w], cv2, np)
                if strip < 0.12:
                    continue
                size_factor = min(1.0, frac / 0.04)
                score = (0.15 + strip) * (0.4 + 0.6 * mean_energy) * fill * size_factor
                cands.append((score, (x, y, w, h)))

        collect(resp_1d, (21, 7), 0.12)
        collect(resp_2d, (11, 11), 0.5)
        if not cands:
            return gray, None
        cands.sort(key=lambda t: t[0], reverse=True)
        x, y, w, h = cands[0][1]
        if scale != 1.0:
            inv = 1.0 / scale
            x = int(round(x * inv)); y = int(round(y * inv))
            w = int(round(w * inv)); h = int(round(h * inv))
        mx = int(round(w * 0.04)) + 2
        my = int(round(h * 0.06)) + 2
        x0 = max(0, x - mx); y0 = max(0, y - my)
        x1 = min(W, x + w + mx); y1 = min(H, y + h + my)
        w = x1 - x0; h = y1 - y0
        if w <= 0 or h <= 0:
            return gray, None
        roi = g[y0:y1, x0:x1]
        if getattr(roi, "size", 0) == 0:
            return gray, None
        return roi, (int(x0), int(y0), int(w), int(h))
    except Exception:
        return gray, None


def _fit_canvas_pil(im, size, bg, fill):
    """Scale ``im`` to fill ``size`` (preserving aspect), centered on ``bg``.

    Mirrors ``generate_dataset._fit_canvas`` EXACTLY (same 560x260 canvas,
    fill=0.92, BILINEAR) so inference sees the same distribution as training.
    """
    from PIL import Image
    im = im.convert("L")
    w, h = size
    iw, ih = im.size
    if iw == 0 or ih == 0:
        return Image.new("L", size, bg)
    scale = min(w / iw, h / ih) * fill
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    im = im.resize((nw, nh), Image.BILINEAR)
    cv = Image.new("L", size, bg)
    cv.paste(im, ((w - nw) // 2, (h - nh) // 2))
    return cv


def prepare_for_cnn(path_or_img, roi=None):
    """Crop the code region and apply the training fit-to-fill; PIL "L" or None.

    Reuses ``roi`` (a bbox/ndarray already segmented upstream) when given, else
    segments on demand via :func:`segment_code`. Returns ``None`` on any failure
    so callers degrade to the raw image instead of breaking.
    """
    try:
        import numpy as np
        from PIL import Image
        from config.inspector import settings
        gray = to_gray(_to_ndarray(path_or_img))
        crop = _region(gray, roi) if roi is not None else segment_code(gray)[0]
        pil = Image.fromarray(np.asarray(crop).astype("uint8"), "L")
        return _fit_canvas_pil(pil, settings.CNN_CANVAS, 255, settings.CNN_CANVAS_FILL)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Barcode PRESENCE detection (without decoding)
# ---------------------------------------------------------------------------
def _stripe_density(region, cv2, np) -> float:
    """Estimate how "striped" a region is (vertical-bars pattern).

    Binarizes the region (Otsu) and counts, per row, the light/dark
    transitions (horizontal edges). A barcode stripe crosses many bars per
    row, consistently across almost every row; flat or text regions have few
    transitions. Returns a confidence in [0, 1].
    """
    try:
        region = np.asarray(region)
        if region.ndim != 2 or region.size == 0:
            return 0.0
        height, width = region.shape[:2]
        # A stripe that is too small is not reliable as a barcode.
        if height < 4 or width < 16:
            return 0.0

        if region.dtype != np.uint8:
            region = cv2.normalize(region, None, 0, 255,
                                   cv2.NORM_MINMAX).astype(np.uint8)
        _, binary = cv2.threshold(region, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Horizontal transitions (0<->1) per row.
        b = (binary > 0).astype(np.int16)
        transitions = np.abs(np.diff(b, axis=1)).sum(axis=1)   # shape (height,)

        # Median transitions per row and fraction of "striped" rows
        # (>= 8 transitions == at least ~4 bars).
        med = float(np.median(transitions))
        striped_frac = float(np.mean(transitions >= 8))

        # Confidence: requires MANY transitions AND consistency across rows.
        conf = striped_frac * min(1.0, med / 16.0)
        return max(0.0, min(1.0, conf))
    except Exception:
        return 0.0


def has_barcode(gray) -> tuple[bool, float]:
    """Detect (without decoding) whether the image plausibly contains a code.

    DETECTION only — does not attempt to read the content. Combines three
    signals and keeps the highest confidence observed:

    1. ``cv2.barcode.BarcodeDetector().detect`` — locates 1D codes;
    2. ``cv2.QRCodeDetector().detect`` — locates 2D QR codes;
    3. light/dark transition density per row in the largest region returned
       by :func:`segment_code` — a very "striped" stripe is typical of bars.

    Heavy imports (cv2/numpy) are LAZY. On any missing library or error,
    degrades gracefully, returning ``(False, 0.0)``.

    Returns ``(detected: bool, confidence: float)`` with confidence in [0, 1].
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return (False, 0.0)

    try:
        arr = np.asarray(gray)
        if arr.ndim != 2:
            arr = to_gray(arr)
    except Exception:
        return (False, 0.0)

    if getattr(arr, "size", 0) == 0:
        return (False, 0.0)

    # OpenCV's detectors are demanding: ensure contiguous uint8.
    try:
        if arr.dtype != np.uint8:
            arr = cv2.normalize(arr, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        arr = np.ascontiguousarray(arr)
    except Exception:
        pass

    confidence = 0.0

    # 1) OpenCV's 1D detector (detect => ok, points).
    try:
        detector = cv2.barcode.BarcodeDetector()
        ok, points = detector.detect(arr)
        if ok and points is not None and len(points) > 0:
            confidence = max(confidence, 0.9)
    except Exception:
        pass

    # 2) OpenCV's QR Code detector (detect => ok, points).
    try:
        qr = cv2.QRCodeDetector()
        ok, points = qr.detect(arr)
        if ok and points is not None and len(points) > 0:
            confidence = max(confidence, 0.9)
    except Exception:
        pass

    # 3) "Stripes" heuristic on the largest candidate region.
    try:
        roi, _bbox = segment_code(arr)
        region = roi if getattr(roi, "size", 0) else arr
        confidence = max(confidence, _stripe_density(region, cv2, np))
    except Exception:
        pass

    detected = confidence >= 0.5
    return (bool(detected), float(round(confidence, 3)))


# ---------------------------------------------------------------------------
# Barcode decoding (pyzbar, with OpenCV fallback — no ZBar)
# ---------------------------------------------------------------------------
def _decode_opencv(gray):
    """Decoding fallback using only OpenCV (without the ZBar system lib).

    Uses cv2.barcode.BarcodeDetector (1D: EAN/UPC/Code128 etc.) and
    cv2.QRCodeDetector (QR). Returns {"symbology", "content"} or None.
    """
    try:
        import cv2
    except Exception:
        return None
    # 1D (cv2.barcode): the return signature varies across versions; we grab
    # the string tuples (decoded_info, decoded_type) defensively and only
    # accept content/type that are non-empty strings (avoids garbage).
    try:
        detector = cv2.barcode.BarcodeDetector()
        res = detector.detectAndDecode(gray)
        tuples = [x for x in (res if isinstance(res, (list, tuple)) else [])
                  if isinstance(x, (list, tuple))]
        infos = tuples[0] if len(tuples) >= 1 else None
        types = tuples[1] if len(tuples) >= 2 else None
        if infos:
            for i, txt in enumerate(infos):
                if isinstance(txt, str) and txt.strip():
                    tp = types[i] if (types is not None and i < len(types)) else "BARCODE"
                    tp = tp if (isinstance(tp, str) and tp.strip()) else "BARCODE"
                    return {"symbology": tp.upper().replace(" ", "").replace("-", ""),
                            "content": txt}
    except Exception:
        pass
    # 2D (QR)
    try:
        qr = cv2.QRCodeDetector()
        data, _points, _ = qr.detectAndDecode(gray)
        if isinstance(data, str) and data.strip():
            return {"symbology": "QRCODE", "content": data}
    except Exception:
        pass
    return None


def decode(path_or_img) -> dict:
    """Decode the barcode, with pyzbar (if available) and OpenCV fallback.

    Order: tries pyzbar (grayscale image and Otsu-thresholded image); if
    pyzbar is unavailable or finds nothing, tries the OpenCV fallback
    (cv2.barcode and cv2.QRCodeDetector), which does NOT depend on the ZBar
    system library. The symbology is normalized to uppercase.

    Returns:
        {"readable": bool|None, "symbology": str|None, "content": str|None,
         "symbol_count": int, "error": str|None}
    """
    result = {"readable": None, "symbology": None, "content": None,
              "symbol_count": 0, "error": None}

    try:
        arr = _to_ndarray(path_or_img)
    except Exception as exc:
        result["error"] = f"failed to load image: {exc}"
        return result
    try:
        gray = to_gray(arr)
    except Exception:
        gray = arr

    warnings = []

    # 1) pyzbar (requires the package and the native libzbar lib)
    try:
        from pyzbar import pyzbar
        # Restrict the enabled symbologies. Left unrestricted, ZBar also runs its
        # PDF417 decoder, whose C implementation floods stderr with harmless
        # "decoder/pdf417.c: Assertion failed" warnings on non-PDF417 images
        # (e.g. a plain EAN-13). None of the labels here use PDF417, so we
        # whitelist the ones we actually expect; this also speeds decoding up.
        try:
            from pyzbar.pyzbar import ZBarSymbol
            zbar_symbols = [
                ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.UPCE,
                ZBarSymbol.CODE128, ZBarSymbol.CODE39, ZBarSymbol.CODE93,
                ZBarSymbol.CODABAR, ZBarSymbol.I25, ZBarSymbol.QRCODE,
                ZBarSymbol.DATABAR, ZBarSymbol.DATABAR_EXP,
            ]
        except Exception:
            zbar_symbols = None   # older pyzbar: fall back to all symbologies
        images = [gray]
        try:
            import cv2
            _, threshold = cv2.threshold(gray, 0, 255,
                                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            images.append(threshold)
        except Exception:
            pass
        for image in images:
            try:
                found = pyzbar.decode(image, symbols=zbar_symbols)
            except Exception as exc:
                warnings.append(f"pyzbar/zbar unavailable: {exc}")
                found = []
            if found:
                first = found[0]
                result["readable"] = True
                result["symbol_count"] = len(found)
                try:
                    result["symbology"] = str(first.type).upper()
                except Exception:
                    result["symbology"] = None
                try:
                    result["content"] = first.data.decode("utf-8", errors="replace")
                except Exception:
                    result["content"] = str(getattr(first, "data", None))
                return result
    except Exception:
        warnings.append("pyzbar missing")

    # 2) OpenCV fallback (no system dependency)
    via_cv = _decode_opencv(gray)
    if via_cv:
        result["readable"] = True
        result["symbol_count"] = 1
        result["symbology"] = via_cv["symbology"]
        result["content"] = via_cv["content"]
        return result

    # 3) nothing decoded
    try:
        import cv2  # noqa: F401  (just to know whether reading was actually attempted)
        result["readable"] = False   # tried (pyzbar and/or OpenCV) and found nothing
    except Exception:
        result["error"] = "; ".join(dict.fromkeys(warnings)) or "no decoder available (pyzbar/opencv missing)"
        result["readable"] = None
    return result


# ---------------------------------------------------------------------------
# Quality indicators
# ---------------------------------------------------------------------------
def indicators(gray, roi=None) -> dict:
    """Estimate print quality indicators over the ROI.

    - contrast   = (Imax - Imin) / 255 over the ROI.
    - uniformity = 1 - (std deviation of the column profile / 128), in [0, 1].
    - sharpness  = min(1, variance of the Laplacian / 1000).

    All values are floats rounded to 3 decimal places. On a missing library
    or error, returns neutral values (0.0).
    """
    neutral = {"contrast": 0.0, "uniformity": 0.0, "sharpness": 0.0}

    try:
        import cv2
        import numpy as np
    except Exception:
        return neutral

    try:
        region = _region(gray, roi)
        region_f = np.asarray(region, dtype=np.float64)
        if region_f.size == 0:
            return neutral

        # Contrast: normalized intensity amplitude.
        imax = float(region_f.max())
        imin = float(region_f.min())
        contrast = (imax - imin) / 255.0

        # Uniformity: the more uniform the column profile, the higher the value.
        column_profile = region_f.mean(axis=0)
        uniformity = 1.0 - (float(column_profile.std()) / 128.0)
        uniformity = max(0.0, min(1.0, uniformity))

        # Sharpness: normalized variance of the Laplacian.
        laplacian = cv2.Laplacian(region_f, cv2.CV_64F)
        sharpness = min(1.0, float(laplacian.var()) / 1000.0)

        return {
            "contrast": round(float(contrast), 3),
            "uniformity": round(float(uniformity), 3),
            "sharpness": round(float(sharpness), 3),
        }
    except Exception:
        return neutral
