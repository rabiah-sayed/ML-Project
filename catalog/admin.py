from django.contrib import admin

from .models import Category, PriceLog, Product, Review, Sale


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'current_price', 'stock')
    list_filter = ('category',)
    search_fields = ('name', 'description')
    autocomplete_fields = ('category',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """The admin's biggest win here: marketing/ops can start or edit a
    sale (mid-month or otherwise) with zero custom UI or engineering."""
    list_display = ('name', 'category', 'discount_percent', 'start_date', 'end_date')
    list_filter = ('category',)
    date_hierarchy = 'start_date'


@admin.register(PriceLog)
class PriceLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'timestamp')
    list_filter = ('product__category',)
    search_fields = ('product__name',)
    date_hierarchy = 'timestamp'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Moderation view -- staff can delete a review, but reviews are
    authored by users and shouldn't be silently edited by admin."""
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('product__name', 'user__username', 'comment')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
