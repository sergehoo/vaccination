from prometheus_client import Counter, Histogram, Gauge
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import socket
import time

REQUEST_DURATION_BUCKETS = (0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60, float('inf'))

# Compteurs personnalisés cohérents avec les labels utilisés
request_total_by_ip = Counter(
    'django_request_total_by_ip',
    'Total des requêtes par adresse IP',
    ['ip', 'method', 'host']
)

errors_by_ip = Counter(
    'django_http_errors_by_ip',
    'Erreurs HTTP par IP',
    ['ip', 'status', 'method', 'host', 'path']
)

requests_by_path = Counter(
    'django_request_total_by_path',
    'Nombre de requêtes par route',
    ['path', 'method', 'status', 'host']
)

errors_by_path = Counter(
    'django_http_errors_by_path',
    'Erreurs HTTP par route',
    ['path', 'status']
)

request_duration = Histogram(
    'django_http_request_duration_seconds',
    'Durée des requêtes HTTP',
    ['method', 'path', 'status', 'host'],
    buckets=REQUEST_DURATION_BUCKETS
)

concurrent_requests = Gauge(
    'django_http_concurrent_requests',
    'Nombre de requêtes concurrentes',
    ['method', 'path', 'host']
)

class EnhancedPrometheusMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.hostname = socket.gethostname()
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')

    def process_request(self, request):
        request._prometheus_start_time = time.time()
        path = self._sanitize_path(request.path)

        concurrent_requests.labels(
            method=request.method,
            path=path,
            host=self.hostname
        ).inc()
        return None

    def process_response(self, request, response):
        ip = self._get_client_ip(request)
        path = self._sanitize_path(request.path)
        status = str(response.status_code)
        method = request.method
        host = self.hostname

        duration = max(time.time() - getattr(request, '_prometheus_start_time', time.time()), 0)

        request_total_by_ip.labels(ip=ip, method=method, host=host).inc()
        requests_by_path.labels(path=path, method=method, status=status, host=host).inc()
        request_duration.labels(method=method, path=path, status=status, host=host).observe(duration)

        if status.startswith(('4', '5')):
            errors_by_ip.labels(ip=ip, status=status, method=method, host=host, path=path).inc()
            errors_by_path.labels(path=path, status=status).inc()

        concurrent_requests.labels(method=method, path=path, host=host).dec()
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _sanitize_path(self, path):
        if path.startswith('/admin'):
            return '/admin'
        if path.startswith('/static'):
            return '/static'
        if path.startswith('/media'):
            return '/media'

        parts = path.split('/')
        for i, part in enumerate(parts):
            if part.isdigit():
                parts[i] = '{id}'
            elif len(part) > 20 and any(c.isdigit() for c in part):
                parts[i] = '{uuid}'

        return '/'.join(parts)

