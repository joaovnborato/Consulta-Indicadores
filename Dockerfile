FROM python:3.10-slim

# Atualiza e instala dependências básicas
RUN apt-get update && apt-get install -y \
    curl gnupg2 apt-transport-https unixodbc-dev ca-certificates && \
    mkdir -p /etc/apt/keyrings && \
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg && \
    curl -sSL https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define o diretório da aplicação
WORKDIR /app

# Copia o código
COPY . /app

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta
EXPOSE 10000

# Inicia o servidor com gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
