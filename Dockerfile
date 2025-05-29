FROM python:3.11-slim

# Atualiza pacotes e instala dependências necessárias
RUN apt-get update && apt-get install -y \
    gnupg2 \
    curl \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    libgssapi-krb5-2 \
    libssl-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Adiciona o repositório da Microsoft de forma segura (sem usar apt-key)
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg

# Instala o driver ODBC da Microsoft
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Cria o diretório da aplicação e copia o conteúdo
WORKDIR /app
COPY . /app

# Instala dependências Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 10000

# Comando para iniciar a aplicação com gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
