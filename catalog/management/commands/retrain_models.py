from django.core.management.base import BaseCommand

from catalog.tasks import retrain_forecast_models


class Command(BaseCommand):
    help = (
        'Runs catalog.tasks.retrain_forecast_models synchronously, without '
        'needing Celery/Redis -- retrains and caches each product\'s '
        'Prophet model, plus cross-validation for a sample of products. '
        'This is what the nightly Celery Beat schedule calls; run it '
        'directly for local dev/demo so /ml-insights/ has fresh data.'
    )

    def handle(self, *args, **options):
        trained = retrain_forecast_models()
        self.stdout.write(self.style.SUCCESS(f'Retrained {trained} product forecast models.'))
