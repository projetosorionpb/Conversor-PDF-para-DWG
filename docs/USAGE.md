# Guia de Uso

O Conversor PDF para DWG oferece diferentes formas de interação dependendo da sua necessidade.

## 1. Interface Gráfica Web (Local)

A forma mais fácil de utilizar é através da interface web que roda localmente em sua máquina.

### Executando o servidor
1. Instale as dependências: `pip install -r requirements.txt`
2. Execute o aplicativo: `python main.py`
3. O servidor Flask irá iniciar e o navegador abrirá automaticamente no endereço `http://127.0.0.1:5077`

### Utilizando
- Na interface, arraste e solte seu arquivo PDF, ou clique para selecionar.
- Utilize o interruptor ("Converter Símbolos em Blocos") caso deseje ativar o reconhecimento inteligente de símbolos de rede elétrica (Postes, Transformadores, etc).
- Aguarde o processamento. O arquivo `.dwg` será gerado e disponibilizado para download.

## 2. CLI (Linha de Comando)

Para uso em scripts ou sem a necessidade de interface gráfica. O arquivo principal ainda permite testes através da linha de comando (ideal encapsular `src/converter.py`). 
Exemplo de importação no Python:

```python
from src.converter import converter_pdf_para_dxf

# Conversão básica
resultado = converter_pdf_para_dxf(
    caminho_pdf="planta_baixa.pdf",
    caminho_dxf="planta_baixa.dwg"
)

# Conversão com parâmetros avançados
resultado = converter_pdf_para_dxf(
    caminho_pdf="projeto_eletrico.pdf",
    caminho_dxf="projeto_eletrico_v2018.dwg",
    paginas=[1, 2],           # Converte apenas páginas 1 e 2
    escala_manual=0.3528,     # Escala fixa
    versao_dxf="R2018",       # Versão do AutoCAD
    converter_blocos=True     # Ativa reconhecimento de blocos
)
print(f"Total de elementos: {resultado['total_elementos']}")
```

## 3. Criando um Executável Standalone (.exe)

Você pode distribuir a aplicação para usuários sem conhecimento de Python através da geração de um arquivo executável para Windows.

### Compilando
1. Instale o PyInstaller e dependências: `pip install -r requirements-dev.txt`
2. Execute o script de build: `python scripts/build_exe.py`
3. O executável será gerado em `dist/Conversor_PDF_para_DWG.exe`.
4. Basta enviar este `.exe` para os usuários. Eles poderão dar dois cliques, a interface abrirá no navegador e toda a conversão acontecerá offline, embutida no `.exe`.
