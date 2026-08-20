from celery import shared_task

from locations.providers import AndreaniLocalitiesAdapter
from locations.services import sync_localities


@shared_task
def sync_andreani_localities():
    return sync_localities(adapter=AndreaniLocalitiesAdapter())
