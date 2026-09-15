from django.urls import path

from . import views

urlpatterns = [
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/qty/<int:product_id>/', views.update_cart_qty, name='update_cart_qty'),
    path('checkout/', views.checkout, name='checkout'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('trigger/<int:product_id>/', views.set_trigger, name='set_trigger'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('my-orders/<int:order_id>/', views.order_tracking, name='order_tracking'),
    path('my-orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('my-triggers/', views.my_triggers, name='my_triggers'),
    path('my-triggers/<int:trigger_id>/cancel/', views.cancel_trigger, name='cancel_trigger'),
    path('wishlist/', views.wishlist_list, name='wishlist_list'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
]
