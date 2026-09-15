"""Suggested trigger price, reusing forecasting.py's output -- doesn't
need its own model.
"""
from .forecasting import forecast_product, price_history_df


def suggested_trigger_price(product_id, lookback_days=180, forecast_days=14):
    """The lower of: the 10th percentile of trailing price history, and
    the forecasted 2-week low. Pre-fills the "Set Trigger Price" modal.
    """
    history = price_history_df(product_id)
    if history.empty:
        return None

    recent = history.tail(lookback_days)
    percentile_10 = float(recent['y'].quantile(0.10))

    forecast = forecast_product(product_id, periods=forecast_days)
    forecast_low = float(forecast['yhat'].tail(forecast_days).min())

    return round(min(percentile_10, forecast_low), 2)
