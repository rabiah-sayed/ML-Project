import logging

from celery import shared_task
from django.utils import timezone

from .models import Order
from .services import check_and_fire_triggers, progress_order_statuses

logger = logging.getLogger(__name__)


@shared_task
def check_triggers():
    """Runs right after catalog.tasks.update_prices. Any active trigger
    whose target price has been reached fires: an Order is created in
    'pending_cancellation' using the trigger's stored payment method and
    address, and the trigger is marked 'fired'.
    """
    fired = check_and_fire_triggers()
    logger.info('check_triggers: fired %s triggers', len(fired))
    return len(fired)


@shared_task
def confirm_pending_orders():
    """Hourly: flips any Order in 'pending_cancellation' older than the
    48h cancellation window to 'confirmed'.
    """
    cutoff = timezone.now() - timezone.timedelta(hours=48)
    qs = Order.objects.filter(status='pending_cancellation', created_at__lte=cutoff)
    count = qs.update(status='confirmed')
    logger.info('confirm_pending_orders: confirmed %s orders', count)
    return count


@shared_task
def progress_orders():
    """Hourly: simulates fulfillment -- placed -> confirmed -> shipped ->
    delivered as time passes, so orders don't just sit at one status
    forever.
    """
    confirmed, shipped, delivered = progress_order_statuses()
    logger.info('progress_orders: confirmed %s, shipped %s, delivered %s', confirmed, shipped, delivered)
    return confirmed, shipped, delivered
