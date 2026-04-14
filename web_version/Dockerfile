# Use uma imagem leve do Python
FROM python:3.10-slim

# Instala dependências do sistema necessárias para bibliotecas gráficas (como PyMuPDF)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto
COPY . .

# Garante que a pasta de uploads existe
RUN mkdir -p uploads

# Expõe a porta que o Flask/Gunicorn vai rodar
EXPOSE 7860

# Comando para rodar a aplicação usando Gunicorn para melhor performance
# --workers 4: Permite processar até 4 conversões simultâneas
# --timeout 120: Dá tempo para PDFs grandes serem processados
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "4", "--timeout", "120", "app:app"]
