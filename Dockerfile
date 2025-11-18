FROM python:3.9-slim

LABEL authors="ogahserge"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1) Dépendances système (WeasyPrint + Node)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    libglib2.0-0 \
    libgirepository-1.0-1 \
    gir1.2-pango-1.0 \
    gir1.2-glib-2.0 \
    gir1.2-gdkpixbuf-2.0 \
    libxml2 \
    libxslt1.1 \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    postgresql-client \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    curl \
    shared-mime-info \
    fonts-dejavu-core \
    nodejs \
    npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 3) Dépendances front (Tailwind)
# On copie juste ce qui est nécessaire pour builder le CSS
COPY package*.json ./
COPY tailwind.config.js postcss.config.js ./
# Si tu as un fichier source dédié : ex : static/src/keneya.css
# adapte au besoin :
COPY static ./static

RUN npm install --production=false
RUN npm run build:css

# 4) On copie le reste du projet (templates, apps, etc.)
COPY . .

# 5) collectstatic (les fichiers Tailwind sont déjà générés)
RUN python manage.py collectstatic --noinput

# 6) Permissions (optionnel suivant ton besoin)
RUN chmod -R 755 /app/staticfiles && \
    mkdir -p /app/media && chmod -R 755 /app/media

EXPOSE 8000

CMD ["gunicorn", "vaccination.wsgi:application", "--bind", "0.0.0.0:8000"]