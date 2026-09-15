from django.contrib import admin

from .models import Order, Trigger, WishlistItem
from .services import advance_order_status


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin oversight for orders -- staff can't hand-edit fields (the
    change form is entirely read-only), but can push an order's
    fulfillment forward via the "Advance to next status" action, e.g.
    for a support request or a demo, without waiting out the normal
    simulated timeline (see orders.services.advance_order_status).
    """
    list_display = ('id', 'user', 'product', 'price_paid', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('user__username', 'product__name')
    date_hierarchy = 'created_at'
    actions = ['advance_to_next_status']

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # True so the changelist and the advance-status action are
        # available; get_readonly_fields still blocks freeform edits.
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Advance selected orders to their next status')
    def advance_to_next_status(self, request, queryset):
        advanced = 0
        skipped = 0
        for order in queryset:
            if advance_order_status(order):
                advanced += 1
            else:
                skipped += 1

        if advanced:
            self.message_user(request, f'Advanced {advanced} order(s) to their next status.')
        if skipped:
            self.message_user(
                request,
                f'{skipped} order(s) were already delivered or cancelled -- nothing to advance.',
                level='warning',
            )


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'product__name')


@admin.register(Trigger)
class TriggerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'target_price', 'status', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('user__username', 'product__name')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
