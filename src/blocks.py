"""
Conversão de Símbolos em Blocos AutoCAD
========================================
Detecta padrões geométricos específicos no DXF convertido e os substitui
por blocos AutoCAD nomeados (INSERT references).

Símbolos detectados:
    - NO_PERTO_FORMADO: Nó de rede formado (polilinha + hatch, área ≈ 2.6437)
    - POSTE_EXISTENTE_FORMADO: Poste tipo A (polilinha + linha interna)
    - POSTE_EXISTENTE_ATERRADO: Poste tipo B/C (com fios de aterramento)
    - TRAFO_EXISTENTE_FORMADO: Transformador (polilinha + hatch + linha)
"""

import math
import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44


# =========================================================================
# UTILITÁRIOS GEOMÉTRICOS E MATEMÁTICOS
# =========================================================================

def calcular_area_shoelace(pontos):
    """Calcula a área de uma polilinha fechada usando a fórmula Shoelace."""
    n = len(pontos)
    if n < 3:
        return 0.0
    soma = 0.0
    for i in range(n):
        p1 = pontos[i]
        p2 = pontos[(i + 1) % n]
        soma += p1[0] * p2[1] - p2[0] * p1[1]
    return abs(soma) / 2.0


def get_area(entity):
    """Obtém a área de LWPOLYLINE ou HATCH."""
    if entity.dxftype() == 'LWPOLYLINE':
        pts = [pt[:2] for pt in entity.get_points()]
        return calcular_area_shoelace(pts)
    elif entity.dxftype() == 'HATCH':
        total_area = 0.0
        try:
            for path in entity.paths.paths:
                if hasattr(path, 'vertices'):
                    pts = [v[:2] for v in path.vertices]
                    total_area += calcular_area_shoelace(pts)
        except Exception:
            pass
        return total_area
    return 0.0


def _extrair_vertices_hatch(entity):
    """Extrai todos os vértices dos boundary paths de um HATCH."""
    pts = []
    try:
        for path in entity.paths.paths:
            if hasattr(path, 'vertices'):
                for v in path.vertices:
                    pts.append((float(v[0]), float(v[1])))
            elif hasattr(path, 'edges'):
                for edge in path.edges:
                    if hasattr(edge, 'start'):
                        pts.append((float(edge.start[0]), float(edge.start[1])))
                    if hasattr(edge, 'end'):
                        pts.append((float(edge.end[0]), float(edge.end[1])))
    except Exception:
        pass
    return pts


def get_bbox(entity):
    """Retorna bounding box da entidade como ((xmin, ymin), (xmax, ymax))."""
    if entity.dxftype() == 'HATCH':
        pts = _extrair_vertices_hatch(entity)
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return ((min(xs), min(ys)), (max(xs), max(ys)))
        return None

    try:
        ext = bbox.extents([entity])
        if ext:
            mn, mx = ext[0], ext[1]
            if abs(mx[0] - mn[0]) > 0.0001 or abs(mx[1] - mn[1]) > 0.0001:
                return (mn[:2], mx[:2])
    except Exception:
        pass

    if entity.dxftype() == 'LWPOLYLINE':
        pts = [pt[:2] for pt in entity.get_points()]
        if pts:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            return ((min(xs), min(ys)), (max(xs), max(ys)))

    return None


def dentro_bbox(pt, bbox_min, bbox_max):
    """Verifica se um ponto (x, y) está dentro do bounding box com tolerância."""
    return (bbox_min[0] - 0.001 <= pt[0] <= bbox_max[0] + 0.001 and
            bbox_min[1] - 0.001 <= pt[1] <= bbox_max[1] + 0.001)


def get_centro(entity):
    """Obtém o centro de uma entidade usando bounding box ou média de vértices."""
    if entity.dxftype() == 'HATCH':
        pts = _extrair_vertices_hatch(entity)
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        return (0.0, 0.0)

    b = get_bbox(entity)
    if b:
        return ((b[0][0] + b[1][0]) / 2.0, (b[0][1] + b[1][1]) / 2.0)

    if entity.dxftype() == 'LWPOLYLINE':
        pts = [pt[:2] for pt in entity.get_points()]
        if pts:
            return (sum(float(p[0]) for p in pts) / len(pts), sum(float(p[1]) for p in pts) / len(pts))
    elif entity.dxftype() == 'LINE':
        p1 = entity.dxf.start
        p2 = entity.dxf.end
        return ((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0)
    return (0.0, 0.0)


def get_comprimento(entity):
    """Obtém o comprimento de LWPOLYLINE ou LINE."""
    if entity.dxftype() == 'LINE':
        p1 = entity.dxf.start
        p2 = entity.dxf.end
        return math.dist((p1.x, p1.y), (p2.x, p2.y))
    elif entity.dxftype() == 'LWPOLYLINE':
        pts = [pt[:2] for pt in entity.get_points()]
        length = 0.0
        for i in range(len(pts) - 1):
            length += math.dist(pts[i], pts[i+1])
        if entity.is_closed and len(pts) > 2:
            length += math.dist(pts[-1], pts[0])
        return length
    return 0.0


def get_angulo(entity):
    """Ângulo da primeira aresta de LWPOLYLINE ou LINE (em radianos)."""
    if entity.dxftype() == 'LWPOLYLINE':
        pts = [pt[:2] for pt in entity.get_points()]
        if len(pts) >= 2:
            return math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])
    elif entity.dxftype() == 'LINE':
        p1 = entity.dxf.start
        p2 = entity.dxf.end
        return math.atan2(p2.y - p1.y, p2.x - p1.x)
    return 0.0


def get_block_angle(doc, block_name):
    """Retorna o ângulo da primeira polyline ou linha contida na definição de um bloco."""
    if block_name in doc.blocks:
        block = doc.blocks.get(block_name)
        for entity in block:
            if entity.dxftype() in ('LWPOLYLINE', 'LINE'):
                return get_angulo(entity)
    return None


def pef_identificar_tipo(area, length):
    """Identifica o tipo de poste (A, B ou C) pelo menor erro combinado."""
    PEF_AREA_A = 17.9521; PEF_LEN_A = 4.0265
    PEF_AREA_B = 17.2936; PEF_LEN_B = 3.9918
    PEF_AREA_C = 17.2805; PEF_LEN_C = 3.9953

    TOL_AREA = 0.15
    TOL_LEN = 0.10

    da = abs(area - PEF_AREA_A) / TOL_AREA + abs(length - PEF_LEN_A) / TOL_LEN
    db = abs(area - PEF_AREA_B) / TOL_AREA + abs(length - PEF_LEN_B) / TOL_LEN
    dc = abs(area - PEF_AREA_C) / TOL_AREA + abs(length - PEF_LEN_C) / TOL_LEN

    if da <= db and da <= dc and da <= 2.0:
        return "A"
    elif db <= da and db <= dc and db <= 2.0:
        return "B"
    elif dc <= da and dc <= db and dc <= 2.0:
        return "C"
    return None


# =========================================================================
# ROTINAS DE CONVERSÃO
# =========================================================================

def converter_no_perto_formado(msp, doc):
    """Rotina 1: NO_PERTO_FORMADO (Pares de polilinhas e hatches na layer COR_000000)."""
    blocos_criados = 0
    lista_poly = []
    lista_hatch = []

    NPF_AREA = 2.6437
    NPF_AREA_ALVO = 0.6761
    NPF_TOL_AREA = 0.010
    NPF_TOLERANCIA = 0.5
    NPF_NOME_BLOCO = "NO_PERTO_FORMADO"

    for entity in msp:
        if not entity.is_alive:
            continue

        layer = entity.dxf.layer
        if not layer.endswith("COR_000000"):
            continue

        if entity.dxftype() == 'LWPOLYLINE':
            area = get_area(entity)
            if abs(area - NPF_AREA) <= NPF_TOL_AREA:
                centro = get_centro(entity)
                lista_poly.append({"entity": entity, "centro": centro, "area": area})
        elif entity.dxftype() == 'HATCH':
            area = get_area(entity)
            if abs(area - NPF_AREA) <= NPF_TOL_AREA:
                centro = get_centro(entity)
                lista_hatch.append({"entity": entity, "centro": centro})

    pares = []
    hatches_usados = set()

    for poly_item in lista_poly:
        poly_ent = poly_item["entity"]
        poly_center = poly_item["centro"]

        melhor_hatch = None
        melhor_dist = float('inf')

        for hatch_item in lista_hatch:
            h_ent = hatch_item["entity"]
            h_center = hatch_item["centro"]

            if h_ent not in hatches_usados:
                d = math.dist(poly_center, h_center)
                if d < melhor_dist:
                    melhor_dist = d
                    melhor_hatch = h_ent

        if melhor_hatch and melhor_dist <= NPF_TOLERANCIA:
            hatches_usados.add(melhor_hatch)
            pares.append({
                "poly": poly_ent,
                "hatch": melhor_hatch,
                "centro": poly_center,
                "area_real": poly_item["area"]
            })

    if not pares:
        return 0

    bloco_existe = NPF_NOME_BLOCO in doc.blocks

    for par in pares:
        poly = par["poly"]
        hatch = par["hatch"]
        cx, cy = par["centro"]
        area_real = par["area_real"]

        if not (poly.is_alive and hatch.is_alive):
            continue

        escala = math.sqrt(NPF_AREA_ALVO / area_real)

        mat = Matrix44.chain(
            Matrix44.translate(-cx, -cy, 0),
            Matrix44.scale(escala, escala, 1.0),
            Matrix44.translate(cx, cy, 0)
        )
        poly.transform(mat)
        hatch.transform(mat)

        if not bloco_existe:
            block_def = doc.blocks.new(name=NPF_NOME_BLOCO)
            for ent in (poly, hatch):
                copied = ent.copy()
                copied.translate(-cx, -cy, 0)
                block_def.add_entity(copied)
            bloco_existe = True

        layer_nome = poly.dxf.layer
        msp.delete_entity(poly)
        msp.delete_entity(hatch)

        msp.add_blockref(NPF_NOME_BLOCO, insert=(cx, cy), dxfattribs={
            'layer': layer_nome,
            'rotation': 0.0
        })
        blocos_criados += 1

    return blocos_criados


def converter_poste_existente(msp, doc, escala_poste=1.0):
    """Rotina 2: POSTE_EXISTENTE (FORMADO/ATERRADO)."""
    blocos_criados = 0
    lista_quad = []
    lista_linha = []
    lista_ater = []

    PEF_NOME_FORMADO = "POSTE_EXISTENTE_FORMADO"
    PEF_NOME_ATERRADO = "POSTE_EXISTENTE_ATERRADO"

    for entity in msp:
        if not entity.is_alive:
            continue

        layer = entity.dxf.layer

        # Fios de aterramento (COR_994533)
        if layer.endswith("COR_994533"):
            if entity.dxftype() in ('LWPOLYLINE', 'LINE'):
                length = get_comprimento(entity)
                centro = get_centro(entity)
                lista_ater.append({"entity": entity, "len": length, "centro": centro})

        # Poste principal (COR_000000)
        elif layer.endswith("COR_000000"):
            if entity.dxftype() == 'LWPOLYLINE':
                area = get_area(entity)
                if 16.85 <= area <= 18.10:
                    centro = get_centro(entity)
                    bbox_val = get_bbox(entity)
                    ang = get_angulo(entity)
                    if bbox_val:
                        lista_quad.append({
                            "entity": entity,
                            "area": area,
                            "centro": centro,
                            "bbox": bbox_val,
                            "ang": ang
                        })
                length = get_comprimento(entity)
                if 3.89 <= length <= 4.13:
                    centro = get_centro(entity)
                    lista_linha.append({"entity": entity, "len": length, "centro": centro})
            elif entity.dxftype() == 'LINE':
                length = get_comprimento(entity)
                if 3.89 <= length <= 4.13:
                    centro = get_centro(entity)
                    lista_linha.append({"entity": entity, "len": length, "centro": centro})

    pares = []
    linhas_usadas = set()
    aterramentos_usados = set()

    for q_item in lista_quad:
        q_ent = q_item["entity"]
        q_center = q_item["centro"]
        q_bbox = q_item["bbox"]
        q_ang = q_item["ang"]

        for l_item in lista_linha:
            l_ent = l_item["entity"]
            l_len = l_item["len"]
            l_center = l_item["centro"]

            if l_ent not in linhas_usadas:
                if dentro_bbox(l_center, q_bbox[0], q_bbox[1]):
                    tipo = pef_identificar_tipo(q_item["area"], l_len)

                    if tipo:
                        ater_ents = []
                        if tipo in ("B", "C"):
                            TOL_ATER = 0.10
                            PEF_LEN_ATER = [1.3051, 2.0872, 1.4571, 1.0432]

                            encontrados = [None, None, None, None]
                            for a_item in lista_ater:
                                a_ent = a_item["entity"]
                                if a_ent in aterramentos_usados or a_ent in ater_ents:
                                    continue

                                d = math.dist(q_center, a_item["centro"])
                                if d <= 25.0:
                                    for idx, ref_len in enumerate(PEF_LEN_ATER):
                                        if encontrados[idx] is None and abs(a_item["len"] - ref_len) <= TOL_ATER:
                                            encontrados[idx] = a_ent
                                            break

                            if all(encontrados):
                                ater_ents = encontrados
                            else:
                                continue

                        linhas_usadas.add(l_ent)
                        for ae in ater_ents:
                            aterramentos_usados.add(ae)

                        pares.append({
                            "quad": q_ent,
                            "linha": l_ent,
                            "ater": ater_ents,
                            "tipo": tipo,
                            "centro": q_center,
                            "ang": q_ang
                        })
                        break

    if not pares:
        return 0

    bloco_formado_existe = PEF_NOME_FORMADO in doc.blocks
    bloco_aterrado_existe = PEF_NOME_ATERRADO in doc.blocks

    ang_ref_formado = get_block_angle(doc, PEF_NOME_FORMADO)
    ang_ref_aterrado = get_block_angle(doc, PEF_NOME_ATERRADO)

    for par in pares:
        q_ent = par["quad"]
        l_ent = par["linha"]
        ater_ents = par["ater"]
        tipo = par["tipo"]
        cx, cy = par["centro"]
        ang_quad = par["ang"]

        all_ents = [q_ent, l_ent] + ater_ents
        if not all(e.is_alive for e in all_ents):
            continue

        # Redimensiona o poste em torno do proprio centro (nao sai do lugar)
        if escala_poste != 1.0:
            mat = Matrix44.chain(
                Matrix44.translate(-cx, -cy, 0),
                Matrix44.scale(escala_poste, escala_poste, escala_poste),
                Matrix44.translate(cx, cy, 0)
            )
            for ent in all_ents:
                ent.transform(mat)

        nome_bloco = PEF_NOME_ATERRADO if tipo in ("B", "C") else PEF_NOME_FORMADO

        if tipo in ("B", "C"):
            if not bloco_aterrado_existe:
                block_def = doc.blocks.new(name=nome_bloco)
                for ent in all_ents:
                    copied = ent.copy()
                    copied.translate(-cx, -cy, 0)
                    block_def.add_entity(copied)
                bloco_aterrado_existe = True
                ang_ref_aterrado = ang_quad

            ang_ref = ang_ref_aterrado if ang_ref_aterrado is not None else ang_quad
            rotacao_deg = math.degrees(ang_quad - ang_ref)

        else:
            if not bloco_formado_existe:
                block_def = doc.blocks.new(name=nome_bloco)
                for ent in all_ents:
                    copied = ent.copy()
                    copied.translate(-cx, -cy, 0)
                    block_def.add_entity(copied)
                bloco_formado_existe = True
                ang_ref_formado = ang_quad

            ang_ref = ang_ref_formado if ang_ref_formado is not None else ang_quad
            rotacao_deg = math.degrees(ang_quad - ang_ref)

        layer_nome = q_ent.dxf.layer
        for ent in all_ents:
            msp.delete_entity(ent)

        msp.add_blockref(nome_bloco, insert=(cx, cy), dxfattribs={
            'layer': layer_nome,
            'rotation': rotacao_deg
        })
        blocos_criados += 1

    return blocos_criados


def converter_trafo_existente(msp, doc):
    """Rotina 4: TRAFO_EXISTENTE_FORMADO (Polilinha + Hatch + Linha)."""
    blocos_criados = 0
    lista_quad = []
    lista_hatch = []
    lista_linha = []

    TRAFO_AREA = 16.3433
    TRAFO_LEN = 4.2512
    TOL_AREA = 0.15
    TOL_LEN = 0.10
    TRAFO_NOME_BLOCO = "TRAFO_EXISTENTE_FORMADO"

    for entity in msp:
        if not entity.is_alive:
            continue

        layer = entity.dxf.layer
        if not layer.endswith("COR_000000"):
            continue

        if entity.dxftype() == 'LWPOLYLINE':
            area = get_area(entity)
            if abs(area - TRAFO_AREA) <= TOL_AREA:
                centro = get_centro(entity)
                bbox_val = get_bbox(entity)
                ang = get_angulo(entity)
                lista_quad.append({"entity": entity, "centro": centro, "bbox": bbox_val, "ang": ang})
            length = get_comprimento(entity)
            if abs(length - TRAFO_LEN) <= TOL_LEN:
                centro = get_centro(entity)
                lista_linha.append({"entity": entity, "centro": centro})
        elif entity.dxftype() == 'HATCH':
            area = get_area(entity)
            if abs(area - TRAFO_AREA) <= TOL_AREA:
                centro = get_centro(entity)
                lista_hatch.append({"entity": entity, "centro": centro})
        elif entity.dxftype() == 'LINE':
            length = get_comprimento(entity)
            if abs(length - TRAFO_LEN) <= TOL_LEN:
                centro = get_centro(entity)
                lista_linha.append({"entity": entity, "centro": centro})

    pares = []
    hatch_usados = set()
    linhas_usadas = set()

    for q_item in lista_quad:
        q_ent = q_item["entity"]
        q_center = q_item["centro"]
        q_ang = q_item["ang"]

        melhor_hatch = None
        melhor_hatch_dist = float('inf')

        for h_item in lista_hatch:
            h_ent = h_item["entity"]
            if h_ent not in hatch_usados:
                d = math.dist(q_center, h_item["centro"])
                if d < melhor_hatch_dist:
                    melhor_hatch_dist = d
                    melhor_hatch = h_ent

        if melhor_hatch and melhor_hatch_dist <= 5.0:
            melhor_linha = None
            melhor_linha_dist = float('inf')

            for l_item in lista_linha:
                l_ent = l_item["entity"]
                if l_ent not in linhas_usadas:
                    d = math.dist(q_center, l_item["centro"])
                    if d < melhor_linha_dist:
                        melhor_linha_dist = d
                        melhor_linha = l_ent

            if melhor_linha and melhor_linha_dist <= 15.0:
                hatch_usados.add(melhor_hatch)
                linhas_usadas.add(melhor_linha)
                pares.append({
                    "quad": q_ent,
                    "hatch": melhor_hatch,
                    "linha": melhor_linha,
                    "centro": q_center,
                    "ang": q_ang
                })

    if not pares:
        return 0

    bloco_existe = TRAFO_NOME_BLOCO in doc.blocks
    ang_ref = get_block_angle(doc, TRAFO_NOME_BLOCO)

    for par in pares:
        q_ent = par["quad"]
        h_ent = par["hatch"]
        l_ent = par["linha"]
        cx, cy = par["centro"]
        ang_atual = par["ang"]

        all_ents = [q_ent, h_ent, l_ent]
        if not all(e.is_alive for e in all_ents):
            continue

        if not bloco_existe:
            block_def = doc.blocks.new(name=TRAFO_NOME_BLOCO)
            for ent in all_ents:
                copied = ent.copy()
                copied.translate(-cx, -cy, 0)
                block_def.add_entity(copied)
            bloco_existe = True
            ang_ref = ang_atual

        ref_angle = ang_ref if ang_ref is not None else ang_atual
        rotacao_deg = math.degrees(ang_atual - ref_angle)

        layer_nome = q_ent.dxf.layer
        for ent in all_ents:
            msp.delete_entity(ent)

        msp.add_blockref(TRAFO_NOME_BLOCO, insert=(cx, cy), dxfattribs={
            'layer': layer_nome,
            'rotation': rotacao_deg
        })
        blocos_criados += 1

    return blocos_criados


# =========================================================================
# PARAMETROS DE ESCALA
# =========================================================================

# Fator de escala aplicado aos postes quando o desenho esta na escala 1:1000,
# para que fiquem com o mesmo tamanho dos postes de 1:500 (comparados via align).
ESCALA_POSTE_1_1000 = 0.7996


# =========================================================================
# ORQUESTRADOR PRINCIPAL
# =========================================================================

def executar_conversao_blocos(msp, doc, escala_desenho=None):
    """Executa as rotinas de conversão em lote e retorna o total de blocos criados."""
    escala_poste = ESCALA_POSTE_1_1000 if escala_desenho == 1000 else 1.0
    total = 0
    total += converter_no_perto_formado(msp, doc)
    total += converter_poste_existente(msp, doc, escala_poste)
    total += converter_trafo_existente(msp, doc)
    return total
