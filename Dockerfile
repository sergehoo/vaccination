FROM python:3.9-slim

LABEL authors="ogahserge"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les dépendances
COPY requirements.txt .

# Installer globalement dans le conteneur (pas besoin de .venv)
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copier tout le code
COPY . .

EXPOSE 8000

CMD ["gunicorn", "vaccination.wsgi:application", "--bind", "0.0.0.0:8000"]