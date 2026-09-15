"""Co-occurrence recommendations: "customers who acted on this product
also acted on..." -- a different ML technique from the forecasting
pipeline (collaborative filtering, not time-series), computed live since
it's a cheap set/count operation, not a model that needs training.

"Acted on" = ordered, triggered, or wishlisted a product -- any signal
that a user cared enough about it to do something, not just view it.
"""
from collections import Counter

from .models import Product


def related_products(product, limit=6):
    from orders.models import Order, Trigger, WishlistItem

    signal_users = set()
    signal_users.update(Order.objects.filter(product=product).values_list('user_id', flat=True))
    signal_users.update(Trigger.objects.filter(product=product).values_list('user_id', flat=True))
    signal_users.update(WishlistItem.objects.filter(product=product).values_list('user_id', flat=True))

    counts = Counter()
    if signal_users:
        counts.update(
            Order.objects.filter(user_id__in=signal_users).exclude(product=product).values_list('product_id', flat=True)
        )
        counts.update(
            Trigger.objects.filter(user_id__in=signal_users).exclude(product=product).values_list('product_id', flat=True)
        )
        counts.update(
            WishlistItem.objects.filter(user_id__in=signal_users).exclude(product=product).values_list('product_id', flat=True)
        )

    if counts:
        ranked_ids = [pid for pid, _ in counts.most_common(limit)]
        products_by_id = Product.objects.in_bulk(ranked_ids)
        recommended = [products_by_id[pid] for pid in ranked_ids if pid in products_by_id]
        if len(recommended) >= limit:
            return recommended

        # Not enough co-occurrence data yet (common for a new/sparse
        # catalog) -- top up with same-category products as a sane
        # fallback rather than showing a half-empty section.
        exclude_ids = {product.id, *ranked_ids}
        fallback = list(
            Product.objects.filter(category=product.category)
            .exclude(id__in=exclude_ids)
            .select_related('category')[:limit - len(recommended)]
        )
        return recommended + fallback

    return list(
        Product.objects.filter(category=product.category)
        .exclude(id=product.id)
        .select_related('category')[:limit]
    )
