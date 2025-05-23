from .base import *

# DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
# SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-CHANGE_ME')

# ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost').split(',') if h.strip()]
ALLOWED_HOSTS = ['localhost', '127.0.0.1','147.93.84.26', 'vaccinationweb']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': int(os.environ.get('DB_PORT', 5432)),
    }
}

# SECURE_SSL_REDIRECT = True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True
# X_FRAME_OPTIONS = 'DENY'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MPI_API_KEY = os.environ.get('MPI_API_KEY', default='key')
