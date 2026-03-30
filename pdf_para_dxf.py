"""
Conversor PDF Vetorial -> DXF/DWG (Fidelidade Total)
=====================================================
Conversor generico de PDFs vetoriais para DXF/DWG
preservando cores RGB exatas, tracejados reais, preenchimentos
solidos, rotacao de textos e deteccao automatica de escala.

INSTALACAO:
    pip install pymupdf ezdxf

USO:
    python pdf_para_dxf.py arquivo.pdf
    python pdf_para_dxf.py arquivo.pdf saida.dwg
    python pdf_para_dxf.py arquivo.pdf --pagina 2
"""

import sys
import os
import argparse
import math
import re

try:
    import fitz
except ImportError:
    print("Instale: pip install pymupdf")
    sys.exit(1)

try:
    import ezdxf
    from ezdxf import rgb2int
except ImportError:
    print("Instale: pip install ezdxf")
    sys.exit(1)


# =============================================================
# TABELA ACI COMPLETA (256 cores AutoCAD)
# =============================================================
# Gera a tabela completa de 256 cores ACI do AutoCAD
def _gerar_tabela_aci():
    """Gera tabela RGB -> ACI com as 256 cores padrao do AutoCAD."""
    tabela = []
    
    # ACI 1-9: cores basicas
    cores_basicas = [
        (255, 0, 0),      # 1 - Vermelho
        (255, 255, 0),    # 2 - Amarelo
        (0, 255, 0),      # 3 - Verde
        (0, 255, 255),    # 4 - Cyan
        (0, 0, 255),      # 5 - Azul
        (255, 0, 255),    # 6 - Magenta
        (255, 255, 255),  # 7 - Branco
        (128, 128, 128),  # 8 - Cinza escuro
        (192, 192, 192),  # 9 - Cinza claro
    ]
    for i, (r, g, b) in enumerate(cores_basicas):
        tabela.append((r, g, b, i + 1))
    
    # ACI 10-249: cores do espectro (geradas algoritmicamente)
    # Baseado na tabela oficial do AutoCAD
    hues = [
        (255, 0, 0),     # 0° Vermelho
        (255, 127, 0),   # 30° Laranja
        (255, 255, 0),   # 60° Amarelo
        (0, 255, 0),     # 120° Verde
        (0, 255, 255),   # 180° Cyan
        (0, 0, 255),     # 240° Azul
        (255, 0, 255),   # 300° Magenta
    ]
    
    # Gerar cores intermediarias para ACI 10-249
    for aci in range(10, 250):
        # Calcular matiz, saturacao e luminosidade baseado no indice
        grupo = (aci - 10) // 10  # 0-23 grupos de matiz
        variacao = (aci - 10) % 10  # 0-9 variacao dentro do grupo
        
        # Angulo de matiz
        angulo = grupo * 15  # 0 a 345 graus em passos de 15
        
        # Converter HSL para RGB simplificado
        h = angulo / 360.0
        
        # Variacao controla luminosidade/saturacao
        if variacao < 5:
            s = 1.0
            l = 0.5 + variacao * 0.1  # 0.5 a 0.9
        else:
            s = 1.0 - (variacao - 5) * 0.2  # 1.0 a 0.0
            l = 0.5
        
        # HSL para RGB
        if s == 0:
            r_f = g_f = b_f = l
        else:
            def hue2rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r_f = hue2rgb(p, q, h + 1/3)
            g_f = hue2rgb(p, q, h)
            b_f = hue2rgb(p, q, h - 1/3)
        
        r = max(0, min(255, int(round(r_f * 255))))
        g = max(0, min(255, int(round(g_f * 255))))
        b = max(0, min(255, int(round(b_f * 255))))
        tabela.append((r, g, b, aci))
    
    # ACI 250-255: escala de cinza
    cinzas = [
        (51, 51, 51),     # 250
        (91, 91, 91),     # 251
        (132, 132, 132),  # 252
        (173, 173, 173),  # 253
        (214, 214, 214),  # 254
        (255, 255, 255),  # 255
    ]
    for i, (r, g, b) in enumerate(cinzas):
        tabela.append((r, g, b, 250 + i))
    
    return tabela

_TABELA_ACI = _gerar_tabela_aci()


# =============================================================
# UTILIDADES DE COR
# =============================================================
def rgb_float_to_int(r, g, b):
    """Converte RGB float (0.0-1.0) para tupla int (0-255)."""
    return (
        max(0, min(255, int(round(r * 255)))),
        max(0, min(255, int(round(g * 255)))),
        max(0, min(255, int(round(b * 255)))),
    )


def rgb_to_hex(ri, gi, bi):
    """Retorna string hex como '00FF00'."""
    return "{:02X}{:02X}{:02X}".format(ri, gi, bi)


def rgb_to_aci(ri, gi, bi):
    """
    Encontra o ACI (AutoCAD Color Index) mais proximo via distancia euclidiana.
    Usa a tabela completa de 256 cores do AutoCAD.
    """
    melhor_dist = float('inf')
    aci_escolhido = 7
    
    for r, g, b, aci in _TABELA_ACI:
        dist = (ri - r)**2 + (gi - g)**2 + (bi - b)**2
        if dist < melhor_dist:
            melhor_dist = dist
            aci_escolhido = aci
            if dist == 0:
                break
    
    return aci_escolhido


def mapear_cor_inteligente(ri, gi, bi):
    """
    Mapeia cores conforme a logica do script LISP:
    - Preto (RGB < 16,16,16) -> ACI 7 (White/Black), Sem TrueColor
    - Cinzas ACI (8, 9, 250-255) -> Mantem ACI original, TrueColor RGB 51,51,51
    - Outras -> ACI mais proximo, TrueColor setado
    
    Retorna (aci, rgb_tupla_ou_None)
    """
    aci = rgb_to_aci(ri, gi, bi)
    
    # CASO 1: Preto Puro ou muito proximo (RGB 0,0,0 ate 15,15,15)
    if ri < 16 and gi < 16 and bi < 16:
        return 7, None  # Cor 7: Branco em fundo escuro, Preto em claro
    
    # CASO 2: Tons de Cinza ACI especificos (8, 9, 250-255)
    if aci == 8 or aci == 9 or (250 <= aci <= 255):
        return aci, (51, 51, 51)  # RGB 51,51,51 (cinza visivel em ambos)
    
    # CASO PADRAO: Usa RGB exato
    return aci, (ri, gi, bi)


# =============================================================
# DETECCAO AUTOMATICA DE ESCALA
# =============================================================
# Tamanhos de papel padrao em mm (largura, altura)
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

# Escalas comuns em desenhos tecnicos
ESCALAS_COMUNS = [
    50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
    600, 750, 1000, 1250, 1500, 2000, 2500, 5000, 10000,
]


def detectar_escala_por_geometria(page, escala_conversao=0.3528):
    """
    Detecta a escala do desenho comparando textos de metragem de cabos
    (ex: 'CAA 2 ABC 160 m') com o comprimento geometrico real das
    polylines no DXF convertido.
    
    Logica:
    - Texto diz '160 m' e polyline no DXF tem length ~160 -> escala 1:1000
    - Texto diz '160 m' e polyline no DXF tem length ~320 -> escala 1:500
    - Formula: escala = 1000 * text_metros / dxf_length
    
    Retorna a escala como inteiro (ex: 500, 1000) ou 1000 como fallback.
    NAO ALTERA A CONVERSAO, apenas detecta para exibicao.
    """
    H = page.rect.height
    
    # ---- Extrair textos com metragem (ex: '160 m', '39 m') ----
    metragens = []  # lista de (valor_metros, x_centro, y_centro)
    blocos = page.get_text("dict")
    
    for bloco in blocos.get("blocks", []):
        if bloco.get("type") != 0:
            continue
        for linha in bloco.get("lines", []):
            # Concatenar todos os spans da linha
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
            
            # Procurar padroes de metragem: "123 m", "45,5 m", "67.8m"
            match = re.search(r'(\d+(?:[.,]\d+)?)\s*m\b', texto_linha)
            if match:
                valor_str = match.group(1).replace(',', '.')
                try:
                    valor = float(valor_str)
                    if 5 <= valor <= 5000:  # metragem plausivel de cabo
                        cx = (bbox_linha[0] + bbox_linha[2]) / 2
                        cy = (bbox_linha[1] + bbox_linha[3]) / 2
                        metragens.append((valor, cx, cy))
                except ValueError:
                    continue
    
    if not metragens:
        print("  Nenhum texto de metragem encontrado, usando escala padrao 1:1000")
        return 1000
    
    # ---- Extrair paths (linhas/cabos) e seus comprimentos ----
    paths = page.get_drawings()
    
    # Calcular comprimento de cada path em coordenadas DXF (mm)
    path_infos = []  # lista de (comprimento_dxf, x_centro_pdf, y_centro_pdf)
    for p in paths:
        items = p.get("items", [])
        cor = p.get("color")
        if not items or not cor:
            continue
        
        # Calcular comprimento total do path
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
                # Aproximar comprimento de bezier
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
        
        if comprimento_pdf < 10 or not xs:  # ignorar paths muito curtos
            continue
        
        comprimento_dxf = comprimento_pdf * escala_conversao
        cx_path = (min(xs) + max(xs)) / 2
        cy_path = (min(ys) + max(ys)) / 2
        path_infos.append((comprimento_dxf, cx_path, cy_path))
    
    if not path_infos:
        print("  Nenhum path com comprimento encontrado, usando escala padrao 1:1000")
        return 1000
    
    # ---- Comparar texto vs geometria ----
    ratios = []
    for valor_m, tx_c, ty_c in metragens:
        # Encontrar o path mais proximo deste texto
        melhor_dist = float('inf')
        melhor_comprimento = None
        
        for comp_dxf, px, py in path_infos:
            dist = math.sqrt((tx_c - px)**2 + (ty_c - py)**2)
            if dist < melhor_dist:
                melhor_dist = dist
                melhor_comprimento = comp_dxf
        
        if melhor_comprimento and melhor_comprimento > 0:
            # ratio = dxf_length / texto_metros
            # 1:1000 -> ratio ~1.0, 1:500 -> ratio ~2.0
            ratio = melhor_comprimento / valor_m
            if 0.3 < ratio < 10:  # plausivel
                ratios.append(ratio)
                print(f"  Metragem: {valor_m}m, DXF length: {melhor_comprimento:.1f}, ratio: {ratio:.2f}")
    
    if not ratios:
        print("  Nao foi possivel correlacionar textos com paths, usando escala padrao 1:1000")
        return 1000
    
    # Mediana dos ratios para robustez
    ratios.sort()
    ratio_mediano = ratios[len(ratios) // 2]
    
    # escala = 1000 / ratio
    escala_calculada = 1000 / ratio_mediano
    
    # Arredondar para escala comum mais proxima
    mais_proxima = min(ESCALAS_COMUNS, key=lambda x: abs(x - escala_calculada))
    
    # Tolerancia de 30% para aceitar
    if abs(mais_proxima - escala_calculada) / max(escala_calculada, 1) < 0.3:
        print(f"  Escala detectada por geometria: 1:{mais_proxima} (ratio mediano: {ratio_mediano:.2f})")
        return mais_proxima
    
    print(f"  Escala calculada {escala_calculada:.0f} nao bate com nenhuma comum, usando 1:1000")
    return 1000


# =============================================================
# LINETYPES - Criacao dinamica a partir dos dash patterns do PDF
# =============================================================
_linetype_cache = {}


def criar_linetype_do_pdf(doc_dxf, dashes_str, escala=1.0):
    """Cria linetype no DXF a partir do dash pattern real do PDF, aplicando escala."""
    if not dashes_str or dashes_str == "[] 0" or dashes_str == "None":
        return "CONTINUOUS"

    cache_key = "{}_s{:.4f}".format(dashes_str, escala)
    if cache_key in _linetype_cache:
        return _linetype_cache[cache_key]

    try:
        num_strs = re.findall(r"[-+]?\d*\.\d+|\d+", dashes_str)
        if not num_strs:
            return "CONTINUOUS"
            
        if "[" in dashes_str and "]" in dashes_str:
            inside = dashes_str[dashes_str.index("[")+1 : dashes_str.index("]")]
            values = [float(v) for v in re.findall(r"[-+]?\d*\.\d+|\d+", inside)]
        else:
            values = [float(v) for v in num_strs[:-1]] if len(num_strs) > 1 else [float(num_strs[0])]

        if not values:
            return "CONTINUOUS"

        scaled_values = [max(0.05, v * escala) for v in values]

        pattern_elements = []
        total = 0
        for i, v in enumerate(scaled_values):
            if i % 2 == 0:
                pattern_elements.append(v)
                total += v
            else:
                pattern_elements.append(-v)
                total += v

        if not pattern_elements:
            return "CONTINUOUS"

        if len(pattern_elements) == 1:
            gap = pattern_elements[0]
            pattern_elements.append(-gap)
            total += gap

        dxf_pattern = [total] + pattern_elements

        name_parts = "_".join("{:.2f}".format(abs(v)) for v in scaled_values)
        ltype_name = "PDF_DASH_{}".format(name_parts.replace(".", "p"))

        if ltype_name not in doc_dxf.linetypes:
            doc_dxf.linetypes.add(
                ltype_name,
                pattern=dxf_pattern,
                description="Tracejado PDF escala {:.3f} [{}]".format(
                    escala, ", ".join("{:.2f}".format(v) for v in values)
                ),
            )

        _linetype_cache[cache_key] = ltype_name
        return ltype_name

    except Exception:
        return "CONTINUOUS"


# =============================================================
# BEZIER
# =============================================================
def bezier_cubica(p0, p1, p2, p3, n=20):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def bezier_quadratica(p0, p1, p2, n=12):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**2*p0[0] + 2*mt*t*p1[0] + t**2*p2[0]
        y = mt**2*p0[1] + 2*mt*t*p1[1] + t**2*p2[1]
        pts.append((x, y))
    return pts


# =============================================================
# LAYERS
# =============================================================
_layers_criados = set()


def obter_ou_criar_layer(doc_dxf, ri, gi, bi, prefixo=""):
    hex_cor = rgb_to_hex(ri, gi, bi)
    nome = "{}COR_{}".format(prefixo, hex_cor)

    if nome not in _layers_criados:
        # Aplica mapeamento inteligente de cores
        aci, rgb_final = mapear_cor_inteligente(ri, gi, bi)
        
        if nome not in doc_dxf.layers:
            layer = doc_dxf.layers.add(nome)
        else:
            layer = doc_dxf.layers.get(nome)
            
        layer.color = aci
        if rgb_final:
            layer.true_color = rgb2int(rgb_final)
        else:
            # Para Cor 7 (Preto/Branco adaptativo), discard true_color para usar apenas ACI
            layer.dxf.discard('true_color')
                 
        layer.lineweight = 0
        _layers_criados.add(nome)

    return nome


def obter_layer_texto(doc_dxf, ri, gi, bi, prefixo=""):
    hex_cor = rgb_to_hex(ri, gi, bi)
    nome = "{}TXT_{}".format(prefixo, hex_cor)

    if nome not in _layers_criados:
        # Aplica mapeamento inteligente de cores
        aci, rgb_final = mapear_cor_inteligente(ri, gi, bi)
        
        if nome not in doc_dxf.layers:
            layer = doc_dxf.layers.add(nome)
        else:
            layer = doc_dxf.layers.get(nome)
            
        layer.color = aci
        if rgb_final:
            layer.true_color = rgb2int(rgb_final)
        else:
            # Para Cor 7 (Preto/Branco adaptativo), discard true_color para usar apenas ACI
            layer.dxf.discard('true_color')
                 
        layer.lineweight = 0
        _layers_criados.add(nome)

    return nome


# =============================================================
# LINEWEIGHT
# =============================================================
def converter_lineweight(largura_pdf):
    """Retorna sempre 0 (0.00mm) para evitar linhas grossas indesejadas."""
    return 0


# =============================================================
# CONVERSAO DE PAGINA
# =============================================================
def converter_pagina(page, msp, doc_dxf, offset_y=0, escala=1.0, prefixo=""):
    H = page.rect.height

    def tx(x):
        return x * escala

    def ty(y):
        return (H - y) * escala + offset_y

    total = 0
    paths = page.get_drawings()

    # ----------------------------------------------------------
    # GEOMETRIA (paths)
    # ----------------------------------------------------------
    for idx, path in enumerate(paths):
        cor = path.get("color")
        fill = path.get("fill")
        dashes = path.get("dashes")
        largura = path.get("width") or 0.0
        items = path.get("items", [])

        if not items:
            continue

        # --- Determina cor do stroke ---
        if cor:
            ri, gi, bi = rgb_float_to_int(cor[0], cor[1], cor[2])
        elif fill and not (fill[0] > 0.95 and fill[1] > 0.95 and fill[2] > 0.95):
            ri, gi, bi = rgb_float_to_int(fill[0], fill[1], fill[2])
        else:
            ri, gi, bi = 0, 0, 0

        layer = obter_ou_criar_layer(doc_dxf, ri, gi, bi, prefixo)

        # --- Linetype ---
        dashes_str = str(dashes) if dashes else ""
        linetype = criar_linetype_do_pdf(doc_dxf, dashes_str, escala=escala)

        # --- Lineweight ---
        lw = converter_lineweight(largura)

        # Aplica mapeamento para a entidade
        aci_ent, rgb_ent = mapear_cor_inteligente(ri, gi, bi)
        atribs = {
            "layer": layer,
            "color": aci_ent,
            "linetype": linetype,
            "lineweight": -1,
        }
        if rgb_ent:
            atribs["true_color"] = rgb2int(rgb_ent)

        # --- HATCH para fill (preenchimento solido) ---
        if fill:
            fill_ri, fill_gi, fill_bi = rgb_float_to_int(fill[0], fill[1], fill[2])

            # Ignorar fills brancos puros (fundo)
            if fill_ri > 250 and fill_gi > 250 and fill_bi > 250:
                if not cor:
                    continue

            pontos = []
            for it in items:
                if not it:
                    continue
                if it[0] == "l":
                    pontos.append((tx(it[1].x), ty(it[1].y)))
                    pontos.append((tx(it[2].x), ty(it[2].y)))
                elif it[0] == "re":
                    rect = it[1]
                    pontos.extend([
                        (tx(rect.x0), ty(rect.y0)),
                        (tx(rect.x1), ty(rect.y0)),
                        (tx(rect.x1), ty(rect.y1)),
                        (tx(rect.x0), ty(rect.y1)),
                    ])
                elif it[0] == "c":
                    if len(it) >= 5:
                        pts_bez = bezier_cubica(
                            (tx(it[1].x), ty(it[1].y)),
                            (tx(it[2].x), ty(it[2].y)),
                            (tx(it[3].x), ty(it[3].y)),
                            (tx(it[4].x), ty(it[4].y)),
                        )
                        pontos.extend(pts_bez)
                elif it[0] == "qu":
                    qq = it[1]
                    pontos.extend([
                        (tx(qq.ul.x), ty(qq.ul.y)),
                        (tx(qq.ur.x), ty(qq.ur.y)),
                        (tx(qq.lr.x), ty(qq.lr.y)),
                        (tx(qq.ll.x), ty(qq.ll.y)),
                    ])

            pontos_unicos = []
            seen = set()
            for p in pontos:
                key = (round(p[0], 2), round(p[1], 2))
                if key not in seen:
                    seen.add(key)
                    pontos_unicos.append(p)

            if len(pontos_unicos) >= 3:
                try:
                    fill_layer = obter_ou_criar_layer(
                        doc_dxf, fill_ri, fill_gi, fill_bi, prefixo
                    )
                    aci_fill, rgb_fill = mapear_cor_inteligente(fill_ri, fill_gi, fill_bi)
                    dxf_attrs = {
                        "layer": fill_layer,
                        "color": aci_fill,
                        "lineweight": -1,
                    }
                    if rgb_fill:
                        dxf_attrs["true_color"] = rgb2int(rgb_fill)
                        
                    hatch = msp.add_hatch(dxfattribs=dxf_attrs)
                    hatch.paths.add_polyline_path(
                        pontos_unicos + [pontos_unicos[0]],
                        is_closed=True
                    )
                    hatch.set_solid_fill()
                    total += 1
                except Exception:
                    pass

        # --- Se nao tem stroke, so desenha o fill (ja feito acima) ---
        if not cor:
            continue

        # --- Desenha geometria do stroke ---
        pt_acumulados = []

        def flush_points():
            nonlocal pt_acumulados
            if len(pt_acumulados) >= 2:
                pts_limpos = [pt_acumulados[0]]
                for i in range(1, len(pt_acumulados)):
                    if math.dist(pt_acumulados[i], pts_limpos[-1]) > 0.001:
                        pts_limpos.append(pt_acumulados[i])
                
                if len(pts_limpos) >= 2:
                    msp.add_lwpolyline(pts_limpos, dxfattribs=atribs).dxf.const_width = 0.0
                    return 1
            pt_acumulados = []
            return 0

        for item in items:
            if not item:
                continue
            tipo = item[0]

            try:
                if tipo == "l":
                    p1, p2 = item[1], item[2]
                    v1 = (tx(p1.x), ty(p1.y))
                    v2 = (tx(p2.x), ty(p2.y))
                    
                    if not pt_acumulados:
                        pt_acumulados = [v1, v2]
                    else:
                        if math.dist(v1, pt_acumulados[-1]) < 0.01:
                            pt_acumulados.append(v2)
                        else:
                            total += flush_points()
                            pt_acumulados = [v1, v2]

                elif tipo == "c":
                    if len(item) < 5:
                        continue
                    pts = bezier_cubica(
                        (tx(item[1].x), ty(item[1].y)),
                        (tx(item[2].x), ty(item[2].y)),
                        (tx(item[3].x), ty(item[3].y)),
                        (tx(item[4].x), ty(item[4].y)),
                    )
                    
                    if not pt_acumulados:
                        pt_acumulados.extend(pts)
                    else:
                        if math.dist(pts[0], pt_acumulados[-1]) < 0.01:
                            pt_acumulados.extend(pts[1:])
                        else:
                            total += flush_points()
                            pt_acumulados.extend(pts)

                elif tipo == "qu":
                    total += flush_points()
                    quad = item[1]
                    try:
                        p_ul = (tx(quad.ul.x), ty(quad.ul.y))
                        p_ur = (tx(quad.ur.x), ty(quad.ur.y))
                        p_lr = (tx(quad.lr.x), ty(quad.lr.y))
                        p_ll = (tx(quad.ll.x), ty(quad.ll.y))
                        msp.add_lwpolyline(
                            [p_ul, p_ur, p_lr, p_ll, p_ul],
                            dxfattribs=atribs
                        ).dxf.const_width = 0.0
                        total += 1
                    except Exception:
                        pass

                elif tipo == "re":
                    total += flush_points()
                    rect = item[1]
                    pts = [
                        (tx(rect.x0), ty(rect.y0)),
                        (tx(rect.x1), ty(rect.y0)),
                        (tx(rect.x1), ty(rect.y1)),
                        (tx(rect.x0), ty(rect.y1)),
                        (tx(rect.x0), ty(rect.y0)),
                    ]
                    msp.add_lwpolyline(pts, dxfattribs=atribs).dxf.const_width = 0.0
                    total += 1

            except Exception:
                pass
        
        # Flush final
        total += flush_points()

    # ----------------------------------------------------------
    # TEXTOS - com rotacao preservada
    # ----------------------------------------------------------
    blocos = page.get_text("dict")

    for bloco in blocos.get("blocks", []):
        if bloco.get("type") != 0:
            continue
        for linha in bloco.get("lines", []):
            direction = linha.get("dir", (1.0, 0.0))
            dx_dir, dy_dir = direction

            # No PDF: dir = (cos(a), sin(a))
            # No DXF: rotation em graus, anti-horario
            # Invertemos Y (PDF y-down -> DXF y-up)
            angulo = math.degrees(math.atan2(-dy_dir, dx_dir))

            for span in linha.get("spans", []):
                texto_bruto = span.get("text", "")
                if not texto_bruto.strip():
                    continue

                size = span.get("size", 5)
                if size < 0.3:
                    continue

                origin = span.get("origin")
                if origin:
                    x0, y0 = tx(origin[0]), ty(origin[1])
                else:
                    bbox = span["bbox"]
                    x0, y0 = tx(bbox[0]), ty(bbox[3])

                # Cor do texto
                cor_int = span.get("color", 0)
                if cor_int == 0 or cor_int is None:
                    tri, tgi, tbi = 0, 0, 0
                else:
                    tri = (cor_int >> 16) & 0xFF
                    tgi = (cor_int >> 8) & 0xFF
                    tbi = cor_int & 0xFF

                layer_txt = obter_layer_texto(doc_dxf, tri, tgi, tbi, prefixo)
                altura_txt = size * escala

                # Aplica mapeamento para o texto
                aci_txt, rgb_txt = mapear_cor_inteligente(tri, tgi, tbi)
                dxf_attrs_txt = {
                    "layer": layer_txt,
                    "char_height": altura_txt,
                    "style": "Arial",
                    "color": aci_txt,
                    "insert": (x0, y0),
                    "rotation": angulo,
                    "lineweight": -1,
                }
                if rgb_txt:
                    dxf_attrs_txt["true_color"] = rgb2int(rgb_txt)

                try:
                    mtext = msp.add_mtext(texto_bruto, dxfattribs=dxf_attrs_txt)
                    mtext.dxf.attachment_point = 7  # bottom-left
                    total += 1
                except Exception:
                    pass

    return total


# =============================================================
# FUNCAO PRINCIPAL
# =============================================================
def converter_pdf_para_dxf(caminho_pdf, caminho_dxf=None,
                            paginas=None, escala_manual=None, versao_dxf="R2010"):
    """
    Converte um PDF vetorial para DXF/DWG.
    
    Args:
        caminho_pdf: Caminho do arquivo PDF
        caminho_dxf: Caminho de saida (se None, usa mesmo nome + .dwg)
        paginas: Lista de paginas (1-based), None = todas
        escala_manual: Escala manual (ex: 0.3528). Se None, detecta automaticamente.
        versao_dxf: Versao DXF ("R2000", "R2010", "R2013", "R2018")
    
    Returns:
        dict com informacoes da conversao (escala_detectada, total_elementos, etc.)
    """
    if not os.path.exists(caminho_pdf):
        print("Arquivo nao encontrado: {}".format(caminho_pdf))
        sys.exit(1)

    if caminho_dxf is None:
        caminho_dxf = os.path.splitext(caminho_pdf)[0] + ".dwg"

    print("\nAbrindo: {}".format(caminho_pdf))
    doc_pdf = fitz.open(caminho_pdf)
    n_pags = len(doc_pdf)
    print("Paginas encontradas: {}".format(n_pags))

    if paginas is None:
        paginas = list(range(n_pags))
    else:
        paginas = [p - 1 for p in paginas if 1 <= p <= n_pags]

    # Fator de conversao FIXO: 0.3528 (1 PDF pt = 0.3528 mm)
    # Nao muda independente da escala do desenho
    escala = 0.3528
    if escala_manual is not None:
        escala = escala_manual
        print(f"  Usando escala manual: {escala}")
    else:
        print(f"  Fator de conversao: {escala}")

    doc_dxf = ezdxf.new("R2010")
    
    # Configurar layer 0
    if "0" in doc_dxf.layers:
        doc_dxf.layers.get("0").lineweight = 0
    else:
        doc_dxf.layers.add("0").lineweight = 0
    
    # Estilo Arial
    if "Arial" not in doc_dxf.styles:
        doc_dxf.styles.new("Arial", dxfattribs={"font": "arial.ttf"})
        
    doc_dxf.header["$INSUNITS"] = 0
    doc_dxf.header["$LTSCALE"] = 1.0
    doc_dxf.header["$CELTSCALE"] = 1.0
    msp = doc_dxf.modelspace()

    # Reset caches globais
    global _linetype_cache, _layers_criados
    _linetype_cache = {}
    _layers_criados = set()

    total = 0
    offset_y = 0

    for num in paginas:
        page = doc_pdf[num]
        prefixo = "P{}_".format(num + 1) if len(paginas) > 1 else ""
        print("\nConvertendo pagina {}...".format(num + 1))
        n = converter_pagina(page, msp, doc_dxf,
                             offset_y=offset_y, escala=escala, prefixo=prefixo)
        print("  {} elementos convertidos".format(n))
        total += n
        offset_y -= (page.rect.height * escala) + 50

    doc_dxf.saveas(caminho_dxf)

    # --- Detectar escala para EXIBICAO (nao altera conversao) ---
    primeira_pagina = doc_pdf[paginas[0]]
    escala_display = detectar_escala_por_geometria(primeira_pagina, escala)
    
    doc_pdf.close()

    kb = os.path.getsize(caminho_dxf) / 1024
    print("\n" + "=" * 50)
    print("Conversao concluida!")
    print("  Total de elementos : {}".format(total))
    print("  Escala detectada   : 1:{}".format(escala_display))
    print("  Fator de conversao : {:.6f}".format(escala))
    print("  Arquivo gerado     : {}".format(caminho_dxf))
    print("  Tamanho            : {:.1f} KB".format(kb))

    print("\nLayers criados:")
    for layer in doc_dxf.layers:
        if layer.dxf.name != "0" and layer.dxf.name != "Defpoints":
            print("  {}".format(layer.dxf.name))

    lts = [lt.dxf.name for lt in doc_dxf.linetypes
           if lt.dxf.name not in ("Standard", "ByBlock", "ByLayer",
                                    "CONTINUOUS", "Continuous")]
    if lts:
        print("\nLinetypes:")
        for lt in lts:
            print("  {}".format(lt))

    print("=" * 50)
    
    return {
        "escala_detectada": escala_display,
        "fator_escala": escala,
        "total_elementos": total,
        "tamanho_kb": kb,
    }


# =============================================================
# CLI
# =============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Converte PDF vetorial para DXF/DWG (fidelidade total)"
    )
    parser.add_argument("entrada", nargs="?", default="arquivo.pdf",
                        help="Caminho do arquivo PDF de entrada")
    parser.add_argument("saida", nargs="?", default=None,
                        help="Caminho do arquivo DXF/DWG de saida (opcional)")
    parser.add_argument("--pagina", "-p", type=int, default=None,
                        help="Numero da pagina a converter (1-based)")
    parser.add_argument("--todas", "-t", action="store_true",
                        help="Converte todas as paginas")
    parser.add_argument("--escala", "-e", type=float, default=None,
                        help="Fator de escala manual (default: auto-detectar)")
    parser.add_argument("--versao", default="R2010",
                        choices=["R2000", "R2010", "R2013", "R2018"],
                        help="Versao do DXF (default: R2010)")
    args = parser.parse_args()

    if args.todas:
        paginas = None
    elif args.pagina:
        paginas = [args.pagina]
    else:
        paginas = None  # Todas por padrao

    converter_pdf_para_dxf(
        caminho_pdf=args.entrada,
        caminho_dxf=args.saida,
        paginas=paginas,
        escala_manual=args.escala,
        versao_dxf=args.versao
    )
