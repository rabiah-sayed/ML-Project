"""Trigger-firing logic shared between the Celery task (orders.tasks.
check_triggers, the periodic/production path) and views that check a
user's own triggers synchronously on page load. The latter matters
because without Celery + Redis running (the common case for local
dev/demo), the periodic task never runs and a trigger would never
appear to fire even after its target price is reached.
"""
import logging

from django.core.mail import send_mail
from django.utils import timezone

from .models import Order, Trigger

logger = logging.getLogger(__name__)

# How long after an order's created_at each status transition happens.
# confirm_pending_orders (orders.tasks) already flips pending_cancellation
# -> confirmed at +48h; these continue that same timeline off created_at
# rather than adding new timestamp fields to Order. PLACE_CONFIRM_AFTER is
# shorter -- a directly-checked-out order ('placed', not trigger-fired)
# has no cancellation window to wait out, just a short processing delay.
PLACE_CONFIRM_AFTER = timezone.timedelta(hours=2)
SHIP_AFTER = timezone.timedelta(hours=72)
DELIVER_AFTER = timezone.timedelta(hours=120)

ORDER_STAGES = ['placed', 'confirmed', 'shipped', 'delivered']


def fire_trigger(trigger):
    order = Order.objects.create(
        user=trigger.user,
        product=trigger.product,
        price_paid=trigger.product.current_price,
        status='pending_cancellation',
        payment_method=trigger.payment_method,
        address=trigger.address,
        trigger=trigger,
    )
    trigger.status = 'fired'
    trigger.save(update_fields=['status'])
    _notify_trigger_fired(trigger, order)
    return order


def _notify_trigger_fired(trigger, order):
    """Best-effort email -- a misconfigured mail backend shouldn't break
    order placement, which is the actual point of firing a trigger."""
    if not trigger.user.email:
        return
    try:
        send_mail(
            subject=f'Your trigger fired: {trigger.product.name}',
            message=(
                f'{trigger.product.name} hit your target price of {trigger.target_price}.\n\n'
                f'Order #{order.id} was placed automatically at {order.price_paid} '
                f'({order.get_payment_method_display()}).\n'
                f'You can cancel it within 48 hours from My Orders.'
            ),
            from_email=None,
            recipient_list=[trigger.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send trigger-fired email for trigger %s', trigger.id)


def check_and_fire_triggers(triggers_qs=None):
    """Fires any active trigger in the queryset whose target price has
    been reached (current_price <= target_price). Defaults to every
    active trigger in the system (the Celery task's use case); pass a
    filtered queryset (e.g. Trigger.objects.filter(user=request.user))
    to check just one user's triggers from a view.
    """
    if triggers_qs is None:
        triggers_qs = Trigger.objects.all()

    fired_orders = []
    for trigger in triggers_qs.filter(status='active').select_related('product', 'address'):
        if trigger.product.current_price <= trigger.target_price:
            fired_orders.append(fire_trigger(trigger))
    return fired_orders


def progress_order_statuses(orders_qs=None):
    """Simulates order fulfillment: placed -> confirmed -> shipped ->
    delivered as time passes, so an order doesn't sit at one status
    forever. Covers both lifecycles: a directly-checked-out order starts
    at 'placed' and is confirmed quickly (no cancellation window to
    wait out); a trigger-fired order starts at 'pending_cancellation'
    and is confirmed by confirm_pending_orders (orders.tasks) after the
    48h cancellation window instead -- both converge on 'confirmed' and
    continue the same ship/deliver timeline from there.

    Called both by a Celery task (production path) and synchronously on
    My Orders / order-tracking views (so it works without Celery
    running, matching how trigger firing already does).
    """
    if orders_qs is None:
        orders_qs = Order.objects.all()

    now = timezone.now()
    confirmed = orders_qs.filter(status='placed', created_at__lte=now - PLACE_CONFIRM_AFTER).update(status='confirmed')
    shipped = orders_qs.filter(status='confirmed', created_at__lte=now - SHIP_AFTER).update(status='shipped')
    delivered = orders_qs.filter(status='shipped', created_at__lte=now - DELIVER_AFTER).update(status='delivered')
    return confirmed, shipped, delivered


def advance_order_status(order):
    """Manually pushes one order to its next status, bypassing the
    normal time-based wait -- for admin staff (see orders/admin.py's
    "Advance to next status" action) to move fulfillment forward on
    demand, e.g. for a support request or a demo, rather than waiting
    out the simulated timeline.

    Returns the new status, or None if the order is already at a
    terminal/non-advanceable status (delivered, cancelled).
    """
    if order.status == 'pending_cancellation':
        next_status = 'confirmed'
    elif order.status in ORDER_STAGES:
        index = ORDER_STAGES.index(order.status)
        if index >= len(ORDER_STAGES) - 1:
            return None
        next_status = ORDER_STAGES[index + 1]
    else:
        return None

    order.status = next_status
    order.save(update_fields=['status'])
    return next_status


def order_tracking_stages(order):
    """Stepper stages for the order-tracking page: each of the 4 normal
    lifecycle stages, whether it's been reached, and (for reached stages)
    the timestamp it happened at -- estimated from created_at + the fixed
    offset above, since Order doesn't store a timestamp per transition.
    Orders that left the normal lifecycle (cancelled) aren't steppable,
    so the view handles those separately.
    """
    offsets = {
        'placed': timezone.timedelta(0),
        'confirmed': PLACE_CONFIRM_AFTER,
        'shipped': SHIP_AFTER,
        'delivered': DELIVER_AFTER,
    }
    if order.status in ORDER_STAGES:
        current_index = ORDER_STAGES.index(order.status)
    elif order.status == 'pending_cancellation':
        # A trigger-fired order: created (~= "placed") but awaiting the
        # 48h cancellation window before confirm_pending_orders confirms
        # it -- the next real transition is 'confirmed', not on this
        # fixed-offset timeline, so it isn't given an estimated date.
        current_index = 0
    else:
        current_index = -1

    stages = []
    for index, stage in enumerate(ORDER_STAGES):
        reached = index <= current_index
        stages.append({
            'key': stage,
            'label': stage.capitalize(),
            'reached': reached,
            'current': index == current_index,
            'at': order.created_at + offsets[stage] if reached else None,
        })
    return stages
