"""Dip detection: is today's actual price outside Prophet's forecast
confidence interval? Powers the "unusually low, good time to buy" banner
on the product detail page.
"""
from django.utils import timezone

from .forecasting import load_cached_model


def detect_anomaly(product_id):
    from catalog.models import Product

    product = Product.objects.get(pk=product_id)
    model = load_cached_model(product_id)

    today = timezone.localdate()
    future = model.make_future_dataframe(periods=1)
    forecast = model.predict(future)
    today_rows = forecast[forecast['ds'].dt.date == today]
    row = today_rows.iloc[-1] if not today_rows.empty else forecast.iloc[-1]

    current_price = float(product.current_price)
    expected_low = round(float(row['yhat_lower']), 2)
    expected_high = round(float(row['yhat_upper']), 2)
    is_low = current_price < expected_low
    is_high = current_price > expected_high

    if is_low:
        message = 'Unusually low right now — good time to buy!'
    elif is_high:
        message = 'Price is unusually high right now.'
    else:
        message = 'Price is within its normal range.'

    return {
        'current_price': current_price,
        'expected_low': expected_low,
        'expected_high': expected_high,
        'is_anomaly': bool(is_low or is_high),
        'is_good_deal': bool(is_low),
        'message': message,
    }
