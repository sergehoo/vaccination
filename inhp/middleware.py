from prometheus_client import Counter
from django.utils.deprecation import MiddlewareMixin

request_total_by_ip = Counter(
    'django_request_total_by_ip',
    'Total des requêtes par adresse IP',
    ['ip']
)

errors_by_ip = Counter(
    'django_http_errors_by_ip',
    'Erreurs HTTP par IP',
    ['ip', 'status']
)

requests_by_path = Counter(
    'django_request_total_by_path',
    'Nombre de requêtes par route',
    ['path']
)

errors_by_path = Counter(
    'django_http_errors_by_path',
    'Erreurs HTTP par route',
    ['path', 'status']
)


class PrometheusIPTrackingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        path = request.path
        status = str(response.status_code)

        request_total_by_ip.labels(ip=ip).inc()
        requests_by_path.labels(path=path).inc()

        if status.startswith('4') or status.startswith('5'):
            errors_by_ip.labels(ip=ip, status=status).inc()
            errors_by_path.labels(path=path, status=status).inc()

        return response