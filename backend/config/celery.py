import os

from celery import Celery

# Importing connects request/job correlation signal handlers before tasks run.
from config import observability  # noqa: F401

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mycdigitalizacion")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
