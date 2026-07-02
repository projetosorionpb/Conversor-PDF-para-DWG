# Arquitetura do Sistema

O **Conversor PDF para DWG** é dividido logicamente em três camadas fundamentais: Interface de Usuário, Orquestrador de Conversão e Processadores Específicos.

## Visão Geral do Fluxo

1. **Interface (Web/Nativa):**
   - Feita em HTML/CSS (Padrão EPD-PB) e JavaScript.
   - Executada nativamente em janela desktop usando **PyWebView**.
   - Comunica-se com o backend via requisições `fetch`.

2. **Backend (Python/Flask + PyWebView):**
   - Recebe o PDF via `multipart/form-data` e o armazena temporariamente na pasta `/tmp/uploads`.
   - O endpoint `/convert` aciona o motor de conversão em `src.converter.converter_pdf_para_dxf`.
4. O motor lê as páginas com `PyMuPDF` e inicializa o arquivo `ezdxf`.
5. Durante o parsing, as geometrias são processadas com apoio dos utilitários em `src/geometry.py`, `src/colors.py` e `src/layers.py`.
6. Terminado os caminhos (paths) e preenchimentos, os textos são passados ao `src/text.py`.
7. Opcionalmente, se ativada a opção "converter_blocos", é feita uma varredura sobre as geometrias brutas no ModelSpace executada pelo `src/blocks.py`.
8. O arquivo DWG é salvo.

## Descrição dos Módulos

### `src/colors.py`
Contém a recriação da Tabela ACI do AutoCAD. Ao processar cores, o sistema verifica aproximação euclidiana das cores originais no PDF e traduz para as melhores cores do ACI, utilizando TrueColor quando necessário, preservando visualização limpa nas telas do CAD.

### `src/geometry.py`
Implementa cálculos vetoriais que faltam no extraído bruto do PDF (como aproximação de Bézier em pontos tangentes finos). Além disso, converte padrões Dash dinamicamente encontrados (como Arrays `[3, 3] 0`) transformando-os numa string estruturada para Linetypes no header do AutoCAD.

### `src/scale_detector.py`
Uma heurística que percorre todas as linhas desenhadas pelo PDF e todas as "palavras" identificáveis com padrões métricos (como "40m", "100.5 m"). Ao cruzar a posição geométrica com o comprimento da linha calculada em milímetros, ele gera um valor de "Ratio". A mediana de Ratios aponta para o fator de escala original de desenho, melhorando em centenas de vezes o redimensionamento de fontes (`src/text.py`).

### `src/blocks.py`
Substituto de um clássico fluxo LISP. Este módulo age *após* a geração bruta de linhas e hatches. Ele procura no `ModelSpace` por geometrias independentes que se encontrem perto e formem certos padrões de blocos reconhecidos (e.g., área X e linhas longas de tamanho Y = Poste X). Se a tolerância de precisão bate, ele deleta os vetores soltos e substitui por um `BlockReference` no mesmo local, enxugando dramaticamente o tamanho e complexidade do DWG.
