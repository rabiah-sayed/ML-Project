from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Address
from catalog.models import Product

PAYMENT_METHOD_CHOICES = [
    ('upi', 'UPI'),
    ('card', 'Card'),
    ('wallet', 'Wallet'),
    ('cod', 'Cash on Delivery'),
]


class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Placed'),
        ('pending_cancellation', 'Pending cancellation'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders')
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='placed')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='orders')
    trigger = models.ForeignKey(
        'orders.Trigger', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.pk} - {self.product} ({self.get_status_display()})'

    @property
    def cancellable_until(self):
        if self.status != 'pending_cancellation':
            return None
        return self.created_at + timezone.timedelta(hours=48)

    @property
    def is_cancellable(self):
        return self.status == 'pending_cancellation' and timezone.now() < self.cancellable_until


class Trigger(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('fired', 'Fired'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='triggers')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='triggers')
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='triggers')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Trigger: {self.product} <= {self.target_price} ({self.get_status_display()})'


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_wishlist_item'),
        ]

    def __str__(self):
        return f'{self.user} wishlisted {self.product}'
