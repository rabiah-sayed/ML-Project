"""Shared demand-curve price formula.

Used by both the live `update_prices` Celery task and the
`backfill_price_history` management command, so historical and live
prices follow the same generative process and the forecasting model
has real, learnable signal instead of pure noise.
"""
import math
import random
from datetime import datetime


def demand_multiplier(when: datetime, product_seed: int) -> float:
    """Weekly seasonality (sine wave) + a mild long-term trend + noise.

    `product_seed` keeps each product's curve distinct (different phase/
    amplitude) while remaining deterministic given the same product.
    """
    rng = random.Random(product_seed)
    phase = rng.uniform(0, 2 * math.pi)
    amplitude = rng.uniform(0.03, 0.08)

    day_of_week = when.weekday()
    weekly_seasonality = amplitude * math.sin(2 * math.pi * day_of_week / 7 + phase)

    days_since_epoch = when.toordinal() - datetime(2020, 1, 1).toordinal()
    trend = 0.00005 * days_since_epoch * rng.uniform(0.5, 1.5)

    noise = random.gauss(0, 0.015)

    return 1 + weekly_seasonality + trend + noise


def price_for(base_price: float, when: datetime, product_id: int, discount_percent: float = 0) -> float:
    price = float(base_price) * demand_multiplier(when, product_id)
    if discount_percent:
        price *= (1 - float(discount_percent) / 100)
    return round(max(price, 0.01), 2)
