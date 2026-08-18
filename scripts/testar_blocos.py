r"""Testa a conversao de simbolos em blocos em um PDF especifico.

Uso:
    python scripts/testar_blocos.py "caminho\do\arquivo.pdf"
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.converter import converter_pdf_para_dxf


def main():
    if len(sys.argv) < 2:
        print("Informe o caminho do PDF: python scripts/testar_blocos.py arquivo.pdf")
        sys.exit(1)

    caminho_pdf = sys.argv[1]
    if not os.path.exists(caminho_pdf):
        print("Arquivo nao encontrado:", caminho_pdf)
        sys.exit(1)

    base = os.path.splitext(os.path.basename(caminho_pdf))[0]
    saida = os.path.join(os.path.dirname(caminho_pdf), base + "_com_blocos.dwg")

    t0 = time.time()
    resultado = converter_pdf_para_dxf(caminho_pdf, saida, converter_blocos=True)
    dt = time.time() - t0

    print("\n" + "=" * 50)
    print("TESTE DE BLOCOS")
    print("=" * 50)
    print("  Escala detectada : 1:{}".format(resultado["escala_detectada"]))
    print("  Elementos        : {}".format(resultado["total_elementos"]))
    print("  Blocos criados   : {}".format(resultado["blocos_criados"]))
    print("  Tamanho          : {:.1f} KB".format(resultado["tamanho_kb"]))
    print("  Tempo            : {:.1f}s".format(dt))
    print("  Arquivo          : {}".format(saida))
    print("=" * 50)

    if resultado["blocos_criados"] > 0:
        print("\n  OK - blocos foram criados. Abra o .dwg no AutoCAD para conferir.")
    else:
        print("\n  NENHUM bloco criado. Verifique se o PDF segue o padrao esperado")


if __name__ == "__main__":
    main()