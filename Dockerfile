FROM python:3.9-slim

LABEL authors="ogahserge"

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier les fichiers requirements.txt dans le conteneur
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier tout le code restant dans le conteneur
COPY . .

# Exposer le port de l'application
EXPOSE 8000

# Commande par défaut pour lancer Gunicorn
CMD ["gunicorn", "vaccination.wsgi:application", "--bind", "0.0.0.0:8000"]