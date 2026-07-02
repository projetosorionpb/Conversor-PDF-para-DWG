"""
Utilitários de Cor — Tabela ACI e Mapeamento Inteligente
=========================================================
Converte cores RGB do PDF para o sistema de cores do AutoCAD (ACI + TrueColor).

Tabela ACI:
    - ACI 1-9: cores básicas
    - ACI 10-249: espectro (geradas algoritmicamente)
    - ACI 250-255: escala de cinza

Mapeamento inteligente:
    - Preto puro (RGB < 16,16,16) → ACI 7 (adaptativo White/Black)
    - Cinzas ACI (8, 9, 250-255) → ACI original + TrueColor 51,51,51
    - Demais → ACI mais próximo + TrueColor exato
"""

from ezdxf import rgb2int


# =============================================================
# TABELA ACI COMPLETA (256 cores AutoCAD)
# =============================================================

def _gerar_tabela_aci():
    """Gera tabela RGB -> ACI com as 256 cores padrão do AutoCAD."""
    tabela = []

    # ACI 1-9: cores básicas
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
    for aci in range(10, 250):
        grupo = (aci - 10) // 10
        variacao = (aci - 10) % 10
        angulo = grupo * 15
        h = angulo / 360.0

        if variacao < 5:
            s = 1.0
            l = 0.5 + variacao * 0.1
        else:
            s = 1.0 - (variacao - 5) * 0.2
            l = 0.5

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
# FUNÇÕES PÚBLICAS
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
    Encontra o ACI (AutoCAD Color Index) mais próximo via distância euclidiana.
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
    Mapeia cores conforme a lógica do padrão AutoCAD:
    - Preto (RGB < 16,16,16) -> ACI 7 (White/Black), Sem TrueColor
    - Cinzas ACI (8, 9, 250-255) -> Mantém ACI original, TrueColor RGB 51,51,51
    - Outras -> ACI mais próximo, TrueColor setado

    Retorna (aci, rgb_tupla_ou_None)
    """
    aci = rgb_to_aci(ri, gi, bi)

    # CASO 1: Preto Puro ou muito próximo (RGB 0,0,0 até 15,15,15)
    if ri < 16 and gi < 16 and bi < 16:
        return 7, None  # Cor 7: Branco em fundo escuro, Preto em claro

    # CASO 2: Tons de Cinza ACI específicos (8, 9, 250-255)
    if aci == 8 or aci == 9 or (250 <= aci <= 255):
        return aci, (51, 51, 51)  # RGB 51,51,51 (cinza visível em ambos)

    # CASO PADRÃO: Usa RGB exato
    return aci, (ri, gi, bi)
