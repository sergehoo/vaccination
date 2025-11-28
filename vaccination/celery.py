# vaccination/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vaccination.settings")

app = Celery("vaccination")

# Charge config depuis settings.py, avec préfixe CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-import des tasks.py dans toutes les apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")