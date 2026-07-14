"""Visão computacional da inspeção de etiquetas (OpenCV + pyzbar + Tesseract).

Responsável por carregar a imagem, localizar a região do código de barras,
decodificá-lo (simbologia + conteúdo), extrair o texto humano-legível (OCR) e
estimar indicadores de qualidade de impressão (contraste, uniformidade, nitidez).

Regras do projeto respeitadas aqui:
- Todos os imports pesados (cv2, numpy, pyzbar, pytesseract, PIL) são LAZY, feitos
  dentro das funções — o módulo importa mesmo sem essas libs instaladas.
- Degradação graciosa: nenhuma função derruba o processo por lib/binário ausente;
  em vez disso devolve valores neutros ou o campo de erro preenchido.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# libzbar empacotada (opcional): torna a lib em ../.native-libs/ visível ao
# pyzbar sem exigir instalação no sistema. O find_library do Linux não usa a
# variável LD_LIBRARY_PATH, então apontamos direto para o arquivo, se existir.
# Assim a decodificação funciona sem sudo (ver README).
# ---------------------------------------------------------------------------
def _registrar_libzbar_local():
    import os
    import ctypes.util
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".native-libs")
    lib = os.path.join(base, "libzbar.so.0")
    if not os.path.exists(lib):
        return
    original = ctypes.util.find_library
    if getattr(original, "_zbar_patched", False):
        return
    def _find(nome):
        return lib if nome == "zbar" else original(nome)
    _find._zbar_patched = True
    ctypes.util.find_library = _find


_registrar_libzbar_local()


# ---------------------------------------------------------------------------
# Auxiliares internos
# ---------------------------------------------------------------------------
def _para_ndarray(caminho_ou_img):
    """Converte a entrada (caminho, ndarray ou imagem PIL) em um ndarray.

    Se `caminho_ou_img` for um caminho de arquivo, delega a `carregar_imagem`.
    Caso contrário, garante que o objeto vire um `numpy.ndarray`.
    """
    if isinstance(caminho_ou_img, (str, bytes)) or hasattr(caminho_ou_img, "__fspath__"):
        return carregar_imagem(str(caminho_ou_img))
    import numpy as np

    return np.asarray(caminho_ou_img)


def _regiao(cinza, roi):
    """Recorta a região de interesse a partir de `roi`.

    `roi` pode ser um bbox (x, y, w, h), um ndarray já recortado ou None (usa a
    imagem inteira). Qualquer inconsistência recai na imagem inteira.
    """
    if roi is None:
        return cinza
    # ROI já é uma imagem (ndarray com pelo menos 2 dimensões).
    if getattr(roi, "ndim", 0) >= 2:
        return roi
    try:
        x, y, w, h = (int(v) for v in roi)
        if w <= 0 or h <= 0:
            return cinza
        recorte = cinza[y:y + h, x:x + w]
        if getattr(recorte, "size", 0) == 0:
            return cinza
        return recorte
    except Exception:
        return cinza


# ---------------------------------------------------------------------------
# Carregamento e conversão
# ---------------------------------------------------------------------------
def carregar_imagem(caminho: str):
    """Lê a imagem do disco em BGR (via cv2.imread).

    Levanta FileNotFoundError se o arquivo não puder ser lido.
    """
    import cv2

    img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Não foi possível ler a imagem: {caminho}")
    return img


def para_cinza(img):
    """Converte a imagem para tons de cinza (aceita já em cinza, BGR ou BGRA)."""
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
# Segmentação da região do código
# ---------------------------------------------------------------------------
def segmentar_codigo(cinza):
    """Detecta a região do código de barras na imagem em cinza.

    Estratégia: gradiente (Scharr = Sobel x - Sobel y) -> convertScaleAbs ->
    blur -> threshold de Otsu -> morfologia (close + erode + dilate) ->
    maior contorno -> boundingRect.

    Retorna (roi_cinza, (x, y, w, h)) quando encontra a região, ou
    (cinza, None) se não localizar nada ou faltar alguma biblioteca.
    """
    try:
        import cv2
    except Exception:
        return cinza, None

    try:
        # Gradiente com Scharr (ksize=-1 no Sobel) e diferença horizontal-vertical:
        # realça as barras verticais do código de barras.
        grad_x = cv2.Sobel(cinza, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad_y = cv2.Sobel(cinza, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
        gradiente = cv2.subtract(grad_x, grad_y)
        gradiente = cv2.convertScaleAbs(gradiente)

        # Suaviza para juntar as barras em um único blob.
        borrada = cv2.blur(gradiente, (9, 9))
        _, limiar = cv2.threshold(borrada, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morfologia: fecha os vãos entre barras e limpa ruído.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        fechada = cv2.morphologyEx(limiar, cv2.MORPH_CLOSE, kernel)
        fechada = cv2.erode(fechada, None, iterations=4)
        fechada = cv2.dilate(fechada, None, iterations=4)

        # Maior contorno = candidato à região do código.
        achados = cv2.findContours(fechada.copy(), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        contornos = achados[0] if len(achados) == 2 else achados[1]
        if not contornos:
            return cinza, None

        maior = max(contornos, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(maior)
        if w <= 0 or h <= 0:
            return cinza, None

        roi = cinza[y:y + h, x:x + w]
        return roi, (int(x), int(y), int(w), int(h))
    except Exception:
        return cinza, None


# ---------------------------------------------------------------------------
# Detecção de PRESENÇA do código (sem decodificar)
# ---------------------------------------------------------------------------
def _densidade_listras(regiao, cv2, np) -> float:
    """Estima o quanto uma região é "listrada" (padrão de barras verticais).

    Binariza a região (Otsu) e conta, por linha, as transições claro/escuro
    (bordas horizontais). Uma faixa de código de barras cruza muitas barras por
    linha, de forma consistente em quase todas as linhas; regiões lisas ou de
    texto têm poucas transições. Devolve uma confiança em [0, 1].
    """
    try:
        regiao = np.asarray(regiao)
        if regiao.ndim != 2 or regiao.size == 0:
            return 0.0
        altura, largura = regiao.shape[:2]
        # Faixa pequena demais não é confiável como código de barras.
        if altura < 4 or largura < 16:
            return 0.0

        if regiao.dtype != np.uint8:
            regiao = cv2.normalize(regiao, None, 0, 255,
                                   cv2.NORM_MINMAX).astype(np.uint8)
        _, binaria = cv2.threshold(regiao, 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Transições horizontais (0<->1) por linha.
        b = (binaria > 0).astype(np.int16)
        transicoes = np.abs(np.diff(b, axis=1)).sum(axis=1)   # shape (altura,)

        # Mediana de transições por linha e fração de linhas "listradas"
        # (>= 8 transições == pelo menos ~4 barras).
        med = float(np.median(transicoes))
        frac_listrada = float(np.mean(transicoes >= 8))

        # Confiança: exige MUITAS transições E consistência entre linhas.
        conf = frac_listrada * min(1.0, med / 16.0)
        return max(0.0, min(1.0, conf))
    except Exception:
        return 0.0


def ha_codigo_de_barras(cinza) -> tuple[bool, float]:
    """Detecta (sem decodificar) se a imagem plausivelmente contém um código.

    DETECÇÃO apenas — não tenta ler o conteúdo. Combina três sinais e fica com a
    maior confiança observada:

    1. ``cv2.barcode.BarcodeDetector().detect`` — localiza códigos 1D;
    2. ``cv2.QRCodeDetector().detect`` — localiza QR Codes 2D;
    3. densidade de transições claro/escuro por linha na maior região retornada
       por :func:`segmentar_codigo` — uma faixa muito "listrada" é típica de barras.

    Imports pesados (cv2/numpy) são LAZY. Em qualquer falta de biblioteca ou erro,
    degrada graciosamente devolvendo ``(False, 0.0)``.

    Retorna ``(detectado: bool, confianca: float)`` com a confiança em [0, 1].
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return (False, 0.0)

    try:
        arr = np.asarray(cinza)
        if arr.ndim != 2:
            arr = para_cinza(arr)
    except Exception:
        return (False, 0.0)

    if getattr(arr, "size", 0) == 0:
        return (False, 0.0)

    # Os detectores do OpenCV são exigentes: garante uint8 contíguo.
    try:
        if arr.dtype != np.uint8:
            arr = cv2.normalize(arr, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        arr = np.ascontiguousarray(arr)
    except Exception:
        pass

    confianca = 0.0

    # 1) Detector 1D do OpenCV (detect => ok, pontos).
    try:
        detector = cv2.barcode.BarcodeDetector()
        ok, pontos = detector.detect(arr)
        if ok and pontos is not None and len(pontos) > 0:
            confianca = max(confianca, 0.9)
    except Exception:
        pass

    # 2) Detector de QR Code do OpenCV (detect => ok, pontos).
    try:
        qr = cv2.QRCodeDetector()
        ok, pontos = qr.detect(arr)
        if ok and pontos is not None and len(pontos) > 0:
            confianca = max(confianca, 0.9)
    except Exception:
        pass

    # 3) Heurística de "listras" na maior região candidata.
    try:
        roi, _bbox = segmentar_codigo(arr)
        regiao = roi if getattr(roi, "size", 0) else arr
        confianca = max(confianca, _densidade_listras(regiao, cv2, np))
    except Exception:
        pass

    detectado = confianca >= 0.5
    return (bool(detectado), float(round(confianca, 3)))


# ---------------------------------------------------------------------------
# Decodificação do código de barras (pyzbar, com fallback OpenCV — sem ZBar)
# ---------------------------------------------------------------------------
def _decodificar_opencv(cinza):
    """Fallback de decodificação usando apenas OpenCV (sem a lib de sistema ZBar).

    Usa cv2.barcode.BarcodeDetector (1D: EAN/UPC/Code128 etc.) e
    cv2.QRCodeDetector (QR). Retorna {"simbologia", "conteudo"} ou None.
    """
    try:
        import cv2
    except Exception:
        return None
    # 1D (cv2.barcode): a assinatura de retorno varia entre versões; pegamos as
    # tuplas de strings (decoded_info, decoded_type) de forma defensiva e só
    # aceitamos conteúdo/tipo que sejam strings não vazias (evita lixo).
    try:
        detector = cv2.barcode.BarcodeDetector()
        res = detector.detectAndDecode(cinza)
        tuplas = [x for x in (res if isinstance(res, (list, tuple)) else [])
                  if isinstance(x, (list, tuple))]
        infos = tuplas[0] if len(tuplas) >= 1 else None
        tipos = tuplas[1] if len(tuplas) >= 2 else None
        if infos:
            for i, txt in enumerate(infos):
                if isinstance(txt, str) and txt.strip():
                    tp = tipos[i] if (tipos is not None and i < len(tipos)) else "BARCODE"
                    tp = tp if (isinstance(tp, str) and tp.strip()) else "BARCODE"
                    return {"simbologia": tp.upper().replace(" ", "").replace("-", ""),
                            "conteudo": txt}
    except Exception:
        pass
    # 2D (QR)
    try:
        qr = cv2.QRCodeDetector()
        dados, _pontos, _ = qr.detectAndDecode(cinza)
        if isinstance(dados, str) and dados.strip():
            return {"simbologia": "QRCODE", "conteudo": dados}
    except Exception:
        pass
    return None


def decodificar(caminho_ou_img) -> dict:
    """Decodifica o código de barras, com pyzbar (se houver) e fallback OpenCV.

    Ordem: tenta o pyzbar (imagem em cinza e limiarizada por Otsu); se o pyzbar
    não estiver disponível ou não achar nada, tenta o fallback OpenCV
    (cv2.barcode e cv2.QRCodeDetector), que NÃO depende da biblioteca de sistema
    ZBar. A simbologia é normalizada para maiúsculas.

    Retorna:
        {"legivel": bool|None, "simbologia": str|None, "conteudo": str|None,
         "n_simbolos": int, "erro": str|None}
    """
    resultado = {"legivel": None, "simbologia": None, "conteudo": None,
                 "n_simbolos": 0, "erro": None}

    try:
        arr = _para_ndarray(caminho_ou_img)
    except Exception as exc:
        resultado["erro"] = f"falha ao carregar imagem: {exc}"
        return resultado
    try:
        cinza = para_cinza(arr)
    except Exception:
        cinza = arr

    avisos = []

    # 1) pyzbar (requer o pacote e a lib nativa libzbar)
    try:
        from pyzbar import pyzbar
        imagens = [cinza]
        try:
            import cv2
            _, limiar = cv2.threshold(cinza, 0, 255,
                                      cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            imagens.append(limiar)
        except Exception:
            pass
        for imagem in imagens:
            try:
                achados = pyzbar.decode(imagem)
            except Exception as exc:
                avisos.append(f"pyzbar/zbar indisponível: {exc}")
                achados = []
            if achados:
                primeiro = achados[0]
                resultado["legivel"] = True
                resultado["n_simbolos"] = len(achados)
                try:
                    resultado["simbologia"] = str(primeiro.type).upper()
                except Exception:
                    resultado["simbologia"] = None
                try:
                    resultado["conteudo"] = primeiro.data.decode("utf-8", errors="replace")
                except Exception:
                    resultado["conteudo"] = str(getattr(primeiro, "data", None))
                return resultado
    except Exception:
        avisos.append("pyzbar ausente")

    # 2) fallback OpenCV (sem dependência de sistema)
    via_cv = _decodificar_opencv(cinza)
    if via_cv:
        resultado["legivel"] = True
        resultado["n_simbolos"] = 1
        resultado["simbologia"] = via_cv["simbologia"]
        resultado["conteudo"] = via_cv["conteudo"]
        return resultado

    # 3) nada decodificado
    try:
        import cv2  # noqa: F401  (só para saber se a leitura foi de fato tentada)
        resultado["legivel"] = False   # tentou (pyzbar e/ou OpenCV) e não encontrou
    except Exception:
        resultado["erro"] = "; ".join(dict.fromkeys(avisos)) or "sem decodificador (pyzbar/opencv ausentes)"
        resultado["legivel"] = None
    return resultado


# ---------------------------------------------------------------------------
# OCR do texto humano-legível (Tesseract)
# ---------------------------------------------------------------------------
def ocr_texto(img_ou_roi) -> str:
    """Extrai o texto legível por humanos via Tesseract (pytesseract).

    Aceita um ndarray, uma imagem PIL ou um caminho de arquivo. Devolve "" em
    qualquer falha (Tesseract/pytesseract ausentes, imagem inválida etc.).
    """
    try:
        import pytesseract
    except Exception:
        return ""

    try:
        entrada = img_ou_roi
        if isinstance(img_ou_roi, (str, bytes)) or hasattr(img_ou_roi, "__fspath__"):
            entrada = carregar_imagem(str(img_ou_roi))
        texto = pytesseract.image_to_string(entrada)
        return (texto or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Indicadores de qualidade
# ---------------------------------------------------------------------------
def indicadores(cinza, roi=None) -> dict:
    """Estima indicadores de qualidade de impressão sobre a ROI.

    - contraste  = (Imax - Imin) / 255 na ROI.
    - uniformidade = 1 - (desvio-padrão do perfil de colunas / 128), em [0, 1].
    - nitidez    = min(1, variância do Laplaciano / 1000).

    Todos os valores são float arredondados a 3 casas. Em caso de falta de
    biblioteca ou erro, devolve valores neutros (0.0).
    """
    neutro = {"contraste": 0.0, "uniformidade": 0.0, "nitidez": 0.0}

    try:
        import cv2
        import numpy as np
    except Exception:
        return neutro

    try:
        regiao = _regiao(cinza, roi)
        regiao_f = np.asarray(regiao, dtype=np.float64)
        if regiao_f.size == 0:
            return neutro

        # Contraste: amplitude de intensidade normalizada.
        imax = float(regiao_f.max())
        imin = float(regiao_f.min())
        contraste = (imax - imin) / 255.0

        # Uniformidade: quanto mais uniforme o perfil de colunas, maior o valor.
        perfil_colunas = regiao_f.mean(axis=0)
        uniformidade = 1.0 - (float(perfil_colunas.std()) / 128.0)
        uniformidade = max(0.0, min(1.0, uniformidade))

        # Nitidez: variância do Laplaciano normalizada.
        laplaciano = cv2.Laplacian(regiao_f, cv2.CV_64F)
        nitidez = min(1.0, float(laplaciano.var()) / 1000.0)

        return {
            "contraste": round(float(contraste), 3),
            "uniformidade": round(float(uniformidade), 3),
            "nitidez": round(float(nitidez), 3),
        }
    except Exception:
        return neutro
