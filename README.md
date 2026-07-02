# Conversor PDF para DWG 🚀

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/flask-latest-green.svg)

Uma ferramenta profissional e leve para converter plantas baixas e projetos arquitetônicos de formato **PDF para DWG/DXF** de maneira rápida e automática, preservando a fidelidade geométrica.

## 🌟 Funcionalidades

- **Mapeamento de Cores Inteligente**: Transforma cores RGB do PDF em ACI (AutoCAD Color Index) + TrueColor, recriando com perfeição os contrastes e linhas de visualização. Tons escuros viram adaptativos (Preto/Branco) e cinzas se mantêm consistentes.
- **Detecção Automática de Escala**: O sistema usa heurísticas verificando os comprimentos geométricos das linhas geradas com os textos (ex: '160 m') inseridos nas proximidades, detectando escalas como 1:500 ou 1:1000 de forma automática.
- **Tracejados Reais**: Transforma os dash patterns complexos do vetor PDF em padrões Linetypes nativos do DXF (`PDF_DASH_...`).
- **Conversão de Símbolos**: Identificação através de padrões matemáticos e geométricos (áreas, tamanhos de linhas) que substitui linhas espalhadas por Instâncias de Blocos AutoCAD formatados corretamente, mantendo a rotação.
- **Aplicativo Nativo**: Interface gráfica moderna renderizada em janela nativa do Windows (Dark Mode), sem depender de navegadores externos.

## 🛠️ Tecnologias Utilizadas

- **Core / Extração**: `PyMuPDF` (leitura veloz e precisa de vetores, preenchimentos sólidos, caminhos bézier, propriedades de textos).
- **Criação DXF**: `ezdxf` (criação estruturada do arquivo vetorial, blocks e linetypes seguindo o padrão oficial).
- **Interface Gráfica**: `PyWebView` + `Flask` (Roteamento leve local embutido em uma janela de Desktop nativa).

## 📂 Estrutura do Projeto

O projeto adota uma estrutura coesa para fácil manutenção.

```
conversor-pdf-dwg/
├── src/                        # Núcleo da lógica de conversão
│   ├── blocks.py               # Identificação e criação de blocos
│   ├── colors.py               # Tabela e conversão de cores para AutoCAD
│   ├── converter.py            # Orquestrador da varredura das páginas PDF
│   ├── geometry.py             # Curvas de Bézier e Tipos de Linhas
│   ├── layers.py               # Criação de camadas estruturadas
│   ├── scale_detector.py       # Heurística para descobrir escalas de engenharia
│   └── text.py                 # Extrator e formatador de fontes e alinhamentos
├── web/                        # Servidor e UI
│   ├── app.py                  # API Flask e inicializador do navegador
│   └── templates/              
│       └── index.html          # Interface responsiva moderna com Drag and Drop
├── scripts/                    # Scripts utilitários
│   └── build_exe.py            # Script PyInstaller para gerar executável
├── docs/                       # Manuais e arquitetura detalhada
├── main.py                     # Entry point da aplicação local
├── requirements.txt            # Dependências em produção
└── requirements-dev.txt        # Dependências de desenvolvimento
```

## ⚙️ Pré-requisitos & Uso

Veja `docs/USAGE.md` para instruções de instalação, uso local e criação de executáveis.

## 📜 Licença

Desenvolvido sob a **MIT License**.
Copyright (c) 2024 Valdeci Filho
