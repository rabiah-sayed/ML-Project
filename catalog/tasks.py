import logging

from celery import shared_task
from django.utils import timezone

from .demand import price_for
from .models import PriceLog, Product

logger = logging.getLogger(__name__)


@shared_task
def update_prices():
    """Recompute every product's current_price via the demand-curve
    formula, applying any active Sale discount, and log the new price.
    Runs every 15 minutes (see pricesense/celery.py beat schedule).
    """
    now = timezone.now()
    updated = 0
    for product in Product.objects.select_related('category').all():
        sale = product.active_sale()
        discount = sale.discount_percent if sale else 0
        new_price = price_for(product.base_price, now, product.id, discount)
        product.current_price = new_price
        product.save(update_fields=['current_price'])
        PriceLog.objects.create(product=product, price=new_price, timestamp=now)
        updated += 1
    logger.info('update_prices: refreshed %s products', updated)
    return updated


@shared_task
def retrain_forecast_models():
    """Nightly retrain of the per-product Prophet forecast, cached to
    disk so ml-insights and anomaly detection don't refit on every
    request. See ml/forecasting.py.

    Also evaluates (Prophet + Holt-Winters + baseline comparison) and
    cross-validates a bounded sample of products -- both refit models
    from scratch (cross-validation several times over), too expensive to
    run for the whole catalog synchronously on every /ml-insights/ page
    view. MAX_EVAL should stay >= the sample size ml_insights() requests,
    so every product it shows renders from cache instead of live-fitting.
    """
    from ml.forecasting import (
        cross_validate_and_cache, evaluate_and_cache, render_and_cache_component_plot, train_and_cache_model,
    )

    MAX_EVAL = 20
    MAX_CV = 8

    trained = 0
    evaluated = 0
    cv_computed = 0
    for product in Product.objects.all():
        if product.price_logs.count() < 14:
            continue
        train_and_cache_model(product.id)
        trained += 1

        if evaluated < MAX_EVAL:
            try:
                evaluate_and_cache(product.id)
                render_and_cache_component_plot(product.id)
                evaluated += 1
            except ValueError:
                pass  # not enough history for evaluate_model's holdout split

        if cv_computed < MAX_CV and cross_validate_and_cache(product.id):
            cv_computed += 1

    logger.info(
        'retrain_forecast_models: trained %s models, evaluated %s, cross-validated %s',
        trained, evaluated, cv_computed,
    )
    return trained
