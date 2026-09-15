"""Synchronous fallback for catalog.tasks.update_prices, mirroring the
fallback pattern already used for trigger firing and order progression
(orders/services.py) -- without Celery Beat running (the common case for
local dev/demo), current_price would otherwise never change.
"""
from django.utils import timezone

from .models import PriceLog

# Matches the Celery Beat schedule for update_prices (pricesense/celery.py)
# so a page load can't force it to run more often than the "real" task would.
PRICE_UPDATE_INTERVAL = timezone.timedelta(minutes=15)


def maybe_update_prices():
    """Runs catalog.tasks.update_prices in-process if it hasn't run
    recently, throttled to PRICE_UPDATE_INTERVAL so a page view doesn't
    refit/re-log the whole catalog on every request. Safe to call from any
    view; a no-op most of the time once something (a request or Celery
    Beat) has run it recently.
    """
    last = PriceLog.objects.order_by('-timestamp').values_list('timestamp', flat=True).first()
    if last and timezone.now() - last < PRICE_UPDATE_INTERVAL:
        return 0

    from .tasks import update_prices
    return update_prices()
