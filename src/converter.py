"""
Motor Principal de Conversão
=============================
Orquestra a conversão completa do PDF para DXF/DWG, coordenando
os módulos de geometria, cores, layers, blocos e textos.
"""

import sys
import os
import math

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

from src.colors import rgb_float_to_int, mapear_cor_inteligente
from src.geometry import bezier_cubica, criar_linetype_do_pdf, converter_lineweight, reset_linetype_cache
from src.layers import obter_ou_criar_layer, reset_layers
from src.scale_detector import detectar_escala_por_geometria
from src.text import processar_textos
from src.blocks import executar_conversao_blocos


def converter_pagina(page, msp, doc_dxf, offset_y=0, escala=1.0, prefixo="", escala_desenho=None):
    """Converte uma página individual do PDF para o ModelSpace do DXF."""
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

        # --- HATCH para fill (preenchimento sólido) ---
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

        # --- Se não tem stroke, só desenha o fill (já feito acima) ---
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
    # TEXTOS - com rotação preservada
    # ----------------------------------------------------------
    total = processar_textos(page, msp, doc_dxf, offset_y, escala, prefixo, escala_desenho, tx, ty, total)

    return total


# =============================================================
# FUNCAO PRINCIPAL
# =============================================================
def converter_pdf_para_dxf(caminho_pdf, caminho_dxf=None,
                            paginas=None, escala_manual=None, versao_dxf="R2010",
                            converter_blocos=False):
    """
    Converte um PDF vetorial para DXF/DWG.

    Args:
        caminho_pdf: Caminho do arquivo PDF
        caminho_dxf: Caminho de saída (se None, usa mesmo nome + .dwg)
        paginas: Lista de páginas (1-based), None = todas
        escala_manual: Escala manual (ex: 0.3528). Se None, detecta automaticamente.
        versao_dxf: Versão DXF ("R2000", "R2010", "R2013", "R2018")
        converter_blocos: Se True, tenta converter símbolos em blocos do AutoCAD.

    Returns:
        dict com informações da conversão (escala_detectada, total_elementos, etc.)
    """
    reset_layers()
    reset_linetype_cache()

    if not os.path.exists(caminho_pdf):
        print("Arquivo não encontrado: {}".format(caminho_pdf))
        sys.exit(1)

    if caminho_dxf is None:
        caminho_dxf = os.path.splitext(caminho_pdf)[0] + ".dwg"

    print("\nAbrindo: {}".format(caminho_pdf))
    doc_pdf = fitz.open(caminho_pdf)
    n_pags = len(doc_pdf)
    print("Páginas encontradas: {}".format(n_pags))

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

    total = 0
    offset_y = 0

    # --- Detectar escala ANTES da conversao para aplicar regras condicionais ---
    print("\nDetectando escala do desenho...")
    primeira_pagina_pre = doc_pdf[paginas[0]]
    escala_desenho = detectar_escala_por_geometria(primeira_pagina_pre, escala)
    print("  Escala identificada: 1:{}".format(escala_desenho))
    if escala_desenho in (500, 1000):
        print("  >> Escala 1:{} detectada: padronização de tamanho de texto ATIVA".format(escala_desenho))
    else:
        print("  >> Padronização de tamanho de texto INATIVA (somente para 1:500 e 1:1000)")

    for num in paginas:
        page = doc_pdf[num]
        prefixo = "P{}_".format(num + 1) if len(paginas) > 1 else ""
        print("\nConvertendo página {}...".format(num + 1))
        n = converter_pagina(page, msp, doc_dxf,
                             offset_y=offset_y, escala=escala, prefixo=prefixo,
                             escala_desenho=escala_desenho)
        print("  {} elementos convertidos".format(n))
        total += n
        offset_y -= (page.rect.height * escala) + 50

    blocos_criados = 0
    if converter_blocos:
        print("\nIniciando conversão de símbolos em blocos...")
        try:
            blocos_criados = executar_conversao_blocos(msp, doc_dxf, escala_desenho=escala_desenho)
            print("  >> Conversão concluída: {} bloco(s) criado(s)".format(blocos_criados))
        except Exception as e:
            print("  >> Erro ao converter símbolos em blocos: {}".format(e))
            import traceback
            traceback.print_exc()

    doc_dxf.saveas(caminho_dxf)

    escala_display = escala_desenho
    doc_pdf.close()

    kb = os.path.getsize(caminho_dxf) / 1024
    print("\n" + "=" * 50)
    print("Conversão concluída!")
    print("  Total de elementos : {}".format(total))
    print("  Escala detectada   : 1:{}".format(escala_display))
    print("  Fator de conversão : {:.6f}".format(escala))
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
        "blocos_criados": blocos_criados,
    }
