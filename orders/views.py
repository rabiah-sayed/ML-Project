from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import Address, Wallet
from catalog.models import Product

from .forms import CheckoutForm, TriggerForm
from .models import Order, Trigger, WishlistItem
from .services import check_and_fire_triggers, order_tracking_stages, progress_order_statuses

CART_SESSION_KEY = 'cart'


def _get_cart(session):
    return session.setdefault(CART_SESSION_KEY, {})


def _safe_redirect(request, fallback):
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    qty = max(1, int(request.POST.get('qty', 1) or 1))
    cart = _get_cart(request.session)
    cart[str(product.id)] = cart.get(str(product.id), 0) + qty
    request.session.modified = True
    messages.success(request, f'Added {product.name} to cart.')
    return _safe_redirect(request, 'cart_detail')


@login_required
def update_cart_qty(request, product_id):
    cart = _get_cart(request.session)
    delta = int(request.POST.get('delta', 0))
    key = str(product_id)
    if key in cart:
        cart[key] = cart[key] + delta
        if cart[key] <= 0:
            cart.pop(key)
        request.session.modified = True
    return redirect('cart_detail')


@login_required
def remove_from_cart(request, product_id):
    cart = _get_cart(request.session)
    cart.pop(str(product_id), None)
    request.session.modified = True
    return redirect('cart_detail')


@login_required
def cart_detail(request):
    cart = _get_cart(request.session)
    products = Product.objects.filter(id__in=[int(pid) for pid in cart.keys()])
    lines = []
    total = Decimal('0')
    subtotal_before_discount = Decimal('0')
    for product in products:
        qty = cart[str(product.id)]
        subtotal = product.current_price * qty
        total += subtotal
        subtotal_before_discount += product.base_price * qty
        lines.append({'product': product, 'qty': qty, 'subtotal': subtotal})
    savings = subtotal_before_discount - total
    return render(request, 'orders/cart_detail.html', {
        'lines': lines, 'total': total, 'savings': savings, 'subtotal': subtotal_before_discount,
    })


def _place_order(user, product, qty, address, payment_method):
    """Raises ValueError (insufficient wallet balance) to let the caller
    roll back the whole checkout atomically -- otherwise a multi-item
    cart could charge the wallet and create orders for earlier items
    before failing on a later one.
    """
    unit_price = product.current_price

    if payment_method == 'wallet':
        wallet, _ = Wallet.objects.get_or_create(user=user)
        wallet.deduct(unit_price * qty)
    # UPI/card/COD are mocked: treated as an immediate simulated success.

    return [
        Order.objects.create(
            user=user, product=product, price_paid=unit_price,
            status='placed', payment_method=payment_method, address=address,
        )
        for _ in range(qty)
    ]


@login_required
def checkout(request):
    """Checks out either the session cart, or a single 'buy now' product
    stashed in the session by buy_now()."""
    buy_now_id = request.session.get('buy_now_product')
    cart = _get_cart(request.session)

    if buy_now_id:
        items = [(get_object_or_404(Product, pk=buy_now_id), 1)]
    else:
        items = [
            (get_object_or_404(Product, pk=int(pid)), qty)
            for pid, qty in cart.items()
        ]

    if not items:
        messages.info(request, 'Your cart is empty.')
        return redirect('product_list')

    if request.method == 'POST':
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            address = get_object_or_404(Address, pk=form.cleaned_data['address'], user=request.user)
            payment_method = form.cleaned_data['payment_method']
            try:
                with transaction.atomic():
                    for product, qty in items:
                        _place_order(request.user, product, qty, address, payment_method)
            except ValueError:
                messages.error(request, 'Insufficient wallet balance for this order.')
                return redirect('checkout')
            request.session.pop('buy_now_product', None)
            request.session[CART_SESSION_KEY] = {}
            request.session.modified = True
            messages.success(request, 'Order placed!')
            return redirect('my_orders')
    else:
        form = CheckoutForm(user=request.user)

    total = sum(product.current_price * qty for product, qty in items)
    return render(request, 'orders/checkout.html', {'form': form, 'items': items, 'total': total})


@login_required
def buy_now(request, product_id):
    get_object_or_404(Product, pk=product_id)
    request.session['buy_now_product'] = product_id
    request.session.modified = True
    return redirect('checkout')


@login_required
def set_trigger(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        form = TriggerForm(request.POST, user=request.user)
        if form.is_valid():
            Trigger.objects.create(
                user=request.user,
                product=product,
                target_price=form.cleaned_data['target_price'],
                payment_method=form.cleaned_data['payment_method'],
                address_id=form.cleaned_data['address'],
            )
            messages.success(request, f'Trigger set for {product.name}.')
            return redirect('product_detail', pk=product.id)
        messages.error(request, 'Could not set trigger, check the form.')
    return redirect('product_detail', pk=product.id)


@login_required
def my_orders(request):
    # Same reasoning as trigger firing: run the status simulation
    # synchronously here too, so orders progress past 'confirmed' even
    # without Celery running.
    progress_order_statuses(Order.objects.filter(user=request.user))
    orders = Order.objects.filter(user=request.user).select_related('product')
    return render(request, 'orders/my_orders.html', {'orders': orders})


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if request.method == 'POST' and order.is_cancellable:
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        messages.success(request, 'Order cancelled.')
    return redirect('my_orders')


@login_required
def order_tracking(request, order_id):
    order = get_object_or_404(Order.objects.select_related('product', 'address'), pk=order_id, user=request.user)
    progress_order_statuses(Order.objects.filter(pk=order.pk))
    order.refresh_from_db()

    stages = order_tracking_stages(order) if order.status not in ('cancelled',) else None
    return render(request, 'orders/order_tracking.html', {'order': order, 'stages': stages})


@login_required
def my_triggers(request):
    # Without Celery+Redis running, the periodic check_triggers task never
    # fires -- checking the user's own triggers here means status is
    # always fresh regardless of whether the background worker is up.
    check_and_fire_triggers(Trigger.objects.filter(user=request.user))
    triggers = list(Trigger.objects.filter(user=request.user).select_related('product'))

    from ml.forecasting import estimated_days_to_target, trigger_fire_probability
    for trigger in triggers:
        trigger.fire_probability = None
        trigger.eta = None
        if trigger.status == 'active':
            try:
                trigger.fire_probability = trigger_fire_probability(trigger.product_id, trigger.target_price)
                trigger.eta = estimated_days_to_target(trigger.product_id, trigger.target_price)
            except Exception:
                pass  # not enough price history yet for this product

    return render(request, 'orders/my_triggers.html', {'triggers': triggers})


@login_required
def cancel_trigger(request, trigger_id):
    trigger = get_object_or_404(Trigger, pk=trigger_id, user=request.user)
    if request.method == 'POST' and trigger.status == 'active':
        trigger.status = 'cancelled'
        trigger.save(update_fields=['status'])
        messages.success(request, 'Trigger cancelled.')
    return redirect('my_triggers')


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        messages.success(request, f'Removed {product.name} from your wishlist.')
    else:
        messages.success(request, f'Added {product.name} to your wishlist.')

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('product_detail', pk=product_id)


@login_required
def wishlist_list(request):
    items = WishlistItem.objects.filter(user=request.user).select_related('product', 'product__category')
    return render(request, 'orders/wishlist.html', {'items': items})
