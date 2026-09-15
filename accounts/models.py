from decimal import Decimal

from django.conf import settings
from django.db import models


class Address(models.Model):
    LABEL_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default='home')
    line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'addresses'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_label_display()} - {self.line1}, {self.city} ({self.user})'


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user} wallet: {self.balance}'

    def add_funds(self, amount):
        self.balance += Decimal(str(amount))
        self.save(update_fields=['balance', 'updated_at'])

    def deduct(self, amount):
        amount = Decimal(str(amount))
        if amount > self.balance:
            raise ValueError('Insufficient wallet balance')
        self.balance -= amount
        self.save(update_fields=['balance', 'updated_at'])
