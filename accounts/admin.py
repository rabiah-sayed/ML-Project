from django.contrib import admin

from .models import Address, Wallet


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'line1', 'city', 'pincode')
    list_filter = ('label', 'city')
    search_fields = ('user__username', 'line1', 'city', 'pincode')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username',)
