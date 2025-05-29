# Usa imagem base leve com Python 3.10
FROM python:3.10-slim

# Instala dependências básicas e o driver ODBC 18 da Microsoft
RUN apt-get update && \
    apt-get install -y curl gnupg apt-transport-https unixodbc-dev && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define diretório da aplicação
WORKDIR /app

# Copia o código da aplicação
COPY . /app

# Instala dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta usada pela aplicação
EXPOSE 10000

# Comando para iniciar o app via Gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
