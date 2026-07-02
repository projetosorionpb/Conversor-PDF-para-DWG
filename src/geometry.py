"""
Utilitários Geométricos — Bézier, Linetypes e Lineweight
==========================================================
Funções para processamento de curvas de Bézier e criação dinâmica
de linetypes no DXF a partir dos dash patterns do PDF.
"""

import re


# =============================================================
# BÉZIER
# =============================================================

def bezier_cubica(p0, p1, p2, p3, n=20):
    """Interpola uma curva de Bézier cúbica em `n` pontos."""
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def bezier_quadratica(p0, p1, p2, n=12):
    """Interpola uma curva de Bézier quadrática em `n` pontos."""
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**2*p0[0] + 2*mt*t*p1[0] + t**2*p2[0]
        y = mt**2*p0[1] + 2*mt*t*p1[1] + t**2*p2[1]
        pts.append((x, y))
    return pts


# =============================================================
# LINETYPES — Criação dinâmica a partir dos dash patterns do PDF
# =============================================================

_linetype_cache = {}


def reset_linetype_cache():
    """Limpa o cache de linetypes para nova conversão."""
    global _linetype_cache
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
# LINEWEIGHT
# =============================================================

def converter_lineweight(largura_pdf):
    """Retorna sempre 0 (0.00mm) para evitar linhas grossas indesejadas."""
    return 0
