# Conversor PDF para DWG/DXF 🚀

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Flask](https://img.shields.io/badge/flask-latest-green.svg)

Uma ferramenta profissional e leve para converter plantas baixas e projetos arquitetônicos de formato **PDF para DWG/DXF** de maneira rápida e automática, com detecção de escala. 

Conta com uma interface moderna na web construída usando Flask e permite exportar a aplicação como um executável `.exe` independente, ideal para apresentações corporativas ou para uso em desktops sem necessidade de instalação de dependências locais.

---

## 🛠️ Tecnologias Utilizadas

- **Python:** Linguagem principal
- **Flask:** Framework web para interface do usuário e roteamento
- **PyMuPDF (`fitz`):** Leitura avançada e extração de blocos, linhas e imagens do PDF
- **ezdxf:** Criação nativa e limpa de arquivos AutoCAD estritamente no padrão DXF/DWG
- **Pyinstaller:** Compilação de binário sem dependências
- **HTML/CSS/JS Vanilla:** Interface Dark Mode super-responsiva (Drag and Drop nativo)

---

## 🚀 Funcionalidades

- Interface amigável com suporte a "Drag and Drop" (Arrastar e Soltar) de arquivos PDF.
- Design **Dark Mode** moderno, responsivo e focado na usabilidade, sem delays.
- A aplicação verifica metadados do PDF e automaticamente extrai geometrias.
- Algoritmo embutido para supor "escala detectada" quando possível.
- Permite usar como um sistema local de processamento (sem limites de rede em envio de dados).
- Exportação como aplicativo Windows Standalone (`.exe`), o que significa que o usuário final basta dar 2 cliques para acessar o projeto localmente.

---

## ⚙️ Pré-requisitos & Instalação

### Instalação em Ambiente de Desenvolvimento

Para rodar este conversor usando linha de comando (CLI) ou modificar o código-fonte, será necessário o Python 3.8+:

1. **Clone este repositório**
   ```bash
   git clone https://github.com/SEU-USUARIO/conversor-pdf-dwg.git
   cd conversor-pdf-dwg
   ```

2. **(Opcional, porém recomendado) Crie um ambiente virtual**
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Como Usar (Modo Servidor Local)

Após a configuração do ambiente, basta executar o seguinte comando a partir da pasta raiz:

```bash
python app.py
```

Isso iniciará um servidor de desenvolvimento em `http://127.0.0.1:5077` e pode abrir seu navegador padrão automaticamente. De lá, basta fazer upload do PDF desejado e o sistema cuidará do resto!

---

## 📦 Como Compilar (.EXE Standalone)

Se o seu objetivo é implantar este conversor para usuários que não têm experiência com Python, você pode compilar a aplicação em um Executável único.

Execute o script autônomo de compilação:

```bash
python build_exe.py
```

**Benefícios:**
- O PyInstaller criará uma pasta `dist/` com um arquivo chamado `Conversor_PDF_para_DWG.exe`.
- Ele já incluirá todas as templates HTML (`index.html`) e bibliotecas escondidas juntas.
- Basta enviar esse `.exe` para os clientes ou time da mesma equipe!

---

## 📂 Estrutura de Diretórios

```bash
.
├── Exemplos/               # Fica livre para você guardar testes
├── templates/              # Páginas de renderização frontal (ex: index.html)
├── app.py                  # Inicialização Flask + Roteamento
├── build_exe.py            # Orquestrador Pyinstaller para gerar standalone executable
├── pdf_para_dxf.py         # Lógica central: lê bloco a bloco do PDF e exporta DXF/DWG
├── requirements.txt        # Especificações de dependência (Flask, pymupdf, pyinstaller, ezdxf)
└── README.md               # Este arquivo
```

---

## 🤝 Contribuição

Sinta-se livre para analisar o código e enviar **Pull Requests** caso consiga aprimorar a extração de SVG de dentro do PyMuPDF ou melhorar a conversão Spline/Polylines do `ezdxf`.

1. Faça o Fork do projeto
2. Crie uma Branch para sua Funcionalidade (`git checkout -b feature/NovaFeature`)
3. Commit suas alterações (`git commit -m 'Add alguma nova feature'`)
4. Faça o Push para a Branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

---

## 📜 Licença

Este projeto é desenvolvido sob a **MIT License**. Veja o arquivo `LICENSE` para mais detalhes.

Copyright (c) 2024 Valdeci Filho
