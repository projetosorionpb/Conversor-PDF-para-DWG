"""
Detecção Automática de Escala
==============================
Detecta a escala do desenho comparando textos de metragem (ex: '160 m')
com o comprimento geométrico real das polylines no DXF convertido.

Escalas suportadas: 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
                    600, 750, 1000, 1250, 1500, 2000, 2500, 5000, 10000
"""

import math
import re


# Tamanhos de papel padrão em mm (largura, altura)
PAPER_SIZES_MM = {
    "A0": (841, 1189),
    "A1": (594, 841),
    "A2": (420, 594),
    "A3": (297, 420),
    "A4": (210, 297),
    "A0_L": (1189, 841),
    "A1_L": (841, 594),
    "A2_L": (594, 420),
    "A3_L": (420, 297),
    "A4_L": (297, 210),
}

# Escalas comuns em desenhos técnicos
ESCALAS_COMUNS = [
    50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
    600, 750, 1000, 1250, 1500, 2000, 2500, 5000, 10000,
]


def detectar_escala_por_geometria(page, escala_conversao=0.3528):
    """
    Detecta a escala do desenho comparando textos de metragem de cabos
    (ex: 'CAA 2 ABC 160 m') com o comprimento geométrico real das
    polylines no DXF convertido.

    Lógica:
    - Texto diz '160 m' e polyline no DXF tem length ~160 -> escala 1:1000
    - Texto diz '160 m' e polyline no DXF tem length ~320 -> escala 1:500
    - Fórmula: escala = 1000 * text_metros / dxf_length

    Retorna a escala como inteiro (ex: 500, 1000) ou 1000 como fallback.
    NÃO ALTERA A CONVERSÃO, apenas detecta para exibição.
    """
    H = page.rect.height

    # ---- Extrair textos com metragem (ex: '160 m', '39 m') ----
    metragens = []  # lista de (valor_metros, x_centro, y_centro)
    blocos = page.get_text("dict")

    for bloco in blocos.get("blocks", []):
        if bloco.get("type") != 0:
            continue
        for linha in bloco.get("lines", []):
            texto_linha = ""
            bbox_linha = None
            for span in linha.get("spans", []):
                texto_linha += span.get("text", "")
                sb = span.get("bbox")
                if sb:
                    if bbox_linha is None:
                        bbox_linha = list(sb)
                    else:
                        bbox_linha[0] = min(bbox_linha[0], sb[0])
                        bbox_linha[1] = min(bbox_linha[1], sb[1])
                        bbox_linha[2] = max(bbox_linha[2], sb[2])
                        bbox_linha[3] = max(bbox_linha[3], sb[3])

            if not texto_linha or not bbox_linha:
                continue

            # Procurar padrões de metragem: "123 m", "45,5 m", "67.8m"
            match = re.search(r'(\d+(?:[.,]\d+)?)\s*m\b', texto_linha)
            if match:
                valor_str = match.group(1).replace(',', '.')
                try:
                    valor = float(valor_str)
                    if 5 <= valor <= 5000:  # metragem plausível de cabo
                        cx = (bbox_linha[0] + bbox_linha[2]) / 2
                        cy = (bbox_linha[1] + bbox_linha[3]) / 2
                        metragens.append((valor, cx, cy))
                except ValueError:
                    continue

    if not metragens:
        print("  Nenhum texto de metragem encontrado, usando escala padrão 1:1000")
        return 1000

    # ---- Extrair paths (linhas/cabos) e seus comprimentos ----
    paths = page.get_drawings()

    path_infos = []  # lista de (comprimento_dxf, x_centro_pdf, y_centro_pdf)
    for p in paths:
        items = p.get("items", [])
        cor = p.get("color")
        if not items or not cor:
            continue

        comprimento_pdf = 0
        xs, ys = [], []
        for it in items:
            if not it:
                continue
            if it[0] == "l":
                dx = it[2].x - it[1].x
                dy = it[2].y - it[1].y
                comprimento_pdf += math.sqrt(dx**2 + dy**2)
                xs.extend([it[1].x, it[2].x])
                ys.extend([it[1].y, it[2].y])
            elif it[0] == "c" and len(it) >= 5:
                pts = []
                for k in range(21):
                    t = k / 20
                    mt = 1 - t
                    x = mt**3*it[1].x + 3*mt**2*t*it[2].x + 3*mt*t**2*it[3].x + t**3*it[4].x
                    y = mt**3*it[1].y + 3*mt**2*t*it[2].y + 3*mt*t**2*it[3].y + t**3*it[4].y
                    pts.append((x, y))
                for k in range(len(pts)-1):
                    dx = pts[k+1][0] - pts[k][0]
                    dy = pts[k+1][1] - pts[k][1]
                    comprimento_pdf += math.sqrt(dx**2 + dy**2)
                xs.extend([it[1].x, it[4].x])
                ys.extend([it[1].y, it[4].y])

        if comprimento_pdf < 10 or not xs:
            continue

        comprimento_dxf = comprimento_pdf * escala_conversao
        cx_path = (min(xs) + max(xs)) / 2
        cy_path = (min(ys) + max(ys)) / 2
        path_infos.append((comprimento_dxf, cx_path, cy_path))

    if not path_infos:
        print("  Nenhum path com comprimento encontrado, usando escala padrão 1:1000")
        return 1000

    # ---- Comparar texto vs geometria ----
    ratios = []
    for valor_m, tx_c, ty_c in metragens:
        melhor_dist = float('inf')
        melhor_comprimento = None

        for comp_dxf, px, py in path_infos:
            dist = math.sqrt((tx_c - px)**2 + (ty_c - py)**2)
            if dist < melhor_dist:
                melhor_dist = dist
                melhor_comprimento = comp_dxf

        if melhor_comprimento and melhor_comprimento > 0:
            ratio = melhor_comprimento / valor_m
            if 0.3 < ratio < 10:
                ratios.append(ratio)
                print(f"  Metragem: {valor_m}m, DXF length: {melhor_comprimento:.1f}, ratio: {ratio:.2f}")

    if not ratios:
        print("  Não foi possível correlacionar textos com paths, usando escala padrão 1:1000")
        return 1000

    # Mediana dos ratios para robustez
    ratios.sort()
    ratio_mediano = ratios[len(ratios) // 2]

    escala_calculada = 1000 / ratio_mediano

    # Arredondar para escala comum mais próxima
    mais_proxima = min(ESCALAS_COMUNS, key=lambda x: abs(x - escala_calculada))

    # Tolerância de 30% para aceitar
    if abs(mais_proxima - escala_calculada) / max(escala_calculada, 1) < 0.3:
        print(f"  Escala detectada por geometria: 1:{mais_proxima} (ratio mediano: {ratio_mediano:.2f})")
        return mais_proxima

    print(f"  Escala calculada {escala_calculada:.0f} não bate com nenhuma comum, usando 1:1000")
    return 1000
