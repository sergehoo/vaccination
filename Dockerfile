FROM python:3.9-slim

LABEL authors="ogahserge"

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/app/.venv/bin:$PATH"

# Installer dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    gcc \
    libc6-dev \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Environnement virtuel (meilleure pratique)
RUN python -m venv .venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copier tout le projet
COPY . .

EXPOSE 8000

# CMD générique (sera surchargé par docker-compose)
CMD ["gunicorn", "vaccination.wsgi:application", "--bind", "0.0.0.0:8000","--workers=4", "--timeout=180", "--access-logfile=-", "--error-logfile=-", "--capture-output", "--log-level=info"]