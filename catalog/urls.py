from django.urls import path

from . import views
from .api import ForecastAPIView, PriceHistoryAPIView, TriggerProbabilityAPIView

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('ml-insights/', views.ml_insights, name='ml_insights'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/review/', views.submit_review, name='submit_review'),
    path('api/products/<int:pk>/price-history/', PriceHistoryAPIView.as_view(), name='api_price_history'),
    path('api/products/<int:pk>/forecast/', ForecastAPIView.as_view(), name='api_forecast'),
    path('api/products/<int:pk>/trigger-probability/', TriggerProbabilityAPIView.as_view(), name='api_trigger_probability'),
]
