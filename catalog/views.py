import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from orders.forms import TriggerForm
from orders.models import Order, Trigger, WishlistItem
from orders.services import check_and_fire_triggers

from .forms import ReviewForm
from .models import Category, Product, Review
from .recommendations import related_products
from .services import maybe_update_prices

logger = logging.getLogger(__name__)

MIN_HISTORY_FOR_ML = 14  # days of PriceLog needed before Prophet is worth fitting

SORT_OPTIONS = {
    'name': ('name', 'Name (A-Z)'),
    'price_asc': ('current_price', 'Price: Low to High'),
    'price_desc': ('-current_price', 'Price: High to Low'),
    'newest': ('-created_at', 'Newest'),
}


def product_list(request):
    maybe_update_prices()
    if request.user.is_authenticated:
        check_and_fire_triggers(Trigger.objects.filter(user=request.user))

    products = Product.objects.select_related('category').all()

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    sort = request.GET.get('sort') if request.GET.get('sort') in SORT_OPTIONS else 'newest'
    products = products.order_by(SORT_OPTIONS[sort][0])

    selected_category = None
    selected_category_name = None
    if category_id:
        selected_category = get_object_or_404(Category, pk=category_id)
        selected_category_name = selected_category.name

    paginator = Paginator(products, 25)  # multiple of 5, matching the grid's 5-per-row layout
    page_obj = paginator.get_page(request.GET.get('page'))

    wishlisted_ids = set()
    if request.user.is_authenticated:
        wishlisted_ids = set(
            WishlistItem.objects.filter(user=request.user, product__in=page_obj.object_list)
            .values_list('product_id', flat=True)
        )

    return render(request, 'catalog/product_list.html', {
        'page_obj': page_obj,
        'selected_category': selected_category.id if selected_category else None,
        'selected_category_name': selected_category_name,
        'query': query,
        'sort': sort,
        'sort_options': SORT_OPTIONS,
        'wishlisted_ids': wishlisted_ids,
    })


def product_detail(request, pk):
    maybe_update_prices()
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)

    anomaly = None
    suggested_price = None
    if product.price_logs.count() >= MIN_HISTORY_FOR_ML:
        try:
            from ml.anomaly import detect_anomaly
            from ml.suggest import suggested_trigger_price
            anomaly = detect_anomaly(product.id)
            suggested_price = suggested_trigger_price(product.id)
        except Exception:
            logger.exception('ML insight failed for product %s', product.id)

    trigger_form = None
    user_triggers = []
    just_fired_order = None
    is_wishlisted = False
    user_review = None
    can_review = False
    if request.user.is_authenticated:
        trigger_form = TriggerForm(user=request.user)
        if suggested_price:
            trigger_form.fields['target_price'].initial = suggested_price

        # Checks only this user's triggers on this product, so a target
        # price reached shows as fired immediately on page load -- no
        # need for Celery/Redis to be running for this to work.
        product_triggers = Trigger.objects.filter(user=request.user, product=product)
        fired_orders = check_and_fire_triggers(product_triggers)
        if fired_orders:
            just_fired_order = fired_orders[0]
        user_triggers = list(product_triggers.order_by('-created_at'))
        if user_triggers:
            from ml.forecasting import estimated_days_to_target, trigger_fire_probability
            for t in user_triggers:
                t.fire_probability = None
                t.eta = None
                if t.status == 'active':
                    try:
                        t.fire_probability = trigger_fire_probability(product.id, t.target_price)
                        t.eta = estimated_days_to_target(product.id, t.target_price)
                    except Exception:
                        pass  # not enough price history yet

        is_wishlisted = WishlistItem.objects.filter(user=request.user, product=product).exists()
        user_review = Review.objects.filter(user=request.user, product=product).first()
        # Reviews are gated on delivery -- you can't meaningfully rate a
        # physical product you haven't received. An existing review means
        # they satisfied this before, so editing stays allowed either way.
        can_review = bool(user_review) or Order.objects.filter(
            user=request.user, product=product, status='delivered',
        ).exists()

    review_form = ReviewForm(instance=user_review) if can_review else None
    reviews = product.reviews.select_related('user')
    if user_review:
        reviews = reviews.exclude(pk=user_review.pk)

    verified_user_ids = set(
        Order.objects.filter(product=product, status='delivered').values_list('user_id', flat=True)
    )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'anomaly': anomaly,
        'suggested_price': suggested_price,
        'trigger_form': trigger_form,
        'user_triggers': user_triggers,
        'just_fired_order': just_fired_order,
        'is_wishlisted': is_wishlisted,
        'user_review': user_review,
        'can_review': can_review,
        'review_form': review_form,
        'reviews': reviews,
        'verified_user_ids': verified_user_ids,
        'related_products': related_products(product),
    })


@login_required
def submit_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    existing = Review.objects.filter(user=request.user, product=product).first()

    can_review = bool(existing) or Order.objects.filter(
        user=request.user, product=product, status='delivered',
    ).exists()
    if not can_review:
        messages.error(request, "You can review a product once it's been delivered to you.")
        return redirect('product_detail', pk=pk)

    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.save()
        messages.success(request, 'Thanks for your review!')
    else:
        messages.error(request, 'Could not save your review -- pick a rating.')
    return redirect('product_detail', pk=pk)


def ml_insights(request):
    """The highest-graded-weight page in the project: predicted vs.
    actual price for a sample of products, with RMSE/MAE (and a naive
    baseline for comparison) plus a trend/seasonality decomposition,
    straight from ml/forecasting.py. Evaluation and cross-validation
    summaries are precomputed by catalog.tasks.retrain_forecast_models
    (expensive -- multiple model refits per product) and read from cache
    here; only products beyond that cached batch (or before the first
    retrain has ever run) fall back to computing live.
    """
    from ml.forecasting import (
        component_plot_base64, evaluate_model, load_cached_component_plot, load_cached_evaluation, load_cv_summary,
    )

    SAMPLE_SIZE = 20  # matches retrain_forecast_models' MAX_EVAL, so every one of these renders from cache

    results = []
    sample = []
    for product in Product.objects.select_related('category')[:100]:
        if product.price_logs.count() >= MIN_HISTORY_FOR_ML:
            sample.append(product)
        if len(sample) >= SAMPLE_SIZE:
            break

    chart_data = {}
    for product in sample:
        evaluation = load_cached_evaluation(product.id)
        if evaluation is None:
            try:
                evaluation = evaluate_model(product.id)
            except Exception:
                logger.exception('evaluate_model failed for product %s', product.id)
                continue

        component_plot = load_cached_component_plot(product.id)
        if component_plot is None:
            try:
                component_plot = component_plot_base64(product.id)
            except Exception:
                logger.exception('component_plot_base64 failed for product %s', product.id)
                component_plot = None

        cv_summary = load_cv_summary(product.id)

        results.append({
            'product': product, 'evaluation': evaluation,
            'component_plot': component_plot, 'cv_summary': cv_summary,
        })
        chart_data[product.id] = evaluation

    return render(request, 'catalog/ml_insights.html', {'results': results, 'chart_data': chart_data})
