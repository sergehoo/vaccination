FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
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

# 1) Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 2) Tailwind / front
COPY package*.json ./
COPY tailwind.config.js postcss.config.js ./
COPY static_src ./static_src
COPY static ./static

RUN npm install --production=false
RUN npm run build:css  # génère ton CSS dans static/...

# 3) Code Django
COPY . .

# 4) collectstatic (avec WhiteNoise)
RUN python manage.py collectstatic --noinput

# 5) media
RUN mkdir -p /app/media && chmod -R 755 /app/media

EXPOSE 8000

CMD ["gunicorn", "vaccination.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--log-level", "info"]