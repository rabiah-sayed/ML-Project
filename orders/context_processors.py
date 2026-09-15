def cart_count(request):
    cart = request.session.get('cart', {})
    return {'cart_count': sum(cart.values())}


def wishlist_count(request):
    if not request.user.is_authenticated:
        return {'wishlist_count': 0}
    from .models import WishlistItem
    return {'wishlist_count': WishlistItem.objects.filter(user=request.user).count()}
