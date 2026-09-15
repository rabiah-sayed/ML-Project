import logging

from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PriceLog
from .serializers import PriceLogSerializer

logger = logging.getLogger(__name__)


class PriceHistoryAPIView(ListAPIView):
    """Feeds the Chart.js price-history chart on the product detail page.
    ?range=6mo|1yr toggles the lookback window.
    """
    serializer_class = PriceLogSerializer

    def get_queryset(self):
        product_id = self.kwargs['pk']
        range_param = self.request.query_params.get('range', '6mo')
        days = 365 if range_param == '1yr' else 182
        since = timezone.now() - timezone.timedelta(days=days)
        return PriceLog.objects.filter(product_id=product_id, timestamp__gte=since).order_by('timestamp')


class ForecastAPIView(APIView):
    """Feeds the forward-looking forecast band on the product detail
    price chart -- Prophet's predicted price + confidence interval for
    the next N days, so the platform's core "forecasts the right moment
    to buy" pitch is visible on the product page, not just used
    internally to drive the anomaly badge and trigger suggestion.
    """

    def get(self, request, pk):
        from ml.forecasting import forecast_product

        periods = min(int(request.query_params.get('periods', 14)), 30)
        try:
            forecast = forecast_product(pk, periods=periods)
        except Exception:
            logger.exception('forecast_product failed for product %s', pk)
            return Response({'detail': 'Not enough price history to forecast yet.'}, status=400)

        future = forecast.tail(periods)
        return Response([
            {
                'date': row.ds.strftime('%Y-%m-%d'),
                'yhat': round(row.yhat, 2),
                'yhat_lower': round(row.yhat_lower, 2),
                'yhat_upper': round(row.yhat_upper, 2),
            }
            for row in future.itertuples()
        ])


class TriggerProbabilityAPIView(APIView):
    """Powers the live "~X% chance within N days" and "expected in ~N
    days" readouts on the Set Trigger Price modal -- a Monte Carlo
    probability plus a point estimate of *when*, both from Prophet's
    own forecast (see ml.forecasting.trigger_fire_probability and
    estimated_days_to_target), recomputed as the target price changes.
    """

    def get(self, request, pk):
        from ml.forecasting import estimated_days_to_target, trigger_fire_probability

        target_price = request.query_params.get('target_price')
        try:
            target_price = float(target_price)
        except (TypeError, ValueError):
            return Response({'detail': 'target_price is required.'}, status=400)

        horizon_days = min(int(request.query_params.get('days', 14)), 30)
        try:
            probability = trigger_fire_probability(pk, target_price, horizon_days=horizon_days)
            eta = estimated_days_to_target(pk, target_price)
        except Exception:
            logger.exception('trigger probability/ETA failed for product %s', pk)
            return Response({'detail': 'Not enough price history to estimate yet.'}, status=400)

        return Response({
            'probability': probability,
            'horizon_days': horizon_days,
            'eta_days': eta['days'] if eta else None,
            'eta_date': eta['date'] if eta else None,
        })
