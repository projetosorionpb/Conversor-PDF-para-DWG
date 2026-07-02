"""
Processamento de Textos
========================
Lida com a conversão de textos do PDF para o DXF, preservando:
- Posição e rotação
- Cores
- Tamanhos relativos
"""

import math
from src.layers import obter_layer_texto
from src.colors import rgb_float_to_int, rgb2int, mapear_cor_inteligente

def processar_textos(page, msp, doc_dxf, offset_y, escala, prefixo, escala_desenho, tx, ty, total):
    """
    Extrai e converte todos os textos de uma página do PDF para o ModelSpace do DXF.
    """
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

                # --------------------------------------------------
                # PADRONIZACAO DE TAMANHO DE TEXTO POR COR (para 1:500 e 1:1000):
                #   Azul  (R<80, G<80, B>150) -> 3.0
                #   Vermelho (R>150, G<80, B<80) -> 3.0
                #   Outros (postes, cabos, etc.) -> 1.5
                # Fora dessas escalas usa o tamanho original do PDF.
                # --------------------------------------------------
                if escala_desenho in (500, 1000):
                    def _eh_azul(r, g, b):
                        return r < 80 and g < 80 and b > 150

                    def _eh_vermelho(r, g, b):
                        return r > 150 and g < 80 and b < 80

                    if _eh_azul(tri, tgi, tbi) or _eh_vermelho(tri, tgi, tbi):
                        altura_txt = 3.0
                    else:
                        altura_txt = 1.5
                else:
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
