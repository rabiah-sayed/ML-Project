from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('onboarding/address/', views.onboarding_address, name='onboarding_address'),
    path('wallet/', views.wallet_detail, name='wallet_detail'),
    path('addresses/', views.address_list, name='address_list'),
]
