import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricesense.settings')

app = Celery('pricesense')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update-prices-every-15-min': {
        'task': 'catalog.tasks.update_prices',
        'schedule': crontab(minute='*/15'),
    },
    'check-triggers-every-15-min': {
        'task': 'orders.tasks.check_triggers',
        'schedule': crontab(minute='*/15'),
    },
    'confirm-pending-orders-hourly': {
        'task': 'orders.tasks.confirm_pending_orders',
        'schedule': crontab(minute=0),
    },
    'progress-orders-hourly': {
        'task': 'orders.tasks.progress_orders',
        'schedule': crontab(minute=0),
    },
    'retrain-forecast-models-nightly': {
        'task': 'catalog.tasks.retrain_forecast_models',
        'schedule': crontab(hour=3, minute=0),
    },
}
