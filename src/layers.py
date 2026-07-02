"""
Gestão de Layers — Criação automática de layers por cor
========================================================
Cria layers no DXF automaticamente baseado nas cores encontradas no PDF.
Nomenclatura: COR_RRGGBB (geometria) e TXT_RRGGBB (textos).
"""

from ezdxf import rgb2int
from src.colors import rgb_to_hex, mapear_cor_inteligente


_layers_criados = set()


def reset_layers():
    """Limpa o cache de layers para nova conversão."""
    global _layers_criados
    _layers_criados = set()


def obter_ou_criar_layer(doc_dxf, ri, gi, bi, prefixo=""):
    """
    Obtém ou cria um layer de geometria com nome COR_RRGGBB.
    Aplica mapeamento inteligente de cores ACI + TrueColor.
    """
    hex_cor = rgb_to_hex(ri, gi, bi)
    nome = "{}COR_{}".format(prefixo, hex_cor)

    if nome not in _layers_criados:
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
    """
    Obtém ou cria um layer de texto com nome TXT_RRGGBB.
    Aplica mapeamento inteligente de cores ACI + TrueColor.
    """
    hex_cor = rgb_to_hex(ri, gi, bi)
    nome = "{}TXT_{}".format(prefixo, hex_cor)

    if nome not in _layers_criados:
        aci, rgb_final = mapear_cor_inteligente(ri, gi, bi)

        if nome not in doc_dxf.layers:
            layer = doc_dxf.layers.add(nome)
        else:
            layer = doc_dxf.layers.get(nome)

        layer.color = aci
        if rgb_final:
            layer.true_color = rgb2int(rgb_final)
        else:
            layer.dxf.discard('true_color')

        layer.lineweight = 0
        _layers_criados.add(nome)

    return nome
