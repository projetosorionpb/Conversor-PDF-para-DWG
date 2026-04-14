# Guia de Hospedagem Online - Conversor PDF para DWG

Esta pasta contém uma versão otimizada do conversor configurada para rodar em servidores Web (Hugging Face, Render, etc.).

## 🚀 Como Hospedar Grátis

### Opção 1: Hugging Face Spaces (Recomendado - Mais Rápido)
1. Crie uma conta em [huggingface.co](https://huggingface.co/).
2. Clique em **"New Space"**.
3. Escolha um nome (ex: `conversor-pdf-dwg`).
4. Em **"Space SDK"**, selecione **Docker**.
5. Em **"Docker template"**, escolha **Blank**.
6. Após criar o espaço, vá na aba **"Files and Versions"** -> **"Add File"** -> **"Upload files"**.
7. Arraste **TODOS** os arquivos desta pasta `web_version` para lá.
8. Clique em **"Commit changes"**.
9. O Hugging Face vai ler o `Dockerfile`, instalar tudo e seu site estará pronto em alguns minutos!

### Opção 2: Render.com
1. Crie um novo repositório no seu **GitHub** e suba os arquivos desta pasta `web_version`.
2. No [Render.com](https://render.com/), crie um **"Web Service"**.
3. Conecte seu repositório do GitHub.
4. O Render detectará o `Dockerfile` automaticamente.
5. Em **"Instance Type"**, escolha o plano **Free**.
6. Clique em **Deploy**.

## ⚙️ Configurações Aplicadas nesta Versão
- **Performance**: Usa `Gunicorn` com 4 processos simultâneos.
- **Estabilidade**: Removidas bibliotecas de interface local (Tkinter) que causariam erro no servidor.
- **Porta**: Configurado para porta `7860` (padrão do Hugging Face) e `5000` (padrão local).
- **Limpeza**: Arquivos temporários são excluídos automaticamente após o download.

---
**Desenvolvido por Valdeci Nunes**
